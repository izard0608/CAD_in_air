# 2025/10/29 Update
## 对于receive.py:
- 把主要功能封装到类里面，提升易用性。
- 增加了websocket，移除了zmq。
- 增加了生成模拟数据函数，便于前端调试。
## 其它：
- requirements.txt增加了requests == 2.32.5,websocket-client == 1.9.0
- 主要的痛苦点：
    - 前后端的指令不匹配
    - 非常容易有死循环等例如self.init()导致的
    - 前端框架本来必须摄像头启动才能处理后端数据，现在必须重新搭框架
    - 3D渲染杂七杂八的问题，例如我前天写前端调试的时候创了一个内联实例，今天又创了另一个内联实例，导致出bug，调了3个小时才发现是这里的问题
    - 由于之前写代码的时候偷懒，事件监听太少，导致出错了都不知道是哪里的问题，今天花了巨量时间补写事件监听
- 现状：前后端确实可以衔接在一起了
---
# 2025/10/30 Update
## feat & fix:
- 完成了点、线、面建构的测试
- 改正了摄像头读取错误的bug
- 虽然没有摄像头没法运行，但是可以在开好flask后在console里输入以下指令调用前端API调试：
```json
fetch("/api/start-modeling", { method: "POST" })
```
---
### GPT5写的代码解析，供参考
 

# 目录（代码与职责）
- `static/js/main.js`：应用编排层（UI/状态/业务流）
  - `CameraManager`（可选模块）  
  - `GestureModelingApp`（核心控制器）
- `static/js/three-scene.js`：渲染层（Three.js 场景与几何）
  - `ThreeScene`
- `static/js/websocket-client.js`：传输层（Socket.IO 客户端）
  - `WebSocketClient`
- `main.py`：服务端（Flask + Socket.IO）
- `receive.py`：手势后端适配器（把识别结果转为指令流发到服务端）
- `templates/index.html`：页面结构 & 测试面板（只创建**一个**应用实例）

---

# 一、`main.js`（应用编排）

## 1) `CameraManager`
- 负责浏览器摄像头权限与 `<video>` 绑定：`startCamera()` / `stopCamera()` / 错误覆盖层。
- 这块对建模渲染不关键（渲染靠 Three.js，与摄像头无关），但提供了“用户可见的输入反馈”。

## 2) `GestureModelingApp`（核心）
**职责**：装配 UI、WebSocket、Three.js，维护建模会话状态，转发 WebSocket 事件到 ThreeScene。

### 属性
- `this.websocketClient`：Socket.IO 客户端
- `this.threeScene`：Three.js 场景实例
- `this.isModeling` / `this.currentSession`：建模状态
- `window.app = this;`：把唯一实例挂到全局，确保测试面板/控制台/事件用的是**同一个**实例

### 生命周期
- `init()`：
  - 调 `/api/check-reset` 做孤儿会话清理（后端无人连接时自动复位）
  - `setupUIEvents()` 绑定按钮（防重复绑定：用 `cloneNode(true)`）
  - `this.websocketClient.connect()` 建立 socket
  - `this.threeScene = new ThreeScene('modeling-scene')` 初始化渲染
  - `setupWebSocketEvents()` 注册事件回调

### UI事件
- 开始/停止/重置建模 → `startModeling()` / `stopModeling()` / `resetScene()`
  - `startModeling()`：调用 `POST /api/start-modeling`，成功后后端广播 `modeling_started`，前端在 `onModelingStarted()` 里把 `isModeling = true`
  - `stopModeling()`：同理

### WebSocket 事件绑定（和服务端事件名一一对应）
```js
connection_established → on('connectionEstablished')
modeling_started       → on('modelingStarted')
modeling_stopped       → on('modelingStopped')
gesture_update         → on('gestureUpdate')  // 核心数据流
error                  → on('error')
```
- `gestureUpdate` → `handleGestureCommand(data)`
  - 只有 `this.isModeling === true` 才处理（防止未开始时误渲染）
  - **指令路由表**（你已补齐）：
    - `start_drawing_point` → `threeScene.createPoint(...)`
    - `start_drawing_line`  → `threeScene.startDrawingLine(...)`
    - `update_drawing_line` → `threeScene.updateDrawingLine(...)`
    - `finish_drawing_line` → `threeScene.finishDrawingLine(...)`
    - `create_rectangle`    → `threeScene.createRectangle(...)`
    - `create_plane`        → 映射为 `createRectangle(...)`（对角点+法向量先走简单版本）

> 关键改动：补齐 `start_drawing_line`/`create_plane` 的分支；并允许“零长度 finish”合并成一个点（见 `three-scene.js`）。

---

# 二、`three-scene.js`（渲染层）

## `ThreeScene`
**职责**：管理 Three.js 场景/相机/渲染器与所有几何对象；提供“点/线/面”的构造 API 与交互状态机。

