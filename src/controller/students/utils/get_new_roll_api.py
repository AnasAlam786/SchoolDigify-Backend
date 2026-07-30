# src/controller/get_new_roll_api.py

from flask import session, request, jsonify, Blueprint

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.utils.get_gapped_rolls import get_gapped_rolls

get_new_roll_api_bp = Blueprint( 'get_new_roll_api_bp',   __name__)


@get_new_roll_api_bp.route('/api/get_new_roll_api', methods=["POST"])
@login_required
@permission_required('admission')
def get_new_roll_api():
    data = request.json
    class_id = data.get('class_id')
    session_id = data.get('session_id')

    if not session_id:
        session_id = session["session_id"]

    try:
        available_rolls = get_gapped_rolls(class_id, session_id)
    except Exception as e:
        return jsonify({"error": f"Error: {e}"}), 400

    return jsonify({ 'gapped_rolls': available_rolls['gapped_rolls'], 'next_roll': available_rolls['next_roll'] })
