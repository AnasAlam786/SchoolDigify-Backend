from flask import session, jsonify, Blueprint, request
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required
from src import r



change_session_bp = Blueprint( 'change_session_bp',   __name__)


@change_session_bp.route('/api/change_session', methods=["POST"])
@login_required
@permission_required('change_session')
def change_session():
    
    data = request.json
    selected_session = data.get('year')


    # Validate input
    if not selected_session or not selected_session.isdigit():
        return jsonify({"error": "Invalid session ID"}), 400
    

    selected_session = int(selected_session)
    
    all_sessions = session["all_sessions"]

    if selected_session in all_sessions:
        session["session_id"] = selected_session
        return jsonify({"message": f"Session Updated to {selected_session}-{(selected_session+1)}"}), 200

    return jsonify({"error": "Session not found"}), 404

    