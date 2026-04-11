# src/controller/students/utils/create_admission_form_api.py

from flask import session, request, jsonify, Blueprint, render_template

from src.model import (
    StudentsDB, ClassData, StudentSessions, Schools
    )

from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

create_admission_form_api_bp = Blueprint( 'create_admission_form_api_bp',   __name__)


@create_admission_form_api_bp.route('/create_admission_form_api', methods=["GET"])
@login_required
@permission_required('admission')
def create_admission_form_api():

    student_id = request.args.get("student_id")
    school_id = session.get("school_id")
    current_session_id = session.get("session_id")

    student_data = db.session.query(
            StudentsDB, StudentSessions, ClassData, Schools
        ).join(
            StudentSessions, StudentsDB.id == StudentSessions.student_id
        ).join(
            ClassData, ClassData.id == StudentSessions.class_id
        ).join(
            Schools, Schools.id == StudentsDB.school_id
        ).filter(
            Schools.id == school_id,
            StudentsDB.id == student_id,
            StudentSessions.session_id == current_session_id,
    ).first()

    if not student_data:
        print(f"No student data found for student_id: {student_id} in school_id: {school_id} for session_id: {current_session_id}")
        return jsonify({"message": "Student not found"}), 404
    

    print(student_data.StudentsDB.dob_indian)          # 17-02-2020
    print(student_data.StudentsDB.admission_date_indian)  # 31-07-2025

    phone_number = student_data.StudentsDB.PHONE
    siblings = db.session.query(
        StudentsDB.STUDENTS_NAME,
        ClassData.CLASS
    ).join(
        StudentSessions, StudentsDB.id == StudentSessions.student_id
    ).join(
        ClassData, ClassData.id == StudentSessions.class_id
    ).filter(
        StudentsDB.PHONE == phone_number,
        StudentsDB.id != student_data.StudentsDB.id,  # exclude self
        StudentSessions.session_id == current_session_id
    ).all()

    
    student = {
        **{k: v for k, v in student_data.StudentsDB.__dict__.items() if not k.startswith('_')},
        "dob": student_data.StudentsDB.dob_indian,
        "admission_date": student_data.StudentsDB.admission_date_indian,
        **{k: v for k, v in student_data.StudentSessions.__dict__.items() if not k.startswith('_')},
        **{k: v for k, v in student_data.ClassData.__dict__.items() if not k.startswith('_')},
        **{k: v for k, v in student_data.Schools.__dict__.items() if not k.startswith('_')}
    }
    
    if siblings:
        student["siblings"] = [{"name": s.STUDENTS_NAME, "class": s.CLASS} for s in siblings]
    else:
        student["siblings"] = []


    html = render_template('pdf-components/admission_form.html', student=student)

    return jsonify({"message":"Form Generated Successfully", "html":str(html)}), 200