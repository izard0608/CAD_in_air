# run.py
import logging
import threading
from app import create_app
from app.receivers.CameraXY import CameraHandTracker
from app.receivers.SerialReceiver import SerialReceiver
from app.utils.LocationCalculate import main as location_calculate_main

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("启动系统...")
    
    # 创建Flask应用
    app, socketio = create_app()
    
    # 启动摄像头（守护线程）
    def start_cam():
        tracker = CameraHandTracker()
        tracker.run()
    
    cam_thread = threading.Thread(target=start_cam, daemon=True)
    cam_thread.start()
    
    # 启动串口（守护线程）
    def start_serial():
        receiver = SerialReceiver()
        receiver.send_data()
    
    serial_thread = threading.Thread(target=start_serial, daemon=True)
    serial_thread.start()
    
    # 启动数据融合（守护线程）
    def start_fusion():
        location_calculate_main()
    
    fusion_thread = threading.Thread(target=start_fusion, daemon=True)
    fusion_thread.start()
    
    # 等待摄像头服务器启动
    import time
    time.sleep(2)
    
    # 启动Flask服务器（主线程）
    logger.info("Flask服务器启动在 http://localhost:5000")
    logger.info("视频流: http://localhost:5001/video_feed")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    main()
