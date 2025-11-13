先说结论：  
**这四段代码在端口、消息格式、ZMQ 模式上是对得上的，可以跑。**  
摄像头给 12 个 `[x,y]`，ToF 给 8×8 深度，`locationcalculate` 融成 12 个 `[x,y,z]`，`receive` 能正常吃。

我按链路一段段给你过一遍，只挑“衔接”和可能踩坑的地方说。

---

## 1️⃣ Camera ↔ LocationCalculate（5556）

### Camera 端

```python
self.socket = self.context.socket(zmq.PUSH)
self.socket.connect("tcp://127.0.0.1:5556")
...
data = {
    "timestamp": time.time(),
    "points": points,             # 12 个 [x, y]
    "type": "camera_coordinates",
    "frame_size": frame_size      # [w, h]
}
self.socket.send_json(data)
```

- PUSH + connect → ✅
- `points`: 12 个 `[x_norm, y_norm]`（MediaPipe 归一化坐标 0~1）→ ✅
- `frame_size`: `[w, h]`，和你后面用的一致（注意是 `[w,h]`，不是 `[h,w]`）→ ✅

### LocationCalculate 端

```python
camera_socket = context.socket(zmq.PULL)
camera_socket.bind("tcp://127.0.0.1:5556")
...
if camera_socket in socks:
    camera_data = camera_socket.recv_json()
...
frame_size = camera_data.get("frame_size", [640, 480])
cam_points = camera_data["points"]  # 12 个 [x_norm, y_norm]
```

- PULL + bind → ✅，和 Camera 对上。
- 用 `recv_json()`，和 Camera 的 `send_json()` 匹配 → ✅
- 读出的内容字段名完全和 Camera 发的一致 → ✅

**小结**：  
Camera→LocationCalculate 这条链没有接口问题。

---

## 2️⃣ serialreceiver ↔ LocationCalculate（5555）

### serialreceiver 端

```python
socket = context.socket(zmq.PUSH)
socket.connect("tcp://127.0.0.1:5555")
...
packet = {
    "type": "tof_depth",
    "start_ms": start_ts,
    "end_ms": end_ts,
    "depth_mm": depth_rows,   # 8x8，单位：毫米
}
socket.send_json(packet)
```

- PUSH + connect → ✅
- `depth_mm` 是 8×8 的整型毫米 → ✅
- `type: "tof_depth"`，后面虽然没用这个字段做判断，但保留没问题。

### LocationCalculate 端

```python
serial_socket = context.socket(zmq.PULL)
serial_socket.bind("tcp://127.0.0.1:5555")
...
serial_msg = serial_socket.recv_json()
depth_mm = np.array(serial_msg["depth_mm"], dtype=float)
depth_m  = depth_mm / 1000.0
pts_cam, valid_mask = depthgrid_to_camera_points(...)
...
if serial_socket in socks:
    serial_msg = serial_socket.recv_json()
    depth_mm = np.array(serial_msg["depth_mm"], dtype=float)
    depth_m  = depth_mm / 1000.0
    pts_cam, valid_mask = depthgrid_to_camera_points(...)
```

- PULL + bind → ✅，和 serialreceiver 对上。
- 收的也是 `recv_json()`，字段名 `depth_mm` 对上 → ✅
- 先在最上面阻塞一次 `recv_json()` 拿一帧 ToF，再进入 poller 循环 → **行为合理**，但意味着：
  - ⚠️ **locationcalculate 启动时会卡在这里，直到 serialreceiver 发出第一帧 ToF 数据**。
  - 所以要么先起 serialreceiver，要么接受刚启动时会小卡一下。

**小结**：  
ToF→LocationCalculate 数据流通顺畅，格式也对。

---

## 3️⃣ LocationCalculate → receive.py（5557）

### LocationCalculate 端

```python
sender_socket = context.socket(zmq.PUSH)
sender_socket.bind("tcp://127.0.0.1:5557")
...
fused_points = fuse_points_with_depth(cam_points, frame_size, pts_cam)

out = {
    "timestamp": camera_data["timestamp"],
    "points": fused_points,  # ★★★ 现在是 12 个 [x,y,z] ★★★
    "frame_size": frame_size,
    "type": "fused_xyz",
}
sender_socket.send_pyobj(out)
```

- PUSH + bind → ✅
- 用的是 `send_pyobj(out)`，会通过 pickle 序列化 → ✅

`fuse_points_with_depth` 也看一下关键部分：

```python
def fuse_points_with_depth(camera_points, frame_size, pts_cam):
    w, h = frame_size
    ...
    pts_img = project_points(pts_cam, K)  # N x 2 (像素坐标)
    u_all = pts_img[:, 0]
    v_all = pts_img[:, 1]
    Z_all = pts_cam[:, 2]

    for p in camera_points:
        ...
        x_norm, y_norm = float(p[0]), float(p[1])
        if x_norm == 0.0 and y_norm == 0.0:
            fused.append([0.0, 0.0, 0.0])
            continue

        u0 = x_norm * w
        v0 = y_norm * h

        du = u_all - u0
        dv = v_all - v0
        dist2 = du*du + dv*dv
        idx = int(np.argmin(dist2))

        z = float(Z_all[idx])  # 米

        fused.append([x_norm, y_norm, z])
```

