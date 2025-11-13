# start_all.py
import subprocess
import time
import sys
import os

def run_command_in_new_terminal(command, title):
    """在新终端窗口中运行命令（Windows）"""
    if sys.platform == "win32":
        subprocess.Popen(f'start "{title}" cmd /k python {command}', shell=True)
    elif sys.platform == "darwin":  # macOS
        subprocess.Popen(f'osascript -e \'tell app "Terminal" to do script "python {command}"\'', shell=True)
    else:  # Linux
        subprocess.Popen(f'gnome-terminal --title="{title}" -- python {command}', shell=True)

def main():
    print("启动手势3D建模系统...")
    
    # 启动顺序
    programs = [
        ("main.py", "Web服务器"),
        ("SerialReceiver.py", "传感器数据"),
        ("Camera.py", "摄像头追踪"), 
        ("LocationCalculate.py", "数据融合"),
        ("receive.py", "手势识别")
    ]
    
    for program, title in programs:
        print(f"启动 {title} ({program})...")
        run_command_in_new_terminal(program, title)
        time.sleep(2)  # 给每个程序启动时间
    
    print("所有程序已启动！")
    print("请在浏览器打开: http://localhost:5000")

if __name__ == "__main__":
    main()