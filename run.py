# run.py
from app import create_app
from socket_handler import *  # 引入 WebSocket 事件处理

app, socketio = create_app()

if __name__ == '__main__':
    logger.info("启动服务器……")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=5000, 
                 debug=True)