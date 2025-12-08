# app.sockets.SocketHandler.py  socketIO相关事件的逻辑，创建websocket服务器
'''
Socket 事件逻辑是指在 WebSocket 连接过程中，客户端和服务器之间进行双向通信时，定义一些事件来处理特定的操作。
本程序用到的事件、函数为了看着方便在Config.py里一起列出来了
'''

from flask_socketio import SocketIO, emit
from models import app_state
import time
import logging # 日志
from app import socketio  # 引入创建好的 SocketIO 实例
# 这里的app不是那个名为app的flask实例，而是整个叫app的模块（__init__上一级那个）

# 配置日志
logger = logging.getLogger(__name__) # 看样子是每个


'''事件1：客户端连接'''
@socketio.on('connect') # 事件装饰器，将某个函数绑定到特定事件上。connect是socketIO库定义的一个事件,这里是说连上的时候会调用handle_connect函数
def handle_connect(): # 定义名为handle_connect的事件处理函数
    app_data.connected_clients +=1 # connected_clients是state.py全局状态里面定义的。一个新客户端连接的时候，connected_clients会加一。
    logger.info(f'客户端连接成功，当前连接数: {app_state.connected_clients}')

    emit('connection_established', { # 向客户端发送一个事件。'connection_established'是事件名称。emit 是 Flask-SocketIO 提供的一个函数，用来从服务器向客户端发送事件和数据。
        'client_id': request.sid, # 当前客户端的唯一会话 ID，sid 是 SocketIO 为每个连接分配的一个唯一标识符。
        'is_modeling': app_state.is_modeling, # 当前是否正在进行建模
        'current_session': app_state.current_session, # 当前的建模会话 ID（如果有的话）
        'connected_clients': app_state.connected_clients, # 当前连接的客户端数目，表示有多少个客户端连接到了服务器。
        'timestamp': time.time() # 时间戳
    })


'''事件2：客户端断开连接'''
@socketio.on('disconnect')
def handle_disconnect():
    app_state.connected_clients -= 1
    logger.info(f'客户端断开连接，当前连接数: {app_state.connected_clients}')


'''事件3：客户端准备就绪'''
@socketio.on('client_ready')
def handle_client_ready(data):
    logger.info(f'客户端准备就绪: {data}')
    emit('server_ready', {
        'message': '服务器准备就绪，可以开始建模',
        'timestamp': time.time()
    })

# 以上三个事件(connect、disconnect、clien_ready)socketIO定义的事件，是由 Socket.IO 客户端和服务器在连接和断开时自动触发的。
# 以下几个事件是在前端WebSocketClient.js里面定义的，后端监听到事件就调用相应函数

'''事件4：接收手势指令数据'''
@socketio.on('gesture_command') # 监听客户端发送的gesture_command事件
def handle_gesture_command(data): # data参数代表客户端传来的数据
    logger.info(f'收到手势指令: {data}')
    
    if not validate_gesture_data(data):  # 验证数据格式（该函数在下文定义）
        emit('error', {'message': '无效的数据格式'}, room=request.sid)  # 数据格式不正确时发送错误信息
        return

    if app_state.is_modeling: # app_state.is_modeling在全局状态里面定义的，表示是否在建模
        emit('gesture_update', data, broadcast=True) # 向所有连接的客户端广播一个 gesture_update 事件，传递更新的手势数据（data）（让所有客户端都看到建模结果）
        logger.info(f'转发手势命令: {data.get("command", "unknown")}')
    else:
        logger.warning(f'收到手势命令但建模未开始: {data}')


'''事件5：接收手部坐标数据'''
@socketio.on('hand_coordinates')
def handle_hand_coordinates(data):
    if app_state.is_modeling:
        emit('hand_update', data, broadcast=True)


'''事件6：接收二进制手部数据（说是传输能更高效）'''
@socketio.on('binary_hand_data')
def handle_binary_hand_data(binary_data):
     if app_state.is_modeling:
        emit('binary_hand_update', binary_data, broadcast=True)


# 事件4中验证格式的函数定义
def validate_gesture_data(data):
    required_fields = ['type', 'timestamp']
    if data.get('type') == 'command':
        required_fields.extend(['command'])
    elif data.get('type') == 'coordinates':
        required_fields.extend(['coordinates'])
    
    return all(field in data for field in required_fields)   # 检查是否包含了所有必须字段




