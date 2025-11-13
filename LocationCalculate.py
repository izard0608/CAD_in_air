import zmq
import time
import numpy as np
import cv2

context = zmq.Context()

camera_socket = context.socket(zmq.PULL)
camera_socket.bind("tcp://127.0.0.1:5556")

serial_socket = context.socket(zmq.PULL)
serial_socket.bind("tcp://127.0.0.1:5555")

sender_socket = context.socket(zmq.PUSH)
sender_socket.bind("tcp://127.0.0.1:5557")

# 示例参数（替换成你的实际量）
W, H = 8, 8
FoV_x = np.deg2rad(40.0)   # 可调整或按 datasheet 确定
FoV_y = np.deg2rad(25.0)
K = np.array([[504.75482615870874, 0, 312.03400445227277],
              [0, 508.21911022517912, 250.01176949694818],
              [0,  0,  1]])  # 填入你的相机内参
R = np.array([
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1]
])   # 填入外参（ToF -> Camera）
t = np.zeros(3) # 填入外参平移（meters）

def zone_angles(W, H, FoV_x, FoV_y):
    cs = np.arange(W)
    rs = np.arange(H)
    c_grid, r_grid = np.meshgrid(cs, rs)
    theta_x = ((c_grid - (W-1)/2) / ((W-1)/2)) * (FoV_x/2.0)
    theta_y = ((r_grid - (H-1)/2) / ((H-1)/2)) * (FoV_y/2.0)
    return theta_x, theta_y

def depthgrid_to_camera_points(depth_grid, K, R, t, FoV_x, FoV_y):
    # depth_grid: HxW in meters (NaN or 0 if invalid)
    theta_x, theta_y = zone_angles(W, H, FoV_x, FoV_y)
    tx = np.tan(theta_x)
    ty = np.tan(theta_y)
    denom = np.sqrt(tx**2 + ty**2 + 1.0)
    dirs = np.stack([tx/denom, ty/denom, 1.0/denom], axis=-1)  # HxWx3
    points_ir = (depth_grid[...,None] * dirs)  # HxWx3 in ToF frame
    # reshape to N x 3
    pts_ir_flat = points_ir.reshape(-1,3)
    # filter invalid depths
    valid = np.isfinite(pts_ir_flat[:,2]) & (pts_ir_flat[:,2] > 0.01)
    pts_ir_valid = pts_ir_flat[valid]
    # transform to camera frame
    pts_cam = (R.dot(pts_ir_valid.T) + t.reshape(3,1)).T  # N x 3
    return pts_cam, valid

def project_points(pts_cam, K):
    X = pts_cam[:,0]; Y = pts_cam[:,1]; Z = pts_cam[:,2]
    u = (K[0,0]*X / Z) + K[0,2]
    v = (K[1,1]*Y / Z) + K[1,2]
    return np.stack([u,v], axis=1)

# ========= 新增：一个小的融合函数（不动你的底层数学） =========

def fuse_points_with_depth(camera_points, frame_size, pts_cam):
    """
    camera_points: 来自 camera 的 12 个 [x_norm, y_norm] (0~1)
    frame_size: [w, h]，像素
    pts_cam: N x 3 的 ToF 点（相机坐标系，单位 m）

    思路：
    1. 用 project_points 把 ToF 点投影到图像平面 (u,v)
    2. 对每个摄像头点 (x_norm, y_norm) -> (u0, v0) 像素
    3. 在全部 ToF 投影点里找最近的点，拿它的 Z 当作这个关键点的 z
    4. 返回 12 个 [x_norm, y_norm, z]
    """
    w, h = frame_size
    fused = []

    if pts_cam is None or len(pts_cam) == 0:
        # 没有任何 ToF 点，直接补 z=0
        for p in camera_points:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                fused.append([0.0, 0.0, 0.0])
            else:
                fused.append([float(p[0]), float(p[1]), 0.0])
        return fused

    # 2D 投影
    pts_img = project_points(pts_cam, K)  # N x 2
    u_all = pts_img[:, 0]
    v_all = pts_img[:, 1]
    Z_all = pts_cam[:, 2]

    for p in camera_points:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            fused.append([0.0, 0.0, 0.0])
            continue

        x_norm, y_norm = float(p[0]), float(p[1])

        # camera 里 [0,0] 表示无效点
        if x_norm == 0.0 and y_norm == 0.0:
            fused.append([0.0, 0.0, 0.0])
            continue

        # 归一化坐标 -> 像素坐标
        u0 = x_norm * w
        v0 = y_norm * h

        # 找最近的投影点
        du = u_all - u0
        dv = v_all - v0
        dist2 = du*du + dv*dv
        idx = int(np.argmin(dist2))

        z = float(Z_all[idx])  # 已经是米

        fused.append([x_norm, y_norm, z])

    return fused

# ========= 先收一帧 ToF，保持你原来的“底层流程”不变 =========

serial_msg = serial_socket.recv_json()

depth_mm = np.array(serial_msg["depth_mm"], dtype=float)   
depth_m  = depth_mm / 1000.0                               

pts_cam, valid_mask = depthgrid_to_camera_points(
    depth_m,
    K, R, t,
    FoV_x, FoV_y
)

# feat : poller

poller = zmq.Poller()
poller.register(camera_socket, zmq.POLLIN)
poller.register(serial_socket, zmq.POLLIN)

camera_data = None
serial_data = None

while True:
    socks = dict(poller.poll())

    # 收摄像头 JSON（points 已经是 12 个点）
    if camera_socket in socks:
        camera_data = camera_socket.recv_json()

    # 收串口 JSON，更新 depth -> pts_cam
    if serial_socket in socks:
        # ✅ 原来是 recv_string() + TODO，这里改成 recv_json()，走你上面的逻辑
        serial_msg = serial_socket.recv_json()
        serial_data = serial_msg

        depth_mm = np.array(serial_msg["depth_mm"], dtype=float)
        depth_m  = depth_mm / 1000.0

        pts_cam, valid_mask = depthgrid_to_camera_points(
            depth_m,
            K, R, t,
            FoV_x, FoV_y
        )

    # ==== 在这里做融合计算 ====
    if camera_data is not None:
        frame_size = camera_data.get("frame_size", [640, 480])
        cam_points = camera_data["points"]  # 12 个 [x_norm, y_norm]

        # ✅ 用最新的 pts_cam 给 12 个点补 z
        fused_points = fuse_points_with_depth(cam_points, frame_size, pts_cam)

        out = {
            "timestamp": camera_data["timestamp"],
            "points": fused_points,  # ★★★ 现在是 12 个 [x,y,z] ★★★
            "frame_size": frame_size,
            "type": "fused_xyz",     # 标一标，现在是融合后的 xyz
        }
        sender_socket.send_pyobj(out)
        camera_data = None   # 用完清空，等待下一帧

    # 如果你后面要用 ToF 深度做更多事情，可以继续用 serial_data / pts_cam / valid_mask
