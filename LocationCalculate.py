import zmq
import time
import numpy as np
import cv2

context=zmq.Context()
socket=context.socket(zmq.PULL)

socket.connect("")

# 示例参数（替换成你的实际量）
W, H = 8, 8
FoV_x = np.deg2rad(70.0)   # 可调整或按 datasheet 确定
FoV_y = np.deg2rad(53.0)
K = np.array([[504.75482615870874, 0, 312.03400445227277],
              [0, 508.21911022517912, 250.01176949694818],
              [0,  0,  1]])  # 填入你的相机内参
R = np.array([
    [-0.18786171 ,-0.38956207 , 0.90163705]
 [-0.91177968 ,-0.27214855 ,-0.30755972]
 [ 0.36519282 ,-0.87987304 ,-0.30406848]
])   # 填入外参（ToF -> Camera）
t = np.array([-0.06918701,-0.02770361,0.04883691]) # 填入外参平移（meters）

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