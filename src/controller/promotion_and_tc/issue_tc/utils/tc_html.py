from flask import render_template, session, request, Blueprint, jsonify
from sqlalchemy import func

from src.model import SchoolSession, StudentsDB
from src.model import ClassData
from src.model import Schools
from src.model import StudentSessions
from src.model import TCRecords
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

get_tc_html_api_bp = Blueprint('get_tc_html_api_bp', __name__)

@get_tc_html_api_bp.route('/api/get_tc_html', methods=['POST'])
@login_required
@permission_required('tc')
def get_tc_html():
    data = request.get_json() or {}
    student_session_id = data.get('student_session_id')

    try:
        user_id = session.get('user_id')
        school_id = session.get('school_id')
        current_session_id = int(session.get('session_id'))
        if not user_id or not school_id or not current_session_id:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Unable to get the session information, Try after logging in again."}), 400

    if not student_session_id:
        return jsonify({"error": "Student session ID is not provided."}), 400

    if not user_id:
        return jsonify({"error": "Unable to get the session information, Try after logging in again."}), 400

    # Check if student session exists and has TC issued
    student_session = (
        StudentSessions.query.filter_by(
            id=student_session_id
        ).first()
    
    )
    previous_session_id = student_session.session_id if student_session else int(current_session_id)-1 

    if not student_session:
        return jsonify({"error": "Student session not found."}), 404

    if student_session.status != "tc":
        return jsonify({"error": "TC not issued for this student."}), 400

    # Fetch allowed classes once, ordered by display_order
    classes = (
        db.session.query(ClassData.id, ClassData.CLASS, ClassData.display_order)
        .filter(ClassData.school_id == school_id)
        .order_by(ClassData.display_order.asc())
        .all()
    )

    # Fetch TC record for the requested student session
    tc_record = (
        TCRecords.query.filter_by(
            student_session_id=student_session_id, 
            status='issued'
        ).order_by(TCRecords.id.desc()).first()
    )
    if not tc_record:
        return jsonify({"error": "No issued TC record found for this student."}), 404

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
        return jsonify({"error": "Student not found."}), 404

    current_class_id = student_data.class_id
    # Find current class display_order
    current_class_info = next((c for c in classes if c[0] == current_class_id), None)
    if not current_class_info:
        return jsonify({"error": "Current class information not found."}), 404

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
            return jsonify({"error": "Next class not found."}), 500
        
        promoted_class = next_class_info[1]  # CLASS name is at index 1


    
    working_days= (
        db.session.query(SchoolSession.working_days)
        .filter(SchoolSession.school_id == school_id,
                SchoolSession.session_id == previous_session_id)
        .scalar()
    )
    working_days = working_days if working_days else "N/A"
    
    tc_number_text = f"TC-{tc_record.tc_no}"  # Format TC number with leading zeros (e.g., TC-0001)

    # Render HTML directly with existing TC data
    html = render_template(
        'pdf-components/tcform.html',
        student=student_data,
        working_days=working_days,
        general_conduct="Very Good",  # Default for reprint
        other_remarks="",  # Default for reprint
        leaving_reason=tc_record.tc_reason or "TC Issued",
        promoted_class=promoted_class,
        tc_number=tc_number_text,
        leaving_date=tc_record.tc_date.strftime('%A, %d %B %Y') if tc_record.tc_date else None,
        left_reason=tc_record.tc_reason
    )

    return jsonify({
        'html': html,
        'tc_number': tc_record.tc_no,
        'leaving_date': tc_record.tc_date.isoformat() if tc_record.tc_date else None,
        'left_reason': tc_record.tc_reason
    })
