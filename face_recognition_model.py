# face_recognition_model.py
import cv2
import numpy as np
from keras.models import load_model
from sklearn.metrics.pairwise import cosine_similarity
import os

# Load pre-trained FaceNet model
MODEL_PATH = os.path.join(os.getcwd(), 'facenet_keras.h5')
model = load_model(MODEL_PATH)

def get_face_embedding(image):
    """
    Extract a 128-dimensional face embedding from the input image using FaceNet.
    """
    # Convert the image to RGB (required for the model)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # Resize the image to the expected input size (160x160 for FaceNet)
    image = cv2.resize(image, (160, 160))

    # Normalize the image
    image = image.astype('float32')
    image = (image / 255.0)

    # Add batch dimension (FaceNet expects an array of images)
    image = np.expand_dims(image, axis=0)

    # Get the face embedding
    embedding = model.predict(image)
    return embedding

def compare_faces(known_embedding, test_embedding):
    """
    Compare two face embeddings using cosine similarity.
    """
    return cosine_similarity(known_embedding, test_embedding)
