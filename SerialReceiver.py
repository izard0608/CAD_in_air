''' 
serial transmission and zmq sender format:

START <start time stamp>

<8*8 matrix data. in rows, values are separated by tabs, every two lines are separated by an empty line>

<end time stamp> END



data packs are separated by an empty line.

example:

START 628571

        2259    2295    2227    2006    1998    2009    2069    2202

        2271    2058    2013    2016    2086    2165    2191    2241

        2002    2018    2075    2188    2223    2187    2216    2195

        2043    2147    2231    2224    2222    2222    2214    2208

        2224    2206    2213    2196    2214    2171    2200    2198

        2196    2205    2238    2237    2207    2180    2148    2162

        2206    2219    2216    2199    2190    2170    2168    2173

        2285    2207    2194    2169    2200    2180    2165    2188

628573 END

START 629558

        2259    2278    2221    2070    1991    1997    2082    2234

        2305    2082    2013    2022    2090    2217    2203    2208

        2008    1993    2063    2199    2208    2213    2185    2209

        2051    2146    2241    2201    2211    2238    2197    2187

        2237    2209    2220    2227    2236    2222    2190    2214

        2229    2165    2207    2213    2191    2209    2205    2174

        2260    2235    2220    2208    2178    2171    2189    2168

        2285    2216    2230    2188    2195    2170    2164    2200

629560 END


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