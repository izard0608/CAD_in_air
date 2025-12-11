# app.service.GestureBackend.py  手势识别后端逻辑
"""
手势识别后端逻辑模块（GestureBackend）

职责：
- 接收来自融合模块的关键点数据帧（points）
- 根据左右手手指距离/角度检测手势：建点、画线、建面
- 将识别到的动作以命令事件通过 WebSocket 发送到服务端

注意：
- 依赖外部模块：WebSocketClient.create_client, MathUtils (mu), Config
- 本文件为实时处理，避免在短时间内频繁发送命令（command_cooldown）
"""
from typing import Any, Dict, List, Optional
import time
import numpy as np
from collections import deque

from sockets.WebSocketClient import create_client
import utils.MathUtils as mu
import Config


class GestureBackend:
    """
    GestureBackend 提供手势检测与命令发送能力。

    主要方法：
    - connect(): 连接到 WebSocket 服务
    - process_data(data): 处理单帧融合数据并在识别到动作时发送命令
    """
    def __init__(self, server_url: Optional[str] = None) -> None:
        # 调试与日志控制
        self.DEBUG: bool = True
        self.LOG_EVERY_N: int = Config.LOG_EVERY_N
        self.HISTORY_N: int = Config.HISTORY_N
        self._history: deque = deque(maxlen=self.HISTORY_N)

        # WebSocket 客户端
        self.sio = create_client(server_url or Config.SERVER_URL)
        self.server_url: str = server_url or Config.SERVER_URL

        # 手指索引与阈值（从 Config 获取）
        self.LEFT_THUMB_FINGER: List[int]  = Config.LEFT_THUMB_FINGER
        self.LEFT_FORE_FINGER: List[int]   = Config.LEFT_FORE_FINGER
        self.RIGHT_THUMB_FINGER: List[int] = Config.RIGHT_THUMB_FINGER
        self.RIGHT_FORE_FINGER: List[int]  = Config.RIGHT_FORE_FINGER

        self.TIME_THRESHOLD: float     = Config.TIME_THRESHOLD
        self.MAXLEN: int               = Config.MAXLEN
        self.POSITION_THRESHOLD: float = Config.POSITION_THRESHOLD
        self.DIS_ON: float             = Config.DIS_ON
        self.DIS_OFF: float            = Config.DIS_OFF
        self.MOVE_EPS: float           = Config.MOVE_EPS
        self.DEGREE_THRESHOLD: float   = Config.DEGREE_THRESHOLD
        self.DIS_THRESHOLD: float      = Config.DIS_THRESHOLD

        # 内部状态
        self.edge_flag: int = 0
        self.left_history: deque = deque(maxlen=self.MAXLEN)
        self.right_history: deque = deque(maxlen=self.MAXLEN)
        self.degree_history: deque = deque(maxlen=self.MAXLEN)

        self._frame: int = 0
        self._last_center: Optional[List[float]] = None
        self.last_command_time: float = 0.0
        self.command_cooldown: float = Config.COMMAND_COOLDOWN

    def connect(self) -> bool:
        """尝试连接到 WebSocket 服务，返回是否成功。"""
        try:
            self.sio.connect(self.server_url)
            print("✅ WebSocket连接成功")
            return True
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")
            return False

    def _json_safe(self, obj: Any) -> Any:
        """
        将 numpy 类型或嵌套列表转换为 JSON 可序列化的 Python 原生类型。
        用于构造要通过 socket 发送的 payload。
        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (list, tuple)):
            return [self._json_safe(x) for x in obj]
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return obj

    def send_command(self, command_type: str, parameters: Dict[str, Any]) -> None:
        """
        发送命令到后端服务（通过 socket emit）。
        使用 cooldown 限制短时间内重复发送。
        """
        current_time = time.time()
        if current_time - self.last_command_time < self.command_cooldown:
            # 在 cooldown 期内忽略重复命令
            return
        self.last_command_time = current_time

        params = dict(parameters)
        # 为点创建命令填充默认显示属性
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

    def process_data(self, data: Dict[str, Any]) -> None:
        """
        处理单帧数据（data），data 格式期望包含：
        - timestamp: float（可选）
        - points: List[List[float]] 12 个三维点（x,y,z）

        识别逻辑包含：
        - 左手拇指与食指靠近并稳定 -> start_drawing_point
        - 右手拇指与食指动作 -> start/update/finish drawing line
        - 双手食指与拇指形成一定角度并稳定 -> create_plane
        """
        self._frame += 1
        timestamp = data.get("timestamp", time.time())
        points: List[List[float]] = data.get("points") or []

        # 未达到点数要求则跳过
        if len(points) < 12:
            if self.DEBUG and self._frame % self.LOG_EVERY_N == 0:
                print(f"⚠️ 数据点不足: {len(points)}/12")
            return

        if self._frame % self.LOG_EVERY_N == 0:
            valid_points = sum(1 for p in points if mu.is_valid_point(p))
            print(f"🎯 处理数据帧 #{self._frame}, 有效点: {valid_points}/12")

        # ---------------- 左手建点 ----------------
        lt_tip = points[self.LEFT_THUMB_FINGER[0]]
        li_tip = points[self.LEFT_FORE_FINGER[0]]

        if mu.is_valid_point(lt_tip) and mu.is_valid_point(li_tip):
            d = mu.distance(lt_tip, li_tip)
            self.left_history.append((timestamp, d, lt_tip, li_tip))

            # 若历史稳定并且距离小于阈值则视为建点动作
            if len(self.left_history) >= 5:
                times = [x[0] for x in self.left_history]
                if times[-1] - times[0] >= self.TIME_THRESHOLD:
                    dvals = [x[1] for x in self.left_history]
                    if max(dvals) - min(dvals) < self.POSITION_THRESHOLD and d < self.DIS_THRESHOLD:
                        new_node = mu.mid(lt_tip, li_tip)
                        self.send_command('start_drawing_point', {'position': new_node})
                        self.left_history.clear()

        # ---------------- 右手画线 ----------------
        rt_tip = points[self.RIGHT_THUMB_FINGER[0]]
        ri_tip = points[self.RIGHT_FORE_FINGER[0]]

        if mu.is_valid_point(rt_tip) and mu.is_valid_point(ri_tip):
            d = mu.distance(rt_tip, ri_tip)
            center = mu.mid(rt_tip, ri_tip)

            self.right_history.append((timestamp, d, center))

            if self.edge_flag == 0:
                # 检测到稳定靠近并进入绘线状态
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
                # 绘线中，根据距离决定结束或更新位置
                if d > self.DIS_OFF:
                    end_node = center
                    self.send_command('finish_drawing_line', {'position': end_node})
                    self.edge_flag = 0
                    self._last_center = None
                    self.right_history.clear()
                else:
                    # 仅当中心移动超过 MOVE_EPS 时发送更新以减少冗余流量
                    if self._last_center is None or mu.distance(center, self._last_center) > self.MOVE_EPS:
                        self.send_command('update_drawing_line', {'position': center})
                        self._last_center = center

        # ---------------- 双手角度建面 ----------------
        if (mu.is_valid_point(points[self.LEFT_FORE_FINGER[1]]) and
            mu.is_valid_point(points[self.LEFT_FORE_FINGER[2]]) and
            mu.is_valid_point(points[self.RIGHT_FORE_FINGER[1]]) and
            mu.is_valid_point(points[self.RIGHT_FORE_FINGER[2]])):

            # 计算两手食指向量与拇指向量之间的夹角
            l_vec = [points[self.LEFT_FORE_FINGER[1]][i] - points[self.LEFT_FORE_FINGER[2]][i] for i in range(3)]
            l_thv = [points[self.LEFT_THUMB_FINGER[1]][i] - points[self.LEFT_THUMB_FINGER[2]][i] for i in range(3)]
            r_vec = [points[self.RIGHT_FORE_FINGER[1]][i] - points[self.RIGHT_FORE_FINGER[2]][i] for i in range(3)]
            r_thv = [points[self.RIGHT_THUMB_FINGER[1]][i] - points[self.RIGHT_THUMB_FINGER[2]][i] for i in range(3)]

            d_left = mu.vector_angle(l_vec, l_thv)
            d_right = mu.vector_angle(r_vec, r_thv)

            # 当两侧角度都大于阈值时，进入角度建面检测
            if d_left > self.DEGREE_THRESHOLD and d_right > self.DEGREE_THRESHOLD:
                self.degree_history.append((timestamp, d_left, d_right))

                if len(self.degree_history) >= 5:
                    times = [x[0] for x in self.degree_history]
                    if times[-1] - times[0] >= self.TIME_THRESHOLD:
                        # 使用食指与拇指的中点作为面上的参考点
                        lp1 = [(points[self.LEFT_FORE_FINGER[1]][i] + points[self.LEFT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                        lp2 = [(points[self.LEFT_FORE_FINGER[2]][i] + points[self.LEFT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]
                        rp1 = [(points[self.RIGHT_FORE_FINGER[1]][i] + points[self.RIGHT_THUMB_FINGER[1]][i]) / 2.0 for i in range(3)]
                        rp2 = [(points[self.RIGHT_FORE_FINGER[2]][i] + points[self.RIGHT_THUMB_FINGER[2]][i]) / 2.0 for i in range(3)]

                        nv = mu.normal_vector(
                            [lp1[i] - lp2[i] for i in range(3)],
                            [rp1[i] - rp2[i] for i in range(3)]
                        )

                        # 若法向量有效，则构建面命令并发送
                        if np.linalg.norm(np.asarray(nv, dtype=float)) > 1e-8:
                            p_start = lp2
                            p_end = mu.point_to_plane(rp2, p_start, nv)

                            self.send_command('create_plane', {
                                'start_position': p_start,
                                'end_position': p_end,
                                'normal_vector': nv
                            })
                            self.degree_history.clear()