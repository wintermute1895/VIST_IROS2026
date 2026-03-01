import array
from enum import Enum
import threading
import numpy as np
import time
import struct
import serial
from threading import Thread, Event
from .handcore import MultiTargetKalman

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
    def __init__(self):
        self.serial_port = None
        self.rightposlist = [0.0] * 21
        self.leftposlist = [0.0] * 21
        self.rightforcelist = [0.0] * 5
        self.leftforcelist = [0.0] * 5
        self.buffer = CircularBuffer()
        self.parser = FrameParser()
        self.running = Event()
        self.thread = None
        self.lasttime = time.time()
        self.multi_target_kf_r = None
        self.firstdata = True
        self.a6recivecount = 0

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
            print(f"串口 {port} 打开成功，波特率 {baudrate}")
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
        """串口数据读取和处理线程"""
        while self.running.is_set():
            # 读取串口数据
            data = self.serial_port.read(self.serial_port.in_waiting)

            if len(data) > 0:
                # hex_data = ' '.join([f'{byte:02x}' for byte in data])
                # print(f"接收内容(Hex): {hex_data}")
                self.buffer.write(data)
                # end_time = time.time()  # 记录结束时间
                # execution_time = end_time - self.lasttime  # 计算执行时间
                # print(f"报文接收间隔: {execution_time:.6f}秒")
                # self._handle_valid_frame(self.parser.frame_buf)
                # self.parser.reset()
                # self.lasttime = end_time
                # 处理接收到的数据
                self._process_data()
                # 避免CPU占用过高
                time.sleep(0.0001)

    def _process_data(self):
        """处理接收到的数据"""
        while True:
            byte = self.buffer.read_byte()
            if byte is None:
                break

            if self.parser.process_byte(byte):
                # end_time = time.time()  # 记录结束时间
                # execution_time = end_time - self.lasttime  # 计算执行时间
                
                # print(f"报文接收间隔: {execution_time:.6f}秒")
                self._handle_valid_frame(self.parser.frame_buf)
                self.parser.reset()
                # self.lasttime = end_time

    def _handle_valid_frame(self, frame):
        """处理有效数据帧"""
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
            version_str = f"{major}.{minor}.{sub}"  # 格式化为1.0.1
            # 第5个字节是状态码
            status_code = frame_data[4]
            print("力反馈设备版本:", version_str, "状态码:", status_code)
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
            self.rightposlist = floats
            # print(self.rightposlist)
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
            self.rightposlist = floats
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

            self.rightposlist = floats
            self.leftposlist = floats
            if self.firstdata:
                self.firstdata = False

            # 假设A4响应数据也需要相应调整（如果需要）
            self.serial_port.write(self.pack_A7_data(self.leftforcelist))
        else:
            print(f"Unknown command: 0x{cmd:02X}")

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

    def pack_04_data(self, float_data):
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
