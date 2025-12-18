from __future__ import annotations

import os
import sys
import time
from os.path import abspath, basename, dirname, join
from multiprocessing import Process
from runpy import run_path

def _run_script(script_path: str, base_dir: str) -> None:
    """Entry point for child processes."""
    try:
        os.chdir(base_dir)
        run_path(script_path, run_name="__main__")
    except SystemExit:
        # allow normal exits
        pass
    except Exception as e:
        # Keep a simple, process-safe error print
        print(f"Exception in {basename(script_path)}: {e}", flush=True)

class ThreadLauncher:
    """Backwards-compatible launcher that now uses multiprocessing instead of threading.

    - Each target script is started in its own OS process (multiprocessing.Process).
    - Readiness waiting via ModuleStatusList is intentionally removed because module-level
      Events are not shared across processes without an explicit Manager.
    - launch_main() starts main.py in its own process and blocks until it exits.
    """

    def __init__(self, target, target_rely_on_main=None):
        self.programs = list(target or [])
        self.target_rely_on_main = list(target_rely_on_main or [])
        self.processes: list[tuple[str, Process]] = []
        self.main_process: Process | None = None
        # ensure scripts run relative to this file's directory
        self.base_dir = dirname(abspath(__file__))

    def _start_process(self, script_rel_path: str) -> Process:
        script_path = script_rel_path
        p = Process(
            target=_run_script,
            args=(script_path, self.base_dir),
            name=basename(script_path),
            daemon=True,
        )
        p.start()
        return p

    def launch_threads(self):
        # start primary targets
        for program, title in self.programs:
            print(f"▶️ 启动 {title} ({program}) as process...")
            p = self._start_process(program)
            self.processes.append((program, p))
            # small stagger to avoid simultaneous heavy imports on startup
            time.sleep(0.05)

        print("✅ 所有独立进程已启动（不再等待 ready 信号）")

        # start rely-on-main targets (also as processes)
        for program, title in self.target_rely_on_main:
            print(f"▶️ 启动 {title} ({program}) as process(relying on main)...")
            p = self._start_process(program)
            self.processes.append((program, p))
            time.sleep(0.05)

    def launch_main(self):
        # Start main.py as its own process and wait.
        print("▶️ 启动 main.py as process...")
        self.main_process = self._start_process("main.py")
        try:
            self.main_process.join()
        except KeyboardInterrupt:
            print("⏹️ 收到 Ctrl+C，正在停止所有子进程...")
            self.terminate_all()
            raise

    def terminate_all(self):
        # Terminate all known processes (best-effort)
        procs = [p for _, p in self.processes]
        if self.main_process is not None:
            procs.append(self.main_process)

        for p in procs:
            if p is None:
                continue
            if p.is_alive():
                try:
                    p.terminate()
                except Exception:
                    pass

        # Give them a moment, then force kill if needed (platform dependent)
        time.sleep(0.2)
        for p in procs:
            if p is None:
                continue
            if p.is_alive():
                try:
                    p.kill()
                except Exception:
                    pass
