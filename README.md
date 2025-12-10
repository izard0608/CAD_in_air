# 项目重构
#### **项目进行了大概的重构（虽然有一些暂时照搬上来了），主要是把多个功能堆在一起的程序拆开并加上详细注释，以及明晰每个程序的作用。我在下面的项目结构上标了哪些要改和改什么，哪些不用管，以及每个程序是干什么的**
## 接下来主要任务
#### 1、手势逻辑重写，可能要重新想逻辑，也可能要加新的东西
#### 2、视频流试试改用WebRTC
#### 3、要把项目跑通，理清楚整个运行的时候先后发生了什么数据怎么传的哪里出了问题
## 现在的项目结构
####  `高亮`：需要更改或重写的程序（剩下的就不用动不用改了）
####  *（ur）*：跟原来几乎一模一样的部分（大概率瓜分一下然后手改了）
####  后面的注释除了写程序是干什么的，还尽可能记录一些能想到的重写需要注意的地方

CAD_in_Air  
├── `run.py`        启动所有程序（启动顺序、有些实例已经创建了有些要在这里创建、最开始导入别忘了或写错（是的我准备跑跑看这个的时候一堆模块导入写错了））  
│  
├── app/  
│   ├── _init__.py      flask服务器  
│   ├── config.py       配置  
│   ├── state.py        记录全局状态的，有is_modeling标记建模是否正在进行，current_session当前建模会话的ID，connected_clients连接的客户端数  
│   ├── LoggingConfig.py        日志配置  
│   │  
│   ├── receivers/  
│   │   ├── `CameraXY.py`*（ur）*       原来的Camera.py，写了两个类，VideoStreamServer处理MPJEG视频流，CameraHandTracker使用mediapipe读取关节坐标并标注  
│   │   └── SerialReceiver.py           把原来的封装到类里，基本没动  
│   │  
│   ├── services/  
│   │   ├── `GestureBackend.py`*（ur）*     手势识别逻辑，还是原来的  
│   │  
│   ├── sockets/  
│   │   ├── SocketHandler.py        websocket服务器，其实好像是一些全局socket事件逻辑（连接建模结束什么的）  
│   │   ├── SocketRoutes.py         路由，就是把前端请求什么的事件绑定到后端视图函数上  
│   │   └── WebSocketClient.py      websocket客户端  
│   │  
│   └── utils/  
│       ├── KalmanFilter.py*（ur）*         没动  
│       ├── LocationCalculate.py*（ur）*    xy和z融合形成坐标，也没动  
│       └── MathUtils.py*（ur）*            一些数学计算用到的工具函数  
│  
├── static/  
│   ├── css/  
│   │   └── style.css*（ur）*   
│   │  
│   └── js/  
│       ├── `main.js`       改了下又该回去了（不过测试的还是删了需要再加回来）两个类，一个处理视频流一个处理socket逻辑  
│       ├── ThreeScene.js*（ur）*       建模场景渲染  
│       └── WebSocketClient.js*（ur）*      前端websocket逻辑  
│  
└── templates/  
    └── `index.html`        前端网页，删了点多余的东西别的没改  
  
  
### 下面是边改边随手记的东西，和一些之前不会的东西的笔记，其实没什么看的必要
bug极其多，主要是视频流用的webRTC不知道以后能不能参考。后面出于先跑通的想法，改回传统的了  
main.py拆分：  
    1、__init__.py flask和socketIO的配置  
    2、route.py 所有的路由定义（把前端访问操作和后端执行的函数绑定）  
    3、LoggingConfig.py 日志配置单独拆了一个py文件（虽然就两行，看这玩意挺新鲜）  
    4、state.py 用来储存全局状态相关变量的  
    6、SocketHandler.py处理socket事件逻辑（把事件和函数绑定，事件是后端或者库里定义的，前端会发送）  
    7、服务器启动丢到run.py里面了  
  
.idea那个文件是当时pycharm里自动生成的，早该删了  
前端三个js一个html暂时没动  
所有计算相关的放到utils里面了  
原来main.py健康检查和重置接口的俩路由不用了（我们就本机不需要）  
  
