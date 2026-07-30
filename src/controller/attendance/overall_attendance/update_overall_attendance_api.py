# src/controller/attendance/update_overall_attendance_api.py

from flask import session, request, jsonify, Blueprint
from sqlalchemy import and_

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from src.model import StudentSessions
from src import db
import json

update_overall_attendance_api_bp = Blueprint('update_overall_attendance_api_bp', __name__)

@update_overall_attendance_api_bp.route('/api/update_overall_attendance', methods=["POST"])
@login_required
@permission_required('attendance')
def update_overall_attendance_api():
    data = request.json
    student_session_id = data.get("student_session_id")
    total_present = data.get("total_present")  # JSON object like {"total_present": 200, "total_absent": 10}


    current_session = session["session_id"]

    if not student_session_id:
        return jsonify({"message": "student_session_id is required"}), 400
    
    if total_present<0:
        return jsonify({"message": "total_present cannot be negative"}), 400


    # Find the student session
    student_session = StudentSessions.query.filter(
        and_(
            StudentSessions.id == student_session_id,
            StudentSessions.session_id == current_session,
        )
    ).first()

    if not student_session:
        return jsonify({"message": "Invalid student session"}), 404

    # Update the Attendance column with JSON
    try:
        student_session.Attendance = total_present
        db.session.commit()
        return jsonify({"message": "Overall attendance updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        print("Update Overall Attendance Error:", e)
        return jsonify({"message": "Database error"}), 500