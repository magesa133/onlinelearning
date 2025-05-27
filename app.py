from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os
import logging
from sqlalchemy import text
from config import Config
from models import db, OnlineSession, User
from datetime import datetime
from forms import TimeSinceFormatter  # Import the formatter class
import humanize
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os
import logging
from sqlalchemy import text
from config import Config
from models import db, OnlineSession, User
from datetime import datetime
from forms import TimeSinceFormatter  # Import the formatter class
import humanize
from datetime import datetime
from pytz import timezone as pytz_timezone
from flask_socketio import SocketIO


# Configure timezone
local_timezone = pytz_timezone('Africa/Dar_es_Salaam')

def make_timezone_aware(dt):
    """Convert naive datetime to timezone-aware datetime"""
    if dt and not dt.tzinfo:
        return local_timezone.localize(dt)
    return dt

def format_datetime(value, format="%b %d at %H:%M"):
    if value is None:
        return ""
    return value.strftime(format)

# Initialize Flask app
app = Flask(__name__)

socketio = SocketIO(app)


@app.template_filter('dateformat')
def dateformat(value, format='%Y-%m-%d'):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value
    return value.strftime(format)



@app.template_filter('humanize')
def humanize_time(delta):
    if delta is None:
        return ""
    seconds = int(delta.total_seconds())
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    
    return ", ".join(parts) if parts else "a few seconds"

def safe_markdown(text):
    """Convert markdown to HTML with safety checks"""
    if not text:
        return ""
    # Basic tags we'll allow
    allowed_tags = [
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
        'strong', 'em', 'a', 'ul', 'ol', 'li', 
        'code', 'pre', 'blockquote'
    ]
    allowed_attributes = {'a': ['href', 'title']}
    
    html = markdown(text)
    return clean(html, tags=allowed_tags, attributes=allowed_attributes)

# Register filters
app.jinja_env.filters['format_datetime'] = format_datetime
app.jinja_env.filters['humanize_time'] = humanize_time
# Register humanize filters with Jinja2
app.jinja_env.filters['naturaltime'] = humanize.naturaltime
app.jinja_env.filters['naturalday'] = humanize.naturalday
app.jinja_env.filters['intcomma'] = humanize.intcomma

app.jinja_env.filters['markdown'] = safe_markdown

# Register the template filter after app creation
# Correct way to register a filter
@app.template_filter('timesince')
def timesince_filter(dt):
    return TimeSinceFormatter().format_time_since(dt)

# Verify registration
# print("Registered filters:", app.jinja_env.filters.keys())  # Should show 'timesince'

# Define the datetimeformat filter
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%b %d, %Y at %I:%M %p'):
    """Custom Jinja2 filter to format datetime objects."""
    if value is None:
        return ""
    return value.strftime(format)

app.config.from_object(Config)

# Disable CSRF protection globally
app.config['WTF_CSRF_ENABLED'] = False

print(app.url_map)

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
        os.system(f'openssl req -x509 -newkey rsa:4096 -keyout {key_path} -out {cert_path} -days 365 -nodes -subj "/CN=localhost"')

if __name__ == "__main__":
    # SSL certificate paths
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    # Setup SSL certificates
    setup_ssl_certificates(cert_file, key_file)

    # Start the Flask app
    app.run(
    host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),  # Listen on all interfaces
    port=int(os.getenv("FLASK_RUN_PORT", 5001)),  # Default port
    debug=os.getenv("FLASK_DEBUG", "True") == "True",  # Debug mode
    ssl_context=(cert_file, key_file)  # Load SSL certificates
)
from pytz import timezone as pytz_timezone

# Configure timezone
local_timezone = pytz_timezone('Africa/Dar_es_Salaam')

def make_timezone_aware(dt):
    """Convert naive datetime to timezone-aware datetime"""
    if dt and not dt.tzinfo:
        return local_timezone.localize(dt)
    return dt

def format_datetime(value, format="%b %d at %H:%M"):
    if value is None:
        return ""
    return value.strftime(format)


# Initialize Flask app
app = Flask(__name__)

@app.template_filter('humanize')
def humanize_time(delta):
    if delta is None:
        return ""
    seconds = int(delta.total_seconds())
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    
    return ", ".join(parts) if parts else "a few seconds"

def safe_markdown(text):
    """Convert markdown to HTML with safety checks"""
    if not text:
        return ""
    # Basic tags we'll allow
    allowed_tags = [
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
        'strong', 'em', 'a', 'ul', 'ol', 'li', 
        'code', 'pre', 'blockquote'
    ]
    allowed_attributes = {'a': ['href', 'title']}
    
    html = markdown(text)
    return clean(html, tags=allowed_tags, attributes=allowed_attributes)

# Register filters
app.jinja_env.filters['format_datetime'] = format_datetime
app.jinja_env.filters['humanize_time'] = humanize_time
# Register humanize filters with Jinja2
app.jinja_env.filters['naturaltime'] = humanize.naturaltime
app.jinja_env.filters['naturalday'] = humanize.naturalday
app.jinja_env.filters['intcomma'] = humanize.intcomma

app.jinja_env.filters['markdown'] = safe_markdown

# Register the template filter after app creation
# Correct way to register a filter
@app.template_filter('timesince')
def timesince_filter(dt):
    return TimeSinceFormatter().format_time_since(dt)

# Verify registration
# print("Registered filters:", app.jinja_env.filters.keys())  # Should show 'timesince'

# Define the datetimeformat filter
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%b %d, %Y at %I:%M %p'):
    """Custom Jinja2 filter to format datetime objects."""
    if value is None:
        return ""
    return value.strftime(format)

app.config.from_object(Config)

# Disable CSRF protection globally
app.config['WTF_CSRF_ENABLED'] = False

print(app.url_map)


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
        os.system(f'openssl req -x509 -newkey rsa:4096 -keyout {key_path} -out {cert_path} -days 365 -nodes -subj "/CN=localhost"')

if __name__ == "__main__":
    # SSL certificate paths
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    # Setup SSL certificates
    setup_ssl_certificates(cert_file, key_file)

    # Start the Flask app
    app.run(
    host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),  # Listen on all interfaces
    port=int(os.getenv("FLASK_RUN_PORT", 5001)),  # Default port
    debug=os.getenv("FLASK_DEBUG", "True") == "True",  # Debug mode
    ssl_context=(cert_file, key_file)  # Load SSL certificates
)
