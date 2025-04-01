from functools import wraps
from flask import abort, current_app
from flask_login import current_user

def role_required(role_name):
    """Decorator to ensure user has the required role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role != role_name:
                current_app.logger.warning(
                    f"Role violation by {current_user.email}: "
                    f"Required {role_name}, had {current_user.role}"
                )
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator