from linkerforce import * 

# 创建串口读取器实例
force_reader = ForceSerialReader()  # Linux
if force_reader.openserial(port='/dev/ttyUSB1',baudrate=2000000):
    time.sleep(1)
    try:
        # 启动数据读取
        force_reader.start()
        force_reader.serial_port.write(force_reader.pack_01_data())
        time.sleep(1)
        force_reader.serial_port.write(force_reader.pack_02_data(1))
        time.sleep(1)       
        # # 主循环中访问数据
        while True:
            force_reader.forcelist = [255,255,255,255,255]
            # force_reader.serial_port.write(force_reader.pack_03_data())
            print(force_reader.poslist)
            time.sleep(0.01)  # 控制循环频率
            
    except KeyboardInterrupt:
        print("正在停止...")
    finally:
        # 确保停止读取线程
        force_reader.stop()