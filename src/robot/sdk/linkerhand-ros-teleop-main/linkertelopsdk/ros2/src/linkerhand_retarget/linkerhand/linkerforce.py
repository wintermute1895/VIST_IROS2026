import array
import enum
from enum import Enum
import threading
import numpy as np
import time
import re
import os
import getpass
import subprocess
import struct
import serial
import serial.tools.list_ports
from threading import Thread, Event

from .constants import HandType
BUFFER_SIZE = 1024
MAX_FRAME_DATA_SIZE = 255
FRAME_HEADER = 0x5D

class CircularBuffer:
    def __init__(self):
        self.data = array.array('B', [0] * BUFFER_SIZE)
        self.read_pos = 0
        self.write_pos = 0
        self.data_len = 0

    def write(self, data):
        """写入数据到环形缓冲区"""
        for byte in data:
            self.data[self.write_pos] = byte
            self.write_pos = (self.write_pos + 1) % BUFFER_SIZE

            if self.data_len < BUFFER_SIZE:
                self.data_len += 1
            else:
                # 缓冲区满，移动读指针
                self.read_pos = (self.read_pos + 1) % BUFFER_SIZE

    def read_byte(self):
        """从环形缓冲区读取一个字节"""
        if self.data_len == 0:
            return None

        byte = self.data[self.read_pos]
        self.read_pos = (self.read_pos + 1) % BUFFER_SIZE
        self.data_len -= 1

        return byte


class FrameParseState(Enum):
    HEADER = 0
    CMD = 1
    LENGTH = 2
    DATA = 3
    CHECKSUM = 4


class FrameParser:
    def __init__(self):
        self.state = FrameParseState.HEADER
        self.frame_buf = array.array('B', [0] * (3 + MAX_FRAME_DATA_SIZE + 1))
        self.expected_len = 0
        self.current_pos = 0
        self.checksum = 0

    def reset(self):
        """重置解析器状态"""
        self.state = FrameParseState.HEADER
        self.current_pos = 0
        self.checksum = 0
        for i in range(len(self.frame_buf)):
            self.frame_buf[i] = 0

    def process_byte(self, byte):
        """处理单个字节，返回是否接收到完整帧"""
        byte = byte & 0xFF  # 确保是uint8
        if self.state == FrameParseState.HEADER:
            if byte == FRAME_HEADER:
                self.frame_buf[0] = byte
                self.current_pos = 1
                self.checksum = 0  # 从包头开始计算校验和
                self.state = FrameParseState.CMD

        elif self.state == FrameParseState.CMD:
            self.frame_buf[1] = byte
            self.current_pos = 2
            self.state = FrameParseState.LENGTH

        elif self.state == FrameParseState.LENGTH:
            self.frame_buf[2] = byte
            self.expected_len = 3 + byte + 1  # header+cmd+len+data+checksum
            self.current_pos = 3
            if 0 < byte <= MAX_FRAME_DATA_SIZE:
                self.state = FrameParseState.DATA
            else:
                # 无效长度，重置状态机
                self.state = FrameParseState.CHECKSUM

        elif self.state == FrameParseState.DATA:
            self.frame_buf[self.current_pos] = byte
            self.current_pos += 1
            if self.current_pos >= self.expected_len - 1:
                self.state = FrameParseState.CHECKSUM

        elif self.state == FrameParseState.CHECKSUM:
            if self.checksum == byte:
                # 校验成功，完成帧接收
                self.frame_buf[self.current_pos] = byte
                return True
            else:
                # 校验失败，重置状态机
                self.reset()

        # 更新校验和（包头到当前字节）
        if self.state != FrameParseState.HEADER:
            self.checksum = (self.checksum + byte) & 0xFF
        
        return False


