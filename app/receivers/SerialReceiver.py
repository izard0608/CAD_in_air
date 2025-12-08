# app.receivers.SerialReceiver.py

# 这里创建SerialReceiver类，
# 波特率、端口号、地址的配置统一放到config里了，
# run.py里创建实例并运行

'''
required serial transmission format:

<time stamp>
<serial data line 1 to line 8>

'''

### socket是zmq里的一个套接字，改不了这个名儿所以注意不要和websocket混淆了

from Config import Config
import serial
import zmq # socket是zmq库里定义的一个类（之前说和websocket容易混淆挺神经的来着）
import time
import logging

# 创建SerialReceiver类
class SerialReceiver:
    def __init__(self):
        self.port = Config.SERIAL_PORT  #
        self.baud_rate = Config.BAUD_RATE  # 
        self.zmq_address = Config.ZMQ_ADDRESS  # 以上三个全在config里统一配置，这样要改会方便一点
        self.ser = None # 储存串口连接的对象
        self.socket = None # 储存zmq套接字对象 这俩none在下面调用的时候才赋值
        self.context = zmq.Context() # 创建上下文

        # 该类的方法调用（方法在下面定义）
        self.setup_serial_connection()
        self.setup_zmq_socket()
        ## 下面定义了五个函数，前两个是创建实例的时候在方法里调用的，后面三个是在run.py中根据运行情况调用的

    '''串口连接'''
    def setup_serial_connection(self):
        while(True):
            try:
                self.ser = serial.Serial(self.port, self.baud_rate, timeout=1) # serial.serial是pyserial库里一个类，超时1s返回空数据
                logging.info(f"串口连接成功: {self.port}")
                break
            except serial.serialutil.SerialException:
                logging.error(f"无法连接串口: {self.port}, 尝试重新连接...") # serial.serialutil.SerialException 是 pyserial 库中定义的一个异常类。
                time.sleep(0.5) # 等待0.5s重试


    '''zmq配置(改用PUSH)'''
    def setup_zmq_socket(self):
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(self.zmq_address)
        logging.info(f"已连接到 ZeroMQ 端口: {self.zmq_address}")


    '''串口读取数据+zmq发送'''
    # 比之前的方法多了错误检查机制
    def send_data(self):
        frame_count = 0
        while True:
            try:
                # 读取START行
                start_line = self.ser.readline().decode('utf-8').strip()
                if start_line.find("START") == -1:
                    continue  # 如果没有找到START，跳过这一轮

                # 发送START时间戳
                self.socket.send_string(start_line)
                logging.info(f"开始时间戳: {start_line}")

                # 读取8x8数据矩阵
                data_list = []
                for _ in range(8):  # 读取8行
                    serial_input = self.ser.readline().decode('utf-8').strip()
                    data_list.append(serial_input)

                if len(data_list) == 8:
                    # 发送8x8矩阵数据
                    self.socket.send_string("\n".join(data_list))
                    logging.info(f"8x8矩阵数据")

                # 读取END行
                end_line = self.ser.readline().decode('utf-8').strip()
                if end_line.find("END") == -1:
                    continue  # 如果没有找到END，跳过这一轮

                # 发送END时间戳
                self.socket.send_string(end_line)
                logging.info(f"结束时间戳: {end_line}")

                frame_count += 1  # 统计发送了多少帧
                time.sleep(0.01)  # 控制发送频率

            except KeyboardInterrupt:
                logging.info("用户中断程序")
                break
            except Exception as e:
                logging.error(f"发生错误: {e}")
                time.sleep(0.5)  # 遇到错误时稍作等待


    '''结束清除串口资源'''
    def close(self):
        if self.ser:
            self.ser.close()
        if self.socket:
            self.socket.close()
        self.context.term()
        logging.info("串口和 ZeroMQ 资源已释放")