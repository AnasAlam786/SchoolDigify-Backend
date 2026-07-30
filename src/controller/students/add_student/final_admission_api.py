# src/controller/students/add_student/final_admission_api.py

from flask import Blueprint, jsonify, request, session
import time

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.students.utils.conflict_verification import verify_conflicts
from src.controller.students.utils.student_service import StudentService

final_admission_api_bp = Blueprint("final_admission_api_bp", __name__)


@final_admission_api_bp.route("/api/add_student", methods=["POST"])
@login_required
@permission_required("admission")
def final_admission_api():
    """Create a new student after final validation."""

    start = time.perf_counter()

    data = request.get_json(silent=True) or {}

    verified_data = data.get("verifiedData", {})
    image_b64 = data.get("IMAGE")

    school_id = session.get("school_id")
    session_id = session.get("session_id")

    if not school_id or not session_id:
        return jsonify({
            "error": "Session context missing."
        }), 400

    # Final conflict verification
    conflict_errors = verify_conflicts(verified_data, mode="add")

    if conflict_errors:
        return jsonify({
            "error": "Some fields must be unique.",
            "errors": conflict_errors
        }), 400

    # Create student
    student_id, error = StudentService.create_student(
        verified_data, image_b64,
        school_id, session_id,
    )

    if error:
        return jsonify({
            "error": error
        }), 500

    end = time.perf_counter()
    print(f"Execution time Final admission: {end - start:.6f} seconds")

    return jsonify({
        "message": "Student added successfully.",
        "student_id": student_id
    }), 200