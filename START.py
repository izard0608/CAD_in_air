import subprocess
import time
import sys
import os

from Profiler import Profiler
# import cProfile

def run_command_in_new_terminal(command, title):
    """在新终端窗口中运行命令"""
    if sys.platform == "win32":
        subprocess.Popen(f'start "{title}" cmd /k python {command}', shell=True)
    elif sys.platform == "darwin":
        subprocess.Popen(f'osascript -e \'tell app "Terminal" to do script "python {command}"\'', shell=True)
    else:
        subprocess.Popen(f'gnome-terminal --title="{title}" -- python {command}', shell=True)

def main():
    print("🚀 启动手势3D建模系统...")
    print("注意：请确保摄像头和ToF传感器已连接")
    
    # 按正确顺序启动程序
    programs = [
        ("LocationCalculate.py", "数据融合中心"),  # 先启动，绑定端口
        ("SerialReceiver.py", "ToF传感器"),       # 然后启动传感器
        ("Camera.py", "摄像头手部追踪"),           # 再启动摄像头
        ("main.py", "Web服务器"),               # 最后启动识别
        ("receive.py", "手势识别")                  # Web界面
    ]
    
    print("⏳ 按顺序启动程序...")
    for program, title in programs:
        print(f"▶️ 启动 {title} ({program})...")
        run_command_in_new_terminal(program, title)
        time.sleep(3)  # 给每个程序足够的启动时间
    
    print("✅ 所有程序已启动完成！")
    print("🌐 请在浏览器打开: http://localhost:5000")
    print("💡 使用说明:")
    print("   1. 等待所有终端显示'初始化完成'")
    print("   2. 在网页点击'开始建模'")
    print("   3. 使用手势进行3D建模操作")

if __name__ == "__main__":
    cp = Profiler()
    cp.start()
    main()
    cp.end("START.prof")