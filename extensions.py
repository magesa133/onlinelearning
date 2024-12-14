from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# Flask extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
