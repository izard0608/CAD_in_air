# state.py 储存全局状态
'''
全局状态的意义：
1、不同功能模块需要访问这些信息来进行判断等（比如处理客户端连接时，根据全局状态判断是否开始建模）
2、每次会话独立，通过全局状态“记住”当前会话信息
'''

class AppState: # 定义一个类来管理全局状态
    def __init__(self):
        self.is_modeling = False # 标记建模是否正在进行
        self.current_session = None # 当前建模会话的ID
        self.connected_clients = 0 # 连接的客户端数

# 创建实例
app_state = AppState()
