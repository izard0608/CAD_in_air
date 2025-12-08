# run.py
import logging
import time
import threading
from app import create_app
from app.receivers.CameraHandTracker import CameraHandTracker
from app.receivers.SerialReceiver import SerialReceiver
from app.utils.LocationCalculate import main as location_calculate_main
from app.services.GestureBackend import GestureBackend 

logger = logging.getLogger(__name__)

# 创建Flask应用和SocketIO实例
app, socketio = create_app()

# 启动视频流服务器
def start_video_stream():
    video_server = VideoStreamServer(port=5001)
    try:
        logging.info("启动视频流服务器……")
        video_server.run()  # 启动视频流服务
    except Exception as e:
        logging.error(f"视频流服务器启动失败: {e}")

# 启动SerialReceiver
def start_serial_receiver():
    receiver = SerialReceiver()  # 使用SerialReceiver类来接收数据
    try:
        logging.info("启动SerialReceiver……")
        receiver.send_data()  # 处理串口数据
    except KeyboardInterrupt:
        logging.info("用户中断程序")
    except Exception as e:
        logging.error(f"串口接收启动失败: {e}")
    finally:
        receiver.close()

# 启动Flask和WebSocket
def start_flask_server():
    try:
        logging.info("启动Flask服务器……")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)  # 启动Flask应用
    except Exception as e:
        logging.error(f"Flask服务器启动失败: {e}")

# 主程序，使用线程来同时启动多个服务
def main():
    # 启动视频流服务器（可以在后台单独运行）
    video_thread = threading.Thread(target=start_video_stream)
    video_thread.daemon = True  # 设置为守护线程，主线程退出时视频线程也会退出
    video_thread.start()

    # 启动串口接收
    serial_thread = threading.Thread(target=start_serial_receiver)
    serial_thread.daemon = True  # 设置为守护线程，主线程退出时串口接收线程也会退出
    serial_thread.start()

    # 启动Flask应用服务器
    start_flask_server()

# 确保主程序启动
if __name__ == "__main__":
    main()
