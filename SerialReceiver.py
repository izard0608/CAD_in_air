'''
required serial transmision format:

<time stamp>
<serial data line 1 to line 8>

'''


import serial
import zmq
import time


RP_COM = "COM5"
BAUD_RATES = 9600


while(True):
    try:
        ser = serial.Serial(RP_COM, BAUD_RATES, timeout = 1)
    except serial.serialutil.SerialException:
        print("unable to open serial port.")
        time.sleep(0.5)
    else:
        break


data_list = []

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5555")


while(not ser.isOpen()):
    pass

while(True):
    try:
        socket.send_string(ser.readline().decode('utf-8'), zmq.NOBLOCK)  # time stamp, ensure the serial data received last time has been sent
    except zmq.ZMQError:
        continue
    
    for _ in range(8):  # read the 8*8 matrix
        serial_input += ser.readline().decode('utf-8')
        data_list.append(serial_input)

    if len(data_list) == 8:  # send data
        socket.send_string("\n".join(data_list))
    time.sleep(0.01)