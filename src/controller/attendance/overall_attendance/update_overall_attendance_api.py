# src/controller/attendance/update_overall_attendance_api.py

from flask import session, request, jsonify, Blueprint, current_app
from sqlalchemy import and_

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from src.model import StudentSessions
from src import db

update_overall_attendance_api_bp = Blueprint('update_overall_attendance_api_bp', __name__)

@update_overall_attendance_api_bp.route('/api/update_overall_attendance', methods=["POST"])
@login_required
@permission_required('overall_attendance')
def update_overall_attendance_api():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "A JSON object is required"}), 400

    student_session_id = data.get("student_session_id")
    if student_session_id is None or student_session_id == "":
        return jsonify({"message": "student_session_id is required"}), 400

    if isinstance(student_session_id, bool):
        return jsonify({"message": "student_session_id must be a positive integer"}), 400

    try:
        if isinstance(student_session_id, int):
            normalized_student_session_id = student_session_id
        elif isinstance(student_session_id, str):
            normalized_student_session_id = int(student_session_id.strip())
        else:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return jsonify({"message": "student_session_id must be a positive integer"}), 400

    if normalized_student_session_id <= 0:
        return jsonify({"message": "student_session_id must be a positive integer"}), 400

    if "total_present" not in data:
        return jsonify({"message": "total_present is required; use null to clear it"}), 400

    raw_total_present = data["total_present"]
    if raw_total_present is None or (isinstance(raw_total_present, str) and not raw_total_present.strip()):
        total_present = None
    else:
        if isinstance(raw_total_present, bool):
            return jsonify({"message": "total_present must be a whole number or null"}), 400

        try:
            if isinstance(raw_total_present, int):
                numeric_total_present = raw_total_present
            elif isinstance(raw_total_present, float) and raw_total_present.is_integer():
                numeric_total_present = int(raw_total_present)
            elif isinstance(raw_total_present, str):
                numeric_total_present = int(raw_total_present.strip())
            else:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            return jsonify({"message": "total_present must be a whole number or null"}), 400

        if numeric_total_present < 0:
            return jsonify({"message": "total_present cannot be negative"}), 400

        total_present = str(numeric_total_present)

    current_session = session["session_id"]

    try:
        student_session = StudentSessions.query.filter(
            and_(
                StudentSessions.id == normalized_student_session_id,
                StudentSessions.session_id == current_session,
            )
        ).first()

        if not student_session:
            return jsonify({"message": "Invalid student session"}), 404

        student_session.Attendance = total_present
        db.session.commit()
        return jsonify({"message": "Overall attendance updated successfully"}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Update overall attendance failed")
        return jsonify({"message": "Database error"}), 500