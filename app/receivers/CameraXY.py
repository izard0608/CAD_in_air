# CameraXY.py

'''
1、openCV捕获摄像头视频流
2、mediapipe处理视频帧，获取xy坐标
3、使用WebRTC推送到前端
4、
关于视频流：使用WebRTC 替代 MJPEG。
    原先用的MJPEG是每一帧都单独编码成 JPEG 图片，然后按顺序传输。文件很大延迟很高。
    WebRTC类似于视频通话，可以降低延迟。
'''