import time

from ModuleStatusList import ModuleStatusList as MSL
from Profiler import Profiler
from ThreadLauncher import ThreadLauncher


import zmq
import cv2
import numpy as np
from mediapipe.python.solutions import hands
from asyncio import new_event_loop, set_event_loop, run_coroutine_threadsafe, sleep as aio_sleep
from flask import Flask, Response, request
from flask_socketio import SocketIO
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, VideoStreamTrack


module_status_list = MSL()
is_running = module_status_list.module_running

def main():
    print("🚀 启动手势3D建模系统...")

    launcher = ThreadLauncher(target = [
        ("LocationCalculate.py", "数据融合中心"),    # 先启动，绑定端口
        ("SerialReceiver.py", "ToF传感器"),         # 然后启动传感器
        ("Camera.py", "摄像头手部追踪"),             # 再启动摄像头
        ("main.py", "Web服务器")                   # 最后启动识别
        ], target_rely_on_main = [("receive.py", "手势识别")])                  
    launcher.launch_threads()
    launcher.launch_main()
    
    try:
        while is_running():
            # print("🟢 START.py 运行中，按 Ctrl+C 停止...")
            # print(module_status_list.module_running())
            time.sleep(1)
        module_status_list.end_all_profile.wait()
    except KeyboardInterrupt:
        print("⏹️ 用户中断启动器，正在退出...")
if __name__ == "__main__":
    cp = Profiler()
    cp.start()
    main()
    cp.end(__file__)