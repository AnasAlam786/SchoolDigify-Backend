# src/controller/students/utils/send_watsapp_message_api.py

from flask import session, request, jsonify, Blueprint

from src.model import (
    StudentsDB, ClassData, StudentSessions, Schools
    )

from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

create_watsapp_message_api_bp = Blueprint( 'create_watsapp_message_api_bp',   __name__)


@create_watsapp_message_api_bp.route('/api/create_watsapp_message_api', methods=["GET"])
@login_required
@permission_required('admission')
def create_watsapp_message_api():

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
        return jsonify({"message": "Student not found"}), 404
    
    student, current_session, class_data, school = student_data
    
    message = f"""
        🎉 Admission Confirmed! 🎉

        Dear {student.FATHERS_NAME},

        We are pleased to inform you that the admission of your child has been successfully completed.

        🧑 Student Name: {student.STUDENTS_NAME}
        🏫 Class: {class_data.CLASS}
        🎓 Roll No: {current_session.ROLL}
        📅 Admission Date: {student.ADMISSION_DATE.strftime('%d-%m-%Y')}

        Welcome to our school family! We look forward to a bright and successful academic journey together. If you have any questions, feel free to contact us.

        Best regards,  
        {school.School_Name}
        📞 {school.Phone}
        """

    # Code to send WhatsApp message
    return jsonify({"message": "WhatsApp message created successfully", "watsapp_message": message, "phone": student.PHONE}), 200