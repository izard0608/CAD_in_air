# serialreceiver.py

import serial
import zmq
import time

RP_COM = "COM3"
BAUD_RATES = 115200

# 打开串口
while True:
    try:
        ser = serial.Serial(RP_COM, BAUD_RATES, timeout=1)
    except serial.serialutil.SerialException:
        print("unable to open serial port.")
        time.sleep(0.5)
    else:
        break

# ZeroMQ：把 ToF 深度发给 locationcalculate.py
context = zmq.Context()
socket = context.socket(zmq.PUSH)
# locationcalculate.py 在 5555 上 PULL.bind
socket.connect("tcp://127.0.0.1:5555")

while not ser.isOpen():
    pass

print("📡 serialreceiver 启动，开始从 VL53L5CX 读取深度...")

while True:
    # 1) 读 START 行，例如： "START 628571"
    start_line = ser.readline().decode('utf-8').strip()
    if not start_line.startswith("START"):
        continue

    parts = start_line.split()
    if len(parts) < 2:
        continue
    start_ts = int(parts[1])

    # 2) 读 8 行深度数据
    depth_rows = []
    for _ in range(8):
        line = ser.readline().decode('utf-8').strip()
        if not line:
            continue

        # 拆成 8 个整数（毫米）
        nums = [int(x) for x in line.split()]
        if len(nums) != 8:
            depth_rows = []
            break
        depth_rows.append(nums)

    if len(depth_rows) != 8:
        continue

    # 3) 读 END 行，例如："628573 END"
    end_line = ser.readline().decode('utf-8').strip()
    if not end_line.endswith("END"):
        continue

    parts = end_line.split()
    if len(parts) < 2:
        continue
    end_ts = int(parts[0])

    # 4) 打包成 JSON 发送
    packet = {
        "type": "tof_depth",
        "start_ms": start_ts,
        "end_ms": end_ts,
        "depth_mm": depth_rows,   # 8x8，单位：毫米
    }

    socket.send_json(packet)
    print("📤 sent depth frame, start_ms =", start_ts, "end_ms =", end_ts)

    time.sleep(0.01)
