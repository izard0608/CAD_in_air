'''
# 用 mediapipe 识别手部节点并标出、连线——————————————————————————————————————————————
import cv2
import mediapipe as mp
from flask import Flask, render_template

cap = cv2.VideoCapture(1)  # VideoCapture(1)是外接摄像头，VideoCapture(0)是本地摄像头
mpHands = mp.solutions.hands
hands = mpHands.Hands()
mpDraw = mp.solutions.drawing_utils



while True:
    ret, img = cap.read()
    if ret:
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = hands.process(imgRGB)
        #print(result.multi_hand_landmarks)
        imgHeight = img.shape[0]
        imgWidth = img.shape[1]

        if result.multi_hand_landmarks:
            for handLms in result.multi_hand_landmarks:
                mpDraw.draw_landmarks(img, handLms, mpHands.HAND_CONNECTIONS,)
                for i, lm in enumerate(handLms.landmark):
                    xPos = lm.x * imgWidth
                    yPos = lm.y * imgHeight
                    print(i,"%.2f"%xPos,"%.2f"%yPos)

        cv2.imshow('img', img)

    if cv2.waitKey(1) == ord('q'):
        break
#——————————————————————————————————————————————————————————————————————————————
# 用终端命令运行的时候，该程序按q退出

'''


#建立网页，Flask框架——————————————————————————————————————————————
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return (render_template('index.html'))

if __name__ == '__main__':
    print("启动3D手势建模系统...")
    print("访问 http://localhost:5000 查看3D效果")
    app.run(debug=True, host='0.0.0.0', port=5000)
#———————————————————————————————————————————————————————————————
# 用终端命令运行的时候，该程序按ctrl+c退出

