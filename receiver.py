'''检查串口设备
import serial.tools.list_ports

ports_list = list(serial.tools.list_ports.comports())
if len(ports_list) <= 0:
    print("无串口设备。")
else:
    print("可用的串口设备如下：")
for comport in ports_list:
    print(comport.device, comport.description)
'''

import serial
ser = serial.Serial("COM5", 9600, timeout=1)  # 打开COM5，将波特率配置为9600，其余参数使用默认值，读超时时间1s
data_list = []


if ser.isOpen():  # 判断串口是否成功打开
    print("打开串口成功。")
    print(ser.name)  # 输出串口号
else:
    print("打开串口失败。")

while True:
    com_input = ser.read(10) # read配置超时时间
    if com_input:  # 如果读取结果非空，则输出
        print(com_input)



