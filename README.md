后端结构全部重构
（回头写一个现在的目录结构）
main.py拆分：
    1、__init__.py flask和socketIO的配置
    2、route.py 所有的路由定义（把前端访问操作和后端执行的函数绑定）
    3、LoggingConfig.py 日志配置单独拆了一个py文件（虽然就两行，看这玩意挺新鲜）
    4、state.py 用来储存全局状态相关变量的
    5、Config.py 所有配置统一放一起了
    6、服务器启动丢到run.py里面了

.idea那个文件是当时pycharm里自动生成的，早该删了
前端三个js一个html暂时没动
所有计算相关的放到utils里面了
原来main.py健康检查和重置接口的俩路由不用了（我们就本机不需要）