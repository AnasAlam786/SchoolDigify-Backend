from flask import session, request, Blueprint, jsonify

from src.controller.utils.get_gapped_rolls import get_gapped_rolls

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

get_available_rolls_api_bp = Blueprint('get_available_rolls_api_bp', __name__)

@get_available_rolls_api_bp.route('/api/get-available-rolls', methods=['POST'])
@login_required
@permission_required('promote')
def get_available_rolls():
    data = request.get_json() or {}
    class_id = data.get('class_id')

    if not class_id:
        return jsonify({"error": "Class ID is required."}), 400

    try:
        session_id = int(session.get('session_id'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session."}), 400

    try:
        result = get_gapped_rolls(class_id, session_id)
        available_rolls = result['gapped_rolls'] + [result['next_roll']]
        return jsonify({
            'available_rolls': available_rolls,
            'next_roll': result['next_roll']
        }), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch available rolls."}), 500
