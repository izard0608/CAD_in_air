# app.service.VideoStreamServer.py
# 用来处理后端的WebRTC视频流

import logging
import cv2
import threading
import time
import asyncio
import json
import numpy as np
from flask import Flask, request, jsonify, Response
from flask_socketio import SocketIO, emit
import base64

logger = logging.getLogger(__name__)

class VideoStreamServer:
    def __init__(self, port=5001, flask_app=None, socketio=None):
        self.port = port
        self.app = flask_app or Flask(__name__)
        self.socketio = socketio or SocketIO(self.app, cors_allowed_origins="*")
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.clients = {}  # 存储客户端连接信息
        
        # WebRTC相关
        self.peer_connections = {}  # client_id -> 虚拟连接信息
        
        self.setup_routes()
        self.setup_socket_events()
        logger.info(f"WebRTC 视频流服务器初始化完成，端口: {port}")
    
    def setup_routes(self):
        """设置HTTP路由"""
        @self.app.route('/health')
        def health():
            return jsonify({"status": "healthy", "clients": len(self.clients)})
        
        @self.app.route('/frame')
        def get_frame():
            """获取当前帧（备用方案）"""
            with self.frame_lock:
                if self.current_frame is None:
                    return Response("No frame", status=404)
                
                # 编码为JPEG
                ret, buffer = cv2.imencode('.jpg', self.current_frame)
                if ret:
                    return Response(buffer.tobytes(), mimetype='image/jpeg')
                return Response("Error encoding", status=500)
    
    def setup_socket_events(self):
        """设置WebSocket事件"""
        @self.socketio.on('connect')
        def handle_connect():
            client_id = request.sid
            logger.info(f"客户端连接: {client_id}")
            self.clients[client_id] = {
                'connected': True,
                'last_active': time.time()
            }
            emit('connected', {'client_id': client_id})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            client_id = request.sid
            if client_id in self.clients:
                del self.clients[client_id]
            if client_id in self.peer_connections:
                del self.peer_connections[client_id]
            logger.info(f"客户端断开: {client_id}")
        
        @self.socketio.on('request_video_stream')
        def handle_video_request(data):
            """客户端请求视频流"""
            client_id = request.sid
            logger.info(f"客户端 {client_id} 请求视频流")
            
            # 发送初始帧（如果有）
            with self.frame_lock:
                if self.current_frame is not None:
                    # 发送base64编码的帧作为初始预览
                    _, buffer = cv2.imencode('.jpg', self.current_frame)
                    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                    emit('video_frame', {
                        'type': 'initial',
                        'frame': jpg_as_text,
                        'timestamp': time.time()
                    }, room=client_id)
            
            # 通知可以开始WebRTC流程
            emit('ready_for_webrtc', {
                'server_url': f'http://localhost:{self.port}'
            }, room=client_id)
        
        @self.socketio.on('webrtc_offer')
        def handle_webrtc_offer(data):
            """处理WebRTC Offer"""
            client_id = request.sid
            logger.info(f"收到来自 {client_id} 的WebRTC Offer")
            
            # 在这里应该处理SDP Offer，但由于我们没有真正的媒体服务器
            # 我们发送一个简单的Answer来建立连接
            answer = {
                'type': 'answer',
                'sdp': 'v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=ice-options:trickle\r\n',
                'client_id': client_id
            }
            
            emit('webrtc_answer', answer, room=client_id)
            
            # 存储连接信息
            self.peer_connections[client_id] = {
                'status': 'connected',
                'last_activity': time.time()
            }
        
        @self.socketio.on('ice_candidate')
        def handle_ice_candidate(data):
            """处理ICE Candidate"""
            client_id = request.sid
            logger.debug(f"收到来自 {client_id} 的ICE Candidate")
            # 转发给其他端（如果需要）
            emit('ice_candidate', data, room=client_id, skip_sid=request.sid)
    
    def update_frame(self, frame):
        """更新当前帧并广播给所有客户端"""
        with self.frame_lock:
            # 调整帧大小以减少带宽
            if frame is not None:
                h, w = frame.shape[:2]
                if w > 640:  # 限制宽度
                    scale = 640 / w
                    new_w = 640
                    new_h = int(h * scale)
                    frame = cv2.resize(frame, (new_w, new_h))
                self.current_frame = frame
        
        # 如果有客户端连接，发送帧数据
        if self.clients:
            try:
                # 编码为JPEG
                _, buffer = cv2.imencode('.jpg', frame)
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # 广播给所有客户端
                self.socketio.emit('video_frame', {
                    'type': 'update',
                    'frame': jpg_as_text,
                    'timestamp': time.time(),
                    'size': frame.shape[:2] if frame is not None else (0, 0)
                })
            except Exception as e:
                logger.error(f"发送视频帧错误: {e}")
    
    def run(self):
        """启动服务器"""
        logger.info(f"启动WebRTC视频流服务器在端口 {self.port}")
        self.socketio.run(
            self.app,
            host='0.0.0.0',
            port=self.port,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False
        )