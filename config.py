class Config:
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:@localhost/learning_system'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disables modification tracking
    
    # Secret Key (for session encryption, CSRF protection, etc.)
    SECRET_KEY = '8a9a28d6f98750fc42b8d295ec8ad64be9c0b04c4b1299e22967a12f550ce4c3'
    
    # Twilio API Credentials (if used for SMS/notifications)
    TWILIO_ACCOUNT_SID = 'your_account_sid'       # Replace with actual Twilio SID
    TWILIO_AUTH_TOKEN = 'your_auth_token'         # Replace with actual Twilio token
    TWILIO_PHONE_NUMBER = '+1234567890'           # Replace with your Twilio number
    
    # Flask-Login Configuration
    SESSION_PROTECTION = 'strong'  # Prevents session hijacking
    
    # Debug Mode (set to False in production!)
    DEBUG = True

    