# src/controller/get_result_api.py

from flask import session, request, jsonify, Blueprint, render_template 
from sqlalchemy import func

from src.model import StudentsDB
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.Schools import Schools
from src.model.TeachersLogin import TeachersLogin
from src import db

from .utils.marks_processing import result_data
from .utils.process_marks import process_marks
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

# import time

get_result_api_bp = Blueprint('get_result_api_bp',   __name__)


@get_result_api_bp.route('/get_result_api', methods=["POST"])
@login_required
@permission_required('get_result')
def get_result_api():

    current_session_id = session["session_id"]
    user_id = session["user_id"]
    school_id = session["school_id"]

    try:
        student_id = int(request.json.get("id"))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid student ID."}), 400
    
    try:
        class_id = int(request.json.get("class_id"))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid class ID."}), 400

    # Session checks
    if not student_id or not current_session_id or not user_id:
        return jsonify({"message": "Session data missing. Please logout and login again!"}), 403
    
    extra_fields = {
        "StudentsDB": ["STUDENTS_NAME", "FATHERS_NAME", "FATHERS_NAME", "IMAGE",
                       "MOTHERS_NAME", "ADDRESS", "PHONE", 'GENDER', "PEN"],
        "expr": [func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label("DOB")],
        "ClassData": ["CLASS"],
        "StudentSessions": ["ROLL", "class_id", "Attendance"], 
    }


    student_marks_data = result_data(school_id, current_session_id, 
                                     class_id, student_ids=[student_id],
                                     extra_fields=extra_fields)

    # print(student_marks_data)

    if not student_marks_data:
        return jsonify({"message": "No Data Found"}), 400

    student_marks = process_marks(student_marks_data, add_grades_flag=True, add_grand_total_flag=True)

    # # Print the structure of result student_marks_dict
    # import pprint
    # pprint.pprint(student_marks)

    # get principal and class teacher sign from database

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

    current_session = int(current_session_id)
    session_year = f"{current_session}-{str(current_session + 1)[-2:]}"

    html = render_template('pdf-components/tall_result.html', students=student_marks, 
                            attandance_out_of = '202', 
                            principle_sign = principal_sign, principle_name = principal_name, 
                            teacher_sign = teacher_sign, teacher_name = teacher_name,
                            school_logo = school.Logo, school_heading_image = school.school_heading_image,
                            sesion_year = session_year)
    return jsonify({"html":str(html)})

