# route.py
'''
路由：将客户端发来的请求映射到服务器某个处理逻辑（函数）上
flask中，路由将不同的URL路径映射到python函数（视图函数）上
flask提供了一个装饰器来定义路由(@app.route)
'''
from flask import render_templayte, request
# render_template: 用于渲染 HTML 模板，返回 HTML 页面内容给客户端
# jsonify: 用于将 Python 字典或其他数据结构转化为 JSON 格式并返回给客户端
# request: 用来获取客户端发来的 HTTP 请求的数据
from app import app, socketio  # 导入 Flask 实例和 SocketIO 实例(__init__.py里面创建的)
from state import app_state # 全局状态
import time # 时间戳
import logging # 日志

logger = logging.getLogger(__name__) 

'''加载前端网页'''
@app.route('/') # 将URL'/'（首页）映射到index函数（将URL与视图函数绑定，检测到特定路径的请求时调用函数）
def index():
    return render_template('index.html') # 返回templateds文件夹中地index.html页面
# '/'就是默认的开发服务器地址 http://localhost:5000
# 这里定义的index()称为视图函数，视图函数就是与特定 URL 路径（路由）绑定的函数
# 用户访问app.route()括号里的东西的时候，flask就调用相应的视图函数


'''获取应用状态'''
@app.route('/api/status')
def get_status():
    return jsonify({
        'is_modeling': app_state.is_modeling,
        'connected_clients': app_state.connected_clients,
        'current_session': app_state.current_session
    })
# @app.route() 装饰器不仅绑定 URL 和函数，还可以定义可访问的 URL 路径。（这里就是定义）
# 这里括号里/api/status打全了应该是http://localhost:5000/api/status，。
# 用json格式返回数据一是通用，二是标准

@app.route('/api/start-modeling',methods=['POST'])
def start_modeling():
    try:
        if app_state.is_modeling:
            return jsonify({'error':'建模会话已在进行中'}),400
# 当客户端访问 /api/start-modeling 路径并发送一个 POST 请求时，执行 start_modeling 函数
# 已经在建了就报错，状态码400

        app_state.is_modeling = True
        app_state.current_session = f"session_{int(time.time())}"
# 第二行是生成新会话ID，用时间戳保证唯一性

        socketio.emit('modeling_started', {
            'session_id': app_state.current_session,
            'timestamp': time.time()
        })
# 给所有客户端发送websocket消息通知建模会话已经开始

        logger.info(f"建模会话开始: {app_state.current_session}")
        return jsonify({
            'session_id': app_state.current_session,
            'message': '建模会话开始成功'
        })
# 日志+响应，前端拿到响应可以进行一些相应操作

    except Exception as e:
        logger.error(f"开始建模失败: {e}")
        return jsonify({'error': str(e)}), 500
# python语法，和上文try一起的。try内发生错误就会跳转到except执行（异常对象存储在变量e中）


'''结束建模会话'''
@app.route('/api/stop-modeling', methods=['POST'])
def stop_modeling():
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
