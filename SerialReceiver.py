import serial
import zmq
import time

from ModuleStatusList import ModuleStatusList as MSL

# 串口配置
SERIAL_PORTS = ["COM3", "COM4", "COM5", "/dev/ttyUSB0", "/dev/ttyACM0"]
BAUD_RATE = 115200

print("🔌 尝试连接串口...")

# 自动检测串口
ser = None
for port in SERIAL_PORTS:
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        print(f"✅ 串口连接成功: {port}")
        break
    except:
        print(f"❌ 无法连接串口: {port}")

if ser is None:
    print("❌ 所有串口连接失败，请检查设备连接")
    module_status_list = MSL()
    module_status_list.set_ready(__file__)
    while True:
        time.sleep(1)

# ZeroMQ设置
context = zmq.Context()
socket = context.socket(zmq.PUSH)
socket.connect("tcp://127.0.0.1:5555")
print("📡 连接到数据融合端口: 5555")

print("🚀 SerialReceiver 启动，开始读取VL53L5CX深度数据...")
module_status_list = MSL()
module_status_list.set_ready(__file__)

frame_count = 0
error_count = 0
max_errors = 10

try:
    while True:
        # 读取START行
        start_line = ser.readline().decode('utf-8', errors='ignore').strip()
        if not start_line.startswith("START"):
            continue

        parts = start_line.split()
        if len(parts) < 2:
            continue

        # 读取8行深度数据
        depth_rows = []
        valid_data = True
        
        for i in range(8):
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                valid_data = False
                break

            try:
                nums = [int(x) for x in line.split() if x.strip()]
                if len(nums) != 8:
                    valid_data = False
                    break
                depth_rows.append(nums)
            except ValueError:
                valid_data = False
                break

        if not valid_data or len(depth_rows) != 8:
            error_count += 1
            if error_count >= max_errors:
                print("❌ 数据格式错误过多，请检查传感器连接")
                break
            continue

        # 读取END行
        end_line = ser.readline().decode('utf-8', errors='ignore').strip()
        if not end_line.endswith("END"):
            error_count += 1
            continue

        error_count = 0  # 重置错误计数

        # 打包数据
        packet = {
            "type": "tof_depth",
            "start_ms": int(parts[1]),
            "end_ms": int(end_line.split()[0]),
            "depth_mm": depth_rows,
        }

        socket.send_json(packet)
        frame_count += 1
        if frame_count % 10 == 0:  # 每10帧打印一次
            print(f"📤 发送ToF深度帧 #{frame_count}")

        time.sleep(0.01)

except KeyboardInterrupt:
    print("⏹️ 用户中断程序")
except Exception as e:
    print(f"❌ SerialReceiver错误: {e}")
finally:
    if ser:
        ser.close()
    socket.close()
    context.term()
    print("✅ 串口资源已释放")