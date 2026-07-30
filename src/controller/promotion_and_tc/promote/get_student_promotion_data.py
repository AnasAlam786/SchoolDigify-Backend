# src/controller/student_data_modal_api.py

from flask import session,  request, jsonify, Blueprint

from src import db
from src.model import StudentsDB
from src.model import StudentSessions
from src.model import ClassData

import datetime

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required
from src.controller.utils.get_gapped_rolls import get_gapped_rolls


get_student_promotion_data_api_bp = Blueprint('get_student_promotion_data_api_bp', __name__)

@get_student_promotion_data_api_bp.route('/api/get_student_promotion_data', methods=["POST"])
@login_required
@permission_required('promote_student')
def get_promotion_student_data():
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
        school_id = session["school_id"]
        current_session_id = int(session["session_id"])
        previous_session_id = current_session_id - 1
    except (KeyError, ValueError):
        return jsonify({"error": "Session data is missing or corrupted. Please logout and login again!"}), 500


    # ----------------------------------------------------------------------
    # 1. Fetch student's current class info FROM PREVIOUS SESSION
    # ----------------------------------------------------------------------
    current_info = (
        db.session.query(ClassData.grade_level, ClassData.is_terminal)
        .join(StudentSessions, StudentSessions.class_id == ClassData.id)
        .filter(
            StudentSessions.student_id == student_id,
            StudentSessions.session_id == previous_session_id,
        )
        .first()
    )

    if not current_info:
        return jsonify({"error": "Student not found in previous session."}), 404

    current_grade_level, is_terminal = current_info


    # ----------------------------------------------------------------------
    # 2. Fetch all possible classes (same or above)
    # ----------------------------------------------------------------------

    available_classes = (
        db.session.query(ClassData.id, ClassData.CLASS, ClassData.grade_level)
        .filter(ClassData.school_id == school_id,
                ClassData.grade_level >= current_grade_level)
        .order_by(ClassData.grade_level.asc())
        .all()
    )

    # ----------------------------------------------------------------------
    # 3. Determine next class (simple scan)
    # ----------------------------------------------------------------------
    
    if is_terminal:
        # Student is in final class → no promotion
        next_class_id = None
        next_class_name = "Higher Class"

    else:
        next_class = None
    
        for c_id, c_name, g_level in available_classes:
            if g_level > current_grade_level:
                next_class = (c_id, c_name)
                break

        if not next_class:
            return jsonify({"error": "Next class not found for non-terminal class."}), 500
        
        next_class_id, next_class_name = next_class


    # ----------------------------------------------------------------------
    # 4. Get available roll numbers for promoted class in CURRENT session
    # ----------------------------------------------------------------------
    if is_terminal:
        available_rolls = []
        next_roll_no = None
    else:
        rolls_data = get_gapped_rolls(next_class_id, current_session_id)

        available_rolls = rolls_data['gapped_rolls'] + [rolls_data['next_roll']]
        next_roll_no = rolls_data['next_roll']


    # ----------------------------------------------------------------------
    # 5. Fetch student base data (much simpler query)
    # ----------------------------------------------------------------------
    student_row = (
        db.session.query(
            StudentsDB.id,
            StudentsDB.STUDENTS_NAME,
            StudentsDB.IMAGE,
            StudentsDB.GENDER,
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
    
    # Add available classes and roll information
    available_classes = [
        {"id": c[0], "name": c[1], "grade_level": c[2]}
        for c in available_classes
    ]


    
    default_form_values = {
        "next_class_name":next_class_name,
        "next_class_id":next_class_id,
        "next_roll_no":next_roll_no,
        "today_date": datetime.date.today().strftime('%Y-%m-%d')
    }

    return jsonify({
        "student_data": result, 
        "default_form_values": default_form_values,
        "available_rolls": available_rolls,
        "available_classes": available_classes
    }), 200
