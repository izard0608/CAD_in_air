'''
required serial transmission format:

<time stamp>
<serial data line 1 to line 8>

'''


import serial
import zmq
import time


RP_COM = "COM3"
BAUD_RATES = 115200


while(True):
    try:
        ser = serial.Serial(RP_COM, BAUD_RATES, timeout = 1)
    except serial.serialutil.SerialException:
        print("unable to open serial port.")
        time.sleep(0.5)
    else:
        break

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5555")


while(not ser.isOpen()):
    pass

while(True):
    data_list = []
    start_line = ser.readline().decode('utf-8') # read start time stamp

    if(start_line.find("START") == -1):
        continue
    try:
        socket.send_string(start_line, zmq.NOBLOCK)  # send start time stamp, ensure the serial data received last time has been sent
        print(start_line)
    except zmq.ZMQError:
        continue
    
    for _ in range(8):  # read the 8 * 8 matrix
        serial_input = ser.readline().decode('utf-8')
        data_list.append(serial_input)

    if len(data_list) == 8:  # send data
        socket.send_string("\n".join(data_list))
        print("\n".join(data_list))

    end_line = ser.readline().decode('utf-8')  # read end time stamp
    if(end_line.find("END") == -1):
        continue

    socket.send_string(end_line)  # send end time stamp
    print(end_line)

    time.sleep(0.01)