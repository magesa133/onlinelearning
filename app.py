from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os
import logging
from config import Config
from sqlalchemy import text
from models import db, OnlineSession, User

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Set up the database and migrations
db.init_app(app)
migrate = Migrate(app, db)

# Logging setup
logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)
logger = logging.getLogger(__name__)

# Test database connection
def test_db_connection():
    try:
        with app.app_context():
            # Wrap the SQL expression in text() for raw SQL query
            db.session.execute(text('SELECT 1'))  # Simple query to test DB connection
            print("Database connection successful!")
    except Exception as e:
        print(f"Database connection error: {e}")
        raise RuntimeError("Unable to connect to the database") from e

# Run test before starting app
test_db_connection()

# Login Manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Import routes
from routes import *

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "True") == "True", host='192.168.1.159',port=5000)
