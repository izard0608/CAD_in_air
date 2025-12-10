// static.js.main.js
// 这里定义了CameraManager和GestureModelingApp两个类
// 负责管理摄像头视频流的获取、停止以及 WebRTC 连接的创建
class CameraManager {
    constructor() {
        this.videoElement = null;
        this.overlayElement = null;
        this.isActive = false;
    }
    
    async startCamera() {
        try {
            console.log('连接视频流...');
            
            this.videoElement = document.getElementById('camera-video');
            this.overlayElement = document.getElementById('camera-overlay');
            
            if (!this.videoElement) {
                throw new Error('未找到视频元素');
            }

            // 直接设置 iframe 的 src
            const streamURL = 'http://localhost:5001/video_feed';
            console.log('设置视频流URL:', streamURL);
            
            this.videoElement.src = streamURL;
            
            // 隐藏覆盖层
            if (this.overlayElement) {
                this.overlayElement.style.display = 'none';
            }
            
            this.isActive = true;
            console.log('视频流连接设置完成');
            
            return true;
            
        } catch (error) {
            console.error('视频流连接失败:', error);
            this.showCameraError(error);
            return false;
        }
    }
    
    stopCamera() {
        if (this.videoElement) {
            this.videoElement.src = '';
        }
        
        this.isActive = false;
        
        if (this.overlayElement) {
            this.overlayElement.style.display = 'block';
            this.overlayElement.innerHTML = `
                <div class="overlay-text">
                    <div>视频流已停止</div>
                    <button onclick="app.cameraManager.startCamera()" 
                            style="margin-top: 10px; padding: 8px 16px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        重新连接
                    </button>
                </div>
            `;
        }
    }
    
    showCameraError(error) {
        const overlay = document.getElementById('camera-overlay');
        if (overlay) {
            overlay.innerHTML = `
                <div class="overlay-text">
                    <div style="color: #ff6b6b; font-size: 1.2em; margin-bottom: 10px;">
                        无法连接视频流
                    </div>
                    <div style="color: #ccc; margin-bottom: 15px; font-size: 0.9em;">
                        请确保 Camera.py 正在运行<br>
                        错误信息: ${error.message}
                    </div>
                    <div>
                        <button onclick="app.cameraManager.startCamera()" 
                                style="padding: 8px 16px; margin: 5px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                            重新连接
                        </button>
                        <button onclick="window.open('http://localhost:5001/video_feed', '_blank')" 
                                style="padding: 8px 16px; margin: 5px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
                            在新窗口测试
                        </button>
                    </div>
                </div>
            `;
            overlay.style.display = 'block';
        }
    }
}



class GestureModelingApp {
    constructor() {
        this.cameraManager = new CameraManager();  // 创建CameraManager实例，用来管理摄像头
        this.websocketClient = new WebSocketClient();  // 创建WebSocket客户端实例，用来与服务器通信
        this.threeScene = null;  // 3D场景实例，后续用于显示建模内容
        this.isModeling = false;  // 表示是否处于建模状态
        this.currentSession = null;  // 当前的建模会话ID
        
        this.init();  // 初始化应用
    }
    
    async init() {
        console.log('初始化手势3D建模应用...');
        
        // 检查后端状态
        try {
            const response = await fetch('/api/check-reset');
            const status = await response.json();
            console.log('后端状态检查:', status);
        } catch (error) {
            console.warn('状态检查失败:', error);
        }
        
        // 初始化UI事件
        this.setupUIEvents();
        
        // 初始化WebSocket连接
        this.websocketClient.connect();
        
        // 初始化3D场景
        this.threeScene = new ThreeScene('modeling-scene');
        
        // 设置WebSocket事件监听
        this.setupWebSocketEvents();
        
        // 自动连接视频流
        setTimeout(() => {
            this.cameraManager.startCamera().catch(error => {
                console.warn('视频流连接失败:', error);
            });
        }, 1000);
        
        console.log('手势3D建模应用初始化完成');
    }
    
