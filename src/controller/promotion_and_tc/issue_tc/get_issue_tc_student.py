# src/controller/student_data_modal_api.py

from flask import session,  request, jsonify, Blueprint

from src import db
from src.model import StudentsDB
from src.model import StudentSessions
from src.model import ClassData
from src.model import TCRecords

import datetime

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

get_issue_tc_student_data_api_bp = Blueprint('get_issue_tc_student_data_api_bp', __name__)


@get_issue_tc_student_data_api_bp.route('/api/get_issue_tc_student_data', methods=["POST"])
@login_required
@permission_required('promote_student')
def ge_promotion_student_data():
    """
    Fetch a single student's data along with promotion details
    based on the previous session.
    """

    # -------------------------
    # Validate request payload
    # -------------------------
    data = request.get_json()
    if not data or "student_id" not in data:
        return jsonify({"error": "Missing required parameters."}), 400

    try:
        student_id = int(data["student_id"])
    except:
        return jsonify({"error": "Invalid parameter format."}), 400

    # -------------------------
    # Validate session values
    # -------------------------
    try:
        current_session_id = int(session["session_id"])
        previous_session_id = current_session_id - 1
    except (KeyError, ValueError):
        return jsonify({"error": "Session data is missing or corrupted. Please logout and login again!"}), 500


    # ----------------------------------------------------------------------
    # 5. Fetch student base data (much simpler query)
    # ----------------------------------------------------------------------
    student_row = (
        db.session.query(
            StudentsDB.id,
            StudentsDB.STUDENTS_NAME,
            StudentsDB.IMAGE,
            StudentsDB.FATHERS_NAME,
            StudentsDB.PHONE,
            ClassData.CLASS,
            StudentSessions.ROLL,
            StudentSessions.id.label("student_session_id"),
            StudentSessions.class_id.label("current_class_id")
        )
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
        .filter(StudentsDB.id == student_id,
                StudentSessions.session_id == previous_session_id)
        .first()
    )

    if not student_row:
        return jsonify({"error": "Student not found"}), 404

    
    # Convert to dict
    result = student_row._asdict()
    

    # If the student already has a cancelled TC for the previous session, expose it.
    cancelled_tc = db.session.query(TCRecords).join(
        StudentSessions,
        TCRecords.student_session_id == StudentSessions.id
    ).filter(
        StudentSessions.student_id == student_id,
        StudentSessions.session_id == previous_session_id,
        TCRecords.status == 'cancelled'
    ).order_by(TCRecords.id.desc()).first()

    if cancelled_tc:
        result["has_cancelled_tc"] = True
        result["cancelled_tc_number"] = int(cancelled_tc.tc_no) if cancelled_tc.tc_no is not None else None
        result["cancelled_tc_date"] = cancelled_tc.tc_date.isoformat() if cancelled_tc.tc_date else None
        result["cancelled_tc_reason"] = cancelled_tc.tc_reason
        result["cancelled_tc_general_conduct"] = cancelled_tc.general_conduct
        result["cancelled_tc_remarks"] = cancelled_tc.remarks
    else:
        result["has_cancelled_tc"] = False
        result["cancelled_tc_number"] = None
        result["cancelled_tc_date"] = None
        result["cancelled_tc_reason"] = None
        result["cancelled_tc_general_conduct"] = None
        result["cancelled_tc_remarks"] = None

    return jsonify(result), 200
