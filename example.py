import socketio
import time

class GestureClient:
    def __init__(self, server_url='http://localhost:5000'):
        self.sio = socketio.Client()
        self.server_url = server_url
        self.setup_events()
    
    def setup_events(self):
        @self.sio.event
        def connect():
            print("连接到Flask服务器成功")
            
        @self.sio.event  
        def disconnect():
            print("与服务器断开连接")
            
        @self.sio.event
        def error(data):
            print(f"服务器错误: {data}")
    
    def connect(self):
        """连接服务器"""
        try:
            self.sio.connect(self.server_url)
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def send_command(self, command_type, parameters):
        """发送手势指令"""
        data = {
            'command': command_type,
            'parameters': parameters,
            'timestamp': time.time()
        }
        self.sio.emit('gesture_command', data)
        print(f"发送指令: {command_type}")
    
    def send_coordinates(self, coords, gesture_state):
        """发送手部坐标"""
        data = {
            'coordinates': coords,
            'gesture_state': gesture_state,
            'timestamp': time.time() 
        }
        self.sio.emit('hand_coordinates', data)

# 使用示例
if __name__ == "__main__":
    client = GestureClient()
    
    if client.connect():
        # 画线流程示例
        client.send_command('start_drawing_point', {'position': [0, 1, 0]})
        time.sleep(1) # 不一定是1秒，咱得看用户的需求
        
        client.send_command('update_drawing_line', {'position': [1, 1, 1]})  
        time.sleep(1)
        
        client.send_command('finish_drawing_line', {'position': [2, 1, 0]})
        
        # 画长方形示例
        client.send_command('create_rectangle', {
            'normal': [0, 1, 0],
            'corner1': [-1, 0, -1],
            'corner2': [1, 0, 1]
        })