class ForceSerialReader:
    def __init__(   self,
                    gettype :HandType, 
                    excludelist = None, 
                    baudrates = None, 
                    isdebug :bool = False, 
                    password = '12345678'):
        self.serial_port = None
        self.poslist = [0.0] * 21
        self.forcelist = [0.0] * 5
        self.realforcelist = [0] * 5
        self.buffer = CircularBuffer()
        self.parser = FrameParser()
        self.running = Event()
        self.handtype = None
        self.gettype = gettype
        self.version = None
        self.thread = None
        self.connflag = False
        self.lasttime = time.time()
        self.multi_target_kf_r = None
        self.firstdata = True
        self.a6recivecount = 0
        self.isdebug = isdebug
        self.sudo_password = password  # 缓存密码
        """
        exclude_list: 需要排除的串口列表
        baudrates: 波特率组合列表
        """
        self.checked_ports = set()  # 记录已经检查过的串口
        self.valid_ports = []       # 存储符合条件的串口
        self.exclude_ports = set(excludelist) if excludelist else set()
        
        # 默认波特率组合
        self.baudrates = baudrates or [2000000, 1000000, 921600, 460800]

    def scan_serial_ports(self):
        """扫描所有可用的串口，并排除指定串口"""
        ports = serial.tools.list_ports.comports()
        available_ports = []
        
        for port in ports:
            port_device = port.device
            if not self.is_usb_device(port_device):
                continue
            # 排除已经在剔除清单中的串口
            if port_device in self.exclude_ports:
                print(f"跳过排除的串口: {port_device}")
                continue
            # 排除已经检查过的串口
            if port_device not in self.checked_ports:
                available_ports.append(port_device)
                
        return available_ports

    def is_usb_device(self, port_name):
        """
        判断是否为USB串口设备
        支持: /dev/ttyUSB*, /dev/ttyACM* 等USB转串口设备
        """
        # 使用正则表达式匹配USB设备
        usb_patterns = [
            r'/dev/ttyUSB\d+',      # USB转串口
            r'/dev/ttyACM\d+',      # USB CDC ACM设备
            r'/dev/ttyXRUSB\d+',    # Exar USB转串口
            r'/dev/ttyOBC\d+',      # 某些USB设备
        ]
        
        for pattern in usb_patterns:
            if re.match(pattern, port_name):
                return True
                
        # 也可以通过设备描述判断
        try:
            ports = serial.tools.list_ports.comports()
            for port_info in ports:
                if port_info.device == port_name:
                    # 检查设备描述是否包含USB关键词
                    description = (port_info.description or "").lower()
                    if any(keyword in description for keyword in ['usb', 'serial', 'com']):
                        return True
                    # 检查硬件ID
                    if port_info.hwid and 'USB' in port_info.hwid.upper():
                        return True
        except:
            pass
            
        return False  

    def query_serial_port(self, port_name, timeout=1):
        """
        快速扫描模式 - 对所有波特率进行简短测试
        """
        best_baudrate = None
        errorcode = None
        
        for baudrate in self.baudrates:
            try:
                with serial.Serial(
                    port_name, 
                    baudrate=baudrate, 
                    timeout=timeout,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                ) as ser:
                    self.serial_port = ser
        
                    self.start()
                    time.sleep(0.1)
                    if self.isdebug:
                        print(f"侦测串口 {port_name} 波特率 {baudrate}是否联通......")   
                    self.handtype = None
                    self.connflag = False
                    self.serial_port.write(self.pack_01_data())
                    time.sleep(1)  # 更短的等待时间

                    self.stop()
                    if self.connflag:
                        if self.handtype is not None:
                            # 记录有响应的波特率
                            if best_baudrate is None:
                                best_baudrate = baudrate
                                if self.isdebug:
                                    print(f"串口 {port_name} 在 {baudrate} 波特率下有响应")
                                return True, best_baudrate, errorcode    
                        return False, best_baudrate, -5      
            except serial.SerialException as e:
                error_msg = str(e)
                if "No such file or directory" in error_msg or "[Errno 2]" in error_msg:
                    errorcode = -1
                    if self.isdebug:
                        print(f"串口设备不存在: {port_name}")
                        print("请检查串口名称或设备是否连接")
                    break
                elif "Permission denied" in error_msg or "[Errno 13]" in error_msg:
                    errorcode = -2
                    print(f"权限被拒绝: {port_name} - 可能需要sudo权限或串口被占用")
                    break
                elif "Device or resource busy" in error_msg:
                    errorcode = -3
                    if self.isdebug:
                        print(f"设备忙: {port_name} - 串口可能已被其他程序占用")
                    break
                else:
                    errorcode = -99
                    if self.isdebug:
                        print(f"串口打开失败: {e}")
                continue
        
        return False, None, errorcode
    
    def find_valid_ports(self, timeout=2, scan_interval=2):
        if self.isdebug:
            print("开始扫描串口...")
            print(f"排除列表: {list(self.exclude_ports)}")
            print(f"波特率组合: {self.baudrates}")

        # 获取未检查的串口
        available_ports = self.scan_serial_ports()
        if self.isdebug:    
            print(f"发现 {len(available_ports)} 个未检查的串口: {available_ports}")
        
        for port in available_ports:           
            # 查询串口
            success, baudrate, errorcode = self.query_serial_port(port, timeout)
            if errorcode == -2:
                print("检测到权限被禁用，尝试修复权限......")
                self.fix_serial_permission(port)
                success, baudrate, errorcode = self.query_serial_port(port, timeout)
            # 记录已检查的串口
            self.checked_ports.add(port)
            
            if success:
                if self.isdebug:
                    print(f"找到有效串口: {port} (波特率: {baudrate})")
                return port, baudrate, errorcode
        return None, None, None

    def fix_serial_permission(self, port_name):
        """尝试修复串口权限"""
        try:
            if os.path.exists(port_name):
                password = self.sudo_password
                # 使用echo传递密码
                command = f'echo "{password}" | sudo -S chmod 666 {port_name}'
                result = subprocess.run(
                    command, 
                    shell=True, 
                    capture_output=True, 
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    print(f"✓ 成功修复 {port_name} 权限")
                    return True
                else:
                    print(f"✗ 权限修复失败: {result.stderr}")
                    return False
        except subprocess.CalledProcessError:
            print(f"无法修复 {port_name} 权限 (chmod失败)")
        except subprocess.TimeoutExpired:
            print(f"修复权限超时")
        except Exception as e:
            print(f"修复权限时出错: {e}")
        
        return False

    def get_sudo_password(self):
        """获取sudo密码（只问一次）"""
        if self.sudo_password is None:
            try:
                self.sudo_password = getpass.getpass("请输入sudo密码: ")
            except KeyboardInterrupt:
                print("\n用户取消输入密码")
                return None
        return self.sudo_password

    def get_current_status(self):
        """获取当前扫描状态"""
        return {
            'valid_ports': self.valid_ports,
            'checked_ports': list(self.checked_ports),
            'exclude_ports': list(self.exclude_ports),
            'baudrates': self.baudrates
        }

    def openserial(self, port, baudrate=2000000):
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.001,  # 超时略小于 2ms，避免阻塞
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            self.running = Event()
            self.handtype = None
            self.version = None
            return True

        except serial.SerialException as e:
            error_msg = str(e)
            if "No such file or directory" in error_msg or "[Errno 2]" in error_msg:
                print(f"串口设备不存在: {port}")
                print("请检查串口名称或设备是否连接")
            elif "Permission denied" in error_msg or "[Errno 13]" in error_msg:
                print(f"权限被拒绝: {port} - 可能需要sudo权限或串口被占用")
            elif "Device or resource busy" in error_msg:
                print(f"设备忙: {port} - 串口可能已被其他程序占用")
            else:
                print(f"串口打开失败: {e}")
            return False 

        except Exception as e:
            print(f"未知错误: {e}")
            return False

   
    def start(self):
        """启动串口数据处理"""
        if self.thread is not None and self.thread.is_alive():
            return

        self.running.set()
        self.thread = Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """停止串口数据处理"""
        self.running.clear()
        if self.thread is not None:
            self.thread.join()
        self.serial_port.close()

    def _run(self):
        parser = FrameParser()
        sendcount = 0
        while self.running.is_set():
            try:
                # 读取所有可用数据
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        # 处理接收到的数据
                        self._process_received_data(data, parser)
                    
                # 避免CPU占用过高                
                if self.handtype is not None:
                    sendcount += 1
                    if sendcount > 10:
                        self.serial_port.write(self.pack_03_data())
                        sendcount = 0
                time.sleep(0.001)
            except Exception as e:
                print(f"串口读取错误: {e}")
                time.sleep(0.01)  # 出错时稍作等待

    def _process_received_data(self, data, parser):
        """处理接收到的数据"""
        for byte in data:
            if parser.process_byte(byte):
                # 收到完整帧
                self._handle_valid_frame(parser.frame_buf)
                parser.reset()

    def _handle_valid_frame(self, frame):
        """处理有效数据帧"""
        self.connflag = True
        cmd = frame[1]
        data_len = frame[2]
        frame_data = frame[3:3 + data_len]
        # 根据命令码处理数据
        if cmd == 0x01:
            value = struct.unpack('<I', frame_data[:4])[0]  # <I表示小端无符号32位
            # 拆分版本号: 假设value=10001 (0x00002711) → 主:1, 副:00, 子:01 → 1.0.1
            value_str = f"{value:05d}"  # 固定为5位数字，前面补零（假设格式为XYYZZ）
            major = int(value_str[0])  # 主版本号: 第1位 → 1
            minor = int(value_str[1:3])  # 副版本号: 第2-3位 → 00 → 0
            sub = int(value_str[3:5])  # 子版本号: 第4-5位 → 01 → 1
            self.version = f"{major}.{minor}.{sub}"  # 格式化为1.0.1
            # 第5个字节是状态码
            status_code = frame_data[4]
            self.handtype = self._get_hand_type(status_code)
        elif cmd == 0x02:
            pass
        elif cmd == 0x03:
            if len(frame_data) % 4 != 0:
                print(f"Payload length must be a multiple of 4 for float data, got {len(frame_data)} bytes")

            # 计算float数据的数量
            num_floats = len(frame_data) // 4
            floats = []

            # 每4字节解析为一个float（小端序）
            for i in range(num_floats):
                float_bytes = frame_data[i * 4: (i + 1) * 4]
                try:
                    # 使用struct.unpack解析小端序float
                    float_value = struct.unpack('<f', float_bytes)[0]  # '<f'表示小端float
                    floats.append(np.deg2rad(float_value))
                except struct.error as e:
                    print(f"Failed to unpack float at position {i}: {e}")
            self.poslist = floats
        elif cmd == 0x04:
            if len(frame_data) % 2 != 0:
                print(f"Payload length must be a multiple of 2 for int16 data, got {len(frame_data)} bytes")
                return

            # 计算int16数据的数量
            num_ints = len(frame_data) // 2
            values = []

            # 每2字节解析为一个int16（小端序），然后转换为浮点角度值（弧度）
            for i in range(num_ints):
                int_bytes = frame_data[i * 2: (i + 1) * 2]
                try:
                    # 使用struct.unpack解析小端序int16
                    int_value = struct.unpack('>h', int_bytes)[0]  # '<h'表示小端int16
                    values.append(int_value)
                except struct.error as e:
                    print(f"Failed to unpack int16 at position {i}: {e}")
            self.realforcelist = values
        elif cmd == 0xA3:
            if len(frame_data) % 4 != 0:
                print(f"Payload length must be a multiple of 4 for float data, got {len(frame_data)} bytes")

            # 计算float数据的数量
            num_floats = len(frame_data) // 4
            floats = []

            # 每4字节解析为一个float（小端序）
            for i in range(num_floats):
                float_bytes = frame_data[i * 4: (i + 1) * 4]
                try:
                    # 使用struct.unpack解析小端序float
                    float_value = struct.unpack('<f', float_bytes)[0]  # '<f'表示小端float
                    floats.append(np.deg2rad(float_value))
                except struct.error as e:
                    print(f"Failed to unpack float at position {i}: {e}")
            self.poslist = floats
            # print(self.rightposlist)
            if self.firstdata:
                self.firstdata = False
            self.a6recivecount += 1
            # end_time = time.time()  # 记录结束时间
            # execution_time = end_time - self.lasttime  # 计算执行时间
            
            # print(f"报文接收间隔: {execution_time:.6f}秒,总接收报文: {self.a6recivecount:.0f}条")
            # self.lasttime = end_time
            # self.serial_port.write(self.pack_A4_data(self.rightforcelist))
        elif cmd == 0xA6:
            if len(frame_data) % 2 != 0:
                print(f"Payload length must be a multiple of 2 for int16 data, got {len(frame_data)} bytes")
                return

            # 计算int16数据的数量
            num_ints = len(frame_data) // 2
            floats = []

            # 每2字节解析为一个int16（小端序），然后转换为浮点角度值（弧度）
            for i in range(num_ints):
                int_bytes = frame_data[i * 2: (i + 1) * 2]
                try:
                    # 使用struct.unpack解析小端序int16
                    int_value = struct.unpack('<h', int_bytes)[0]  # '<h'表示小端int16
                    # 将整型值转换回浮点，并转换为弧度
                    float_value = np.deg2rad(int_value / 100)
                    floats.append(float_value)
                except struct.error as e:
                    print(f"Failed to unpack int16 at position {i}: {e}")

            self.poslist = floats
            if self.firstdata:
                self.firstdata = False

            # 假设A4响应数据也需要相应调整（如果需要）
            self.serial_port.write(self.pack_A7_data(self.leftforcelist))
        else:
            print(f"Unknown command: 0x{cmd:02X}")

    def _get_hand_type(self, status_code):
        """
        将状态码转换为手类型
        status_code: 0 或 1
        返回: HandType 枚举
        """
        
        if status_code == 0 and self.gettype  == HandType.left:
            return "Left"
        elif status_code == 1 and self.gettype  == HandType.right:
            return "Right"
        else:
            return None


    @staticmethod
    def calculate_checksum(data):
        checksum = 0
        for byte in data:
            checksum += byte
        return checksum & 0xFF  # 取低 8 位作为校验和

    def pack_01_data(self):
        header_packed = struct.pack('BBB', FRAME_HEADER, 0x01, 0x00)
        checksum = self.calculate_checksum(header_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + checksum_packed
        return data

    def pack_02_data(self, mastersendflag):
        header_packed = struct.pack('BBB', FRAME_HEADER, 0x02, 0x05)
        other_packed = struct.pack('BBBBB', mastersendflag, 0, 0, 0, 0)
        checksum = self.calculate_checksum(header_packed + other_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + other_packed + checksum_packed
        # hex_list = [hex(byte) for byte in data]
        # print(hex_list)
        return data

    def pack_03_data(self):
        header_packed = struct.pack('BBB', FRAME_HEADER, 0x03, 0x00)
        checksum = self.calculate_checksum(header_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + checksum_packed
        return data

    def pack_A3_data(self):
        header_packed = struct.pack('BBB', FRAME_HEADER, 0xA3, 0x00)
        checksum = self.calculate_checksum(header_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + checksum_packed
        return data

    def pack_04_data(self):
        float_data = self.forcelist
        header_packed = struct.pack('BBB', FRAME_HEADER, 0x04, len(float_data) * 4)
        float_packed = struct.pack(f'{len(float_data)}f', *float_data)
        checksum = self.calculate_checksum(header_packed + float_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + float_packed + checksum_packed
        return data

    def pack_A4_data(self, float_data):
        header_packed = struct.pack('BBB', FRAME_HEADER, 0xA4, len(float_data) * 4)
        float_packed = struct.pack(f'{len(float_data)}f', *float_data)
        checksum = self.calculate_checksum(header_packed + float_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + float_packed + checksum_packed
        return data

    def pack_A7_data(self, float_data):
        header_packed = struct.pack('BBB', FRAME_HEADER, 0xA7, len(float_data) * 4)
        float_packed = struct.pack(f'{len(float_data)}f', *float_data)
        checksum = self.calculate_checksum(header_packed + float_packed)
        checksum_packed = struct.pack('B', checksum)
        # 组合所有数据
        data = header_packed + float_packed + checksum_packed
        return data
