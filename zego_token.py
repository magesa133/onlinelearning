import time
import jwt

# Replace with your ZEGOCLOUD credentials
APP_ID = "1271126531"
APP_SECRET = "5261b8e7778bf38bbe00c844ca26b988"

def generate_token(user_id):
    current_time = int(time.time())
    expiration_time = current_time + 3600  # Token valid for 1 hour

    payload = {
        "app_id": APP_ID,
        "user_id": user_id,
        "nonce": int(time.time()),
        "iat": current_time,
        "exp": expiration_time,
    }

    # Generate JWT token
    token = jwt.encode(payload, APP_SECRET, algorithm="HS256")
    return token
