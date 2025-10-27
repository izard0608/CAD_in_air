# 解决传进来的点为空的情况
# 左手捏住->点 右手捏住->线
# 传入数据格式：data = {"timestamp": time, "points": points}

import zmq
import time
import math
import numpy as np
from collections import deque

# 左手大拇指（从指尖编号）： 0，1，2
# 左手食指（从指尖编号）：3，4，5
# 右手大拇指（从指尖编号）：6，7，8
# 右手食指（从指尖编号）：9，10，11
LEFT_THUMB_FINGER=[0,1,2]
LEFT_FORE_FINGER=[3,4,5]
RIGHT_THUMB_FINGER=[6,7,8]
RIGHT_FORE_FINGER=[9,10,11]

# 位置变化阈值（滤波？）
POSITION_THRESHOLD=0.1
# 时间阈值
TIME_THRESHOLD=2.0
# 队列长度=帧数x时间阈值
MAXLEN=50

# 捏住食指拇指距离阈值
DIS_THRESHOLD=2.0
# 新建面时食指拇指角度阈值
DEGREE_THRESHOLD=70.0

# 欧式距离
def distance(p1,p2):
    return math.sqrt(sum((a-b)**2 for a,b in zip(p1,p2)))

# 三维向量求角度
def vector_angle(p1,p2):
    dot=sum(x*y for x,y in zip(p1,p2))
    norm_p1=math.sqrt(sum(x**2 for x in p1))
    norm_p2=math.sqrt(sum(x**2 for x in p2))
    if norm_p1==0 or norm_p2==0:
        return 0.0
    cos_theta=dot/(norm_p1*norm_p2)
    cos_theta=max(-1.0,min(1.0,cos_theta))
    return math.degrees(math.acos(cos_theta))

# 求直线的单位向量
def unit(v):
    n=np.linalg.norm(v)
    return v/n

# 求平面法向量
def normal_vector(a,b):
    a=np.asarray(a,dtype=float)
    b=np.asarray(b,dtype=float)
    ua=unit(a)
    ub=unit(b)
    nP=np.cross(a,b)
    if np.linalg.norm(nP)==0:
        return [0.0,0.0,0.0]
    v=ua-ub
    nQ=np.cross(nP,v)
    return nQ/np.linalg.norm(nQ)

# 求点到面上投影
def point_to_plane(x,p0,n):
    n=np.asarray(n,dtype=float)
    x=np.asarray(x,dtype=float)
    p0=np.asarray(p0,dtype=float)
    n_norm2=np.dot(n,n)
    t=np.dot(x-p0,n)/n_norm2
    return x-t*n

context=zmq.Context()
socket=context.socket(zmq.PULL)

socket.connect("tcp://127.0.0.1:5555")

print(f"Begin to receive data...")

edge_flag=0
left_history=deque(maxlen=MAXLEN)
right_history=deque(maxlen=MAXLEN)
degree_history=deque(maxlen=MAXLEN)

