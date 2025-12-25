from os import system, name
from os.path import join, basename
from threading import Thread
from ModuleStatusList import ModuleStatusList as MSL
from runpy import run_path

class ThreadLauncher:
    """
    ThreadLauncher
    Manage launching multiple Python scripts as daemon threads and running a main script in the calling (main) thread.
    Parameters
    - target: iterable of (script_path, title) tuples
        Scripts to launch immediately as daemon threads. Each entry should be a pair where
        `script_path` is a filesystem path (string) to a Python script and `title` is a human-readable label.
    - target_rely_on_main: optional iterable of (script_path, title) tuples (default: None)
        Additional scripts that are intended to rely on the main script. These are started by
        launch_threads after the primary `target` scripts are launched.
    Behavior
    - launch_threads()
        - Starts each script in `target` in its own daemon threading.Thread.
        - Threads are named using os.path.basename(script_path).
        - For each `target` script, launch_threads blocks (polling every 0.05s) until the
          associated module is marked ready by the internal Module Status List (self.module_status_list).
          The module-status check is performed using module_status_list.is_ready(program).
        - After all `target` scripts are launched and reported ready, any `target_rely_on_main` items
          are started as daemon threads as well. These are started without waiting for readiness and
          are not appended to self.threads in the current implementation.
        - Exceptions raised while running scripts inside threads are caught and printed; SystemExit
          is handled specially and reported.
        - Threads are created as daemon threads (they will not prevent Python from exiting).
        - The thread objects for the primary `target` scripts are stored in self.threads as tuples
          (script_path, Thread).
    - launch_main()
        - Runs "main.py" in the calling thread using runpy.run_path(..., run_name="__main__").
        - Exceptions and SystemExit are caught and printed.
    Attributes
    - programs: the provided `target` iterable
    - target_rely_on_main: the provided `target_rely_on_main` iterable (or None)
    - threads: list of (script_path, Thread) tuples for scripts launched from `programs`
    - main_script: reserved attribute (currently unused; initialized to None)
    - module_status_list: instance of MSL used to determine when launched modules are "ready"
    Notes and expectations
    - The code expects an MSL class (module status list) with a method is_ready(program) that returns
      True when the named module is initialized and ready.
    - script_path is passed to runpy.run_path; ensure each path is a valid Python file path.
    - Because threads are daemonized, long-running processes in threads may be terminated abruptly
      when the main thread exits.
    - launch_threads waits for readiness only for entries in `target`. Entries in `target_rely_on_main`
      are started but not awaited and are not recorded in self.threads (current behavior).
    - Caller is responsible for calling launch_threads() and then launch_main() in the desired order.
    Thread-safety
    - This class is intended for sequential use from a single thread (e.g., call launch_threads(), then launch_main()).
    - Access to shared resources between launched scripts should be synchronized by the caller or within the scripts themselves.
    """
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
                    run_path(script_path, run_name = "__main__")
                except SystemExit:
                    print(f"{basename(script_path)} exited (SystemExit)")
                except Exception as e:
                    print(f"Exception in {basename(script_path)}: {e}")

            t = Thread(target = target, daemon = True, name = basename(script_path))
            t.start()
            return t
        
        msl = self.module_status_list.ready_dict
        thread_append = self.threads.append

        for program, title in self.programs:
            script_path = join(program)
            print(f" 启动 {title} ({program}) as thread...")
            t = run_script_in_thread(script_path)
            thread_append((program, t))

            # 等待模块在其线程中标记为就绪
            print(f" 等待 {title} ({program}) 就绪...")
            msl[program].wait()
            print(f" {title} ({program}) ready.")
        
        system('cls' if name == 'nt' else 'clear')
        print(" 所有独立线程已启动")
        
        for program, title in self.target_rely_on_main or []:
            script_path = join(program)
            print(f" 启动 {title} ({program}) as thread(relying on main)...")
            t = run_script_in_thread(script_path)

    def launch_main(self):
        try:
            run_path("main.py", run_name = '__main__')
        except SystemExit:
            print("main.py exited (SystemExit)")
        except Exception as e:
            print(f"Exception while running main.py in main thread: {e}")


    