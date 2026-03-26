# src/controller/attendance/get_overall_attendance_data_api.py

from flask import session, request, jsonify, Blueprint
from sqlalchemy import and_

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from src.model import StudentsDB, StudentSessions, ClassData
from src import db
import json

get_overall_attendance_data_api_bp = Blueprint('get_overall_attendance_data_api_bp', __name__)

@get_overall_attendance_data_api_bp.route('/api/get_overall_attendance_data', methods=["GET"])
@login_required
@permission_required('attendance')
def get_overall_attendance_data_api():
    class_id = request.args.get("classID")

    current_session = session["session_id"]


    if not class_id:
        return jsonify({"message": "classID is required"}), 400

    try:

        # Build query to get students with their overall attendance
        students_data = (
            db.session.query(
                StudentsDB.STUDENTS_NAME,
                StudentsDB.FATHERS_NAME,
                StudentsDB.IMAGE,
                StudentsDB.PHONE,
                ClassData.CLASS,
                StudentSessions.ROLL,
                StudentSessions.id.label("student_session_id"),
                StudentSessions.Attendance
            )
            .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
            .join(ClassData, ClassData.id == StudentSessions.class_id)
            .filter(
                StudentSessions.class_id == class_id,
                StudentSessions.session_id == current_session
            )
            .order_by(StudentSessions.ROLL.asc())
        ).all()
    except Exception as e:
        print("Database Query Error:", e)
        return jsonify({"message": "Database error"}), 500

    # Process the data
    students_list = []
    for student in students_data:

        students_list.append({
            "student_name": student.STUDENTS_NAME,
            "fathers_name": student.FATHERS_NAME,
            "image": student.IMAGE,
            "phone": student.PHONE,
            "class": student.CLASS,
            "roll": student.ROLL,
            "student_session_id": student.student_session_id,
            "total_present": student.Attendance
        })

    return jsonify({"students": students_list}), 200