# init.py 集中管理初始化
'''
1、Flask 应用的创建
2、配置文件的加载（日志，密钥）
3、Flask 扩展（如 SocketIO、CORS）的初始化
'''

from flask import Flask
from flask_socketio import SocketIO # Flask-SocketIO 是一个 Flask 扩展，SocketIO 是 Flask-SocketIO 库中的一个类
from flask_cors import CORS # 跨域资源共享（一种浏览器机制，浏览器为了安全防止一个网站在未经许可的情况下访问另一个网站的数据），一般浏览器默认禁止，但通过CORS，后端可以显式地允许来自特定域的请求
from LoggingConfig import configure_logging # 调用日志配置
from Config import config  # 导入配置类

# 配置日志 调用了LoggingConfig.py里的函数
logger = configure_logging()

#创建flask类，创建名为app的flask实例
app = Flask(__name__,#第一个参数是函数模块或包的名称
            #python中__name__是一个特殊变量，用于表示当前模块的名称
    template_folder='templates',# 告诉flask去哪里找相应资源
    static_folder='static'
)


# 从Config.py里加载flask密钥的配置
app.config.from_object('Config') # 从config里面加载配置

# 将 CORS 设置到 Flask 应用实例 app 上，CORS是什么见上文import处
CORS(app, origins=app.config['CORS_ALLOWED_ORIGINS'])
# 根据配置文件中的 CORS_ALLOWED_ORIGINS 设置 CORS

# 创建SocketIO实例
socketio = SocketIO(app, cors_allowed_origins=app.config['CORS_ALLOWED_ORIGINS'], async_mode=app.config['SOCKET_IO_ASYNC_MODE'])
# 创建 SocketIO 实例时，从配置中读取 cors_allowed_origins 和 async_mode

# 返回 app 和 socketio 对象，方便在其他模块使用
def create_app():
    return app, socketio




