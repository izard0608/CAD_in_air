import time
from Profiler import Profiler
from ThreadLauncher import ThreadLauncher

def main():
    print("🚀 启动手势3D建模系统（multiprocessing 进程模式）...")

    launcher = ThreadLauncher(
        target=[
            ("LocationCalculate.py", "数据融合中心"),
            ("SerialReceiver.py", "ToF传感器"),
            ("Camera.py", "摄像头手部追踪"),
        ],
        target_rely_on_main=[
            ("receive.py", "手势识别"),
        ],
    )

    launcher.launch_threads()

    try:
        # main.py 作为独立进程运行（阻塞直到退出）
        launcher.launch_main()
    finally:
        # main.py 退出后，确保其余子进程也退出
        launcher.terminate_all()

if __name__ == "__main__":
    cp = Profiler()
    cp.start()
    try:
        main()
        # 让 profiler 有机会落盘（如果你们的 Profiler 依赖进程内事件，这里只记录 START.py 自己）
        time.sleep(0.1)
    except KeyboardInterrupt:
        print("⏹️ 用户中断启动器，正在退出...")
    finally:
        cp.end(__file__)
