from Singleton import singleton
from threading import Event

@singleton
class ModuleStatusList():
    def __init__(self):
        self.ready_dict = {"LocationCalculate.py": Event(), "SerialReceiver.py": Event(), "Camera.py": Event(), "main.py": Event(), "receive.py": Event()}
    def set_ready(self, module_name):
        try:
            self.ready_dict[module_name].set()
        except KeyError:
            raise KeyError(f"Module name {module_name} not recognized in ready_dict.")