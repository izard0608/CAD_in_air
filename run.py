# run.py
import logging
from SerialReceiver import SerialReceiver
from app import create_app # 创建服务器用
from socketio import SocketIO
from SocketHandler import *  # 引入 WebSocket 事件处理



'''先分块把启动部分写上，顺序回头再调整'''



# 创建服务器（app是init.py里面创建的实例）
app, socketio = create_app()

if __name__ == '__main__':
    logger.info("启动服务器……")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=5000, 
                 debug=True)
    


# 为SerialReceiver.py里面的类创建实例并启动
def main():
    # 设置日志
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 创建并启动SerialReceiver
    receiver = SerialReceiver() # 参数都在SerialReceiver.py赋好值了（config里统一修改）
    try:
        logging.info("启动SerialReceiver")
        receiver.send_data()
    except KeyboardInterrupt:
        logging.info("用户中断程序")
    finally:
        receiver.close()

if __name__ == "__main__":
    main()