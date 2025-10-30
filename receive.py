# receive.py (REPLACED)
import zmq
import time
import math
import numpy as np
from collections import deque
import socketio
import threading
import json

class GestureBackend:
    def __init__(self, server_url='http://localhost:5000'):
        # === 调试与历史 ===
        self.DEBUG = True
        self.LOG_EVERY_N = 5
        self.HISTORY_N = 200
        self._history = deque(maxlen=self.HISTORY_N)

        # === Socket.IO ===
        self.sio = socketio.Client()
        self.server_url = server_url
        self.setup_websocket()

        # === 手指索引（从指尖编号开始）===
        # 左手大拇指：0,1,2； 左手食指：3,4,5
        # 右手大拇指：6,7,8； 右手食指：9,10,11
        self.LEFT_THUMB_FINGER  = [0,1,2]
        self.LEFT_FORE_FINGER   = [3,4,5]
        self.RIGHT_THUMB_FINGER = [6,7,8]
        self.RIGHT_FORE_FINGER  = [9,10,11]

        # === 阈值参数 ===
        # 稳定窗口
        self.TIME_THRESHOLD     = 0.6    # 秒（起笔时需要稳定这么久）
        self.MAXLEN             = 50     # 历史容量（帧）
        self.POSITION_THRESHOLD = 0.05   # 窗口内“距离波动”允许的最大幅度

        # 捏合/松手的迟滞阈值（右手画线用）
        self.DIS_ON   = 0.03    # 进入捏合（更严格、更小）
        self.DIS_OFF  = 0.06    # 退出捏合（更宽松、更大）
        self.MOVE_EPS = 1e-4    # 中点位移阈值（防抖）

        # 其它
        self.DEGREE_THRESHOLD   = 70.0   # 建面角度阈值（度）
        # 兼容你左手建点原逻辑（仍然用一个宽松上限判断“手是靠得比较近的某个动作”）
        self.DIS_THRESHOLD      = 2.0

        # === 状态/历史 ===
        self.edge_flag = 0                  # 0=未画线, 1=画线中
        self.left_history   = deque(maxlen=self.MAXLEN)
        self.right_history  = deque(maxlen=self.MAXLEN)  # (t, d, center)
        self.degree_history = deque(maxlen=self.MAXLEN)

        self._frame = 0
        self._last_center = None

    # ------------------------------
    # WebSocket
    # ------------------------------
    def setup_websocket(self):
        @self.sio.event
        def connect():
            print("Connected to Flask server")

        @self.sio.event
        def disconnect():
            print("Disconnected from server")

    def connect(self):
        try:
            self.sio.connect(self.server_url)
            return True
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            return False

    # ------------------------------
    # Utils
    # ------------------------------
    def _json_safe(self, obj):
        """把 numpy 类型递归转成原生，便于 json.dumps """
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
        """
        透传 parameters（不要强行假设有 'position'）
        仅在“创建点”时，附加色彩/大小/名字（前端会忽略无关字段）。
        """
        params = dict(parameters)  # 浅拷贝
        if command_type == 'start_drawing_point' and 'position' in params:
            params.setdefault('color', 0xff0000)
            params.setdefault('size', 0.05)
            params.setdefault('name', f"point_{int(time.time()*1000)}")

        payload = {
            'type': 'command',
            'command': command_type,
            'parameters': self._json_safe(params),
            'timestamp': time.time()
        }
        self._history.append(payload)
        if self.DEBUG:
            try:
                print("📤 SEND", json.dumps(payload))
            except Exception:
                print("📤 SEND (non-json-printable)")

        self.sio.emit('gesture_command', payload)

    # 欧式距离
    def distance(self, p1, p2):
        return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

    # 三维向量夹角（度）
    def vector_angle(self, p1, p2):
        dot = sum(x*y for x, y in zip(p1, p2))
        n1 = math.sqrt(sum(x**2 for x in p1))
        n2 = math.sqrt(sum(x**2 for x in p2))
        if n1 == 0 or n2 == 0:
            return 0.0
        cos_theta = max(-1.0, min(1.0, dot/(n1*n2)))
        return math.degrees(math.acos(cos_theta))

    # 单位化（除零保护）
    def unit(self, v):
        v = np.asarray(v, dtype=float)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    # 平面法向量（鲁棒）
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

    # 点到平面投影
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

    # ------------------------------
    # 主处理：判定 + 发命令
    # ------------------------------
    def process_data(self, data):
        self._frame += 1
        timestamp = data.get("timestamp", time.time())
        points    = data.get("points") or []
        if len(points) < 12:
            if self.DEBUG and self._frame % self.LOG_EVERY_N == 0:
                print("⚠️ points 数量不足:", len(points))
            return

        # ---------- 左手：稳定建点（保留你的逻辑，小幅清理） ----------
        lt_tip = points[self.LEFT_THUMB_FINGER[0]]
        li_tip = points[self.LEFT_FORE_FINGER[0]]
        if lt_tip != li_tip:
            d = self.distance(lt_tip, li_tip)
            self.left_history.append((timestamp, d))
            if len(self.left_history) >= 3:
                t0 = self.left_history[0][0]
                t1 = self.left_history[-1][0]
                if t1 - t0 >= self.TIME_THRESHOLD:
                    dvals = [x[1] for x in self.left_history]
                    if max(dvals) - min(dvals) < self.POSITION_THRESHOLD and max(dvals) <= self.DIS_THRESHOLD:
                        new_node = self._mid(lt_tip, li_tip)
                        self.send_command('start_drawing_point', {'position': new_node})
                        self.left_history.clear()

        # ---------- 右手：实时画线（捏住→update→松手） ----------
        rt_tip = points[self.RIGHT_THUMB_FINGER[0]]
        ri_tip = points[self.RIGHT_FORE_FINGER[0]]
        if rt_tip != ri_tip:
            d = self.distance(rt_tip, ri_tip)
            center = self._mid(rt_tip, ri_tip)

            # 记录窗口（仅用于“起笔稳定”）
            self.right_history.append((timestamp, d, center))

            # 日志
            if self.DEBUG and self._frame % self.LOG_EVERY_N == 0:
                print(f"🧪 frame={self._frame} edge_flag={self.edge_flag} d={d:.4f} center=({center[0]:.3f},{center[1]:.3f},{center[2]:.3f})")

            if self.edge_flag == 0:
                # 起笔需要稳住 TIME_THRESHOLD 秒 + 距离进入捏合（<= DIS_ON）
                if len(self.right_history) >= 3:
                    t0 = self.right_history[0][0]
                    t1 = self.right_history[-1][0]
                    if t1 - t0 >= self.TIME_THRESHOLD:
                        dvals = [x[1] for x in self.right_history]
                        if max(dvals) - min(dvals) < self.POSITION_THRESHOLD and min(dvals) <= self.DIS_ON:
                            start_node = self.right_history[-1][2]
                            self.send_command('start_drawing_line', {'position': start_node})
                            self.edge_flag = 1
                            self._last_center = start_node
                            self.right_history.clear()
            else:
                # 画线中：先看是否松手
                if d > self.DIS_OFF:
                    end_node = center
                    self.send_command('finish_drawing_line', {'position': end_node})
                    self.edge_flag = 0
                    self._last_center = None
                    self.right_history.clear()
                else:
                    # 仍在捏住：按位移阈值发 update
                    if (self._last_center is None) or (self.distance(center, self._last_center) > self.MOVE_EPS):
                        self.send_command('update_drawing_line', {'position': center})
                        self._last_center = center

        # ---------- 双手角度：稳定建面（更鲁棒的零向量判断） ----------
        lf0, lt0 = points[self.LEFT_FORE_FINGER[0]],  points[self.LEFT_THUMB_FINGER[0]]
        rf0, rt0 = points[self.RIGHT_FORE_FINGER[0]], points[self.RIGHT_THUMB_FINGER[0]]
        if lf0 != lt0 and rf0 != rt0:
            l_vec = [points[self.LEFT_FORE_FINGER[1]][i] - points[self.LEFT_FORE_FINGER[2]][i] for i in range(3)]
            l_thv = [points[self.LEFT_THUMB_FINGER[1]][i] - points[self.LEFT_THUMB_FINGER[2]][i] for i in range(3)]
            r_vec = [points[self.RIGHT_FORE_FINGER[1]][i] - points[self.RIGHT_FORE_FINGER[2]][i] for i in range(3)]
            r_thv = [points[self.RIGHT_THUMB_FINGER[1]][i] - points[self.RIGHT_THUMB_FINGER[2]][i] for i in range(3)]

            d_left  = self.vector_angle(l_vec, l_thv)
            d_right = self.vector_angle(r_vec, r_thv)

            if d_left < self.DEGREE_THRESHOLD or d_right < self.DEGREE_THRESHOLD:
                self.degree_history.clear()
            else:
                # 这里继续沿用你原先用拇食距离做“稳定性”的口味
                d_pair = self.distance(rt_tip, ri_tip)
                self.degree_history.append((timestamp, d_pair))
                if len(self.degree_history) >= 3:
                    t0 = self.degree_history[0][0]
                    t1 = self.degree_history[-1][0]
                    if t1 - t0 >= self.TIME_THRESHOLD:
                        dvals = [x[1] for x in self.degree_history]
                        if max(dvals) - min(dvals) < self.POSITION_THRESHOLD:
                            lp1 = [(points[self.LEFT_FORE_FINGER[1]][i] + points[self.LEFT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                            lp2 = [(points[self.LEFT_FORE_FINGER[2]][i] + points[self.LEFT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]
                            rp1 = [(points[self.RIGHT_FORE_FINGER[1]][i] + points[self.RIGHT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                            rp2 = [(points[self.RIGHT_FORE_FINGER[2]][i] + points[self.RIGHT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]

                            nv = self.normal_vector(
                                [lp1[i] - lp2[i] for i in range(3)],
                                [rp1[i] - rp2[i] for i in range(3)]
                            )

                            # 若仍退化，尝试备选叉积；再不行则跳过本次建面
                            if np.linalg.norm(np.asarray(nv, dtype=float)) < 1e-8:
                                alt = np.cross(
                                    np.asarray([lp1[i] - lp2[i] for i in range(3)], dtype=float),
                                    np.asarray([points[self.LEFT_FORE_FINGER[2]][i] - points[self.LEFT_THUMB_FINGER[2]][i] for i in range(3)], dtype=float)
                                )
                                n = np.linalg.norm(alt)
                                if n < 1e-8:
                                    self.degree_history.clear()
                                    return
                                nv = (alt / n).tolist()

                            p_start = lp2
                            p_end   = self.point_to_plane(rp2, p_start, nv)

                            self.send_command('create_plane', {
                                'start_position': p_start,
                                'end_position':   p_end,
                                'normal_vector':  nv
                            })
                            self.degree_history.clear()

    # ------------------------------
    # 模拟：捏住→移动→松手（循环）
    # ------------------------------
    def start_simulation(self,
                     dt: float = 0.12,           # 帧间隔（越大越慢；0.12 ≈ 8.3 FPS）
                     move_duration: float = 6.0, # 每条线移动总时长（秒）
                     pause_between_lines: float = 3.0,  # 每条线完成后的停顿（秒）
                     pinch_gap: float = 0.01,    # 捏住时拇指/食指间距
                     release_gap: float = 0.12,  # 松手时拇指/食指间距（要 > DIS_OFF）
                     hold_before_start: float = 1.0  # 起笔前保持稳定捏住的时间（秒）
                     ):
        """
        慢速直线演示（循环）：
        - 稳定捏住 hold_before_start 秒 → 触发 start_drawing_line
        - 沿直线移动 move_duration 秒（线性插值，多帧 update_drawing_line）
        - 松手 → 触发 finish_drawing_line
        - 停 pause_between_lines 秒 → 开始下一条线
        直线路径会在一组预设起点/终点中轮换。
        """
        print("Start simulation (slow straight lines, looping)...")

        import threading, time, itertools

        # --- 工具函数 ---
        def pack3(p): return [p, p, p]
        def build(l_thumb, l_index, r_thumb, r_index):
            return pack3(l_thumb) + pack3(l_index) + pack3(r_thumb) + pack3(r_index)

        def lerp(a, b, t):
            return [a[i] + (b[i] - a[i]) * t for i in range(3)]

        # 左手固定姿势（无关动作）
        left_thumb = [0.0, 1.0, 0.0]
        left_index = [1.0, 1.0, 1.0]

        # --- 预设一组“直线”的起点/终点（都是右手拇/食中点的轨迹）---
        # 你可以按需要改动这些坐标；都会被线性插值成“直线”
        lines = [
            ([2.0, 2.0, 2.0], [3.6, 2.0, 2.0]),  # 水平
            ([3.6, 2.0, 2.0], [3.6, 3.2, 2.0]),  # 垂直
            ([3.6, 3.2, 2.0], [2.4, 2.0, 2.8]),  # 斜线1
            ([2.4, 2.0, 2.8], [2.0, 2.8, 3.2]),  # 斜线2
        ]
        line_cycle = itertools.cycle(lines)

        # 帧数计算
        hold_frames = max(1, int(hold_before_start / dt))
        move_frames = max(2, int(move_duration / dt))  # 至少2帧，保证能看到移动

        def loop():
            while True:
                start_center, end_center = next(line_cycle)

                # 1) 起笔前：稳定捏住（中点=起点）
                for _ in range(hold_frames):
                    r_thumb = [start_center[0] - pinch_gap / 2, start_center[1], start_center[2]]
                    r_index = [start_center[0] + pinch_gap / 2, start_center[1], start_center[2]]
                    pts = build(left_thumb, left_index, r_thumb, r_index)
                    self.process_data({"timestamp": time.time(), "points": pts})
                    time.sleep(dt)

                # 2) 移动：沿直线 start → end，线性插值（每帧都会让前端 update）
                for i in range(move_frames):
                    t = i / float(move_frames - 1)
                    c = lerp(start_center, end_center, t)
                    r_thumb = [c[0] - pinch_gap / 2, c[1], c[2]]
                    r_index = [c[0] + pinch_gap / 2, c[1], c[2]]
                    pts = build(left_thumb, left_index, r_thumb, r_index)
                    self.process_data({"timestamp": time.time(), "points": pts})
                    time.sleep(dt)

                # 3) 松手：把拇指/食指拉开到 release_gap（中点保持在终点）
                for _ in range(2):
                    r_thumb = [end_center[0] - release_gap / 2, end_center[1], end_center[2]]
                    r_index = [end_center[0] + release_gap / 2, end_center[1], end_center[2]]
                    pts = build(left_thumb, left_index, r_thumb, r_index)
                    self.process_data({"timestamp": time.time(), "points": pts})
                    time.sleep(dt)

                # 4) 停顿一段时间，再开始下一条线
                time.sleep(pause_between_lines)

        threading.Thread(target=loop, daemon=True).start()

    def start_plane_simulation(self,
                           dt: float = 0.10,          # 每帧间隔
                           hold_duration: float = 0.8, # 保持稳定的时长(>TIME_THRESHOLD)
                           pause_after: float = 1.0    # 触发后停顿
                           ):
        """
        触发 receive.py 的“稳定建面”分支：
        - 同时给出左/右手 12 点（拇指/食指的 tip, joint1, joint2）
        - 左右手拇/食骨向量近似正交(≈90°) -> 夹角 > DEGREE_THRESHOLD
        - 右手拇指尖-食指尖距离在窗口内稳定 >= TIME_THRESHOLD
        - 非退化几何，确保能算出法向量
        触发后会向前端发送 create_plane：
        { start_position, end_position, normal_vector }
        """
        import time, threading

        # --- 构造一帧 12 点（顺序必须是：左拇[0,1,2] 左食[3,4,5] 右拇[6,7,8] 右食[9,10,11]） ---
        # 统一放在 z = 2.0 平面附近
        z = 2.0

        # 左手（拇指骨向量≈+X，食指骨向量≈+Y，二者近似正交）
        LT_tip  = [2.35, 2.00, z]  # 左拇指 tip (0)
        LT_j1   = [2.30, 2.00, z]  # 左拇指 joint1 (1)
        LT_j2   = [2.00, 2.00, z]  # 左拇指 joint2 (2)

        LF_tip  = [2.00, 2.35, z]  # 左食指 tip (3)
        LF_j1   = [2.00, 2.30, z]  # 左食指 joint1 (4)
        LF_j2   = [2.00, 2.20, z]  # 左食指 joint2 (5)
        # 注意：让 LF_j2 与 LT_j2 不同，避免后续法向量退化

        # 右手（拇指骨向量≈-X，食指骨向量≈-Y，同样近似正交）
        RT_tip  = [3.15, 3.00, z]  # 右拇指 tip (6)
        RT_j1   = [3.20, 3.00, z]  # 右拇指 joint1 (7)
        RT_j2   = [3.50, 3.00, z]  # 右拇指 joint2 (8)

        RI_tip  = [3.50, 2.45, z]  # 右食指 tip (9)
        RI_j1   = [3.50, 2.50, z]  # 右食指 joint1 (10)
        RI_j2   = [3.50, 2.80, z]  # 右食指 joint2 (11)

        # 右手 tip 间距将用来做“稳定窗口”的度量（degree_history）
        # 这里保持恒定，满足 TIME_THRESHOLD 与 POSITION_THRESHOLD 的稳定条件

        # 组装成一帧 points
        def build_points():
            return [
                LT_tip, LT_j1, LT_j2,   # 0,1,2 左拇
                LF_tip, LF_j1, LF_j2,   # 3,4,5 左食
                RT_tip, RT_j1, RT_j2,   # 6,7,8 右拇
                RI_tip, RI_j1, RI_j2,   # 9,10,11 右食
            ]

        hold_frames = max(2, int(hold_duration / dt))

        def loop():
            # 1) 保持稳定若干帧，满足 TIME_THRESHOLD + 稳定性判定
            for _ in range(hold_frames):
                self.process_data({"timestamp": time.time(), "points": build_points()})
                time.sleep(dt)

            # 2) 稍作停顿（便于肉眼辨识一次触发）
            time.sleep(pause_after)

            print("✅ Plane simulation: create_plane should have been emitted once.")

        threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    backend = GestureBackend()

    if backend.connect():
        print("select mode:")
        print("1. real")
        print("2. simulation")
        print("3. plane simulation")
        choice = input(" (1/2/3): ")

        if choice == "1":
            context = zmq.Context()
            socket  = context.socket(zmq.PULL)
            socket.connect("tcp://127.0.0.1:5555")
            try:
                while True:
                    data = socket.recv_pyobj()
                    backend.process_data(data)
            except KeyboardInterrupt:
                print("Stopped receiving data")

        elif choice == "2":
            backend.start_simulation()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Stopped simulation")

        elif choice == "3":
            backend.start_plane_simulation()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Stopped rectangle simulation")
