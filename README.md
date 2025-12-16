# 性能优化相关

## Profiler类

- ``start()`` 启动Profiler

- ``end(filename)`` 结束Profiler，该函数调用后会自动在**ProfileResults**文件夹内生成三个文件，分别是``.prof``，``.txt``和``.svg``，分别是原始二进制文件，可读版本和火焰图（**注意：调用该函数时``filename``一定要包含后缀``.prof``！！！！**）

- 使用例见``START.py``

## Singleton.py

- 提供了三种实现单例的方式，装饰器``singleton``，元类``SingletonMeta``和简单单例类``Singleton``

- 示例：
```python
    from Singleton import Singleton, singleton, SingletonMeta

    s1 = Singleton("第一个实例")
    s2 = Singleton("第二个实例")

    assert(s1 is s2)    # true, note: 与元类单例不同，简单单例每次调用初始化都会覆盖前一次的内容

    @singleton
    class ConfigurationManager:
        def __init__(self):
            self.settings = {}
            self.load_default_settings()
    
        def load_default_settings(self):
            self.settings = {
                "app_name": "我的应用",
                "version": "1.0.0",
                "debug_mode": True
            }
    
        def get_setting(self, key):
            return self.settings.get(key)
    
        def set_setting(self, key, value):
            self.settings[key] = value
    
    config1 = ConfigurationManager()
    config2 = ConfigurationManager()

    class Logger(metaclass = SingletonMeta):
        def __init__(self, log_file="app.log"):
            self.log_file = log_file
            self.logs = []
            print(f"日志器初始化，文件: {log_file}")
    
        def log(self, message):
            log_entry = f"[{self.get_timestamp()}] {message}"
            self.logs.append(log_entry)
            print(f"记录日志: {log_entry}")
            return log_entry
    
        def get_timestamp(self):
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
        def get_logs(self):
            return self.logs.copy()
    
    logger1 = Logger("application.log")
    logger2 = Logger("different.log")   # 该文件名会被忽略
```

## ThreadLauncher类
- 原先多console的运行方式无法正常使用单例，想要做全局变量只能用sql，所以改了一版多线程的
- 目前除了```START.py```，```main.py```在主线程运行，其余文件都有单独线程
- 改了启动顺序，把```main.py```放在了最后
- 修改了```receive.py```中的服务器连接为等待到```main```启动完毕再尝试连接，适配新的启动顺序
- 考虑到整体结构的改变，后续可能会直接优化掉```zmq```，改用```threading```的信号量或者其他线程库提供的方法
- 懒得写doc，自己去看源文件（）