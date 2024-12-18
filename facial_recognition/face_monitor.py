import cv2
import time
import requests

# URL for notifying the teacher (e.g., via backend endpoint)
NOTIFY_URL = "https://172.16.0.71:5000/notify_teacher"

def notify_teacher(student_id, session_id):
    """Notify teacher when student is out of frame."""
    payload = {"student_id": student_id, "session_id": session_id}
    try:
        requests.post(NOTIFY_URL, json=payload)
    except Exception as e:
        print(f"Error notifying teacher: {e}")

def monitor_face(student_id, session_id):
    """Monitor the face of the student using webcam."""
    cap = cv2.VideoCapture(0)  # Open webcam
    if not cap.isOpened():
        print("Error: Unable to access the webcam.")
        return

    face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    face_lost_start = None  # Time when the face was first lost
    FACE_LOSS_THRESHOLD = 5  # Notify if the face is out of the frame for 5 seconds

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame from the webcam.")
            break

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Convert frame to grayscale
        faces = face_detector.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            # Reset the face lost timer if a face is detected
            face_lost_start = None
        else:
            # Start the timer if no face is detected
            if face_lost_start is None:
                face_lost_start = time.time()
            elif time.time() - face_lost_start > FACE_LOSS_THRESHOLD:
                print("Face not detected for 5 seconds. Notifying the teacher...")
                notify_teacher(student_id, session_id)
                face_lost_start = None  # Avoid multiple notifications for the same event

        # Display the frame for debugging (can be removed in production)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.imshow("Face Monitoring", frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    monitor_face(student_id=1, session_id=101)  # Replace with dynamic IDs
