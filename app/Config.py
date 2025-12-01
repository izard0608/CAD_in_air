# Config.py 配置文件

# 手指标号
LEFT_THUMB_FINGER  =  [0, 1, 2]
LEFT_FORE_FINGER   =  [3, 4, 5]
RIGHT_THUMB_FINGER =  [6, 7, 8]
RIGHT_FORE_FINGER  =  [9, 10, 11]

# 相关阈值
TIME_THRESHOLD = 0.8
MAXLEN = 30
POSITION_THRESHOLD = 0.08
DIS_ON = 0.04
DIS_OFF = 0.08
MOVE_EPS = 0.02
DEGREE_THRESHOLD = 60.0
DIS_THRESHOLD = 2
LOG_EVERY_N = 10
HISTORY_N = 200
COMMAND_COOLDOWN = 0.5

# 服务器地址
SERVER_URL = 'http://localhost:5000'

# 其他配置
class Config:
    SECRET_KEY = 'This-is-a-secret-key' # flask用于加密会话的密钥
    CORS_ALLOWED_ORIGINS = "*" # 表示允许来自 所有域名 的跨域请求（"*" 是通配符，表示允许任何来源的请求。）
    SOCKET_IO_ASYNC_MODE = 'threading' # 异步模式，表示 Flask-SocketIO 使用 多线程 模式来处理客户端连接和事件。（"threading"表示每个事件都会在单独的线程中处理）


# SocketHandler.py中事件、函数一览
'''
#（为了前端对应和看着方便）----------------------------------------------------------------------------
# 事件配置：集中管理客户端与服务器之间所有的 WebSocket 事件
# 这些事件会在客户端与服务器之间的通信中触发。
EVENTS = {
    "connect": "客户端连接事件",  # 客户端成功连接到服务器时触发
    "disconnect": "客户端断开连接事件",  # 客户端断开与服务器的连接时触发
    "client_ready": "客户端准备就绪事件",  # 客户端表示已准备好并可以开始建模时触发
    "gesture_command": "处理手势指令数据",  # 处理客户端发送的手势指令事件
    "hand_coordinates": "接收手部坐标数据",  # 处理客户端发送的手部坐标数据事件
    "binary_hand_data": "接收二进制手部数据"  # 处理客户端发送的二进制手部数据事件
}

# 函数配置：集中管理每个事件对应的处理函数
# 每个事件都有一个对应的函数来处理事件的数据。
FUNCTIONS = {
    "handle_connect": "处理客户端连接的函数",  # 处理客户端连接事件的函数
    "handle_disconnect": "处理客户端断开连接的函数",  # 处理客户端断开连接事件的函数
    "handle_client_ready": "处理客户端准备就绪的函数",  # 处理客户端准备就绪事件的函数
    "handle_gesture_command": "处理手势指令的函数",  # 处理客户端发送的手势指令的函数
    "handle_hand_coordinates": "处理手部坐标的函数",  # 处理客户端发送的手部坐标数据的函数
    "handle_binary_hand_data": "处理二进制手部数据的函数"  # 处理客户端发送的二进制手部数据的函数
    # 下面这个虽然不是事件触发的函数但也放进来了（是SocketHandler.py里的函数）
    "validate_gesture_data": "验证手势数据格式的函数"  # 验证数据格式
}
-----------------------------------------------------------------------------------------------
'''














