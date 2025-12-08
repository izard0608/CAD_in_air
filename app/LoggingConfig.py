# LoggingConfig 日志配置
'''
单开了一个文件配置是因为之前不认识这个，打算多写点注释
日志级别的定义从低到高分别是:DEBUG < INFO < WARNING < ERROR < CRITICAL
logger对象有多个方法，比如logger.info(),logger.debug()记录不同级别日志信息
每个函数后面加一个日志输出可以监控程序行为，方便调试
'''
import logging

def configure_logging():
    logging.basicConfig(level=logging.INFO) 
        # 日志的基本配置，配置最低记录级别位INFO。此配置是全局性的。
    logger = logging.getLogger(__name__) 
        # 创建一个日志对象，使用当前模块名作为日志名。用__name__保证每个模块有一个单独的logger实例。
        