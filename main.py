from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import time
import logging
import threading

from ModuleStatusList import ModuleStatusList as MSL


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
    try:
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
        return jsonify({
            'session_id': app_state.current_session,
            'message': '建模会话开始成功'
        })
        
    except Exception as e:
        logger.error(f"开始建模失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop-modeling', methods=['POST'])
def stop_modeling():
    """结束建模会话"""
    try:
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
        return jsonify({
            'message': '建模会话已结束',
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"停止建模失败: {e}")
        return jsonify({'error': str(e)}), 500

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
        'connected_clients': app_state.connected_clients,
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
    """
    logger.info(f'收到手势指令: {data}')
    
    # 验证数据格式
    if not validate_gesture_data(data):
        emit('error', {'message': '无效的数据格式'}, room=request.sid)
        return
    
    # 只有在建模状态下才转发手势命令
    if app_state.is_modeling:
        emit('gesture_update', data, broadcast=True)
        logger.info(f'转发手势命令: {data.get("command", "unknown")}')
    else:
        logger.warning(f'收到手势命令但建模未开始: {data}')

@socketio.on('hand_coordinates')
def handle_hand_coordinates(data):
    """
    接收实时手部坐标数据
    """
    if app_state.is_modeling:
        emit('hand_update', data, broadcast=True)

@socketio.on('binary_hand_data')
def handle_binary_hand_data(binary_data):
    """
    接收二进制手部数据（高效传输）
    """
    if app_state.is_modeling:
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

    def _server_ready_notifier(host='127.0.0.1', port=5000, path='/health', poll_interval=0.25):
        """Background task: poll the local health endpoint until it responds,
        then mark main.py as ready in ModuleStatusList and notify clients.
        """
        import urllib.request
        import urllib.error

        url = f'http://{host}:{port}{path}'
        module_status_list = MSL()

        while True:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if getattr(resp, 'status', None) in (200, None):
                        try:
                            module_status_list.set_ready('main.py')
                        except Exception:
                            pass
                        # Broadcast server ready to any connected clients
                        try:
                            socketio.emit('server_ready', {
                                'message': 'server_ready',
                                'timestamp': time.time()
                            })
                        except Exception:
                            pass
                        print('🔔 main.py ready — notified ModuleStatusList and clients')
                        return
            except Exception:
                pass
            time.sleep(poll_interval)

    # start notifier in background so it can detect when the server is actually
    # accepting requests; useful when running the server inside a launcher.
    socketio.start_background_task(_server_ready_notifier)

    socketio.run(app,
                host='0.0.0.0',
                port=5000,
                debug=True,
                use_reloader=False,
                allow_unsafe_werkzeug=True)