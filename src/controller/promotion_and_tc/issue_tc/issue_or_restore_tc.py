# src/controller/generate_tc_form_api.py

from flask import render_template, session, request, Blueprint, jsonify
from sqlalchemy import func

from src.model import SchoolSession, StudentsDB
from src.model import ClassData
from src.model import Schools
from src.model import StudentSessions
from src.model import TCRecords
from src import db

from datetime import datetime

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

issue_or_restore_tc_api_bp = Blueprint('issue_or_restore_tc_api_bp', __name__)

@issue_or_restore_tc_api_bp.route('/api/issue_or_restore_tc', methods=['POST'])
@login_required
@permission_required('tc')
def issue_or_restore_tc():

    data = request.get_json() or {}

    restore_requested = bool(data.get("restore_tc", False))
    student_session_id = data.get("student_session_id")
    tc_number_input = data.get("tc_number")

    leaving_reason = (data.get("leaving_reason") or "").strip()
    leaving_date_str = data.get("leaving_date")
    general_conduct = (data.get("general_conduct") or "").strip()
    other_remarks = (data.get("other_remarks") or "").strip()

    if not student_session_id:
        return jsonify({"error": "Student session ID is required."}), 400
    if not leaving_reason:
        return jsonify({"error": "Leaving reason is required."}), 400
    if not leaving_date_str:
        return jsonify({"error": "Leaving date is required."}), 400
    if not general_conduct:
        return jsonify({"error": "General conduct is required."}), 400
    if not restore_requested and not tc_number_input:
        return jsonify({"error": "TC number is required."}), 400
    

    # ------------------------------
    # Session + User Validation
    # ------------------------------

    current_session_id = int(session.get('session_id'))
    user_id = session.get('user_id')
    school_id = session.get('school_id')
    
    # ------------------------------
    # Leaving Date Validation
    # ------------------------------
    try:
        leaving_date_parsed = datetime.strptime(leaving_date_str, "%Y-%m-%d").date()
    except Exception:
        return jsonify({"error": "Invalid leaving date format. Use YYYY-MM-DD."}), 400



    # -------------------------------------------------------
    # Restore Validation
    # -------------------------------------------------------

    cancelled_tc_record = (
        TCRecords.query.filter_by(
            student_session_id=student_session_id, 
            status='cancelled'
        ).order_by(TCRecords.id.desc())
        .first()
    )

    if restore_requested and not cancelled_tc_record:
        return jsonify({"error": "No cancelled TC record found to restore."}), 400



    # ------------------------------
    # Validate student_session
    # ------------------------------
    student_session = StudentSessions.query.filter_by(
        id=student_session_id
    ).first()

    if not student_session:
        return jsonify({"error": "Student session not found."}), 404

    if student_session.status == "promoted":
        return jsonify({"error": "Student is already promoted."}), 400

    previous_session_id = student_session.session_id

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
        return jsonify({"error": "Student not found."}), 404

    # ------------------------------
    # Load School Classes
    # ------------------------------

    classes = (
        db.session.query(ClassData.id, ClassData.CLASS, ClassData.display_order, ClassData.is_terminal)
        .filter(ClassData.school_id == school_id)
        .order_by(ClassData.display_order.asc())
        .all()
    )
        
    current_class = next(
            (c for c in classes if c.id == student_data.class_id),
            None
        )
    if not current_class:
        return jsonify({"error": "Current class information not found."}), 404


    # -------------------------------------------------------
    # Determine Promoted Class
    # -------------------------------------------------------


    # ✅ If terminal → no next class
    if current_class.is_terminal:
        promoted_class = f"Higher Class"

    else:
        next_class  = None

        for cls in classes:

            if (cls.display_order is not None 
                and cls.display_order > current_class.display_order ):

                next_class = cls
                break  # Found the next class, exit loop

        if not next_class:
            # Safety fallback (data inconsistency)
            return jsonify({"error": "Next class not found, but class is not terminal."}), 500

        promoted_class = next_class.CLASS


    # ------------------------------
    # TC number (manual override possible)
    # ------------------------------

    tc_number = None

    if restore_requested:
        if cancelled_tc_record.tc_no is None:
            return jsonify({"error": "Cancelled TC record has no TC number."}), 400
        
        tc_number = cancelled_tc_record.tc_no

    else:
        try:
            tc_number = int(tc_number_input)
        except (ValueError, TypeError):
            return jsonify({"error": "TC number must be a valid integer."}), 400

        if tc_number <= 0:
            return jsonify({"error": "TC number must be greater than 0."}), 400

        duplicate = (
            db.session.query(TCRecords)
            .join(StudentSessions, TCRecords.student_session_id == StudentSessions.id)
            .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
            .filter(StudentsDB.school_id == school_id, TCRecords.tc_no == tc_number)
            .first()
        )

        duplicate_session_number = (
            db.session.query(StudentSessions)
            .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
            .filter(StudentsDB.school_id == school_id, StudentSessions.tc_number == tc_number)
            .first()
        )

        if duplicate:
            return jsonify({"error": "This TC number is already in use. Please choose another."}), 400
        if duplicate_session_number:
            return jsonify({"error": "This TC number is already in use. Please choose another."}), 400

    # Prevent multiple issued TCRecords for the same student_session
    existing_tc_record = TCRecords.query.filter_by(student_session_id=student_session_id, status='issued').first()
    if existing_tc_record:
        return jsonify({"error": "An issued TC already exists for this student session."}), 400


    # ------------------------------
    # Update TC record
    # ------------------------------
    student_session.status = "tc"

    if restore_requested:
        tc_record = cancelled_tc_record
        tc_record.status = "issued"
        tc_record.tc_date = leaving_date_parsed
        tc_record.tc_reason = leaving_reason
        tc_record.general_conduct = general_conduct
        tc_record.remarks = other_remarks if other_remarks else None
    else:
        tc_record = TCRecords(
            student_session_id=student_session_id,
            tc_no=tc_number,
            tc_date=leaving_date_parsed,
            tc_reason=leaving_reason,
            general_conduct=general_conduct,
            remarks=other_remarks if other_remarks else None,
            status="issued"
        )
        db.session.add(tc_record)

    # ------------------------------
    # Attempt Commit
    # ------------------------------
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error while saving TC."}), 500

    # ------------------------------
    # Render TC HTML
    # ------------------------------
    working_days = (
        db.session.query(SchoolSession.working_days)
        .filter(SchoolSession.school_id == school_id,
                SchoolSession.session_id == previous_session_id)
        .scalar()
    )

    working_days = working_days if working_days else "N/A"
    
    tc_number_text = f"TC-{tc_number}"  # Format TC number with leading zeros (e.g., TC-0001)
    leaving_date = tc_record.tc_date.strftime("%A, %d %B %Y")


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
        tc_date=tc_record.tc_date.isoformat(),
        left_reason=tc_record.tc_reason
    )

    return jsonify({
        'html': html,
        'state': "TC_ISSUED",
        'tc_number': tc_number,
        'tc_date': tc_record.tc_date.isoformat(),
        'left_reason': tc_record.tc_reason
    })

