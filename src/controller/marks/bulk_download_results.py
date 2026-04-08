# src/controller/marks/bulk_download_results.py

from flask import session, request, jsonify, Blueprint, render_template
from sqlalchemy import func

from src.model import SchoolSession, StudentsDB
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.Schools import Schools
from src.model.TeachersLogin import TeachersLogin
from src import db


from .utils.marks_processing import result_data
from .utils.process_marks import process_marks
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

bulk_download_results_bp = Blueprint('bulk_download_results_bp', __name__)


@bulk_download_results_bp.route('/bulk_download_results', methods=["POST"])
@login_required
@permission_required('get_result')  # Assuming same permission as single download
def bulk_download_results():
    current_session_id = session["session_id"]
    user_id = session["user_id"]
    school_id = session["school_id"]

    try:
        student_ids = request.json.get("student_ids", [])
        class_id = int(request.json.get("class_id"))
        if not isinstance(student_ids, list) or not student_ids:
            return jsonify({"message": "Invalid student IDs."}), 400
        student_ids = [int(sid) for sid in student_ids]
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid input."}), 400

    # Session checks
    if not student_ids or not current_session_id or not user_id:
        return jsonify({"message": "Session data missing. Please logout and login again!"}), 403

    extra_fields = {
        "StudentsDB": ["STUDENTS_NAME", "FATHERS_NAME", "IMAGE",
                       "MOTHERS_NAME", "ADDRESS", "PHONE", 'GENDER', "PEN"],
        "expr": [func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label("DOB")],
        "ClassData": ["CLASS"],
        "StudentSessions": ["ROLL", "class_id", "Attendance"],
    }

    student_marks_data = result_data(school_id, current_session_id, 
                                     class_id, student_ids=student_ids,
                                     extra_fields=extra_fields)

    if not student_marks_data:
        return jsonify({"message": "No Data Found"}), 400

    student_marks = process_marks(student_marks_data, add_grades_flag=True, add_grand_total_flag=True)

    school = (
        db.session.query(
            Schools.Logo,
            Schools.school_heading_image
        )
        .filter(Schools.id == school_id)
        .first()
    )

    rows = (
        db.session.query(
            TeachersLogin.Sign,
            TeachersLogin.Name,
            Roles.role_name,
            ClassAccess.class_id
        )
        .join(Roles, Roles.id == TeachersLogin.role_id)
        .outerjoin(ClassAccess, ClassAccess.staff_id == TeachersLogin.id)
        .filter(
            TeachersLogin.school_id == school_id,
            Roles.role_name.in_(["Principal", "Teacher"])
        )
        .all()
    )

    principal_sign = None
    teacher_sign = None

    for sign, name, role, cls_id in rows:
        if role == "Principal":
            principal_sign = sign
            principal_name = name.split(" ")[0]
            
        elif role == "Teacher" and cls_id == class_id:
            teacher_sign = sign
            teacher_name = name.split(" ")[0]


    working_days = (
        db.session.query(SchoolSession.working_days)
        .filter(SchoolSession.school_id == school_id,
                SchoolSession.session_id == current_session_id)
        .scalar()
    )
    attandance_out_of = working_days if working_days else "N/A"



    current_session = int(current_session_id)
    session_year = f"{current_session}-{str(current_session + 1)[-2:]}"

    # Generate HTML for bulk results
    html = render_template('pdf-components/tall_result.html', students=student_marks, 
                            attandance_out_of = attandance_out_of, 
                            principle_sign=principal_sign, teacher_sign=teacher_sign, 
                            principal_name=principal_name, teacher_name=teacher_name,
                            school_logo=school.Logo, school_heading_image=school.school_heading_image,
                            sesion_year=session_year)

    return jsonify({"html": html})