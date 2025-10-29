# main.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import time
import logging
import threading

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static' 
)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局状态
class AppState:
    def __init__(self):
        self.is_modeling = False
        self.current_session = None
        self.connected_clients = 0

app_state = AppState()

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """获取应用状态"""
    return jsonify({
        'is_modeling': app_state.is_modeling,
        'connected_clients': app_state.connected_clients,
        'current_session': app_state.current_session
    })

@app.route('/api/start-modeling', methods=['POST'])
def start_modeling():
    """开始建模会话"""
    if app_state.is_modeling:
        return jsonify({'error': '建模会话已在进行中'}), 400
    
    app_state.is_modeling = True
    app_state.current_session = f"session_{int(time.time())}"
    
    # 通知所有客户端开始建模
    socketio.emit('modeling_started', {
        'session_id': app_state.current_session,
        'timestamp': time.time()
    })
    
    logger.info(f"建模会话开始: {app_state.current_session}")
    return jsonify({'session_id': app_state.current_session})

@app.route('/api/stop-modeling', methods=['POST'])
def stop_modeling():
    """结束建模会话"""
    if not app_state.is_modeling:
        return jsonify({'error': '没有正在进行的建模会话'}), 400
    
    session_id = app_state.current_session
    app_state.is_modeling = False
    app_state.current_session = None
    
    # 通知所有客户端结束建模
    socketio.emit('modeling_stopped', {
        'session_id': session_id,
        'timestamp': time.time()
    })
    
    logger.info(f"建模会话结束: {session_id}")
    return jsonify({'message': '建模会话已结束'})

# WebSocket 事件处理
@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    app_state.connected_clients += 1
    logger.info(f'客户端连接成功，当前连接数: {app_state.connected_clients}')
    
    # 发送当前状态给新连接的客户端
    emit('connection_established', {
        'client_id': request.sid,
        'is_modeling': app_state.is_modeling,
        'current_session': app_state.current_session,
        'timestamp': time.time()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    app_state.connected_clients -= 1
    logger.info(f'客户端断开连接，当前连接数: {app_state.connected_clients}')

@socketio.on('client_ready')
def handle_client_ready(data):
    """客户端准备就绪"""
    logger.info(f'客户端准备就绪: {data}')
    emit('server_ready', {
        'message': '服务器准备就绪，可以开始建模',
        'timestamp': time.time()
    })

# 后端数据接收接口 - 给手势处理同学调用
@socketio.on('gesture_command')
def handle_gesture_command(data):
    """
    接收手势指令数据
    数据格式:
    {
        "type": "command",  # 或 "stream"
        "command": "create_cube",  # 指令类型
        "parameters": {...},       # 指令参数
        "timestamp": 1234567890.123
    }
    """
    logger.info(f'收到手势指令: {data}')
    
    # 验证数据格式
    if not validate_gesture_data(data):
        emit('error', {'message': '无效的数据格式'}, room=request.sid)
        return
    
    # 转发给所有前端客户端
    emit('gesture_update', data, broadcast=True)

@socketio.on('hand_coordinates')
def handle_hand_coordinates(data):
    """
    接收实时手部坐标数据
    数据格式:
    {
        "type": "coordinates",
        "session_id": "session_123",
        "coordinates": {
            "palm_center": [x, y, z],
            "index_tip": [x, y, z],
            "thumb_tip": [x, y, z]
        },
        "gesture_state": "pointing",
        "timestamp": 1234567890.123
    }
    """
    # 只转发给前端，不做复杂处理
    emit('hand_update', data, broadcast=True)

@socketio.on('binary_hand_data')
def handle_binary_hand_data(binary_data):
    """
    接收二进制手部数据（高效传输）
    """
    # 直接转发二进制数据
    emit('binary_hand_update', binary_data, broadcast=True)

def validate_gesture_data(data):
    """验证手势数据格式"""
    required_fields = ['type', 'timestamp']
    if data.get('type') == 'command':
        required_fields.extend(['command'])
    elif data.get('type') == 'coordinates':
        required_fields.extend(['coordinates'])
    
    return all(field in data for field in required_fields)

# 健康检查
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/api/check-reset', methods=['GET'])
def check_reset():
    """前端页面加载时检查并重置会话"""
    # 如果当前没有客户端连接但建模状态为True，说明是孤立会话，需要重置
    if app_state.connected_clients == 0 and app_state.is_modeling:
        old_session = app_state.current_session
        app_state.is_modeling = False
        app_state.current_session = None
        logger.info(f"重置孤立的建模会话: {old_session}")
        
        return jsonify({
            'reset': True,
            'old_session': old_session,
            'message': '已重置孤立会话'
        })
    
    return jsonify({
        'reset': False,
        'is_modeling': app_state.is_modeling,
        'connected_clients': app_state.connected_clients,
        'message': '状态正常'
    })

if __name__ == '__main__':
    logger.info("启动手势3D建模服务器...")
    socketio.run(app, 
                host='0.0.0.0', 
                port=5000, 
                debug=True, 
                allow_unsafe_werkzeug=True)