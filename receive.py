import zmq
import time
import math
import numpy as np
from collections import deque
import socketio
import threading

class GestureBackend:
    def __init__(self, server_url='http://localhost:5000'):
        # WebSocket连接
        self.sio = socketio.Client()
        self.server_url = server_url
        
        # 解决传进来的点为空的情况
        # 左手捏住->点 右手捏住->线
        # 传入数据格式：data = {"timestamp": time, "points": points}

        # 左手大拇指（从指尖编号）： 0，1，2
        # 左手食指（从指尖编号）：3，4，5
        # 右手大拇指（从指尖编号）：6，7，8
        # 右手食指（从指尖编号）：9，10，11
        self.LEFT_THUMB_FINGER=[0,1,2]
        self.LEFT_FORE_FINGER=[3,4,5]
        self.RIGHT_THUMB_FINGER=[6,7,8]
        self.RIGHT_FORE_FINGER=[9,10,11]

        # 位置变化阈值（滤波？）
        self.POSITION_THRESHOLD=0.1
        # 时间阈值
        self.TIME_THRESHOLD=2.0
        # 队列长度=帧数x时间阈值
        self.MAXLEN=50

        # 捏住食指拇指距离阈值
        self.DIS_THRESHOLD=2.0
        # 新建面时食指拇指角度阈值
        self.DEGREE_THRESHOLD=70.0

        self.edge_flag=0
        self.left_history=deque(maxlen=self.MAXLEN)
        self.right_history=deque(maxlen=self.MAXLEN)
        self.degree_history=deque(maxlen=self.MAXLEN)
        
        self.setup_websocket()

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

    def send_command(self, command_type, parameters):
        data = {
            'command': command_type,
            'parameters': parameters,
            'timestamp': time.time()
        }
        self.sio.emit('gesture_command', data)

    # 欧式距离
    def distance(self, p1,p2):
        return math.sqrt(sum((a-b)**2 for a,b in zip(p1,p2)))

    # 三维向量求角度
    def vector_angle(self, p1,p2):
        dot=sum(x*y for x,y in zip(p1,p2))
        norm_p1=math.sqrt(sum(x**2 for x in p1))
        norm_p2=math.sqrt(sum(x**2 for x in p2))
        if norm_p1==0 or norm_p2==0:
            return 0.0
        cos_theta=dot/(norm_p1*norm_p2)
        cos_theta=max(-1.0,min(1.0,cos_theta))
        return math.degrees(math.acos(cos_theta))

    # 求直线的单位向量
    def unit(self, v):
        n=np.linalg.norm(v)
        return v/n

    # 求平面法向量
    def normal_vector(self, a,b):
        a=np.asarray(a,dtype=float)
        b=np.asarray(b,dtype=float)
        ua=self.unit(a)
        ub=self.unit(b)
        nP=np.cross(a,b)
        if np.linalg.norm(nP)==0:
            return [0.0,0.0,0.0]
        v=ua-ub
        nQ=np.cross(nP,v)
        return nQ/np.linalg.norm(nQ)

    # 求点到面上投影
    def point_to_plane(self, x,p0,n):
        n=np.asarray(n,dtype=float)
        x=np.asarray(x,dtype=float)
        p0=np.asarray(p0,dtype=float)
        n_norm2=np.dot(n,n)
        t=np.dot(x-p0,n)/n_norm2
        return x-t*n

    def process_data(self, data):
        timestamp=data["timestamp"]
        points=data["points"]
        p1=points[self.LEFT_THUMB_FINGER[0]]
        p2=points[self.LEFT_FORE_FINGER[0]]
        if p1!=p2:
            d=self.distance(p1,p2)
            if len(self.left_history)==self.MAXLEN:
                self.left_history.popleft()
            self.left_history.append((timestamp,d))
            if len(self.left_history)>2:
                t_start=self.left_history[0][0]
                t_end=self.left_history[-1][0]
                if t_end-t_start>=self.TIME_THRESHOLD:
                    dis=[x[1] for x in self.left_history]
                    d_max=max(dis)
                    d_min=min(dis)
                    if d_max-d_min<self.POSITION_THRESHOLD and d_max<=self.DIS_THRESHOLD:
                        # 在 new_node 建一个新点
                        new_node=[((p1[i]+p2[i])/2) for i in range(3)]
                        self.send_command('create_point', {'position': new_node})
                        self.left_history.clear()
        p1=points[self.RIGHT_THUMB_FINGER[0]]
        p2=points[self.RIGHT_FORE_FINGER[0]]
        # 持续 TIME_THRESHOLD 秒食指拇指指尖距离小于 DIS_THRESHOLD 且不移动
        if p1!=p2:
            d=self.distance(p1,p2)
            if len(self.right_history)==self.MAXLEN:
                self.right_history.popleft()
            self.right_history.append((timestamp,d))
            if len(self.right_history)>2:
                t_start=self.right_history[0][0]
                t_end=self.right_history[-1][0]
                if t_end-t_start>=self.TIME_THRESHOLD:
                    dis=[x[1] for x in self.right_history]
                    d_max=max(dis)
                    d_min=min(dis)
                    if d_max-d_min<self.POSITION_THRESHOLD and d_max<=self.DIS_THRESHOLD:
                        if self.edge_flag==0:
                            # 以 start_node 为起点建一条新线段
                            start_node=[((p1[i]+p2[i])/2) for i in range(3)]
                            self.send_command('start_line', {'position': start_node})
                            self.edge_flag=1
                        else:
                            # 以 end_node 为终点结束建立新线段
                            end_node=[((p1[i]+p2[i])/2) for i in range(3)]
                            self.send_command('end_line', {'position': end_node})
                            self.edge_flag=0
                        self.right_history.clear()
            # 是否并且能否实时表示线段当前终点在哪？
            # if edge_flag==1:
            #     now_node=[((p1[i]+p2[i])/2) for i in range(3)]
            #     print(f"the new edge now end at x={now_node[0]},y={now_node[1]},z={now_node[2]}")
        # 持续 TIME_THRESHOLD 秒两手食指拇指角度都大于 DEGREE_THRESHOLD 且不移动
        if points[self.LEFT_FORE_FINGER[0]]!=points[self.LEFT_THUMB_FINGER[0]] and points[self.RIGHT_FORE_FINGER[0]]!=points[self.RIGHT_THUMB_FINGER[0]]:
            d_left=self.vector_angle([(points[self.LEFT_FORE_FINGER[1]][i]-points[self.LEFT_FORE_FINGER[2]][i])for i in range(3)],[(points[self.LEFT_THUMB_FINGER[1]][i]-points[self.LEFT_THUMB_FINGER[2]][i])for i in range(3)])
            d_right=self.vector_angle([(points[self.RIGHT_FORE_FINGER[1]][i]-points[self.RIGHT_FORE_FINGER[2]][i])for i in range(3)],[(points[self.RIGHT_THUMB_FINGER[1]][i]-points[self.RIGHT_THUMB_FINGER[2]][i])for i in range(3)])
            if d_left<self.DEGREE_THRESHOLD or d_right<self.DEGREE_THRESHOLD:
                self.degree_history.clear()
            else:
                d=self.distance(p1,p2)
                if len(self.degree_history)==self.MAXLEN:
                    self.degree_history.popleft()
                self.degree_history.append((timestamp,d))
                if len(self.degree_history)>2:
                    t_start=self.degree_history[0][0]
                    t_end=self.degree_history[-1][0]
                    if t_end-t_start>=self.TIME_THRESHOLD:
                        dis=[x[1] for x in self.degree_history]
                        d_max=max(dis)
                        d_min=min(dis)
                        if d_max-d_min<self.POSITION_THRESHOLD:
                            # 新建面
                            lp1=[(points[self.LEFT_FORE_FINGER[1]][i]+points[self.LEFT_THUMB_FINGER[1]][i])/2 for i in range(3)]
                            lp2=[(points[self.LEFT_FORE_FINGER[2]][i]+points[self.LEFT_THUMB_FINGER[2]][i])/2 for i in range(3)]
                            rp1=[(points[self.RIGHT_FORE_FINGER[1]][i]+points[self.RIGHT_THUMB_FINGER[1]][i])/2 for i in range(3)]
                            rp2=[(points[self.RIGHT_FORE_FINGER[2]][i]+points[self.RIGHT_THUMB_FINGER[2]][i])/2 for i in range(3)]
                            nv=self.normal_vector([(lp1[i]-lp2[i]) for i in range(3)],[(rp1[i]-rp2[i]) for i in range(3)])
                            if nv==[0.0,0.0,0.0]:
                                nv=np.cross([(lp1[i]-lp2[i]) for i in range(3)],[(points[self.LEFT_FORE_FINGER[2]][i]-points[self.LEFT_THUMB_FINGER[2]][i])for i in range(3)])
                                nv=nv/np.linalg.norm(nv)
                            p_start=lp2
                            p_end=self.point_to_plane(rp2,p_start,nv)
                            # 以 p_start 和 p_end 为对角线，nv 为法向量建立平面
                            self.send_command('create_plane', {
                                'start_position': p_start,
                                'end_position': p_end,
                                'normal_vector': nv.tolist() if hasattr(nv, 'tolist') else nv
                            })
                            self.degree_history.clear()

    def start_simulation(self): # 画点模拟，供前端调试用
        print("Start simulation...")
        
        def simulation_loop():
            step = 0
            while True:
                if step % 20 == 0:
                    simulated_points = [
                        [0.5, 1.0, 0.5], [0.5, 1.0, 0.5], [0.5, 1.0, 0.5],  # 左手大拇指 - 捏合
                        [0.5, 1.0, 0.5], [0.5, 1.0, 0.5], [0.5, 1.0, 0.5],  # 左手食指 - 捏合
                        [2.0, 2.0, 2.0], [2.0, 2.0, 2.0], [2.0, 2.0, 2.0],  # 右手大拇指 - 远离
                        [3.0, 3.0, 3.0], [3.0, 3.0, 3.0], [3.0, 3.0, 3.0]   # 右手食指 - 远离
                    ]
                else:
                    simulated_points = [
                        [0.0, 1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 0.0],  
                        [1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0],  
                        [2.0, 2.0, 2.0], [2.0, 2.0, 2.0], [2.0, 2.0, 2.0], 
                        [3.0, 3.0, 3.0], [3.0, 3.0, 3.0], [3.0, 3.0, 3.0]   
                    ]
                
                simulated_data = {
                    "timestamp": time.time(),
                    "points": simulated_points
                }
                
                self.process_data(simulated_data)
                
                step += 1
                time.sleep(0.1)
        
        thread = threading.Thread(target=simulation_loop)
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    backend = GestureBackend()
    
    if backend.connect():
        print("select mode:")
        print("1. real")
        print("2. simulation")
        
        choice = input(" (1/2): ")
        
        if choice == "1":
            context=zmq.Context()
            socket=context.socket(zmq.PULL)
            socket.connect("tcp://127.0.0.1:5555")
        elif choice == "2":
            backend.start_simulation()
