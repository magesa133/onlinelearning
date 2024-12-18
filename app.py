from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os
import logging
from sqlalchemy import text
from config import Config
from models import db, OnlineSession, User

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Database and migration setup
db.init_app(app)
migrate = Migrate(app, db)

# Configure logging
log_level = logging.DEBUG if app.debug else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

def test_db_connection():
    """
    Test the database connection by executing a simple query.
    Raise an exception if the connection fails.
    """
    try:
        with app.app_context():
            db.session.execute(text('SELECT 1'))
            logger.info("Database connection successful!")
    except Exception as error:
        logger.error(f"Database connection error: {error}")
        raise RuntimeError("Unable to connect to the database") from error

# Ensure database connection is valid before starting the app
test_db_connection()

# Login manager setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    """
    Load a user from the database using their ID.
    """
    return User.query.get(int(user_id))

# Import application routes
from routes import *

def setup_ssl_certificates(cert_path="cert.pem", key_path="key.pem"):
    """
    Ensure SSL certificates exist; generate them if not found.
    """
    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        logger.info("SSL certificates not found. Generating new ones...")
        os.system(f'openssl req -x509 -newkey rsa:4096 -keyout {key_path} -out {cert_path} -days 365 -nodes')

if __name__ == "__main__":
    # SSL certificate paths
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    # Setup SSL certificates
    setup_ssl_certificates(cert_file, key_file)

    # Start the Flask app
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "192.168.1.159"),  # Local IP address
        port=int(os.getenv("FLASK_RUN_PORT", 5000)),        # Port number
        debug=os.getenv("FLASK_DEBUG", "True") == "True",  # Debug mode
        ssl_context=(cert_file, key_file)                  # SSL certificates
    )
