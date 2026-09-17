from flask import session, jsonify
from functools import wraps
from src import r
from .save_sessions import save_sessions

required_keys = [
    "user_id", "role", "school_id",
    "session_id", "current_running_session",
    "permissions", "school_name", "permission_no",
    "logo"
]

def login_required(f):
   
    @wraps(f)
    def decorated_function(*args, **kwargs):
        
        for key in required_keys:            
            if key not in session:
               
               return jsonify({
                "authenticated": False,
                "error": "Login Required!"
            }), 401

        try:
            redis_permission_no = r.get(session["user_id"])
        except Exception:
            return jsonify({
                "authenticated": False,
                "error": "Server Error"
            }), 500
        

        if not redis_permission_no:
            session.clear()
            return jsonify({
                "authenticated": False,
                "error": "Session Expired! Login Again."
            }), 401
        

        if int(session["permission_no"]) != int(redis_permission_no):
            try:
                is_success, message = save_sessions(user_id=session["user_id"])
            except Exception:
                session.clear()
                return jsonify({
                    "authenticated": False,
                    "error": "Unable to refresh session. Please login again."
                }), 401

            if not is_success:
                session.clear()
                return jsonify({
                    "authenticated": False,
                    "error": message or "Unable to refresh session. Please login again."
                }), 401

        return f(*args, **kwargs)
    return decorated_function