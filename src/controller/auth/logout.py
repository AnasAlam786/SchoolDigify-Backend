from flask import jsonify, session, url_for, redirect, Blueprint

logout_bp = Blueprint( 'logout_bp',   __name__)

@logout_bp.route('/logout', methods=["POST"])
def logout():
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    }), 200