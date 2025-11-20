// static/js/main.js
class CameraManager {
    constructor() {
        this.videoElement = null;
        this.overlayElement = null;
        this.isActive = false;
    }
    
    async startCamera() {
        try {
            console.log('🎥 连接视频流...');
            
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
            console.log('✅ 视频流连接设置完成');
            
            return true;
            
        } catch (error) {
            console.error('❌ 视频流连接失败:', error);
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
                    <div>📷 视频流已停止</div>
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
                        ❌ 无法连接视频流
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
        this.cameraManager = new CameraManager();
        this.websocketClient = new WebSocketClient();
        this.threeScene = null;
        this.isModeling = false;
        this.currentSession = null;
        
        this.init();
    }
    
    async init() {
        console.log('🎮 初始化手势3D建模应用...');
        
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
        
        console.log('✅ 手势3D建模应用初始化完成');
    }
    
    setupUIEvents() {
        const startBtn = document.getElementById('btn-start');
        const stopBtn = document.getElementById('btn-stop');
        const resetBtn = document.getElementById('btn-reset');
        
        // 移除旧的事件监听器
        startBtn.replaceWith(startBtn.cloneNode(true));
        stopBtn.replaceWith(stopBtn.cloneNode(true));
        resetBtn.replaceWith(resetBtn.cloneNode(true));
        
        // 重新获取元素
        const newStartBtn = document.getElementById('btn-start');
        const newStopBtn = document.getElementById('btn-stop');
        const newResetBtn = document.getElementById('btn-reset');
        
        // 建模控制按钮
        newStartBtn.addEventListener('click', () => {
            console.log('🟢 开始建模按钮被点击');
            this.startModeling();
        });
        
        newStopBtn.addEventListener('click', () => {
            console.log('🔴 停止建模按钮被点击');
            this.stopModeling();
        });
        
        newResetBtn.addEventListener('click', () => {
            console.log('🔄 重置场景按钮被点击');
            this.resetScene();
        });
    }
    
    setupWebSocketEvents() {
        console.log('🔧 设置WebSocket事件监听');
    
        // 连接状态事件
        this.websocketClient.on('connectionEstablished', (data) => {
            console.log('✅ WebSocket连接已建立');
            this.updateClientCount(data.connected_clients);
            this.updateConnectionStatus('online');
        });
        
        // 建模控制事件
        this.websocketClient.on('modelingStarted', (data) => {
            console.log('🎯 收到建模开始事件:', data);
            this.onModelingStarted(data);
        });
        
        this.websocketClient.on('modelingStopped', (data) => {
            console.log('🎯 收到建模结束事件:', data);
            this.onModelingStopped(data);
        });
        
        // 手势数据事件
        this.websocketClient.on('gestureUpdate', (data) => {
            console.log('🎯 收到手势命令:', data.command);
            this.handleGestureCommand(data);
        });
        
        // 错误处理
        this.websocketClient.on('error', (error) => {
            console.error('WebSocket错误:', error);
            this.showError('系统错误: ' + error.message);
        });
    }
    
    async startModeling() {
        console.log('🟢 startModeling 方法开始执行');
        
        if (this.isModeling) {
            console.log('❌ 建模已在进行中，跳过');
            this.showNotification('建模会话已在进行中', 'warning');
            return;
        }
        
        try {
            console.log('📡 发送开始建模请求...');
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
            console.log('✅ 建模会话启动成功:', data);
            
        } catch (error) {
            console.error('❌ 启动建模失败:', error);
            this.showError('启动建模失败: ' + error.message);
        }
    }
    
    async stopModeling() {
        try {
            console.log('📡 发送停止建模请求...');
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
            console.log('✅ 建模会话停止成功:', data);
            
        } catch (error) {
            console.error('❌ 停止建模失败:', error);
            this.showError('停止建模失败: ' + error.message);
        }
    }
    
    onModelingStarted(data) {
        this.isModeling = true;
        this.currentSession = data.session_id;
        
        // 更新UI状态
        document.getElementById('btn-start').disabled = true;
        document.getElementById('btn-stop').disabled = false;
        document.getElementById('session-id').textContent = this.currentSession;
        
        this.updateModelingStatus('active');
        this.updateOperationHint('手势建模已开始，请使用手势进行3D建模操作');
        this.showNotification('建模会话已开始', 'success');
        
        console.log('✅ 前端建模状态已更新: 开始');
    }
    
    onModelingStopped(data) {
        this.isModeling = false;
        this.currentSession = null;
        
        // 更新UI状态
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-stop').disabled = true;
        document.getElementById('session-id').textContent = '未开始';
        
        this.updateModelingStatus('inactive');
        this.updateOperationHint('建模会话已结束，点击"开始建模"重新开始');
        this.showNotification('建模会话已结束', 'info');
        
        console.log('✅ 前端建模状态已更新: 结束');
    }
    
    handleGestureCommand(data) {
        if (!this.isModeling) {
            console.log('⚠️ 收到手势命令但建模未开始');
            return;
        }
        
        console.log('🟢 处理手势命令:', data.command);
        
        if (!this.threeScene) {
            console.error('❌ ThreeScene未初始化');
            return;
        }
        
        try {
            switch(data.command) {
                case 'start_drawing_point':
                    console.log('🎯 创建点:', data.parameters.position);
                    this.threeScene.createPoint(data.parameters);
                    break;
                case 'start_drawing_line':
                    console.log('📏 开始画线:', data.parameters.position);
                    this.threeScene.startDrawingLine(data.parameters);
                    break;
                case 'update_drawing_line':
                    this.threeScene.updateDrawingLine(data.parameters);
                    break;
                case 'finish_drawing_line':
                    console.log('✅ 完成画线:', data.parameters.position);
                    this.threeScene.finishDrawingLine(data.parameters);
                    break;
                case 'create_plane':
                    console.log('🟦 创建平面');
                    this.threeScene.createRectangle({
                        corner1: data.parameters.start_position,
                        corner2: data.parameters.end_position,
                        normal: data.parameters.normal_vector,
                        color: 0x3498db,
                        opacity: 0.7
                    });
                    break;
                default:
                    console.log('未知命令:', data.command);
            }
        } catch (error) {
            console.error('❌ 处理手势命令失败:', error);
        }
    }
    
    resetScene() {
        if (this.threeScene) {
            this.threeScene.clearScene();
            this.showNotification('场景已重置', 'info');
        }
    }
    
    // UI更新方法
    updateOperationHint(hint) {
        const hintElement = document.getElementById('operation-hint');
        if (hintElement) {
            hintElement.textContent = hint;
        }
    }
    
    updateClientCount(count) {
        const countElement = document.getElementById('client-count');
        if (countElement) {
            countElement.textContent = count;
        }
    }
    
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = status === 'online' ? '在线' : '离线';
            statusElement.className = status === 'online' ? 'status-online' : 'status-offline';
        }
    }
    
    updateModelingStatus(status) {
        const statusElement = document.getElementById('modeling-status');
        if (statusElement) {
            statusElement.textContent = status === 'active' ? '进行中' : '未开始';
            statusElement.className = status === 'active' ? 'status-active' : 'status-inactive';
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
                    hintElement.textContent = originalText;
                }
            }, 3000);
        }
    }
    
    showError(message) {
        this.showNotification('❌ ' + message, 'error');
    }
    
    // 销毁方法
    destroy() {
        if (this.websocketClient) {
            this.websocketClient.disconnect();
        }
        
        if (this.threeScene) {
            this.threeScene.destroy();
        }
        
        this.cameraManager.stopCamera();
    }
}

// 启动应用
let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new GestureModelingApp();
    window.app = app;
});

window.addEventListener('beforeunload', () => {
    if (app) {
        app.destroy();
    }
});
