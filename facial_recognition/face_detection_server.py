import cv2
import numpy as np
import base64
from flask import Flask
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# Load Haar Cascade model
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

@sock.route('/face-detection')
def face_detection(ws):
    while True:
        # Receive data from the client
        message = ws.receive()
        if not message:
            continue

        # Decode and check if there's a face
        try:
            request = json.loads(message)
            if request.get("action") == "check_face":
                # Assuming we have access to the webcam feed for processing
                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                cap.release()

                if ret:
                    # Convert frame to grayscale for detection
                    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5)

                    ws.send(json.dumps({"faceDetected": len(faces) > 0}))
        except Exception as e:
            ws.send(json.dumps({"error": str(e)}))
