# src/controller/final_update_api.py

from flask import session, request, jsonify, Blueprint

from src import db
from src.controller.utils.get_available_rolls import get_available_rolls
from src.model import StudentSessions
from src.model import ClassData

import datetime

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required


update_promoted_api_bp = Blueprint('update_promoted_api_bp', __name__)


@update_promoted_api_bp.route('/api/update_promoted', methods=["POST"])
@login_required
@permission_required('promote_student')
def update_promotion():

    current_session = session.get("session_id")

    data = request.json or {}
    student_session_id = data.get('student_session_id')
    promoted_roll = data.get('promoted_roll')
    promoted_date = data.get('promoted_date')
    promoted_class_id = data.get('promoted_class_id')

    if not student_session_id or not promoted_roll or not promoted_date or not promoted_class_id:
        return jsonify({"message": "Missing required parameters."}), 400

    # Convert numbers
    try:
        student_session_id = int(student_session_id)
        promoted_roll = int(promoted_roll)
        promoted_class_id = int(promoted_class_id)
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid parameter format."}), 400

    # Convert date
    try:
        promoted_date = datetime.datetime.strptime(promoted_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid promoted date."}), 400

    # Fetch existing student session
    student_session = StudentSessions.query.filter_by(id=student_session_id).first()
    if not student_session:
        return jsonify({"message": "Student not promoted, Try promoting again!"}), 404

    old_roll = student_session.ROLL
    old_class_id = student_session.class_id

    # Validate selected class
    school_id = session.get("school_id")
    selected_class = ClassData.query.filter_by(
        id=promoted_class_id, school_id=school_id
    ).first()
    if not selected_class:
        return jsonify({"message": "Selected class does not exist."}), 400

    # ---------------------------
    # ROLL NUMBER VALIDATION LOGIC
    # ---------------------------

    roll_changed = promoted_roll != old_roll
    class_changed = promoted_class_id != old_class_id

    try:


        if roll_changed or class_changed:
            # Get available rolls for the target class
            available_result = get_available_rolls(promoted_class_id, current_session)
            available_rolls = available_result['available_rolls']

            if promoted_roll not in available_rolls:
                allowed_rolls = ", ".join(map(str, available_rolls))
                return jsonify({
                    "error": f"Roll number already assigned. You can only assign one of these rolls: {allowed_rolls}."
                }), 400
    except Exception as e:
        print(e)
        return jsonify({ "error": e }), 400

    # ---------------------
    # APPLY THE PROMOTION ON NEW SESSION ROW
    # ---------------------

    try:
        student_session.ROLL = promoted_roll
        student_session.status = 'active'
        student_session.created_at = promoted_date
        student_session.class_id = promoted_class_id

        db.session.commit()

        new_class = selected_class.CLASS

        return jsonify({
            "message": "Student record updated successfully.",
            "state": "PROMOTED",
            # "promoted_session_id": student_session.id,
            "new_roll": promoted_roll,
            "new_class": new_class,
            "promoted_date": promoted_date.isoformat()
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({"message": "Error updating student record."}), 500
