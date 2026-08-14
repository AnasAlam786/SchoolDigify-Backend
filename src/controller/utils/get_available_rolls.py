from flask import Blueprint, jsonify, request, session
from sqlalchemy import select
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model import StudentSessions
from src import db

def get_available_rolls(class_id, session_id, excluded_student_id=None ):
    # Query to get all roll numbers for the given class and session, ordered by roll
    query = (
        select(StudentSessions.ROLL)
        .where(
            StudentSessions.class_id == class_id,
            StudentSessions.session_id == session_id,
            StudentSessions.ROLL.isnot(None)
        )
        .order_by(StudentSessions.ROLL)
    )

    if excluded_student_id is not None:
        query = query.where(
            StudentSessions.student_id != excluded_student_id
        )

    # Execute the query and get the list of rolls
    result = db.session.execute(query).scalars().all()
    rolls = list(result)

    if not rolls:
        return {"available_rolls": [1]}

    max_roll = rolls[-1]  # Already sorted

    available_rolls = sorted(
        set(range(1, max_roll + 1)) - set(rolls)
    )

    available_rolls.append(max_roll + 1)
    return { 'available_rolls': available_rolls, }


get_available_rolls_api_bp = Blueprint('get_available_rolls_api_bp', __name__)
@get_available_rolls_api_bp.route('/api/get-available-rolls', methods=['POST'])
@login_required
def get_available_rolls_api():
    data = request.get_json() or {}
    class_id = data.get('class_id')
    excluded_student_id = data.get('excluded_student_id', None)

    if not class_id:
        return jsonify({"message": "Class ID is required."}), 400

    try:
        session_id = int(session.get('session_id'))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid session."}), 400

    try:
        result = get_available_rolls(class_id, session_id, excluded_student_id)
        available_rolls = result['available_rolls']
        return jsonify({
            'available_rolls': available_rolls,
            'next_roll': available_rolls[-1]
        }), 200
    except Exception as e:
        return jsonify({"message": "Unable to fetch available rolls."}), 500