while True:
    data=socket.recv_pyobj()
    timestamp=data["timestamp"]
    points=data["points"]
    p1=points[LEFT_THUMB_FINGER[0]]
    p2=points[LEFT_FORE_FINGER[0]]
    if p1!=p2:
        d=distance(p1,p2)
        if len(left_history)==MAXLEN:
            left_history.popleft()
        left_history.append((timestamp,d))
        if len(left_history)>2:
            t_start=left_history[0][0]
            t_end=left_history[-1][0]
            if t_end-t_start>=TIME_THRESHOLD:
                dis=[x[1] for x in left_history]
                d_max=max(dis)
                d_min=min(dis)
                if d_max-d_min<POSITION_THRESHOLD and d_max<=DIS_THRESHOLD:
                    # 在 new_node 建一个新点
                    new_node=[((p1[i]+p2[i])/2) for i in range(3)]
                    print(f"create a new node at x={new_node[0]},y={new_node[1]},z={new_node[2]}")
                    left_history.clear()
    p1=points[RIGHT_THUMB_FINGER[0]]
    p2=points[RIGHT_FORE_FINGER[0]]
    # 持续 TIME_THRESHOLD 秒食指拇指指尖距离小于 DIS_THRESHOLD 且不移动
    if p1!=p2:
        d=distance(p1,p2)
        if len(right_history)==MAXLEN:
            right_history.popleft()
        right_history.append((timestamp,d))
        if len(right_history)>2:
            t_start=right_history[0][0]
            t_end=right_history[-1][0]
            if t_end-t_start>=TIME_THRESHOLD:
                dis=[x[1] for x in right_history]
                d_max=max(dis)
                d_min=min(dis)
                if d_max-d_min<POSITION_THRESHOLD and d_max<=DIS_THRESHOLD:
                    if edge_flag==0:
                        # 以 start_node 为起点建一条新线段
                        start_node=[((p1[i]+p2[i])/2) for i in range(3)]
                        print(f"create a new edge from x={start_node[0]},y={start_node[1]},z={start_node[2]}")
                        edge_flag=1
                    else:
                        # 以 end_node 为终点结束建立新线段
                        end_node=[((p1[i]+p2[i])/2) for i in range(3)]
                        print(f"end a new edge at x={end_node[0]},y={end_node[1]},z={end_node[2]}")
                        edge_flag=0
                    right_history.clear()
        # 是否并且能否实时表示线段当前终点在哪？
        # if edge_flag==1:
        #     now_node=[((p1[i]+p2[i])/2) for i in range(3)]
        #     print(f"the new edge now end at x={now_node[0]},y={now_node[1]},z={now_node[2]}")
    # 持续 TIME_THRESHOLD 秒两手食指拇指角度都大于 DEGREE_THRESHOLD 且不移动
    if points[LEFT_FORE_FINGER[0]]!=points[LEFT_THUMB_FINGER[0]] and points[RIGHT_FORE_FINGER[0]]!=points[RIGHT_THUMB_FINGER[0]]:
        d_left=vector_angle([(points[LEFT_FORE_FINGER[1]][i]-points[LEFT_FORE_FINGER[2]][i])for i in range(3)],[(points[LEFT_THUMB_FINGER[1]][i]-points[LEFT_THUMB_FINGER[2]][i])for i in range(3)])
        d_right=vector_angle([(points[RIGHT_FORE_FINGER[1]][i]-points[RIGHT_FORE_FINGER[2]][i])for i in range(3)],[(points[RIGHT_THUMB_FINGER[1]][i]-points[RIGHT_THUMB_FINGER[2]][i])for i in range(3)])
        if d_left<DEGREE_THRESHOLD or d_right<DEGREE_THRESHOLD:
            degree_history.clear()
        else:
            d=distance(p1,p2)
            if len(degree_history)==MAXLEN:
                degree_history.popleft()
            degree_history.append((timestamp,d))
            if len(degree_history)>2:
                t_start=degree_history[0][0]
                t_end=degree_history[-1][0]
                if t_end-t_start>=TIME_THRESHOLD:
                    dis=[x[1] for x in degree_history]
                    d_max=max(dis)
                    d_min=min(dis)
                    if d_max-d_min<POSITION_THRESHOLD:
                        # 新建面
                        lp1=[(points[LEFT_FORE_FINGER[1]][i]+points[LEFT_THUMB_FINGER[1]][i])/2 for i in range(3)]
                        lp2=[(points[LEFT_FORE_FINGER[2]][i]+points[LEFT_THUMB_FINGER[2]][i])/2 for i in range(3)]
                        rp1=[(points[RIGHT_FORE_FINGER[1]][i]+points[RIGHT_THUMB_FINGER[1]][i])/2 for i in range(3)]
                        rp2=[(points[RIGHT_FORE_FINGER[2]][i]+points[RIGHT_THUMB_FINGER[2]][i])/2 for i in range(3)]
                        nv=normal_vector([(lp1[i]-lp2[i]) for i in range(3)],[(rp1[i]-rp2[i]) for i in range(3)])
                        if nv==[0.0,0.0,0.0]:
                            nv=np.cross([(lp1[i]-lp2[i]) for i in range(3)],[(points[LEFT_FORE_FINGER[2]][i]-points[LEFT_THUMB_FINGER[2]][i])for i in range(3)])
                            nv=nv/np.linalg.norm(nv)
                        p_start=lp2
                        p_end=point_to_plane(rp2,p_start,nv)
                        # 以 p_start 和 p_end 为对角线，nv 为法向量建立平面
                        print(f"create a new plane from x={p_start[0]},y={p_start[1]},z={p_start[2]},to x={p_end[0]},y={p_end[1]},={p_end[2]},with normal vector x={nv[0]},y={nv[1]},z={nv[2]}")
                        degree_history.clear()
