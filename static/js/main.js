class CameraManager {
    constructor() {
        this.stream = null;
        this.isActive = false;
    }
    
    async startCamera() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                } 
            });
            
            const videoElement = document.getElementById('camera-video');
            if (videoElement) {
                videoElement.srcObject = this.stream;
                
                // 隐藏覆盖层
                const overlay = document.getElementById('camera-overlay');
                if (overlay) {
                    overlay.style.display = 'none';
                }
            }
            
            this.isActive = true;
            console.log('✅ 摄像头启动成功');
            return true;
            
        } catch (error) {
            console.error('❌ 摄像头启动失败:', error);
            this.showCameraError(error);
            return false;
        }
    }
    
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        this.isActive = false;
    }
    
    showCameraError(error) {
        const overlay = document.getElementById('camera-overlay');
        if (overlay) {
            overlay.innerHTML = `
                <div class="overlay-text">
                    <div>❌ 摄像头错误</div>
                    <div style="font-size: 0.8em; margin-top: 10px;">${error.message}</div>
                    <button onclick="location.reload()" style="margin-top: 10px; padding: 5px 10px;">重试</button>
                </div>
            `;
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
    
    init() {
        // 初始化UI事件
        this.setupUIEvents();
        
        // 初始化WebSocket连接
        this.websocketClient.connect();
        
        // 初始化3D场景
        this.threeScene = new ThreeScene('modeling-scene');
        
        // 设置WebSocket事件监听
        this.setupWebSocketEvents();
        
        // 初始化摄像头
        this.initCamera();
        
        console.log('🎮 手势3D建模应用初始化完成');
    }
    
    setupUIEvents() {
        // 建模控制按钮
        document.getElementById('btn-start').addEventListener('click', () => {
            this.startModeling();
        });
        
        document.getElementById('btn-stop').addEventListener('click', () => {
            this.stopModeling();
        });
        
        document.getElementById('btn-reset').addEventListener('click', () => {
            this.resetScene();
        });
        
        // 工具按钮
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleToolSelection(e.target.dataset.tool);
            });
        });
        
        // 窗口大小调整
        window.addEventListener('resize', () => {
            if (this.threeScene) {
                this.threeScene.onResize();
            }
        });
    }
    
    setupWebSocketEvents() {
        // 连接状态事件
        this.websocketClient.on('connectionEstablished', (data) => {
            this.updateClientCount(data.connected_clients);
        });
        
        // 建模控制事件
        this.websocketClient.on('modelingStarted', (data) => {
            this.onModelingStarted(data);
        });
        
        this.websocketClient.on('modelingStopped', (data) => {
            this.onModelingStopped(data);
        });
        
        // 手势数据事件
        this.websocketClient.on('gestureUpdate', (data) => {
            this.handleGestureCommand(data);
        });
        
        this.websocketClient.on('handUpdate', (data) => {
            this.handleHandCoordinates(data);
        });
        
        this.websocketClient.on('binaryHandUpdate', (binaryData) => {
            this.handleBinaryHandData(binaryData);
        });
        
        // 错误处理
        this.websocketClient.on('error', (error) => {
            this.showError('系统错误: ' + error.message);
        });
    }
    
    async startModeling() {
        await this.cameraManager.startCamera();
        try {
            const response = await fetch('/api/start-modeling', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})  // 添加空的请求体
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('建模会话启动成功:', data);
            
        } catch (error) {
            console.error('启动建模失败:', error);
            this.showError('启动建模失败: ' + error.message);
        }
    }
    
    async stopModeling() {
        this.cameraManager.stopCamera();
        try {
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
            this.showError('停止建模失败: ' + error.message);
        }
    }
    
    onModelingStarted(data) {
        this.isModeling = true;
        this.currentSession = data.session_id;
        
        // 更新UI状态
        document.getElementById('btn-start').disabled = true;
        document.getElementById('btn-stop').disabled = false;
        
        this.updateOperationHint('手势建模已开始，请使用手势进行3D建模操作');
        this.showNotification('建模会话已开始', 'success');
    }
    
    onModelingStopped(data) {
        this.isModeling = false;
        this.currentSession = null;
        
        // 更新UI状态
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-stop').disabled = true;
        
        this.updateOperationHint('建模会话已结束，点击"开始建模"重新开始');
        this.showNotification('建模会话已结束', 'info');
    }
    
    handleGestureCommand(data) {
        if (!this.isModeling) return;
        
        console.log('收到手势命令:', data);
        
        // 直接调用ThreeScene，不经过复杂的逻辑
        switch(data.command) {
            case 'start_drawing_point':
                this.threeScene.startDrawingLine(data.parameters);
                break;
            case 'update_drawing_line':
                this.threeScene.updateDrawingLine(data.parameters);
                break;
            case 'finish_drawing_line':
                this.threeScene.finishDrawingLine(data.parameters);
                break;
            case 'create_rectangle':
                this.threeScene.createRectangle(data.parameters);
                break;
            default:
                console.log('未知命令:', data.command);
        }
}
    
    handleHandCoordinates(data) {
        if (!this.isModeling) return;
        
        // 更新手势状态
        if (data.gesture_state) {
            this.updateGestureState(data.gesture_state);
        }
        
        // 这里可以添加手部坐标的可视化
        // 例如：更新3D场景中的手部光标位置
    }
    
    handleBinaryHandData(binaryData) {
        if (!this.isModeling) return;
        
        // 处理二进制手部数据
        // 需要和后端同学协商数据格式
        console.log('收到二进制手部数据:', binaryData);
    }
    
    handleToolSelection(tool) {
        // 更新工具按钮状态
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeBtn = document.querySelector(`[data-tool="${tool}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
        
        // 这里可以添加工具选择逻辑
        console.log('选择工具:', tool);
    }
    
    resetScene() {
        if (this.threeScene) {
            this.threeScene.clearScene();
            this.showNotification('场景已重置', 'info');
        }
    }
    
    async initCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: 640, 
                    height: 480 
                } 
            });
            
            const videoElement = document.getElementById('camera-video');
            videoElement.srcObject = stream;
            
            // 隐藏覆盖层
            const overlay = document.getElementById('camera-overlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
            
        } catch (error) {
            console.error('摄像头初始化失败:', error);
            this.showError('无法访问摄像头: ' + error.message);
        }
    }
    
    // UI更新方法
    updateGestureState(state) {
        const stateElement = document.getElementById('gesture-state');
        if (stateElement) {
            stateElement.textContent = this.getGestureStateText(state);
        }
    }
    
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
    
    updatePacketStats() {
        const stats = this.websocketClient.getStats();
        const packetElement = document.getElementById('packet-count');
        const latencyElement = document.getElementById('latency');
        
        if (packetElement) {
            packetElement.textContent = stats.received;
        }
        
        if (latencyElement) {
            const latency = Date.now() - stats.lastPacketTime;
            latencyElement.textContent = latency + 'ms';
        }
    }
    
    getGestureStateText(state) {
        const stateMap = {
            'pointing': '👆 指向',
            'pinching': '🤏 捏合',
            'open': '🖐️ 张开',
            'fist': '✊ 握拳',
            'create_cube': '⬜ 创建立方体',
            'create_sphere': '🔵 创建球体',
            'create_cylinder': '🟪 创建圆柱',
            'create_line': '📐 创建线条',
            'processing': '🔄 处理中'
        };
        
        return stateMap[state] || state;
    }
    
    showNotification(message, type = 'info') {
        // 简单的通知实现，可以替换为更完整的通知系统
        console.log(`[${type}] ${message}`);
        
        // 这里可以添加UI通知显示
        const hintElement = document.getElementById('operation-hint');
        if (hintElement) {
            const originalText = hintElement.textContent;
            hintElement.textContent = message;
            
            // 3秒后恢复原提示
            setTimeout(() => {
                hintElement.textContent = originalText;
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
        
        // 停止摄像头流
        const videoElement = document.getElementById('camera-video');
        if (videoElement && videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
    }
}

// 启动应用
let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new GestureModelingApp();
});

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    if (app) {
        app.destroy();
    }
});