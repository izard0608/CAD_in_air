// websocket.js
class WebSocketClient {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 3000;
        
        this.packetStats = {
            received: 0,
            sent: 0,
            lastPacketTime: 0
        };
        
        this.eventHandlers = new Map();
    }
    
    connect() {
        try {
            this.socket = io('http://localhost:5000');
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket连接失败:', error);
            this.handleReconnection();
        }
    }
    
    setupEventHandlers() {
        // 连接事件
        this.socket.on('connect', () => {
            console.log(' 已连接到服务器');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.updateConnectionStatus('online');
            this.socket.emit('client_ready', { timestamp: Date.now() });
        });
        
        this.socket.on('disconnect', () => {
            console.log(' 与服务器断开连接');
            this.isConnected = false;
            this.updateConnectionStatus('offline');
            this.handleReconnection();
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('连接错误:', error);
            this.updateConnectionStatus('error');
        });
        
        // 服务器就绪事件
        this.socket.on('server_ready', (data) => {
            console.log('服务器就绪:', data);
            this.emit('serverReady', data);
        });
        
        this.socket.on('connection_established', (data) => {
            console.log('连接已建立:', data);
            this.emit('connectionEstablished', data);
        });
        
        // 建模控制事件
        this.socket.on('modeling_started', (data) => {
            console.log('建模会话开始:', data);
            this.updateModelingStatus('active', data.session_id);
            this.emit('modelingStarted', data);
        });
        
        this.socket.on('modeling_stopped', (data) => {
            console.log('建模会话结束:', data);
            this.updateModelingStatus('inactive');
            this.emit('modelingStopped', data);
        });
        
        // 数据流事件
        this.socket.on('gesture_update', (data) => {
            this.packetStats.received++;
            this.packetStats.lastPacketTime = Date.now();
            this.emit('gestureUpdate', data);
        });
        
        this.socket.on('hand_update', (data) => {
            this.packetStats.received++;
            this.emit('handUpdate', data);
        });
        
        this.socket.on('binary_hand_update', (binaryData) => {
            this.packetStats.received++;
            this.emit('binaryHandUpdate', binaryData);
        });
        
        // 错误事件
        this.socket.on('error', (error) => {
            console.error('服务器错误:', error);
            this.emit('error', error);
        });
    }
    
    // 事件管理
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }
    
    // 在 WebSocketClient 的 emit 方法中添加
    emit(event, data) {
        console.log(` WebSocketClient 触发事件: ${event}`, data);
        
        if (this.eventHandlers.has(event)) {
            const handlers = this.eventHandlers.get(event);
            console.log(` 找到 ${handlers.length} 个处理器`);
            
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`事件处理错误 (${event}):`, error);
                }
            });
        } else {
            console.log(` 没有找到 ${event} 事件的处理器`);
        }
    }
    
    // 发送消息到服务器
    sendGestureCommand(command) {
        if (!this.isConnected) {
            console.warn('未连接到服务器，无法发送指令');
            return false;
        }
        
        const commandData = {
            ...command,
            timestamp: Date.now(),
            client_id: this.socket.id
        };
        
        this.socket.emit('gesture_command', commandData);
        this.packetStats.sent++;
        return true;
    }
    
    sendHandCoordinates(coordinates) {
        if (!this.isConnected) {
            return false;
        }
        
        const coordinateData = {
            type: 'coordinates',
            coordinates: coordinates,
            timestamp: Date.now(),
            client_id: this.socket.id
        };
        
        this.socket.emit('hand_coordinates', coordinateData);
        this.packetStats.sent++;
        return true;
    }
    
    // 重连处理
    handleReconnection() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('达到最大重连次数，停止重连');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectInterval * this.reconnectAttempts;
        
        console.log(`尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    // UI更新
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = 
                status === 'online' ? '在线' : 
                status === 'offline' ? '离线' : '错误';
                
            statusElement.className = 
                status === 'online' ? 'status-online' : 
                status === 'offline' ? 'status-offline' : 'status-offline';
        }
    }
    
    updateModelingStatus(status, sessionId = null) {
        const statusElement = document.getElementById('modeling-status');
        const sessionElement = document.getElementById('session-id');
        
        if (statusElement) {
            statusElement.textContent = 
                status === 'active' ? '进行中' : '未开始';
            statusElement.className = 
                status === 'active' ? 'status-active' : 'status-inactive';
        }
        
        if (sessionElement) {
            sessionElement.textContent = sessionId || '未开始';
        }
    }
    
    // 工具方法
    getStats() {
        return {
            ...this.packetStats,
            isConnected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts
        };
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
        this.isConnected = false;
    }
}