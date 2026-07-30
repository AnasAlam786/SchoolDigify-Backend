# src/controller/students/update/final_student_update_api.py

from flask import session, Blueprint, request, jsonify

from src.controller.students.utils.conflict_verification import verify_conflicts
from src.controller.students.utils.student_service import StudentService

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required


final_update_student_api_bp = Blueprint('final_update_student_api_bp', __name__)


@final_update_student_api_bp.route('/api/update_student', methods=["POST"])
@login_required
@permission_required('update_student')
def student_update_api():
    """Update an existing student after all validations."""
    payload = request.get_json() or {}
    
    student_id = payload.get("student_id")
    verified_data = payload.get("verifiedData", [])
    image_b64 = payload.get("image")
    image_status = payload.get("image_status", "unchanged")

    school_id = session.get("school_id")
    session_id = session.get("session_id")
    if not school_id or not session_id:
        return jsonify({"message": "Session context missing."}), 400
    
    #conflics validating
    error = verify_conflicts(verified_data, mode='update', student_id=student_id)
    if error:
        return jsonify(error), 400

    error = StudentService.update_student(student_id, verified_data, image_b64, image_status, school_id, session_id)
    if error:
        return jsonify([{"message": error}]), 500

    return jsonify({"message": "Student updated successfully.", "student_id": student_id}), 200
   