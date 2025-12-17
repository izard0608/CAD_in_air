import zmq
import time
import math
import numpy as np
from collections import deque
import socketio
import threading
import json

from ModuleStatusList import ModuleStatusList as MSL

class GestureBackend:
    def __init__(self, server_url='http://localhost:5000'):
        self.DEBUG = True
        self.LOG_EVERY_N = 10
        self.HISTORY_N = 200
        self._history = deque(maxlen=self.HISTORY_N)

        # Socket.IO
        self.sio = socketio.Client()
        self.server_url = server_url
        self.setup_websocket()

        # 手指索引
        self.LEFT_THUMB_FINGER  = [0,1,2]
        self.LEFT_FORE_FINGER   = [3,4,5]
        self.RIGHT_THUMB_FINGER = [6,7,8]
        self.RIGHT_FORE_FINGER  = [9,10,11]

        # 阈值参数
        self.TIME_THRESHOLD     = 0.8
        self.MAXLEN             = 30
        self.POSITION_THRESHOLD = 0.08
        self.DIS_ON   = 0.04
        self.DIS_OFF  = 0.08
        self.MOVE_EPS = 0.02
        self.DEGREE_THRESHOLD   = 60.0
        self.DIS_THRESHOLD      = 2

        # 状态
        self.edge_flag = 0
        self.left_history   = deque(maxlen=self.MAXLEN)
        self.right_history  = deque(maxlen=self.MAXLEN)
        self.degree_history = deque(maxlen=self.MAXLEN)

        self._frame = 0
        self._last_center = None
        self.last_command_time = 0
        self.command_cooldown = 0.5  # 命令冷却时间

    def setup_websocket(self):
        @self.sio.event
        def connect():
            print("✅ 连接到Flask服务器")

        @self.sio.event
        def disconnect():
            print("❌ 与服务器断开连接")

    def connect(self):
        module_status_list = MSL().ready_dict
        module_status_list[__file__].wait()
        print("⏳ 等待main.py就绪...")
        try:
            self.sio.connect(self.server_url)
            print("✅ WebSocket连接成功")
            return True
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")
            return False

    def _json_safe(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (list, tuple)):
            return [self._json_safe(x) for x in obj]
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return obj

    def send_command(self, command_type, parameters):
        # 命令冷却
        current_time = time.time()
        if current_time - self.last_command_time < self.command_cooldown:
            return
            
        self.last_command_time = current_time
        
        params = dict(parameters)
        if command_type == 'start_drawing_point' and 'position' in params:
            params.setdefault('color', 0xff0000)
            params.setdefault('size', 0.1)
            params.setdefault('name', f"point_{int(time.time()*1000)}")

        payload = {
            'type': 'command',
            'command': command_type,
            'parameters': self._json_safe(params),
            'timestamp': time.time()
        }
        self._history.append(payload)
        
        print(f"📤 发送命令: {command_type}")
        if self.DEBUG:
            print(f"   参数: {params}")

        try:
            self.sio.emit('gesture_command', payload)
        except Exception as e:
            print(f"❌ 发送命令失败: {e}")

    def distance(self, p1, p2):
        return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

    def vector_angle(self, p1, p2):
        dot = sum(x*y for x, y in zip(p1, p2))
        n1 = math.sqrt(sum(x**2 for x in p1))
        n2 = math.sqrt(sum(x**2 for x in p2))
        if n1 == 0 or n2 == 0:
            return 0.0
        cos_theta = max(-1.0, min(1.0, dot/(n1*n2)))
        return math.degrees(math.acos(cos_theta))

    def unit(self, v):
        v = np.asarray(v, dtype=float)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def normal_vector(self, a, b):
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        nP = np.cross(a, b)
        nP_norm = np.linalg.norm(nP)
        if nP_norm < 1e-12:
            return [0.0, 0.0, 0.0]
        ua = self.unit(a)
        ub = self.unit(b)
        v  = ua - ub
        nQ = np.cross(nP, v)
        nq_norm = np.linalg.norm(nQ)
        if nq_norm < 1e-12:
            return [0.0, 0.0, 0.0]
        return (nQ / nq_norm).tolist()

    def point_to_plane(self, x, p0, n):
        n = np.asarray(n, dtype=float)
        x = np.asarray(x, dtype=float)
        p0 = np.asarray(p0, dtype=float)
        nn = float(np.dot(n, n))
        if nn < 1e-12:
            return x.tolist()
        t = float(np.dot(x - p0, n) / nn)
        return (x - t * n).tolist()

    def _mid(self, a, b):
        return [(a[i]+b[i])/2.0 for i in range(3)]

    def is_valid_point(self, point):
        """检查点是否有效（非零值）"""
        return point[0] != 0.0 or point[1] != 0.0 or point[2] != 0.0

    def process_data(self, data):
        self._frame += 1
        timestamp = data.get("timestamp", time.time())
        points = data.get("points") or []
        
        if len(points) < 12:
            if self.DEBUG and self._frame % self.LOG_EVERY_N == 0:
                print(f"⚠️ 数据点不足: {len(points)}/12")
            return

        if self._frame % self.LOG_EVERY_N == 0:
            valid_points = sum(1 for p in points if self.is_valid_point(p))
            print(f"🎯 处理数据帧 #{self._frame}, 有效点: {valid_points}/12")

        # 左手：稳定建点
        lt_tip = points[self.LEFT_THUMB_FINGER[0]]
        li_tip = points[self.LEFT_FORE_FINGER[0]]
        
        if self.is_valid_point(lt_tip) and self.is_valid_point(li_tip):
            d = self.distance(lt_tip, li_tip)
            self.left_history.append((timestamp, d, lt_tip, li_tip))
            
            if len(self.left_history) >= 5:
                times = [x[0] for x in self.left_history]
                if times[-1] - times[0] >= self.TIME_THRESHOLD:
                    dvals = [x[1] for x in self.left_history]
                    if max(dvals) - min(dvals) < self.POSITION_THRESHOLD and d < self.DIS_THRESHOLD:
                        new_node = self._mid(lt_tip, li_tip)
                        self.send_command('start_drawing_point', {'position': new_node})
                        self.left_history.clear()

        # 右手：实时画线
        rt_tip = points[self.RIGHT_THUMB_FINGER[0]]
        ri_tip = points[self.RIGHT_FORE_FINGER[0]]
        
        if self.is_valid_point(rt_tip) and self.is_valid_point(ri_tip):
            d = self.distance(rt_tip, ri_tip)
            center = self._mid(rt_tip, ri_tip)

            self.right_history.append((timestamp, d, center))

            if self.edge_flag == 0:
                # 开始画线：稳定捏合
                if len(self.right_history) >= 5:
                    times = [x[0] for x in self.right_history]
                    if times[-1] - times[0] >= self.TIME_THRESHOLD:
                        dvals = [x[1] for x in self.right_history]
                        if max(dvals) - min(dvals) < self.POSITION_THRESHOLD and d < self.DIS_ON:
                            start_node = self.right_history[-1][2]
                            self.send_command('start_drawing_line', {'position': start_node})
                            self.edge_flag = 1
                            self._last_center = start_node
                            self.right_history.clear()
            else:
                # 画线中
                if d > self.DIS_OFF:
                    # 松手结束画线
                    end_node = center
                    self.send_command('finish_drawing_line', {'position': end_node})
                    self.edge_flag = 0
                    self._last_center = None
                    self.right_history.clear()
                else:
                    # 移动更新
                    if (self._last_center is None or 
                        self.distance(center, self._last_center) > self.MOVE_EPS):
                        self.send_command('update_drawing_line', {'position': center})
                        self._last_center = center

        # 双手角度：建面
        if (self.is_valid_point(points[self.LEFT_FORE_FINGER[1]]) and 
            self.is_valid_point(points[self.LEFT_FORE_FINGER[2]]) and
            self.is_valid_point(points[self.RIGHT_FORE_FINGER[1]]) and 
            self.is_valid_point(points[self.RIGHT_FORE_FINGER[2]])):
            
            l_vec = [points[self.LEFT_FORE_FINGER[1]][i] - points[self.LEFT_FORE_FINGER[2]][i] for i in range(3)]
            l_thv = [points[self.LEFT_THUMB_FINGER[1]][i] - points[self.LEFT_THUMB_FINGER[2]][i] for i in range(3)]
            r_vec = [points[self.RIGHT_FORE_FINGER[1]][i] - points[self.RIGHT_FORE_FINGER[2]][i] for i in range(3)]
            r_thv = [points[self.RIGHT_THUMB_FINGER[1]][i] - points[self.RIGHT_THUMB_FINGER[2]][i] for i in range(3)]

            d_left = self.vector_angle(l_vec, l_thv)
            d_right = self.vector_angle(r_vec, r_thv)

            if d_left > self.DEGREE_THRESHOLD and d_right > self.DEGREE_THRESHOLD:
                self.degree_history.append((timestamp, d_left, d_right))
                
                if len(self.degree_history) >= 5:
                    times = [x[0] for x in self.degree_history]
                    if times[-1] - times[0] >= self.TIME_THRESHOLD:
                        # 创建平面
                        lp1 = [(points[self.LEFT_FORE_FINGER[1]][i] + points[self.LEFT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                        lp2 = [(points[self.LEFT_FORE_FINGER[2]][i] + points[self.LEFT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]
                        rp1 = [(points[self.RIGHT_FORE_FINGER[1]][i] + points[self.RIGHT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                        rp2 = [(points[self.RIGHT_FORE_FINGER[2]][i] + points[self.RIGHT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]

                        nv = self.normal_vector(
                            [lp1[i] - lp2[i] for i in range(3)],
                            [rp1[i] - rp2[i] for i in range(3)]
                        )

                        if np.linalg.norm(np.asarray(nv, dtype=float)) > 1e-8:
                            p_start = lp2
                            p_end = self.point_to_plane(rp2, p_start, nv)

                            self.send_command('create_plane', {
                                'start_position': p_start,
                                'end_position': p_end,
                                'normal_vector': nv
                            })
                            self.degree_history.clear()

if __name__ == "__main__":
    backend = GestureBackend()

    if backend.connect():
        print("🚀 启动实时手势识别模式...")
        context = zmq.Context()
        socket = context.socket(zmq.PULL)
        socket.connect("tcp://127.0.0.1:5557")
        print("✅ 连接到融合数据端口: 5557")
        module_status_list = MSL()
        module_status_list.set_ready(__file__)
        try:
            while True:
                data = socket.recv_pyobj()
                backend.process_data(data)
        except KeyboardInterrupt:
            print("⏹️ 用户停止程序")
        except Exception as e:
            print(f"❌ 数据接收错误: {e}")
        finally:
            socket.close()
            context.term()
    else:
        print("❌ 无法连接到Web服务器，请确保main.py正在运行")