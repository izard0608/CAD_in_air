# app.service.GestureBackend.py  手势识别后端逻辑
import time
import numpy as np
from collections import deque

from WebSocketClient import create_client
import MathUtils as mu
import Config

class GestureBackend:
    def __init__(self, server_url=None):
        self.DEBUG = True
        self.LOG_EVERY_N = Config.LOG_EVERY_N
        self.HISTORY_N = Config.HISTORY_N
        self._history = deque(maxlen=self.HISTORY_N)

        self.sio = create_client(server_url or Config.SERVER_URL)
        self.server_url = server_url or Config.SERVER_URL

        self.LEFT_THUMB_FINGER  = Config.LEFT_THUMB_FINGER
        self.LEFT_FORE_FINGER   = Config.LEFT_FORE_FINGER
        self.RIGHT_THUMB_FINGER = Config.RIGHT_THUMB_FINGER
        self.RIGHT_FORE_FINGER  = Config.RIGHT_FORE_FINGER

        self.TIME_THRESHOLD     = Config.TIME_THRESHOLD
        self.MAXLEN             = Config.MAXLEN
        self.POSITION_THRESHOLD = Config.POSITION_THRESHOLD
        self.DIS_ON   = Config.DIS_ON
        self.DIS_OFF  = Config.DIS_OFF
        self.MOVE_EPS = Config.MOVE_EPS
        self.DEGREE_THRESHOLD   = Config.DEGREE_THRESHOLD
        self.DIS_THRESHOLD      = Config.DIS_THRESHOLD

        self.edge_flag = 0
        self.left_history   = deque(maxlen=self.MAXLEN)
        self.right_history  = deque(maxlen=self.MAXLEN)
        self.degree_history = deque(maxlen=self.MAXLEN)

        self._frame = 0
        self._last_center = None
        self.last_command_time = 0
        self.command_cooldown = Config.COMMAND_COOLDOWN

    def connect(self):
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

    def process_data(self, data):
        self._frame += 1
        timestamp = data.get("timestamp", time.time())
        points = data.get("points") or []

        if len(points) < 12:
            if self.DEBUG and self._frame % self.LOG_EVERY_N == 0:
                print(f"⚠️ 数据点不足: {len(points)}/12")
            return

        if self._frame % self.LOG_EVERY_N == 0:
            valid_points = sum(1 for p in points if mu.is_valid_point(p))
            print(f"🎯 处理数据帧 #{self._frame}, 有效点: {valid_points}/12")

        # 左手建点
        lt_tip = points[self.LEFT_THUMB_FINGER[0]]
        li_tip = points[self.LEFT_FORE_FINGER[0]]

        if mu.is_valid_point(lt_tip) and mu.is_valid_point(li_tip):
            d = mu.distance(lt_tip, li_tip)
            self.left_history.append((timestamp, d, lt_tip, li_tip))

            if len(self.left_history) >= 5:
                times = [x[0] for x in self.left_history]
                if times[-1] - times[0] >= self.TIME_THRESHOLD:
                    dvals = [x[1] for x in self.left_history]
                    if max(dvals) - min(dvals) < self.POSITION_THRESHOLD and d < self.DIS_THRESHOLD:
                        new_node = mu.mid(lt_tip, li_tip)
                        self.send_command('start_drawing_point', {'position': new_node})
                        self.left_history.clear()

        # 右手画线
        rt_tip = points[self.RIGHT_THUMB_FINGER[0]]
        ri_tip = points[self.RIGHT_FORE_FINGER[0]]

        if mu.is_valid_point(rt_tip) and mu.is_valid_point(ri_tip):
            d = mu.distance(rt_tip, ri_tip)
            center = mu.mid(rt_tip, ri_tip)

            self.right_history.append((timestamp, d, center))

            if self.edge_flag == 0:
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
                if d > self.DIS_OFF:
                    end_node = center
                    self.send_command('finish_drawing_line', {'position': end_node})
                    self.edge_flag = 0
                    self._last_center = None
                    self.right_history.clear()
                else:
                    if self._last_center is None or mu.distance(center, self._last_center) > self.MOVE_EPS:
                        self.send_command('update_drawing_line', {'position': center})
                        self._last_center = center

        # 双手角度建面
        if (mu.is_valid_point(points[self.LEFT_FORE_FINGER[1]]) and 
            mu.is_valid_point(points[self.LEFT_FORE_FINGER[2]]) and
            mu.is_valid_point(points[self.RIGHT_FORE_FINGER[1]]) and 
            mu.is_valid_point(points[self.RIGHT_FORE_FINGER[2]])):

            l_vec = [points[self.LEFT_FORE_FINGER[1]][i] - points[self.LEFT_FORE_FINGER[2]][i] for i in range(3)]
            l_thv = [points[self.LEFT_THUMB_FINGER[1]][i] - points[self.LEFT_THUMB_FINGER[2]][i] for i in range(3)]
            r_vec = [points[self.RIGHT_FORE_FINGER[1]][i] - points[self.RIGHT_FORE_FINGER[2]][i] for i in range(3)]
            r_thv = [points[self.RIGHT_THUMB_FINGER[1]][i] - points[self.RIGHT_THUMB_FINGER[2]][i] for i in range(3)]

            d_left = mu.vector_angle(l_vec, l_thv)
            d_right = mu.vector_angle(r_vec, r_thv)

            if d_left > self.DEGREE_THRESHOLD and d_right > self.DEGREE_THRESHOLD:
                self.degree_history.append((timestamp, d_left, d_right))

                if len(self.degree_history) >= 5:
                    times = [x[0] for x in self.degree_history]
                    if times[-1] - times[0] >= self.TIME_THRESHOLD:
                        lp1 = [(points[self.LEFT_FORE_FINGER[1]][i] + points[self.LEFT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                        lp2 = [(points[self.LEFT_FORE_FINGER[2]][i] + points[self.LEFT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]
                        rp1 = [(points[self.RIGHT_FORE_FINGER[1]][i] + points[self.RIGHT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                        rp2 = [(points[self.RIGHT_FORE_FINGER[2]][i] + points[self.RIGHT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]

                        nv = mu.normal_vector(
                            [lp1[i] - lp2[i] for i in range(3)],
                            [rp1[i] - rp2[i] for i in range(3)]
                        )

                        if np.linalg.norm(np.asarray(nv, dtype=float)) > 1e-8:
                            p_start = lp2
                            p_end = mu.point_to_plane(rp2, p_start, nv)

                            self.send_command('create_plane', {
                                'start_position': p_start,
                                'end_position': p_end,
                                'normal_vector': nv
                            })
                            self.degree_history.clear()