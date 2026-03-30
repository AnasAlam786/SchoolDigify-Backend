# src/controller/get_result_api.py

from flask import session, request, jsonify, Blueprint, render_template, url_for 
from sqlalchemy import func

from src.model import StudentsDB
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.Schools import Schools
from src.model.TeachersLogin import TeachersLogin
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
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

    principal_sign = ""
    teacher_sign = ""
    principal_name = ""
    teacher_name = ""

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

def _prepare_certificate_students(student_items):
    certified_students = []

    for item in student_items:
        print(item)
        
        try:
            student_id = int(item.get('student_id'))
        except (TypeError, ValueError):
            continue

        rank = item.get('rank')
        percentage = item.get('percentage')


        student = StudentsDB.query.filter_by(id=student_id).first()
        print(f"Processing student: {student} (ID: {student_id})")
        if not student:
            continue

        

        student_session = StudentSessions.query.filter_by(student_id=student_id, session_id=session.get('session_id')).first()
        class_name = None
        if student_session and student_session.class_id:
            class_row = ClassData.query.filter_by(id=student_session.class_id).first()
            class_name = class_row.CLASS if class_row else None

        print(item)

        img_src = None
        if student.IMAGE:
            img_src = f'https://lh3.googleusercontent.com/d/{student.IMAGE}=s220'

        if not img_src:
            img_src = url_for('static', filename='images/default_student.png', _external=False)

        certified_students.append({
            'STUDENTS_NAME': student.STUDENTS_NAME or 'Student Name',
            'FATHERS_NAME': student.FATHERS_NAME or 'Father Name',
            'CLASS': class_name or student.CLASS or 'N/A',
            'rank': str(rank) if rank is not None else 'N/A',
            'percentage': str(percentage) if percentage is not None else '0',
            'student_image': img_src,
        })

    return certified_students



@get_result_api_bp.route('/print_certificate_api', methods=["POST"])
@login_required
@permission_required('get_result')
def print_certificate_api():
    payload = request.json or {}
    student_items = payload.get('students')
    school_name = session.get('school_name')

    if not student_items or not isinstance(student_items, list):
        return jsonify({'message': 'students list is required and must be an array.'}), 400

    try:
        certified_students = _prepare_certificate_students(student_items)
        if not certified_students:
            return jsonify({'message': 'No valid student data for certificate generation.'}), 400

        school_logo = session.get('logo') or ''
        session_year = 'N/A'
        current_session_id = session.get('session_id')
        if isinstance(current_session_id, int):
            session_year = f"{current_session_id}-{str(current_session_id + 1)[-2:]}"

        html = render_template('pdf-components/certificates/certificate.html',
                            students=certified_students,
                            session_year=session_year,
                            school_logo=school_logo, school_name=school_name)

        return jsonify({'html': str(html)})
    except Exception as e:
        print(f"Error generating certificate: {e}")
        return jsonify({'message': 'An error occurred while generating the certificate.', 'error': str(e)}), 500


# bulk route kept for backward support; same as single route expects student list
@get_result_api_bp.route('/bulk_print_certificate_api', methods=["POST"])
@login_required
@permission_required('get_result')
def bulk_print_certificate_api():
    payload = request.json or {}
    student_items = payload.get('students')
    school_name = session.get('school_name')

    if not student_items or not isinstance(student_items, list):
        return jsonify({'message': 'students list is required and must be an array.'}), 400

    certified_students = _prepare_certificate_students(student_items)

    print(f"Prepared certified students data: {certified_students}")  # Debug log

    if not certified_students:
        return jsonify({'message': 'No valid student certificate data found.'}), 400

    school_logo = session.get('logo') or ''
    session_year = 'N/A'
    current_session_id = session.get('session_id')
    if isinstance(current_session_id, int):
        session_year = f"{current_session_id}-{str(current_session_id + 1)[-2:]}"

    html = render_template('pdf-components/certificates/certificate.html',
                           students=certified_students,
                           session_year=session_year,
                           school_logo=school_logo, school_name=school_name)
    return jsonify({'html': str(html)})
