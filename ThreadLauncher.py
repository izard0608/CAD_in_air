import os
import threading
from ModuleStatusList import ModuleStatusList as MSL
import runpy
import time

class ThreadLauncher:
    def __init__(self, target, target_rely_on_main = None):
        self.programs = target
        self.target_rely_on_main = target_rely_on_main
        self.threads = []
        self.main_script = None
        self.module_status_list = MSL()
    
    def launch_threads(self):

        def run_script_in_thread(script_path):
            def target():
                try:
                    runpy.run_path(script_path, run_name="__main__")
                except SystemExit:
                    print(f"{os.path.basename(script_path)} exited (SystemExit)")
                except Exception as e:
                    print(f"Exception in {os.path.basename(script_path)}: {e}")

            t = threading.Thread(target=target, daemon=True, name=os.path.basename(script_path))
            t.start()
            return t
        
        msl = self.module_status_list
        thread_append = self.threads.append

        for program, title in self.programs:
            script_path = os.path.join(program)
            print(f"▶️ 启动 {title} ({program}) as thread...")
            t = run_script_in_thread(script_path)
            thread_append((program, t))

            # 等待模块在其线程中标记为就绪
            while not msl.is_ready(program):
                time.sleep(0.05)
            print(f"✅ {title} ({program}) ready.")
        
        for program, title in self.target_rely_on_main or []:
            script_path = os.path.join(program)
            print(f"▶️ 启动 {title} ({program}) as thread(relying on main)...")
            t = run_script_in_thread(script_path)

    def launch_main(self):
        try:
            runpy.run_path("main.py", run_name = '__main__')
        except SystemExit:
            print("main.py exited (SystemExit)")
        except Exception as e:
            print(f"Exception while running main.py in main thread: {e}")


    