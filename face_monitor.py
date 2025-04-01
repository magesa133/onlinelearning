# import cv2
# import time
# from flask import Flask, jsonify, request

# app = Flask(__name__)

# # Load the Haar Cascade for face detection
# face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# # Dictionaries to store participant data
# participant_last_seen = {}
# notification_sent = {}

# # Monitor session status
# session_active = False


# @app.route('/start_monitoring', methods=['POST'])
# def start_monitoring():
#     """Start face monitoring."""
#     global session_active
#     session_active = True
#     return jsonify({"status": "Monitoring started"})


# @app.route('/stop_monitoring', methods=['POST'])
# def stop_monitoring():
#     """Stop face monitoring."""
#     global session_active
#     session_active = False
#     return jsonify({"status": "Monitoring stopped"})


# @app.route('/monitor', methods=['GET'])
# def monitor_faces():
#     """Face monitoring loop."""
#     global session_active

#     # Use the default camera source or a remote feed
#     camera_index = request.args.get('camera_index', 0, type=int)
#     cap = cv2.VideoCapture(camera_index)
#     if not cap.isOpened():
#         return jsonify({"error": "Failed to access the camera"})

#     while session_active:
#         ret, frame = cap.read()
#         if not ret:
#             break

#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

#         current_time = time.time()

#         if len(faces) > 0:
#             for (x, y, w, h) in faces:
#                 user_id = f"{x}-{y}"  # Generate a unique ID for the face
#                 participant_last_seen[user_id] = current_time
#                 if user_id in notification_sent:
#                     del notification_sent[user_id]

#             cv2.putText(frame, "Face Detected", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#         else:
#             for user_id, last_seen in list(participant_last_seen.items()):
#                 if current_time - last_seen > 120:  # If absent for over 2 minutes
#                     if user_id not in notification_sent:
#                         notify_teacher_and_student(user_id)
#                         notification_sent[user_id] = True

#         # Display the monitoring frame
#         cv2.imshow('Face Monitor', frame)

#         # Terminate monitoring if 'q' is pressed
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     cap.release()
#     cv2.destroyAllWindows()
#     return jsonify({"status": "Monitoring stopped"})


# @app.route('/participant_activity', methods=['GET'])
# def participant_activity():
#     """Fetch the current participant activity."""
#     current_time = time.time()
#     activity = []

#     for user_id, last_seen in participant_last_seen.items():
#         status = "Active" if current_time - last_seen <= 120 else "Inactive"
#         activity.append({"user_id": user_id, "status": status})

#     return jsonify(activity)


# def notify_teacher_and_student(user_id):
#     """Send an alert for missing participants."""
#     print(f"Alert: Participant {user_id} has not been detected for over 2 minutes!")


# if __name__ == '__main__':
#     app.run(debug=True, port=5001)
