后端结构全部重构
# （回头写一个现在的目录结构）
main.py拆分：
    1、__init__.py flask和socketIO的配置
    2、route.py 所有的路由定义（把前端访问操作和后端执行的函数绑定）
    3、LoggingConfig.py 日志配置单独拆了一个py文件（虽然就两行，看这玩意挺新鲜）
    4、state.py 用来储存全局状态相关变量的
    5、Config.py 所有配置统一放一起了
    6、SocketHandler.py处理socket事件逻辑（把事件和函数绑定，事件是后端或者库里定义的，前端会发送）
    7、服务器启动丢到run.py里面了

.idea那个文件是当时pycharm里自动生成的，早该删了
前端三个js一个html暂时没动
所有计算相关的放到utils里面了
原来main.py健康检查和重置接口的俩路由不用了（我们就本机不需要）

SerialReiver.py (相对于最初zyh版本的修改)
PUB改成PUSH(消息顺序严格更可靠，传输速度高一点)
把所有封装进类，然后在run.py里面创建实例并运行
# 别忘了把接收端改掉

原先的camera.py改成了CameraXY.py
换了视频流推送用的方法
（用的WebRTC 使用aiortc库 官方：https://aiortc.readthedocs.io/en/latest/index.html）
此处大改：
前端：index标签替换成WebRTC的，websocket的js添加相关逻辑
后端：拓展websocket功能
接下来一个一个说改动：
index.html 测试函数、测试面板（那个scripts标签下的）删了
main.js里面是定义了两个类，和一个启动，第一个类和视频流相关，做了较大改动
    cameraManager类里stopCamera 和 showCameraError方法用不到了删掉了
# 一会儿把main.js里面的方法列一下
# <!-- 使用 iframe 显示视频流 -->这里改网页的视频显示