- Camera 发的是归一化坐标 `[x_norm,y_norm]`，绘制时你也是 `x = x_norm*w`；这里也用 `x_norm*w` / `y_norm*h` 去找最近的 ToF 投影点 → **坐标系一致** ✅
- `z` 直接用 `pts_cam` 的 Z（单位米），不会再乱改 → ✅
- 无效点 `[0,0]` 被直接变成 `[0,0,0]`，不会误用 ToF 数据 → ✅

### receive.py 端

```python
socket  = context.socket(zmq.PULL)
socket.connect("tcp://127.0.0.1:5557")
...
data = socket.recv_pyobj()
backend.process_data(data)
```

- PULL + connect → ✅，和 LocationCalculate 的 PUSH.bind 对上。
- `recv_pyobj()` 和 `send_pyobj(out)` 配套 → ✅

`process_data` 里对 `points` 的用法：

- 一上来就：

```python
points    = data.get("points") or []
if len(points) < 12:
    ...
    return
```

- 后面所有几何都假定 `points[i]` 是 **长度 3 的列表 [x,y,z]**：
  - `distance` 是在 3 维上算欧氏距离；
  - `_mid` / `normal_vector` / `point_to_plane` 都按 3D 处理；
  - 各种动作识别用到的都是 `[0..11]` 这 12 个点。

你现在在 `locationcalculate` 里拼出来的正好是 12 个 `[x_norm, y_norm, z_m]`，完全符合它的预期 → ✅

**唯一要注意的一点（不是 bug，只是需要你心里有数）：**

- 现在：
  - `x,y` 是 0~1 之间的归一化图像坐标；
  - `z` 是 “米” 级的深度；
- 以前如果你是纯 MediaPipe 3D 的话，三个坐标可能是同一个单位尺度（它自己的相机坐标系）；  
  现在水平/垂直方向在 0~1，而深度可能在 0.5~2.0 左右，这会改变“距离”的绝对值。
- 所以：
  - 左右手捏合的距离 `d`，现在主要由 x,y 差主导，z 差可能也有贡献；
  - `DIS_ON / DIS_OFF / DIS_THRESHOLD / POSITION_THRESHOLD` 这些阈值，有可能需要你 **重新调一调数值**，但这已经超出“衔接是否正确”的范畴了。

---

## 4️⃣ 整体数据流检查（端口 & 模式）

整理一下：

1. **Camera → LocationCalculate**
   - Camera: `PUSH.connect("tcp://127.0.0.1:5556")`
   - Calculate: `PULL.bind("tcp://127.0.0.1:5556")`
   - 协议：JSON（`send_json` / `recv_json`）

2. **serialreceiver → LocationCalculate**
   - serialreceiver: `PUSH.connect("tcp://127.0.0.1:5555")`
   - Calculate: `PULL.bind("tcp://127.0.0.1:5555")`
   - 协议：JSON（`send_json` / `recv_json`）

3. **LocationCalculate → receive**
   - Calculate: `PUSH.bind("tcp://127.0.0.1:5557")`
   - receive(real mode): `PULL.connect("tcp://127.0.0.1:5557")`
   - 协议：PyObject（`send_pyobj` / `recv_pyobj`）

模式上全部是 **单向 PUSH→PULL**，每个端口只有一侧 bind，另一侧 connect，ZMQ 是喜欢这样的，没问题 ✅。

---

## 5️⃣ 我建议你注意的几个小点（不是必须改）

1. **启动顺序的小坑**  
   - `locationcalculate` 在一开始就 `serial_socket.recv_json()`，所以如果你先跑它，而 serialreceiver 暂时没发数据，它会在这里一直堵着，看起来像“没动静”。
   - 最保险的顺序：
     1. 先跑 `serialreceiver.py`
     2. 再跑 `locationcalculate.py`
     3. 再跑 `Camera` 和 `receive.py`

2. **阈值可能要调一调**  
   - 因为现在坐标的尺度变了（x、y 小于 1，z 大概在 1 附近），`DIS_ON`, `DIS_OFF`, `DIS_THRESHOLD` 这些数你以后可以根据实际手感微调。

3. **无 ToF 时的行为**  
   - 只要 serialreceiver 在跑，`locationcalculate` 一启动就会收到一帧 ToF，这种情况没问题；
   - 如果某次运行中 ToF 掉线了，`pts_cam` 会停在最后一帧的值，不会变成 None；行为是“用最后一帧的深度继续补 z”，这一点你心里知道就行。

---

## ✅ 总结一句话

- **端口 / ZMQ 模式：完全对得上**  
- **消息格式：Camera/ToF → Calculate → receive 一路字段名都对，类型也对**  
- **receive 期待的 `points` 结构现在确实是 12 个 `[x,y,z]`，可以无缝用**

如果你接下来跑起来遇到的是“逻辑不对 / 手感奇怪”（比如不容易触发、线太短之类），那就是阈值标定和外参标定的问题了，不是“衔接”问题。到时候你可以再把具体现象跟我说，我帮你一起调参数。

