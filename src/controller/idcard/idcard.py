# src/controller/idcard/idcard.py

from flask import render_template, session, Blueprint, jsonify
from sqlalchemy import func

from src.model import Schools, TeachersLogin
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required



idcard_bp = Blueprint( 'idcard_bp',   __name__)

@idcard_bp.route('/idcard', methods=['GET'])
@login_required
@permission_required('idcard')
def idcards_page():

    school_id = session['school_id']
    user_id = session["user_id"]

    classes_query = (
        db.session.query(ClassData)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .filter(ClassAccess.staff_id == user_id)
        .order_by(ClassData.id.asc())
    )

    classes = classes_query.all()

    school = db.session.query(
        func.upper(Schools.School_Name).label('School_Name'),
        Schools.Address,
        Schools.Phone,
        Schools.Logo,
        Schools.UDISE
    ).filter(
        Schools.id == school_id
    ).first()

    return render_template('/idcard.html', school=school, classes=classes)

@idcard_bp.route('/api/idcard_students/<int:class_id>', methods=['GET'])
@login_required
@permission_required('idcard')
def get_students_by_class(class_id):
    school_id = session['school_id']
    current_session = session["session_id"]
    user_id = session["user_id"]

    # Check if user has access to this class
    has_access = db.session.query(ClassAccess).filter(
        ClassAccess.staff_id == user_id,
        ClassAccess.class_id == class_id
    ).first()
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    # Query students for the specific class
    students_query = db.session.query(
        StudentsDB.id.label("student_id"),
        StudentsDB.STUDENTS_NAME,
        func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label('dob'),
        StudentsDB.FATHERS_NAME,
        StudentsDB.IMAGE,
        StudentsDB.PHONE,
        StudentsDB.ADDRESS,
        StudentSessions.ROLL,
        StudentSessions.class_id,
        ClassData.CLASS,
        ClassData.Section,
        TeachersLogin.Sign.label('teachers_sign')
    ).join(
        StudentSessions, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, StudentSessions.class_id == ClassData.id
    ).outerjoin(
        TeachersLogin, ClassData.class_teacher_id == TeachersLogin.id
    ).filter(
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == current_session,
        ClassData.id == class_id
    ).order_by(
        StudentSessions.ROLL.asc()
    ).all()

    # Get school data
    school = db.session.query(
        func.upper(Schools.School_Name).label('School_Name'),
        Schools.Address,
        Schools.Phone,
        Schools.Logo,
        Schools.UDISE
    ).filter(
        Schools.id == school_id
    ).first()

    principal_sign = db.session.query(TeachersLogin.Sign).filter(
        TeachersLogin.school_id == school_id,
        TeachersLogin.role_id == 2
    ).scalar()

    current_session = int(current_session)
    session_year = f"{current_session}-{str(current_session + 1)[-2:]}"

    students_data = []
    for student in students_query:
        students_data.append({
            'student_id': student.student_id,
            'student_name': student.STUDENTS_NAME,
            'dob': student.dob,
            'father_name': student.FATHERS_NAME,
            'image': student.IMAGE,
            'phone': student.PHONE,
            'address': student.ADDRESS,
            'roll': student.ROLL,
            'class': student.CLASS,
            'section': student.Section,
            'teacher_sign': student.teachers_sign,
            'class_roll': f"{student.CLASS} - {student.ROLL}",
            'session_year': session_year
        })

    return jsonify({
        'students_data': students_data,
        'school_data': {
            'name': school.School_Name if school else '',
            'address': school.Address if school else '',
            'phone': school.Phone if school else '',
            'logo': school.Logo if school else '',
            'udise': school.UDISE if school else '',
            'principal_sign': principal_sign if principal_sign else ''
        },
        
    })

