import os
import time
import threading
import runpy

from ModuleStatusList import ModuleStatusList as MSL
from Profiler import Profiler
from ThreadLauncher import ThreadLauncher

def main():
    print("🚀 启动手势3D建模系统...")

    launcher = ThreadLauncher(target=[
        ("LocationCalculate.py", "数据融合中心"),    # 先启动，绑定端口
        ("SerialReceiver.py", "ToF传感器"),         # 然后启动传感器
        ("Camera.py", "摄像头手部追踪"),             # 再启动摄像头
        ("main.py", "Web服务器")                   # 最后启动识别
        ], target_rely_on_main = [("receive.py", "手势识别")])                  
    launcher.launch_threads()
    launcher.launch_main()
    
    print("✅ 所有程序线程已启动并就绪！")
    print("🌐 请在浏览器打开: http://localhost:5000")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("⏹️ 用户中断启动器，正在退出...")


if __name__ == "__main__":
    cp = Profiler()
    cp.start()
    main()
    cp.end("START.prof")