    setupUIEvents() {
        // 获取UI按钮元素
        const startBtn = document.getElementById('btn-start');
        const stopBtn = document.getElementById('btn-stop');
        const resetBtn = document.getElementById('btn-reset');
        
        // 移除旧的事件监听器，防止重复绑定
        startBtn.replaceWith(startBtn.cloneNode(true));
        stopBtn.replaceWith(stopBtn.cloneNode(true));
        resetBtn.replaceWith(resetBtn.cloneNode(true));
        
        // 重新获取UI按钮元素
        const newStartBtn = document.getElementById('btn-start');
        const newStopBtn = document.getElementById('btn-stop');
        const newResetBtn = document.getElementById('btn-reset');
        
        // 建模控制按钮事件绑定
        newStartBtn.addEventListener('click', () => {
            console.log('开始建模按钮被点击');
            this.startModeling();  // 点击后开始建模
        });
        
        newStopBtn.addEventListener('click', () => {
            console.log('停止建模按钮被点击');
            this.stopModeling();  // 点击后停止建模
        });
        
        newResetBtn.addEventListener('click', () => {
            console.log('重置场景按钮被点击');
            this.resetScene();  // 点击后重置场景
        });
    }
    
    setupWebSocketEvents() {
        console.log('设置WebSocket事件监听');
    
        // 连接状态事件
        this.websocketClient.on('connectionEstablished', (data) => {
            console.log('WebSocket连接已建立');
            this.updateClientCount(data.connected_clients);  // 更新连接的客户端数量
            this.updateConnectionStatus('online');  // 更新连接状态为在线
        });
        
        // 建模控制事件
        this.websocketClient.on('modelingStarted', (data) => {
            console.log('收到建模开始事件:', data);
            this.onModelingStarted(data);  // 开始建模
        });
        
        this.websocketClient.on('modelingStopped', (data) => {
            console.log('收到建模结束事件:', data);
            this.onModelingStopped(data);  // 停止建模
        });
        
        // 手势数据事件
        this.websocketClient.on('gestureUpdate', (data) => {
            console.log('收到手势命令:', data.command);
            this.handleGestureCommand(data);  // 处理手势命令
        });
        
        // 错误处理
        this.websocketClient.on('error', (error) => {
            console.error('WebSocket错误:', error);
            this.showError('系统错误: ' + error.message);  // 显示错误信息
        });
    }
    
