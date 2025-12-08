# app.receivers.CameraXY.py

'''
1、openCV捕获摄像头视频流
2、mediapipe处理视频帧，获取xy坐标
3、使用WebRTC推送到前端
4、
关于视频流：使用WebRTC 替代 MJPEG。
    原先用的MJPEG是每一帧都单独编码成 JPEG 图片，然后按顺序传输。文件很大延迟很高。
    WebRTC类似于视频通话，可以降低延迟。
'''

import logging
import cv2
import mediapipe as mp
import zmq
import time
import threading
import numpy as np

class CameraHandTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # ZeroMQ设置
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect("tcp://127.0.0.1:5556")
        self.logger = logging.getLogger(__name__)  # 获取logger
        self.logger.info("🎥 摄像头手部追踪器初始化完成")
        
        # 视频流服务器
        self.video_server = VideoStreamServer(port=5001)
        
        # 启动视频流服务器
        self.logger.info("🔄 启动视频流服务器...")
        server_thread = threading.Thread(target=self.video_server.run, daemon=True)
        server_thread.start()
        time.sleep(2)  # 给服务器启动时间

    def find_working_camera(self):
        """查找可用的摄像头"""
        self.logger.info("查找可用摄像头...")
        for camera_index in [1, 0]:
            self.logger.info(f"尝试摄像头索引: {camera_index}")
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                time.sleep(1)
                for attempt in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        cap.release()
                        self.logger.info(f"摄像头 {camera_index} 可用")
                        return camera_index
                    time.sleep(0.1)
                cap.release()
        self.logger.error("未找到可用摄像头")
        return None

    def process_frame(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        all_points = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                points = self.get_all_required_points(hand_landmarks)
                all_points.extend(points)
        else:
            all_points = [[0.0, 0.0]] * 6
        
        return all_points

    def send_coordinates(self, points, frame_size):
        data = {
            "timestamp": time.time(),
            "points": points,
            "type": "camera_coordinates",
            "frame_size": frame_size
        }
        self.socket.send_json(data)
        self.logger.info(f"📤 发送 {len(points)}/12 个手部点坐标")

    def draw_landmarks(self, frame, points):
        h, w, _ = frame.shape
        for i, point in enumerate(points):
            x_norm, y_norm = point
            if x_norm == 0 and y_norm == 0:
                continue
            x = int(x_norm * w)
            y = int(y_norm * h)
            cv2.circle(frame, (x, y), 8, (0, 255, 0), -1)
            cv2.putText(frame, str(i), (x+10, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def run(self):
        camera_index = self.find_working_camera()
        if camera_index is None:
            self.logger.error("没有可用摄像头，程序终止")
            return
        
        self.logger.info(f"📷 使用摄像头索引: {camera_index}")
        
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.logger.error(f"❌ 无法打开摄像头 {camera_index}")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        frame_count = 0
        last_send_time = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    self.logger.error("❌ 无法读取摄像头帧")
                    continue
                
                frame_count += 1
                display_frame = frame.copy()
                process_frame = frame.copy()
                
                h, w, _ = process_frame.shape
                frame_size = [w, h]
                
                points = self.process_frame(process_frame)
                
                current_time = time.time()
                if current_time - last_send_time > 0.2:  # 5 FPS
                    self.send_coordinates(points, frame_size)
                    last_send_time = current_time
                
                self.draw_landmarks(display_frame, points)
                
                self.video_server.update_frame(display_frame)
                
                cv2.imshow("Hand Tracking", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except KeyboardInterrupt:
            self.logger.info("⏹️ 用户中断程序")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.hands.close()
            self.logger.info("✅ 摄像头资源已释放")

if __name__ == "__main__":
    tracker = CameraHandTracker()
    tracker.run()