### 初始化
- `init()`：
  - `scene = new THREE.Scene()`，背景深色
  - 透视相机：`PerspectiveCamera(75, aspect, 0.1, 1000)`，位于 `(0,5,10)`
  - `WebGLRenderer`（抗锯齿+软阴影）
  - 清空并挂载到容器 `#modeling-scene`
  - 光照：环境光 + 方向光；参考网格 + 坐标轴
  - `animate()` 循环渲染 + 简单 FPS 统计

### 内部状态
- `this.objects: Map<string, THREE.Object3D>`：命名对象集合（便于选中/删除）
- “画线状态机”：
  - `isDrawing`：是否在“画线模式”
  - `startPoint`：绿点 Mesh（起点）
  - `dynamicLine`：预览线（`THREE.Line`）

### 核心 API（被 `GestureModelingApp` 调用）
- **点**
  - `createPoint({position, color, size, name})`  
    - **改进**：可选“近邻合并”（你可以保留我给的 `_findPointNear`，避免同坐标重复加点导致闪烁）
- **线**
  - `startDrawingLine({position})`：创建绿起点 + `dynamicLine`
  - `updateDrawingLine({position})`：更新 `dynamicLine` 的第二个端点
  - `finishDrawingLine({position, color})`：  
    - **关键修复**：如果 `end ≈ start`（阈值 `EPS=1e-4`），**不再新建红点**，而是直接把起点改红并结束；否则创建红终点与最终静态线  
    - 清理 `dynamicLine`，重置状态  
- **面**
  - `createRectangle({corner1, corner2, normal, color, opacity, name})`：当前实现为平贴地面的矩形（`BoxGeometry(w, 0.01, h)`），先跑通“视觉表达”；如果将来要按任意法向构造真正平面，可加 `createPlane({center, width, height, normal})`。
- **对象操作**：`selectObject()`（对 `MeshBasicMaterial` 无 `emissive` 加了保护）、`moveObject()`、`deleteObject()`、`clearScene()`
- **自适应**：`onResize()` 调整相机与渲染器
- **销毁**：`destroy()` 释放动画与渲染器

### 渲染注意点
- **闪烁（Z-fighting）根因与修复**  
  - 根因：同坐标重复创建了红/绿两球（`start` 与 `finish` 完全重合），深度缓冲竞争  
  - 修复：在 `finishDrawingLine` 做“零长度线段合并”；（可选）在 `createPoint` 启用“近邻复用”

---

# 三、`websocket-client.js`（Socket.IO 客户端）

## `WebSocketClient`
**职责**：管理与后端的 Socket.IO 连接、重连策略、事件转发给外部（观察者模式）。

### 连接 & 重连
- `connect()`：`io('http://localhost:5000')`
- `handleReconnection()`：指数回退（次数上限 `maxReconnectAttempts=5`）

### 内置事件（与后端事件名一致）
- `connect` / `disconnect` / `connect_error`  
- `server_ready` → `emit('serverReady', data)`  
- `connection_established` → `emit('connectionEstablished', data)`  
- `modeling_started` → `emit('modelingStarted', data)`  
- `modeling_stopped` → `emit('modelingStopped', data)`  
- `gesture_update` → `emit('gestureUpdate', data)` **←核心**  
- `hand_update` / `binary_hand_update` → 分别 `emit('handUpdate')`/`emit('binaryHandUpdate')`  
- `error` → `emit('error', error)`

### 观察者模式
- `on(event, handler)`：注册回调到 `eventHandlers: Map<string, Function[]>`
- `emit(event, data)`：调用所有回调（控制台有详细日志，便于你追踪事件流）

### 统计与 UI
- 维护 `packetStats`（收发计数 / 最近包时间）  
- `updateConnectionStatus()` / `updateModelingStatus()` 直接更新 DOM（状态文本与样式类名）

---

# 四、`main.py`（Flask + Socket.IO 服务端）

## 结构
- `Flask` + `Flask-SocketIO(async_mode='threading')`，允许 CORS，端口 5000
- 全局状态 `AppState`：`is_modeling` / `current_session` / `connected_clients`

## HTTP 路由
- `GET /`：渲染 `index.html`
- `GET /api/status`：返回当前状态（给前端 UI）
- `POST /api/start-modeling`：置 `is_modeling=True`，生成 `current_session`，**广播** `modeling_started`
- `POST /api/stop-modeling`：清状态，**广播** `modeling_stopped`
- `GET /api/check-reset`：无客户端却仍建模中 → 自动复位（防“孤儿会话”）

## Socket 事件（与前端一一对应）
- `connect`：连接数 +1，单播 `connection_established`
- `disconnect`：连接数 -1
- `client_ready`：回 `server_ready`
- `gesture_command`：**接收**来自 `receive.py` 的指令  
  - `validate_gesture_data(data)`：要求包含 `type` 和 `timestamp`；当 `type=="command"` 要有 `command`  
  - 验证通过 → **广播** `gesture_update`
- `hand_coordinates` / `binary_hand_data`：广播到前端对应事件

> 关键坑点：**`receive.py` 必须带 `type: "command"`**，否则服务端会判为非法数据、不会广播（你已修）。

---

# 五、`receive.py`（手势后端 → 指令桥接）

