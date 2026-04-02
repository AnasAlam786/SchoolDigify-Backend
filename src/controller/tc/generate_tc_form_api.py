# src/controller/generate_tc_form_api.py

from flask import render_template, session, request, Blueprint, jsonify
from sqlalchemy import select, func

from src.model import StudentsDB
from src.model import ClassData
from src.model import Schools
from src.model import StudentSessions
from src.model import ClassAccess
from src import db

from datetime import datetime

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

generate_and_save_tc_api_bp = Blueprint('generate_and_save_tc_api_bp', __name__)

@generate_and_save_tc_api_bp.route('/api/tc/generate-and-save', methods=['POST'])
@login_required
@permission_required('tc')
def generate_and_save_tc():

    data = request.get_json() or {}
    student_session_id = data.get('student_session_id')
    leaving_reason = data.get('leavingReason', '')
    leaving_date = data.get('leavingDate')
    general_conduct = data.get('generalConduct', '')
    other_remarks = data.get('otherRemarks', '')

    # ------------------------------
    # Session + User Validation
    # ------------------------------
    try:
        current_session_id = int(session.get('session_id'))
        previous_session_id = current_session_id - 1
        user_id = session.get('user_id')
        school_id = session.get('school_id')
        if not user_id or not school_id:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"message": "Unable to get the session information, Try logging in again."}), 400

    if not student_session_id:
        return jsonify({"message": "Student session ID is not provided."}), 400

    if not leaving_reason or not leaving_date or not general_conduct:
        return jsonify({"message": "All fields are required."}), 400

    # ------------------------------
    # Leaving Date Validation
    # ------------------------------
    try:
        leaving_date_parsed = datetime.strptime(leaving_date, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"message": "Invalid leaving date format. Use YYYY-MM-DD."}), 400

    # ------------------------------
    # Validate student_session
    # ------------------------------
    student_session = StudentSessions.query.filter_by(id=student_session_id).first()
    if not student_session:
        return jsonify({"message": "Student session not found."}), 404

    if student_session.status == "promoted":
        return jsonify({"message": "Student is already promoted."}), 400

    # ------------------------------
    # Fetch classes for the school
    # ------------------------------
    classes = (
        db.session.query(ClassData.id, ClassData.CLASS, ClassData.display_order, ClassData.is_terminal)
        .filter(ClassData.school_id == school_id)
        .order_by(ClassData.display_order.asc())
        .all()
    )

    # ------------------------------
    # Load student details
    # ------------------------------
    student_data = (
        db.session.query(
            StudentsDB.STUDENTS_NAME, StudentsDB.AADHAAR, StudentsDB.SR,
            StudentsDB.FATHERS_NAME, StudentsDB.MOTHERS_NAME, StudentsDB.PHONE,
            StudentsDB.ADMISSION_NO, StudentsDB.ADDRESS, StudentsDB.Caste_Type, StudentsDB.RELIGION,
            StudentsDB.ADMISSION_DATE, StudentsDB.SR, StudentsDB.IMAGE,
            StudentsDB.GENDER, StudentsDB.PEN, StudentsDB.APAAR,
            func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label('DOB'),
            StudentSessions.Attendance, StudentSessions.class_id,
            StudentSessions.Height, StudentSessions.Weight, StudentSessions.status,
            StudentSessions.tc_number, StudentSessions.tc_date,
            StudentSessions.left_reason,
            ClassData.CLASS.label('current_class'),
            Schools.Logo.label('school_logo'),
            Schools.school_heading_image.label('school_heading_image')
        )
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
        .join(Schools, Schools.id == StudentsDB.school_id)
        .filter(StudentSessions.id == student_session_id)
        .first()
    )

    if not student_data:
        return jsonify({"message": "Student not found."}), 404

    # ------------------------------
    # Determine promoted class
    # ------------------------------
    current_class_id = student_data.class_id
    current_class_info = next((c for c in classes if c[0] == current_class_id), None)

    if not current_class_info:
        return jsonify({"message": "Current class information not found."}), 404

    current_display_order = current_class_info[2]
    current_class_name = current_class_info[1]
    is_terminal = current_class_info[3]

    # ✅ If terminal → no next class
    if is_terminal:
        promoted_class = f"Higher Class"

    else:
        next_class_info = None
        min_order = float('inf')

        for c in classes:
            print(c)
            display_order = c[2]

            if display_order is not None and current_display_order < display_order < min_order:
                min_order = display_order
                next_class_info = c

        if not next_class_info:
            # Safety fallback (data inconsistency)
            return jsonify({"message": "Next class not found, but class is not terminal."}), 500

        promoted_class = next_class_info[1]


    # ------------------------------
    # TC number (manual override possible)
    # ------------------------------

    tc_number_input = data.get('tc_number')
    tc_number = None

    if not tc_number_input:
        return jsonify({"message": "TC number must be a valid integer."}), 400

    try:
        tc_number = int(tc_number_input)
    except ValueError:
        return jsonify({"message": "TC number must be a valid integer."}), 400

    if tc_number <= 0:
        return jsonify({"message": "TC number must be greater than 0."}), 400

    duplicate = (
        db.session.query(StudentSessions)
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .filter(StudentsDB.school_id == school_id, StudentSessions.tc_number == tc_number)
        .first()
    )

    if duplicate:
        return jsonify({"message": "This TC number is already in use. Please choose another."}), 400


    # ------------------------------
    # Update TC record
    # ------------------------------
    tc_row = StudentSessions.query.filter_by(
        id=student_session_id,
        session_id=previous_session_id
    ).first()

    if not tc_row:
        return jsonify({"message": "Student session not found for TC generation."}), 404

    tc_row.status = "tc"
    tc_row.left_reason = leaving_reason
    tc_row.tc_date = leaving_date_parsed
    tc_row.tc_number = tc_number

    # ------------------------------
    # Attempt Commit
    # ------------------------------
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Database error while saving TC."}), 500

    # ------------------------------
    # Render TC HTML
    # ------------------------------
    working_days = 202
    tc_number_text = f"TC-{tc_number}"  # Format TC number with leading zeros (e.g., TC-0001)
    leaving_date = tc_row.tc_date.strftime("%A, %d %B %Y")


    html = render_template(
        'pdf-components/tcform.html',
        student=student_data,
        working_days=working_days,
        general_conduct=general_conduct,
        leaving_date=leaving_date,
        other_remarks=other_remarks,
        leaving_reason=leaving_reason,
        promoted_class=promoted_class,
        tc_number=tc_number_text,
        tc_date=tc_row.tc_date.isoformat(),
        left_reason=tc_row.left_reason
    )

    return jsonify({
        'html': html,
        'state': "TC_ISSUED",
        'tc_number': tc_number_text,
        'tc_date': tc_row.tc_date.isoformat(),
        'left_reason': tc_row.left_reason
    })


def get_highest_tc_no():
    school_id = session.get('school_id')
    highest_tc = ( 
        db.session.query(func.max(StudentSessions.tc_number))
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .filter(StudentsDB.school_id == school_id)
        .scalar() 
    )

    if highest_tc is None:
        return 0
    
    return highest_tc


@generate_and_save_tc_api_bp.route('/api/tc/get-new-tc-number', methods=['POST'])
@login_required
@permission_required('tc')
def api_get_new_tc_number():
    highest_tc = get_highest_tc_no()
    try:
        highest_tc = int(highest_tc) if highest_tc else 0
    except Exception:
        return jsonify({"message": "Error computing TC number"}), 500
    return jsonify({"next_tc_number": highest_tc + 1})