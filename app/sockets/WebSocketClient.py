# app.sockets.WebSocketClient.py
# 创建一个连接到 Flask 服务器的 WebSocket 客户端实例。
# 处理与服务器之间的实时通信。

'''
sockets文件夹下两个文件区别：
SocketHandler.py 中，SocketIO实例的代码是用来创建WebSocket服务器
而这里是创建 WebSocket 客户端
'''

import socketio 
import logging

# 配置日志
logger = logging.getLogger(__name__) 

def create_client(server_url='http://localhost:5000'):
    sio = socketio.Client()

    @sio.event # 这块语法和SocketHandler.py里面那个差不多
    def connect():
        logger.info("连接到Flask服务器")

    @sio.event # sio是socketio.Client()的实例，.event是sio类的一个方法，用来注册事件处理函数
    def disconnect():
        logger.info("与服务器断开连接")

    sio.server_url = server_url
    return sio

