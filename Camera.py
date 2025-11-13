# Camera
import cv2
import mediapipe as mp
import zmq
import time
import json

class CameraHandTracker:
    def __init__(self):
        # MediaPipe手势识别
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        
        # ZeroMQ设置 - 发送到LocationCalculate.py
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://127.0.0.1:5556")  # 摄像头数据端口
        
        print("🎥 摄像头手部追踪器初始化完成")

    def get_all_required_points(self, hand_landmarks, hand_type):
        """获取一只手的所有6个关键点坐标"""
        h, w = 480, 640  # 假设的帧尺寸，实际会在运行时获取
        
        points = []
        
        # 根据receive.py的要求，每只手需要6个点：
        # 大拇指3个点 + 食指3个点
        
        # 大拇指的3个点
        thumb_points = [
            self.mp_hands.HandLandmark.THUMB_TIP,      # 指尖
            self.mp_hands.HandLandmark.THUMB_IP,       # 第一关节
            self.mp_hands.HandLandmark.THUMB_MCP       # 第二关节
        ]
        
        # 食指的3个点
        index_points = [
            self.mp_hands.HandLandmark.INDEX_FINGER_TIP,  # 指尖
            self.mp_hands.HandLandmark.INDEX_FINGER_PIP,  # 第一关节
            self.mp_hands.HandLandmark.INDEX_FINGER_MCP   # 第二关节
        ]
        
        # 获取所有6个点的坐标
        for landmark in thumb_points + index_points:
            point = hand_landmarks.landmark[landmark]
            # 转换为3D坐标 (x, y, z)
            # MediaPipe的z是相对深度，值越小离摄像头越近
            points.append([point.x, point.y, point.z])
        
        return points

    def process_frame(self, frame):
        """处理一帧图像并返回手部坐标"""
        # 转换BGR到RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 手势识别
        results = self.hands.process(rgb_frame)
        
        all_points = []  # 存储所有12个点（左手6个 + 右手6个）
        
        if results.multi_hand_landmarks and results.multi_handedness:
            left_hand_detected = False
            right_hand_detected = False
            
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                hand_type = handedness.classification[0].label  # 'Left' 或 'Right'
                
                if hand_type == "Left" and not left_hand_detected:
                    left_points = self.get_all_required_points(hand_landmarks, "Left")
                    all_points.extend(left_points)
                    left_hand_detected = True
                    print("✅ 检测到左手")
                    
                elif hand_type == "Right" and not right_hand_detected:
                    right_points = self.get_all_required_points(hand_landmarks, "Right")
                    all_points.extend(right_points)
                    right_hand_detected = True
                    print("✅ 检测到右手")
            
            # 如果只检测到一只手，用默认值填充另一只手
            if not left_hand_detected:
                all_points.extend([[0, 0, 0]] * 6)  # 填充左手6个点
                print("❌ 未检测到左手，使用默认值")
                
            if not right_hand_detected:
                all_points.extend([[0, 0, 0]] * 6)  # 填充右手6个点
                print("❌ 未检测到右手，使用默认值")
                
        else:
            # 没检测到手，填充12个零点
            all_points = [[0, 0, 0]] * 12
            print("❌ 未检测到手部")
        
        return all_points

    def send_coordinates(self, points):
        """发送坐标数据"""
        data = {
            "timestamp": time.time(),
            "points": points,
            "type": "camera_coordinates",
            "frame_size": [640, 480]  # 帧尺寸信息
        }
        
        # 发送JSON数据
        self.socket.send_json(data)
        print(f"📤 发送摄像头数据: {len(points)}个点")

    def draw_landmarks(self, frame, points):
        """在图像上绘制手部关键点（调试用）"""
        h, w, _ = frame.shape
        
        colors = [(0, 255, 0), (0, 200, 0), (0, 150, 0),  # 左手绿色系
                  (255, 0, 0), (200, 0, 0), (150, 0, 0)]   # 右手红色系
        
        for i, point in enumerate(points):
            if point[0] == 0 and point[1] == 0:  # 跳过无效点
                continue
                
            x = int(point[0] * w)
            y = int(point[1] * h)
            
            # 选择颜色：前6个点左手，后6个点右手
            color = colors[i % 6] if i < 6 else colors[i % 6]
            
            # 绘制点
            cv2.circle(frame, (x, y), 6, color, -1)
            
            # 标注点编号
            cv2.putText(frame, str(i), (x+8, y-8), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    def run(self):
        """主运行循环"""
        # 🎯 关键修改：这里打开摄像头！
        cap = cv2.VideoCapture(0)
        
        # 设置摄像头参数
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not cap.isOpened():
            print("❌ 无法打开摄像头")
            return
        
        print("🎥 开始摄像头手部追踪...")
        print("按 'q' 键退出程序")
        print("等待摄像头初始化...")
        
        # 给摄像头一些初始化时间
        time.sleep(2)
        
        frame_count = 0
        try:
            while True:
                # 🎯 关键：读取摄像头帧
                ret, frame = cap.read()
                if not ret:
                    print("❌ 无法读取摄像头帧")
                    break
                
                frame_count += 1
                
                # 翻转帧使其更自然
                frame = cv2.flip(frame, 1)
                
                # 处理帧获取手部坐标
                points = self.process_frame(frame)
                
                # 发送坐标数据
                if frame_count % 5 == 0:  # 每5帧发送一次，减少负载
                    self.send_coordinates(points)
                
                # 在图像上绘制点
                self.draw_landmarks(frame, points)
                
                # 显示状态信息
                status = f"Points: {len(points)} | Frame: {frame_count}"
                cv2.putText(frame, status, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # 显示图像
                cv2.imshow('Hand Tracking - Camera Data', frame)
                
                # 按'q'退出
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except KeyboardInterrupt:
            print("⏹️ 用户中断程序")
        except Exception as e:
            print(f"❌ 程序错误: {e}")
        finally:
            # 释放资源
            cap.release()
            cv2.destroyAllWindows()
            self.hands.close()
            print("✅ 摄像头资源已释放")

if __name__ == "__main__":
    tracker = CameraHandTracker()
    tracker.run()