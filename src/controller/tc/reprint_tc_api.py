from flask import render_template, session, request, Blueprint, jsonify
from sqlalchemy import func

from src.model import StudentsDB
from src.model import ClassData
from src.model import Schools
from src.model import StudentSessions
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

reprint_tc_api_bp = Blueprint('reprint_tc_api_bp', __name__)

@reprint_tc_api_bp.route('/api/tc/reprint', methods=['POST'])
@login_required
@permission_required('tc')
def reprint_tc():
    data = request.get_json() or {}
    student_session_id = data.get('student_session_id')

    try:
        user_id = session.get('user_id')
        school_id = session.get('school_id')
    except (TypeError, ValueError):
        return jsonify({"message": "Unable to get the session information, Try after logging in again."}), 400

    if not student_session_id:
        return jsonify({"message": "Student session ID is not provided."}), 400

    if not user_id:
        return jsonify({"message": "Unable to get the session information, Try after logging in again."}), 400

    # Check if student session exists and has TC issued
    student_session = StudentSessions.query.filter_by(id=student_session_id).first()
    if not student_session:
        return jsonify({"message": "Student session not found."}), 404

    if student_session.status != "tc":
        return jsonify({"message": "TC not issued for this student."}), 400

    # Fetch allowed classes once, ordered by display_order
    classes = (
        db.session.query(ClassData.id, ClassData.CLASS, ClassData.display_order)
        .filter(ClassData.school_id == school_id)
        .order_by(ClassData.display_order.asc())
        .all()
    )

    # Bulk load student details
    student_data = (
        db.session.query(

            StudentsDB.STUDENTS_NAME, StudentsDB.AADHAAR, StudentsDB.SR,
            StudentsDB.FATHERS_NAME, StudentsDB.MOTHERS_NAME, StudentsDB.PHONE,
            StudentsDB.ADMISSION_NO, StudentsDB.ADDRESS, StudentsDB.Caste_Type, StudentsDB.RELIGION,
            StudentsDB.ADMISSION_DATE, StudentsDB.SR, StudentsDB.IMAGE,
            StudentsDB.GENDER, StudentsDB.PEN,
            StudentsDB.APAAR,
            func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label('DOB'),

            StudentSessions.Attendance,
            StudentSessions.class_id,
            StudentSessions.Height,
            StudentSessions.Weight,
            StudentSessions.status,
            StudentSessions.tc_number,
            func.to_char(StudentSessions.tc_date, 'Dy, DD Mon YYYY').label('tc_date'),
            StudentSessions.left_reason,
            ClassData.CLASS.label('current_class'),
            ClassData.is_terminal,


            Schools.Logo.label('school_logo'),
            Schools.school_heading_image.label('school_heading_image'),
        )
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
        .join(Schools, Schools.id == StudentsDB.school_id)
        .filter(
            StudentSessions.id == student_session_id,
        )
        .first()
    )

    if not student_data:
        return jsonify({"message": "Student not found."}), 404

    current_class_id = student_data.class_id
    # Find current class display_order
    current_class_info = next((c for c in classes if c[0] == current_class_id), None)
    if not current_class_info:
        return jsonify({"message": "Current class information not found."}), 404

    current_display_order = current_class_info[2]  # display_order is at index 2
    current_class_name = current_class_info[1]  # CLASS name is at index 1

    if student_data.is_terminal:
        # Final class → no promotion
        promoted_class = "Higher Class"
    else:

        # Find next class by display_order
        next_class_info = next(
            (c for c in classes if c[2] is not None and c[2] > current_display_order),
            None
        )

        if not next_class_info:
            return jsonify({"message": "Next class not found."}), 500
        
        promoted_class = next_class_info[1]  # CLASS name is at index 1



    # Fixed metadata (could be moved to config)
    working_days = 202
    tc_number_text = f"TC-{student_session.tc_number}"  # Format TC number with leading zeros (e.g., TC-0001)

    # Render HTML directly with existing TC data
    html = render_template(
        'pdf-components/tcform.html',
        student=student_data,
        working_days=working_days,
        general_conduct="Very Good",  # Default for reprint
        other_remarks="",  # Default for reprint
        leaving_reason=student_session.left_reason or "TC Issued",
        promoted_class=promoted_class,
        tc_number=tc_number_text,
        leaving_date=student_data.tc_date,
        left_reason=student_session.left_reason
    )

    return jsonify({
        'html': html,
        'tc_number': student_session.tc_number,
        'tc_date': student_data.tc_date,
        'left_reason': student_session.left_reason
    })
