class Config:
    # Configure the database connection
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:@localhost/learning_system'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Set the secret key (replace with the generated key)
    SECRET_KEY = '8a9a28d6f98750fc42b8d295ec8ad64be9c0b04c4b1299e22967a12f550ce4c3'

    
    # Twilio API Credentials
    TWILIO_ACCOUNT_SID = 'your_account_sid'
    TWILIO_API_KEY = 'your_api_key'
    TWILIO_API_SECRET = 'your_api_secret'