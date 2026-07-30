# src/controller/auth.py

from flask import jsonify, session, Blueprint, request
from cryptography.fernet import Fernet
from sqlalchemy.exc import ProgrammingError
from src.controller.auth.login_required import login_required
from src.model.Schools import Schools
from .save_sessions import save_sessions
from src.model.TeachersLogin import TeachersLogin
from src.model.Roles import Roles
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
        user = (
            TeachersLogin.query
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

    if not save_sessions(user=user):
        return jsonify({
            "success": False,
            "message": "Something didn't go well, try again!"
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
    return jsonify({
        "authenticated": True,
        "sessionData": dict(session)
    }), 200