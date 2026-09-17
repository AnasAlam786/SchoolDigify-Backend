# src/controller/auth.py

from flask import jsonify, session, Blueprint, request
from cryptography.fernet import Fernet
from sqlalchemy.exc import ProgrammingError
from src.controller.auth.login_required import login_required
from src.model.Schools import Schools
from .save_sessions import save_sessions
from src.model.TeachersLogin import TeachersLogin
from src.model.Roles import Roles
from src import db
import os


login_bp = Blueprint('login_bp', __name__)
FERNET_KEY = os.environ.get('FERNET_KEY')


@login_bp.route('/login', methods=["GET", "POST"])
def login():
    """Central login page (no subdomain)"""

    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    session.clear()

    try:
        user_data = (
            db.session.query(TeachersLogin, Roles)
            .join(Roles, Roles.id == TeachersLogin.role_id)
            .filter(TeachersLogin.email == email)
            .first()
        )
    except ProgrammingError as e:
        # Database schema not initialized or wrong table name/case.
        return jsonify({
            "success": False,
            "message": "Database tables not found",
            "debug": str(e)
        }), 500

    user, role = user_data

    if not user:
        return jsonify({
            "success": False,
            "message": "No user found with this email"
        }), 404
    try:
        decrypted_password = Fernet(FERNET_KEY).decrypt(user.Password).decode()
    except Exception:
        return jsonify({
            "success": False,
            "message": "Password decryption failed"
        }), 500
    
    if decrypted_password != password:
        return jsonify({
            "success": False,
            "message": "Wrong email or password"
        }), 401

    try:
        is_success, message = save_sessions(user=user_data)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": e
        }), 500

    if not is_success:
        return jsonify({
            "success": False,
            "message": message or "Something didn't go well, try again!"
        }), 500

    school = Schools.query.filter_by(id=user.school_id).first()
    if not school or not school.id:
        return jsonify({
            "success": False,
            "message": "School configuration error"
        }), 500


    return jsonify({
        "success": True,
        "message": "Login successful",
        "session_data": dict(session)
    }), 200



@login_bp.route("/api/me", methods=["GET"])
@login_required
def me():
    try:
        dict_session = dict(session)
    except Exception as e:
        return jsonify({ "error": e }), 400

    return jsonify({
        "authenticated": True,
        "sessionData": dict_session
    }), 200