SerialReiver.py (相对于最初zyh版本的修改)  
PUB改成PUSH(消息顺序严格更可靠，传输速度高一点)  
把所有封装进类，然后在run.py里面创建实例并运行  
希望别忘了把接收端改掉  
  
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
  
回头最好把main.js里面的方法列一下  
<!-- 使用 iframe 显示视频流 -->这里改网页的视频显示  
记录一些之后需要改动的逻辑问题  
摄像头，识别是一个更大的画面而前端显示只截取了一个比较小的画面（有些操作用户看不见自己的手也实现了）  
WebRTC有点复杂有一堆必须步骤我直接丢给ai了（）晚点单独分个人出来研究一下 main.js index.html cameraXY里都有  
新修改：把routes重命名为SocketRoutes因为它处理的都是socket的路由  
  
##### 1、python特殊变量name  
  
    ```python
    # test.py
    def greet():
        print("Hello from the test module!")

    if __name__ == "__main__":
        print("This is the main module.")
        greet()
    ```

    ```python
    # main.py
    import test
    test.greet()
    ```
  
简单来说，在a程序里写了__name__这个变量  
1.在执行a程序的时候__name__就等于main  
2.在b程序里import了a并调用含__name__的函数时，__name__就等于a  
  
##### 2、python的缩进
缩进相同的区域表示一个代码块  
  
##### 3、模块：通常就是一个.py结尾的文件（集合了函数、类、变量等）
（其实那些库也就是包含python代码的文件）  
  
##### 4、日志
用于跟踪执行过程，记录关键信息，方便调试  
本项目中例子  
```python
# 配置日志
logging.basicConfig(level=logging.INFO) # 日志级别
logger = logging.getLogger(__name__)
```
日志级别的定义从低到高分别是：  
DEBUG：最详细的信息，通常只用于开发阶段，记录一些开发者关注的调试信息。  
INFO：记录正常的运行信息，如系统启动、用户登录等。  
WARNING：记录警告信息，通常是系统正常运行时的小问题。  
ERROR：记录错误信息，表示程序出现异常，不能继续正常运行。  
CRITICAL：严重错误，程序不能继续运行，通常意味着需要立即干预。  
  
##### 5、解耦
减少不同模块间的依赖，增加可维护性  
  
##### 6、类、方法
类：面向对象编程的基础  
方法：类的一部分，类中定义的方法  
  
类就像是 蓝图 或 模板，它定义了对象的属性和行为。用类来定义对象的共性，再通过类创建多个具体的对象。可以把类理解为一组有共同特征的对象的模板。类的方法：描述对象可以做的事情。方法是 类的函数，它是类的组成部分，用来定义对象的行为。  
在 Python 中，方法的第一个参数是 self，它代表 当前对象（实例）。你每次用类创建一个对象时，方法都能通过 self 访问到这个对象的属性和行为。self 就是一个指向当前对象的指针。在类里面，self 让方法知道它应该操作哪一个对象。  
self 只在类的方法内部使用，用来 引用类的当前对象。  
  
##### 7、API、路由
前端和后端之间进行通信的桥梁。它定义了一些规则，允许前端请求后端提供的数据，或者让前端执行一些操作。  
通常由 HTTP请求 和 相应 构成  
HTTP请求：  
GET 请求 用来从服务器获取数据，比如获取用户信息、应用状态等。  
POST 请求 用来向服务器发送数据，比如提交表单数据、创建新资源等。  
路由：一种将 URL 地址 映射到 后端函数 的方式。当你在浏览器中访问一个 URL 时，后端通过 路由 来决定如何响应请求。  
  
