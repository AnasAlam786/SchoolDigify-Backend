from flask import request, jsonify, render_template
from functools import wraps
from .has_permission import has_permission

def permission_required(permission_name):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):

            if not has_permission(permission_name):
                return jsonify(
                    {"error": "You do not have permission to access this resource."}
                ), 403
                
            return f(*args, **kwargs)
        return wrapped
    return decorator
