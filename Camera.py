from time import sleep, time
import cv2
from mediapipe.python.solutions import hands
from zmq import Context, PUSH
from threading import Lock, Thread
from asyncio import new_event_loop, set_event_loop, run_coroutine_threadsafe, sleep as aio_sleep
from flask import Flask, Response, request
from flask_socketio import SocketIO
from numpy import zeros, uint8

# WebRTC (aiortc)
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, VideoStreamTrack
from av import VideoFrame


from ModuleStatusList import ModuleStatusList as MSL
from Profiler import Profiler


module_status_list = MSL()
is_running = module_status_list.module_running

class VideoStreamServer:
    def __init__(self, port=5001):
        self.port = port
        self.app = Flask(__name__)
        self.current_frame = None
        self.frame_lock = Lock()

        # Socket.IO（用于 WebRTC 信令）
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode="threading")

        # WebRTC: 维护每个客户端的 PeerConnection
        self.peer_connections = {}  # sid -> RTCPeerConnection

        # aiortc 需要 asyncio loop：单独开一个后台事件循环线程
        self.loop = new_event_loop()
        Thread(target=self._run_loop, daemon=True).start()

        self.setup_routes()
        self.setup_webrtc_signaling()

    def _run_loop(self):
        set_event_loop(self.loop)
        self.loop.run_forever()
        
    def setup_routes(self):
        @self.app.route('/video_feed')
        def video_feed():
            """提供MJPEG视频流"""
            return Response(self.generate_frames(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/test')
        def test():
            return "视频流服务器运行正常"
        
        @self.app.route('/status')
        def status():
            return "视频流服务器状态: 运行中"
    
    def generate_frames(self):
        """生成MJPEG视频流"""
        frame_count = 0
        while True:
            with self.frame_lock:
                if self.current_frame is not None:
                    try:
                        # 编码为JPEG
                        _, buffer = cv2.imencode('.jpg', self.current_frame)
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                        frame_count += 1
                    except Exception as e:
                        print(f"视频流编码错误: {e}")
                else:
                    # 没有摄像头时显示测试画面
                    test_frame = zeros((480, 640, 3), dtype=uint8)
                    cv2.putText(test_frame, "Camera Initializing...", (150, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    _, buffer = cv2.imencode('.jpg', test_frame)
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    frame_count += 1
            
            sleep(0.033)  # ~30fps
    
    def update_frame(self, frame):
        """更新当前帧"""
        with self.frame_lock:
            self.current_frame = frame

    # ===================== WebRTC =====================
    class _OpenCVTrack(VideoStreamTrack):
        """从 VideoStreamServer.current_frame 读取最新帧并推送为 WebRTC 视频轨"""
        def __init__(self, server):
            super().__init__()
            self.server = server

        async def recv(self):
            pts, time_base = await self.next_timestamp()

            with self.server.frame_lock:
                frame = None if self.server.current_frame is None else self.server.current_frame.copy()

            if frame is None:
                await aio_sleep(0.01)
                return await self.recv()

            # BGR -> RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            vf = VideoFrame.from_ndarray(rgb, format="rgb24")
            vf.pts = pts
            vf.time_base = time_base
            return vf

    def setup_webrtc_signaling(self):
        """Socket.IO 信令：webrtc_offer / webrtc_answer / webrtc_ice"""

        @self.socketio.on('webrtc_offer')
        def _on_offer(offer):
            sid = request.sid
            fut = run_coroutine_threadsafe(self._handle_offer(sid, offer), self.loop)
            # 调试期：让异常直接抛出
            fut.result()

        @self.socketio.on('webrtc_ice')
        def _on_ice(candidate):
            sid = request.sid
            fut = run_coroutine_threadsafe(self._handle_ice(sid, candidate), self.loop)
            fut.result()

        @self.socketio.on('disconnect')
        def _on_disconnect():
            sid = request.sid
            fut = run_coroutine_threadsafe(self._cleanup_peer(sid), self.loop)
            fut.result()

    async def _handle_offer(self, sid, offer):
        # 每个 sid 只保留一个连接
        await self._cleanup_peer(sid)

        pc = RTCPeerConnection()
        self.peer_connections[sid] = pc

        # 推送视频轨（来自 update_frame 的最新帧）
        pc.addTrack(self._OpenCVTrack(self))

        @pc.on('icecandidate')
        def _on_local_ice(candidate):
            if candidate is None:
                return
            self.socketio.emit('webrtc_ice', {
                'candidate': candidate.candidate,
                'sdpMid': candidate.sdpMid,
                'sdpMLineIndex': candidate.sdpMLineIndex,
            }, room=sid)

        @pc.on('connectionstatechange')
        async def _on_state_change():
            if pc.connectionState in ('failed', 'closed', 'disconnected'):
                await self._cleanup_peer(sid)

        # 处理远端 offer
        desc = RTCSessionDescription(sdp=offer['sdp'], type=offer['type'])
        await pc.setRemoteDescription(desc)

        # 创建 answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        self.socketio.emit('webrtc_answer', {
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type,
        }, room=sid)

    async def _handle_ice(self, sid, candidate):
        pc = self.peer_connections.get(sid)
        if pc is None or candidate is None:
            return

        # candidate 来自浏览器：{candidate, sdpMid, sdpMLineIndex, ...}
        c = RTCIceCandidate(
            candidate=candidate.get('candidate'),
            sdpMid=candidate.get('sdpMid'),
            sdpMLineIndex=candidate.get('sdpMLineIndex'),
        )
        try:
            await pc.addIceCandidate(c)
        except Exception as e:
            print(f"addIceCandidate error: {e}")

    async def _cleanup_peer(self, sid):
        pc = self.peer_connections.pop(sid, None)
        if pc is not None:
            try:
                await pc.close()
            except Exception:
                pass
    
    def run(self):
        """启动视频流服务器"""
        print(f" 视频流服务器运行在: http://localhost:{self.port}/video_feed")
        print(f" WebRTC 信令（Socket.IO）运行在: http://localhost:{self.port}")
        try:
            # 必须用 socketio.run 才能同时支持 Socket.IO 信令
            self.socketio.run(self.app, host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            print(f" 视频流服务器错误: {e}")

class CameraHandTracker:
    def __init__(self):
        self.mp_hands = hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # ZeroMQ设置
        self.context = Context()
        self.socket = self.context.socket(PUSH)
        self.socket.connect("tcp://127.0.0.1:5556")
        print(" 摄像头手部追踪器初始化完成")
        
        # 视频流服务器
        self.video_server = VideoStreamServer(port=5001)
        
        # 启动视频流服务器
        print(" 启动视频流服务器...")
        server_thread = Thread(target=self.video_server.run, daemon=True)
        server_thread.start()
        sleep(2)  # 给服务器启动时间

    def find_working_camera(self):
        """查找可用的摄像头"""
        print(" 查找可用摄像头...")
        # 优先尝试摄像头1（外置），如果不行就用摄像头0（内置）
        for camera_index in [1, 0]:
            print(f"尝试摄像头索引: {camera_index}")
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                # 给摄像头初始化时间
                sleep(1)
                # 尝试多次读取
                for attempt in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f" 摄像头 {camera_index} 可用 - 分辨率: {frame.shape[1]}x{frame.shape[0]}")
                        cap.release()
                        return camera_index
                    sleep(0.1)
                cap.release()
                print(f" 摄像头 {camera_index} 可打开但无法读取帧")
            else:
                print(f" 摄像头 {camera_index} 不可用")
        
        print(" 未找到可用摄像头")
        return None

    def get_all_required_points(self, hand_landmarks, hand_type):
        points = []
        
        thumb_points = [
            self.mp_hands.HandLandmark.THUMB_TIP,
            self.mp_hands.HandLandmark.THUMB_IP,
            self.mp_hands.HandLandmark.THUMB_MCP
        ]
        
        index_points = [
            self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
            self.mp_hands.HandLandmark.INDEX_FINGER_PIP,
            self.mp_hands.HandLandmark.INDEX_FINGER_MCP
        ]
        
        for landmark in thumb_points + index_points:
            point = hand_landmarks.landmark[landmark]
            points.append([point.x, point.y])
        
        return points

    def process_frame(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        all_points = []
        
        if results.multi_hand_landmarks and results.multi_handedness:
            left_hand_detected = False
            right_hand_detected = False
            
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                hand_type = handedness.classification[0].label
                
                if hand_type == "Left" and not left_hand_detected:
                    left_points = self.get_all_required_points(hand_landmarks, "Left")
                    all_points.extend(left_points)
                    left_hand_detected = True
                    print(" 检测到左手")
                    
                elif hand_type == "Right" and not right_hand_detected:
                    right_points = self.get_all_required_points(hand_landmarks, "Right")
                    all_points.extend(right_points)
                    right_hand_detected = True
                    print(" 检测到右手")
            
            if not left_hand_detected:
                all_points.extend([[0.0, 0.0]] * 6)
                
            if not right_hand_detected:
                all_points.extend([[0.0, 0.0]] * 6)
                
        else:
            all_points = [[0.0, 0.0]] * 12
        
        return all_points

    def send_coordinates(self, points, frame_size):
        data = {
            "timestamp": time(),
            "points": points,
            "type": "camera_coordinates",
            "frame_size": frame_size
        }
        
        self.socket.send_json(data)
        
        # 打印调试信息
        valid_points = sum(1 for p in points if p[0] != 0 or p[1] != 0)
        if valid_points > 0:
            print(f" 发送 {valid_points}/12 个手部点坐标")

    def draw_landmarks(self, frame, points):
        h, w, _ = frame.shape
        
        # 左手用绿色，右手用红色
        left_colors = [(0, 255, 0), (0, 200, 0), (0, 150, 0)]  # 绿色系
        right_colors = [(255, 0, 0), (200, 0, 0), (150, 0, 0)]  # 红色系
        
        for i, point in enumerate(points):
            x_norm, y_norm = point
            if x_norm == 0 and y_norm == 0:
                continue
                
            # 关键：这里不进行镜像翻转，保持原始坐标
            x = int(x_norm * w)
            y = int(y_norm * h)
            
            # 选择颜色：前6个点左手，后6个点右手
            if i < 6:  # 左手
                color = left_colors[i % 3]
            else:  # 右手
                color = right_colors[i % 3]
                
            cv2.circle(frame, (x, y), 8, color, -1)
            cv2.putText(frame, str(i), (x+10, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def run(self):
        # 查找可用摄像头
        camera_index = self.find_working_camera()
        if camera_index is None:
            print(" 无可用摄像头，视频流服务器继续运行（显示测试画面）")
            while is_running():
                sleep(1)
            return
        
        print(f" 使用摄像头索引: {camera_index}")
        
        # 打开摄像头
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f" 无法打开摄像头 {camera_index}")
            return
        
        # 设置摄像头参数
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print(" 开始摄像头手部追踪...")
        print(" 视频流地址: http://localhost:5001/video_feed")
        print(" 提示: 手部移动方向应该与标注点移动方向一致")
        
        module_status_list.set_ready("Camera.py")

        frame_count = 0
        last_send_time = 0
        first_send_time = 0
        first_time_flag = True

        try:
            while is_running():
                ret, frame = cap.read()
                if not ret:
                    print(" 无法读取摄像头帧")
                    # 显示错误画面
                    error_frame = zeros((480, 640, 3), dtype=uint8)
                    cv2.putText(error_frame, "Camera Error", (200, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    self.video_server.update_frame(error_frame)
                    sleep(0.1)
                    continue
                
                frame_count += 1
                
                # 关键修改：不进行镜像翻转，保持原始方向
                display_frame = frame.copy()  # 不使用flip，保持原始方向
                process_frame = frame.copy()
                
                h, w, _ = process_frame.shape
                frame_size = [w, h]
                
                # 处理帧获取手部坐标
                points = self.process_frame(process_frame)
                
                # 每秒发送5次数据
                current_time = time()
                if first_time_flag:
                    first_send_time = current_time
                    first_time_flag = False
                if current_time - last_send_time > 0.2:  # 5 FPS
                    self.send_coordinates(points, frame_size)
                    last_send_time = current_time
                
                # 在显示帧上绘制标记点
                self.draw_landmarks(display_frame, points)
                
                # 更新视频流服务器
                self.video_server.update_frame(display_frame)
                
                # 显示检测状态
                valid_points = sum(1 for p in points if p[0] != 0 or p[1] != 0)
                status = f"Camera {camera_index} | Fps: {frame_count / (current_time - first_send_time) if current_time - first_send_time else 0:.1f} | Hands: {valid_points}/12"
                cv2.putText(display_frame, status, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # 显示方向提示
                direction_hint = "Direction: Natural (No Flip)"
                cv2.putText(display_frame, direction_hint, (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # 显示本地窗口
                window_name = f'Hand Tracking - Camera {camera_index} (Natural Direction)'
                cv2.imshow(window_name, display_frame)
                
        except Exception as e:
            print(f" 程序错误: {e}")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.hands.close()
            print(" 摄像头资源已释放")

if __name__ == "__main__":
    print(" 启动摄像头手部追踪系统...")
    cp = Profiler()
    cp.start()
    tracker = CameraHandTracker()
    tracker.run()
    print(" 摄像头手部追踪系统已停止")
    cp.end("Camera.prof")
    module_status_list.profile_end("Camera.py")