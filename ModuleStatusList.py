from Singleton import singleton
from multiprocessing import Event

@singleton
class ModuleStatusList:
    def __init__(self):
        # These Events are only shareable within a single process unless a multiprocessing.Manager is used.
        # They are still useful for intra-process coordination and for unit tests.
        self.ready_dict = {
            "LocationCalculate.py": Event(),
            "SerialReceiver.py": Event(),
            "Camera.py": Event(),
            "main.py": Event(),
            "receive.py": Event(),
        }
        self.end_profile_dict = {
            "LocationCalculate.py": Event(),
            "SerialReceiver.py": Event(),
            "Camera.py": Event(),
            "main.py": Event(),
            "receive.py": Event(),
        }
        self.end_all_profile = Event()
        self.thread_terminate = False

    def set_ready(self, module_name: str):
        try:
            self.ready_dict[module_name].set()
        except KeyError:
            raise KeyError(f"Module name {module_name} not recognized in ready_dict.")

    def profile_end(self, module_name: str):
        try:
            self.end_profile_dict[module_name].set()
            if all(event.is_set() for event in self.end_profile_dict.values()):
                self.end_all_profile.set()
        except KeyError:
            raise KeyError(f"Module name {module_name} not recognized in end_profile_dict.")

    def terminate(self):
        self.thread_terminate = True

    def module_running(self) -> bool:
        return not self.thread_terminate