1. Flask 路由（@app.route）和视图函数  
• 视图函数是你定义的函数，负责处理特定 URL 请求时执行的操作。Flask 通过 @app.route() 装饰器将 URL 和视图函数绑定。例如，@app.route('/api/status') 将访问 /api/status 路径的请求绑定到 get_status 函数。  
• @app.route() 装饰器不仅绑定 URL 和函数，还可以定义可访问的 URL 路径。例如：@app.route('/api/status') 会在用户访问 http://localhost:5000/api/status 时触发对应的视图函数。  
• 视图函数返回的内容通常是 HTML 页面、JSON 数据等。  
2. API 与 URL  
• API（应用程序接口） 是系统间交互的接口。在 Flask 中，/api/ 路径通常用于提供数据接口，而不是直接返回 HTML 页面。这些接口允许前端与后端通过数据交互。举个例子，/api/status 是一个返回当前应用状态的接口，通常返回 JSON 格式的数据。  
• URL 是统一资源定位符（Uniform Resource Locator），它指向某个资源或服务。在 Flask 中，http://localhost:5000 是你的服务器地址，/api/status 是路径的一部分，指向某个特定的服务或功能。  
3. Flask 路由与前端交互  
• Flask 会根据请求的 URL 和 HTTP 方法（如 GET、POST）调用相应的视图函数。在你的案例中：  
• 用户访问 http://localhost:5000（根路径）时，Flask 会返回 index.html页面，显示前端界面。  
• 当前端 JavaScript 文件（如 main.js、websocket-client.js）向后端发送请求时，例如访问 /api/status，Flask 会执行与该路径绑定的视图函数，返回数据给前端。  
4. 静态文件（static）和模板文件（templates）  
• 静态文件（如 JavaScript、CSS、图片等）存放在 static 文件夹下，可以通过 url_for('static', filename='...') 访问。例如，在 index.html 中通过 <script src="{{ url_for('static', filename='js/main.js') }}"></script> 引入了 JavaScript 文件。  
• 模板文件（如 HTML）存放在 templates 文件夹下，Flask 会通过 render_template() 渲染这些文件并返回给客户端。index.html 是一个模板文件，显示在浏览器中。  
5. JavaScript 文件的加载与功能  
• 在 index.html 中，你通过 <script> 标签引入了其他的 JavaScript 文件：websocket-client.js、three-scene.js 和 main.js。  
• 这些文件加载后，会在浏览器端执行。例如：  
• websocket-client.js 负责与 Flask 后端通过 WebSocket 建立连接。  
• three-scene.js 可能负责 3D 场景的渲染。  
• main.js 可能包含页面的交互逻辑，比如开始建模、更新状态等。  
6. url_for 函数  
• url_for() 是 Flask 提供的一个函数，用于生成静态文件或路由的 URL。它确保生成的 URL 在不同环境下（开发、生产等）都能正确指向目标文件。例如，url_for('static', filename='js/main.js') 会生成 http://localhost:5000/static/js/main.js，指向 static/js/main.js 文件。  
7. 关于 @app.route('/api/status') 的困惑  
• @app.route('/api/status') 是在 Flask 中定义的一个路由，它将访问 /api/status 路径的请求与 get_status 视图函数绑定。  
• 在你的前端，main.js 或其他 JavaScript 文件会通过 fetch('/api/status') 或 WebSocket 发送请求到这个 API 路径。尽管用户直接访问 http://localhost:5000，但 JavaScript 会在后台发起对 /api/status 的请求。  
8. 后端与前端的交互  
• 后端通过 Flask 提供 API 路径，前端通过 JavaScript 发送请求（例如使用 fetch或 WebSocket）。请求的 URL 由 Flask 路由定义，而返回的数据通常是 JSON 格式，供前端动态使用。  
• 例如，/api/status 返回应用的状态，前端 JavaScript 会处理返回的 JSON 数据，更新页面上的状态显示。  
  
##### 8、HTTP请求类型  
HTTP 协议有几种常用的请求方法，不同的方法有不同的用途：  
GET: 获取数据（从服务器请求资源），一般用于读取数据。  
POST: 提交数据（向服务器发送数据），一般用于提交表单数据或进行修改、创建资源的操作。  
PUT: 更新数据，用于替代指定资源（或部分资源）。  
DELETE: 删除资源。  
PATCH: 部分更新资源。  
  
##### 9、前端
js和html文件的联动  
  
##### 10、WebRTC
https://aiortc.readthedocs.io/en/latest/index.html  