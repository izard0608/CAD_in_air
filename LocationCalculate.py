import zmq
import time
import numpy as np
import cv2

from ModuleStatusList import ModuleStatusList as MSL

context = zmq.Context()

# 绑定端口 - 接收摄像头和ToF数据
camera_socket = context.socket(zmq.PULL)
camera_socket.bind("tcp://127.0.0.1:5556")
print("📷 摄像头端口绑定: 5556")

serial_socket = context.socket(zmq.PULL)
serial_socket.bind("tcp://127.0.0.1:5555")
print("📡 ToF端口绑定: 5555")

# 发送融合数据到手势识别
sender_socket = context.socket(zmq.PUSH)
sender_socket.bind("tcp://127.0.0.1:5557")
print("📤 融合数据端口绑定: 5557")

# 示例参数
W, H = 8, 8
FoV_x = np.deg2rad(45.0)
FoV_y = np.deg2rad(45.0)
K = np.array([[500, 0, 320],
              [0, 500, 240],
              [0, 0, 1]])
R = np.eye(3)
t = np.array([0, 0, 0])

def zone_angles(W, H, FoV_x, FoV_y):
    cs = np.arange(W)
    rs = np.arange(H)
    c_grid, r_grid = np.meshgrid(cs, rs)
    theta_x = ((c_grid - (W-1)/2) / ((W-1)/2)) * (FoV_x/2.0)
    theta_y = ((r_grid - (H-1)/2) / ((H-1)/2)) * (FoV_y/2.0)
    return theta_x, theta_y

def depthgrid_to_camera_points(depth_grid, K, R, t, FoV_x, FoV_y):
    try:
        theta_x, theta_y = zone_angles(W, H, FoV_x, FoV_y)
        tx = np.tan(theta_x)
        ty = np.tan(theta_y)
        denom = np.sqrt(tx**2 + ty**2 + 1.0)
        dirs = np.stack([tx/denom, ty/denom, 1.0/denom], axis=-1)
        points_ir = (depth_grid[...,None] * dirs)
        pts_ir_flat = points_ir.reshape(-1,3)
        valid = np.isfinite(pts_ir_flat[:,2]) & (pts_ir_flat[:,2] > 0.01)
        pts_ir_valid = pts_ir_flat[valid]
        pts_cam = (R.dot(pts_ir_valid.T) + t.reshape(3,1)).T
        return pts_cam, valid
    except Exception as e:
        print(f"❌ 深度数据转换错误: {e}")
        return np.array([]), np.array([])

def project_points(pts_cam, K):
    if len(pts_cam) == 0:
        return np.array([])
    X = pts_cam[:,0]; Y = pts_cam[:,1]; Z = pts_cam[:,2]
    u = (K[0,0]*X / Z) + K[0,2]
    v = (K[1,1]*Y / Z) + K[1,2]
    return np.stack([u,v], axis=1)

def fuse_points_with_depth(camera_points, frame_size, pts_cam):
    w, h = frame_size
    fused = []

    if pts_cam is None or len(pts_cam) == 0:
        print("⚠️ 无ToF点云数据，使用默认深度")
        for p in camera_points:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                fused.append([0.0, 0.0, 0.0])
            else:
                # 给2D点添加默认深度
                fused.append([float(p[0]), float(p[1]), 1.0])  # 默认深度1米
        return fused

    try:
        pts_img = project_points(pts_cam, K)
        if len(pts_img) == 0:
            raise ValueError("投影点为空")
            
        u_all = pts_img[:, 0]
        v_all = pts_img[:, 1]
        Z_all = pts_cam[:, 2]

        for p in camera_points:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                fused.append([0.0, 0.0, 0.0])
                continue

            x_norm, y_norm = float(p[0]), float(p[1])

            if x_norm == 0.0 and y_norm == 0.0:
                fused.append([0.0, 0.0, 0.0])
                continue

            u0 = x_norm * w
            v0 = y_norm * h

            # 找最近的投影点
            du = u_all - u0
            dv = v_all - v0
            dist2 = du*du + dv*dv
            
            if len(dist2) > 0:
                idx = int(np.argmin(dist2))
                z = float(Z_all[idx])
                # 深度范围限制
                z = max(0.1, min(5.0, z))
            else:
                z = 1.0  # 默认深度

            fused.append([x_norm, y_norm, z])
            
    except Exception as e:
        print(f"❌ 数据融合错误: {e}")
        # 出错时返回带默认深度的点
        for p in camera_points:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                fused.append([0.0, 0.0, 0.0])
            else:
                fused.append([float(p[0]), float(p[1]), 1.0])

    return fused

# ========= 主循环 =========
module_status_list = MSL()
module_status_list.set_ready("LocationCalculate.py")

print(module_status_list.ready_dict)

print("🔄 开始数据融合循环...")

poller = zmq.Poller()
poller.register(camera_socket, zmq.POLLIN)
poller.register(serial_socket, zmq.POLLIN)

camera_data = None
pts_cam = None
last_tof_time = 0
frame_count = 0

try:
    while True:
        socks = dict(poller.poll(timeout=100))

        # 接收摄像头数据
        if camera_socket in socks:
            camera_data = camera_socket.recv_json()
            print(f"📷 收到摄像头数据帧 #{frame_count}")

        # 接收ToF数据
        if serial_socket in socks:
            try:
                serial_msg = serial_socket.recv_json()
                depth_mm = np.array(serial_msg["depth_mm"], dtype=float)
                depth_m = depth_mm / 1000.0
                
                # 处理无效值
                depth_m = np.where(depth_m > 0.01, depth_m, np.nan)
                
                pts_cam, valid_mask = depthgrid_to_camera_points(
                    depth_m, K, R, t, FoV_x, FoV_y
                )
                last_tof_time = time.time()
                print(f"📊 ToF点云: {len(pts_cam) if pts_cam is not None else 0}个点")
                
            except Exception as e:
                print(f"❌ ToF数据处理错误: {e}")
                pts_cam = None

        # 数据融合处理
        if camera_data is not None:
            frame_size = camera_data.get("frame_size", [640, 480])
            cam_points = camera_data["points"]
            
            fused_points = fuse_points_with_depth(cam_points, frame_size, pts_cam)
            
            out = {
                "timestamp": time.time(),
                "points": fused_points,
                "frame_size": frame_size,
                "type": "fused_xyz",
            }
            
            sender_socket.send_pyobj(out)
            frame_count += 1
            print(f"📤 发送融合数据帧 #{frame_count}: {len(fused_points)}个3D点")
            camera_data = None

        # ToF数据超时处理
        if pts_cam is not None and time.time() - last_tof_time > 3.0:
            print("⚠️ ToF数据超时")
            pts_cam = None

except KeyboardInterrupt:
    print("⏹️ 用户中断程序")
except Exception as e:
    print(f"❌ 程序错误: {e}")
finally:
    camera_socket.close()
    serial_socket.close()
    sender_socket.close()
    context.term()