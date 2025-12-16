from Singleton import singleton

@singleton
class ModuleStatusList():
    def __init__(self):
        self.ready_dict = {"LocationCalculate.py": False, "SerialReceiver.py": False, "Camera.py": False, "main.py": False, "receive.py": False}
    def is_ready(self, module_name):
        return self.ready_dict[module_name]
    def set_ready(self, module_name):
        try:
            self.ready_dict[module_name] = True
        except KeyError:
            raise KeyError(f"Module name {module_name} not recognized in ready_dict.")