**职责**：连接 Flask-SocketIO 服务器，订阅手势识别流（真实或模拟），把“捏合/角度/静止”等规则转换成建模指令并 `emit('gesture_command', data)`。

## Socket 客户端
- `socketio.Client()` 直连 Flask 服务端（默认 `http://localhost:5000`）
- `send_command(command_type, parameters)` → **统一打包**：
  ```py
  data = {
    'type': 'command',         # 必须：被 main.py 校验
    'command': command_type,   # e.g. 'start_drawing_point' / 'start_drawing_line' / 'finish_drawing_line' / 'create_plane'
    'parameters': {...},       # e.g. {'position':[x,y,z]} / {'start_position':...,'end_position':...,'normal_vector':...}
    'timestamp': time.time()
  }
  self.sio.emit('gesture_command', data)
  ```

## 规则与状态
- 手指索引约定（左右手拇指/食指各三个点），阈值参数：
  - `POSITION_THRESHOLD`、`TIME_THRESHOLD`、`DIS_THRESHOLD`、`DEGREE_THRESHOLD`
- 逻辑：
  - **左手捏合稳定** → 发送 `start_drawing_point`（创建点）
  - **右手捏合稳定**：首次 → `start_drawing_line`；再次 → `finish_drawing_line`
    - **可选优化**：如果 `end ≈ start`，改发 `start_drawing_point`（避免零长度线）
  - **双手角度稳定且大于阈值** → 计算法向量与投影 → 发送 `create_plane`（前端临时映射为 `createRectangle` 以便可视化）

## 模拟模式
- `start_simulation()`：定时产生“左手捏合稳定”的数据，验证整条链路（后端广播→前端渲染）

---

# 六、`index.html`（唯一实例、测试面板）

- 右侧 `#modeling-scene` 作为 Three.js 容器
- **注意**：只创建**一个** `GestureModelingApp` 实例，并挂到 `window.app`（避免多实例互相覆盖/各自连各自的 socket）
- 测试面板按钮**直接调用** `window.app.threeScene.*`，绕过 WebSocket，用于快速验证渲染 API 是否正常

---

# 七、事件 & 数据结构（对照表）

| 层级 | 事件名 | 方向 | 载荷示例 |
|---|---|---|---|
| `receive.py`→`main.py` | `gesture_command` | client→server | `{type:'command', command:'start_drawing_point', parameters:{position:[x,y,z], color:0xff0000, size:0.05, name:'point_...'}, timestamp:...}` |
| `main.py`→前端 | `gesture_update` | server→clients | 同上（原样广播） |
| 前端 `WebSocketClient` | `gestureUpdate` | 内部分发 | `GestureModelingApp.handleGestureCommand(data)` |
| 系统控制 | `modeling_started`/`stopped` | server→clients | `{session_id:'...', timestamp:...}` |
| 链接握手 | `connection_established` | server→client | `{client_id: sid, is_modeling, current_session, timestamp}` |
| 心跳就绪 | `server_ready` | server→client | `{message, timestamp}` |

---

# 八、状态机 & 关键不变量

- **建模状态**：`isModeling` 必须为 `true` 才处理 `gesture_update`  
  - 入口：点击“开始建模”→ `/api/start-modeling` 成功 → `onModelingStarted()`  
  - 退出：点击“结束建模”或页面关闭 → `destroy()` / `onModelingStopped()`
- **画线状态机**（前端）：
  - `startDrawingLine()` → `isDrawing=true`、生成 `startPoint`（绿）与 `dynamicLine`
  - `updateDrawingLine()` → 更新预览线终点
  - `finishDrawingLine()` → **若 end≈start：只把起点变红**；否则新建红点 + 静态线；清理 `dynamicLine`；`isDrawing=false`
- **对象集合**：`this.objects` 中**名字唯一**，便于后续选择/移动/删除

---

# 九、调试与排错要点

1) **对照日志**：前端 `handleGestureCommand` 的“收到命令”→ThreeScene 的“创建点/开始画线/完成画线”，链路是否完整  
2) **控制台注入**：  
   - 直渲染：`app.threeScene.createPoint({ position:[0,0,0], color:0xff0000 })`  
   - 模拟广播：`app.websocketClient.emit('gestureUpdate', {...})`  
3) **防多实例**：确保只在一处 `new GestureModelingApp()`，并赋给 `window.app`  
4) **格式校验**：`receive.py` 的每条消息必须带 `type:'command'` + `timestamp`  
5) **Z-fighting**：零长度线段不要叠加红/绿点—前端已在 `finishDrawingLine` 兜底处理

---

# 十、可选的后续增强

- 真正的**任意法向平面**：新增 `createPlane({center,width,height,normal})`，对几何体做旋转对齐  
- **撤销/重做**：维护操作栈（命令模式），`undo/redo` 操作堆栈与对象快照  
- **网络抖动去重**：在前端按 `name` 或坐标 hash 做幂等保护  
- **性能**：大场景使用 `InstancedMesh` 管点，降低 draw calls；或把动态线切到 `Line2`（three/examples）提升观感  
- **协议版本**：在消息里加入 `schemaVersion`，方便将来协议演进