    async startModeling() {
        console.log('startModeling 方法开始执行');
        
        // 如果建模已经在进行中，跳过
        if (this.isModeling) {
            console.log('建模已在进行中，跳过');
            this.showNotification('建模会话已在进行中', 'warning');
            return;
        }
        
        try {
            console.log('发送开始建模请求...');
            const response = await fetch('/api/start-modeling', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('建模会话启动成功:', data);
            
        } catch (error) {
            console.error('启动建模失败:', error);
            this.showError('启动建模失败: ' + error.message);  // 显示错误信息
        }
    }
    
    async stopModeling() {
        try {
            console.log('发送停止建模请求...');
            const response = await fetch('/api/stop-modeling', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error('停止建模失败');
            }
            
            const data = await response.json();
            console.log('建模会话停止成功:', data);
            
        } catch (error) {
            console.error('停止建模失败:', error);
            this.showError('停止建模失败: ' + error.message);  // 显示错误信息
        }
    }
    
    onModelingStarted(data) {
        this.isModeling = true;  // 更新建模状态为进行中
        this.currentSession = data.session_id;  // 保存当前建模会话的ID
        
        // 更新UI状态
        document.getElementById('btn-start').disabled = true;  // 禁用开始建模按钮
        document.getElementById('btn-stop').disabled = false;  // 启用停止建模按钮
        document.getElementById('session-id').textContent = this.currentSession;  // 显示当前会话ID
        
        this.updateModelingStatus('active');  // 更新建模状态
        this.updateOperationHint('手势建模已开始，请使用手势进行3D建模操作');  // 更新操作提示
        this.showNotification('建模会话已开始', 'success');  // 显示通知
        
        console.log('前端建模状态已更新: 开始');
    }
    
    onModelingStopped(data) {
        this.isModeling = false;  // 更新建模状态为结束
        this.currentSession = null;  // 清空当前会话ID
        
        // 更新UI状态
        document.getElementById('btn-start').disabled = false;  // 启用开始建模按钮
        document.getElementById('btn-stop').disabled = true;  // 禁用停止建模按钮
        document.getElementById('session-id').textContent = '未开始';  // 显示"未开始"
        
        this.updateModelingStatus('inactive');  // 更新建模状态
        this.updateOperationHint('建模会话已结束，点击"开始建模"重新开始');  // 更新操作提示
        this.showNotification('建模会话已结束', 'info');  // 显示通知
        
        console.log('前端建模状态已更新: 结束');
    }
    
    handleGestureCommand(data) {
        if (!this.isModeling) {
            console.log('收到手势命令但建模未开始');
            return;
        }
        
        console.log('处理手势命令:', data.command);
        
        if (!this.threeScene) {
            console.error('ThreeScene未初始化');
            return;
        }
        
        try {
            switch(data.command) {
                case 'start_drawing_point':
                    console.log('创建点:', data.parameters.position);
                    this.threeScene.createPoint(data.parameters);  // 创建点
                    break;
                case 'start_drawing_line':
                    console.log('开始画线:', data.parameters.position);
                    this.threeScene.startDrawingLine(data.parameters);  // 开始画线
                    break;
                case 'update_drawing_line':
                    this.threeScene.updateDrawingLine(data.parameters);  // 更新画线
                    break;
                case 'finish_drawing_line':
                    console.log('完成画线:', data.parameters.position);
                    this.threeScene.finishDrawingLine(data.parameters);  // 完成画线
                    break;
                case 'create_plane':
                    console.log('创建平面');
                    this.threeScene.createRectangle({
                        corner1: data.parameters.start_position,
                        corner2: data.parameters.end_position,
                        normal: data.parameters.normal_vector,
                        color: 0x3498db,
                        opacity: 0.7
                    });  // 创建平面
                    break;
                default:
                    console.log('未知命令:', data.command);  // 处理未知命令
            }
        } catch (error) {
            console.error('处理手势命令失败:', error);  // 错误处理
        }
    }
    
    resetScene() {
        if (this.threeScene) {
            this.threeScene.clearScene();  // 清空3D场景
            this.showNotification('场景已重置', 'info');  // 显示通知
        }
    }
    
    // UI更新方法
    updateOperationHint(hint) {
        const hintElement = document.getElementById('operation-hint');
        if (hintElement) {
            hintElement.textContent = hint;  // 更新操作提示
        }
    }
    
    updateClientCount(count) {
        const countElement = document.getElementById('client-count');
        if (countElement) {
            countElement.textContent = count;  // 更新连接的客户端数
        }
    }
    
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = status === 'online' ? '在线' : '离线';  // 更新连接状态
            statusElement.className = status === 'online' ? 'status-online' : 'status-offline';  // 根据状态设置class
        }
    }
    
    updateModelingStatus(status) {
        const statusElement = document.getElementById('modeling-status');
        if (statusElement) {
            statusElement.textContent = status === 'active' ? '进行中' : '未开始';  // 更新建模状态
            statusElement.className = status === 'active' ? 'status-active' : 'status-inactive';  // 根据状态设置class
        }
    }
    
    showNotification(message, type = 'info') {
        console.log(`[${type}] ${message}`);
        
        // 简单的通知显示
        const hintElement = document.getElementById('operation-hint');
        if (hintElement) {
            const originalText = hintElement.textContent;
            hintElement.textContent = message;
            
            setTimeout(() => {
                if (hintElement.textContent === message) {
                    hintElement.textContent = originalText;  // 3秒后恢复原始文本
                }
            }, 3000);
        }
    }
    
    showError(message) {
        this.showNotification('系统错误: ' + message, 'error');  // 显示错误信息
    }
    
    // 销毁方法
    destroy() {
        if (this.websocketClient) {
            this.websocketClient.disconnect();  // 断开WebSocket连接
        }
        
        if (this.threeScene) {
            this.threeScene.destroy();  // 销毁3D场景
        }
        
        this.cameraManager.stopCamera();  // 停止摄像头
    }
}

// 启动应用
let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new GestureModelingApp();  // 初始化应用
    window.app = app;
});

window.addEventListener('beforeunload', () => {
    if (app) {
        app.destroy();  // 页面卸载时销毁应用
    }
});
