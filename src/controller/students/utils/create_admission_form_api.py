# src/controller/students/utils/create_admission_form_api.py

import logging
from flask import session, request, jsonify, Blueprint, render_template
from sqlalchemy.exc import SQLAlchemyError

from src import db
from src.model import StudentsDB, ClassData, StudentSessions, Schools
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

logger = logging.getLogger(__name__)

create_admission_form_api_bp = Blueprint('create_admission_form_api_bp', __name__)


def to_dict(model_instance):
    """Safely converts an SQLAlchemy model instance into a dictionary without internal metadata."""
    if not model_instance:
        return {}
    return {
        k: v for k, v in model_instance.__dict__.items() 
        if not k.startswith('_')
    }


@create_admission_form_api_bp.route('/create_admission_form_api', methods=["GET"])
@login_required
@permission_required('admission')
def create_admission_form_api():
    student_id = request.args.get("student_id")
    school_id = session.get("school_id")
    current_session_id = session.get("session_id")

    # 1. Input Validation
    if not student_id:
        return jsonify({"status": "error", "message": "Missing required query parameter: 'student_id'"}), 400

    if not school_id or not current_session_id:
        return jsonify({"status": "error", "message": "Invalid session context. Please re-authenticate."}), 401

    try:
        # 2. Subquery for student's admission session
        admission_session_subquery = (
            db.session.query(StudentsDB.admission_session_id)
            .filter(
                StudentsDB.id == student_id,
                StudentsDB.school_id == school_id
            )
            .scalar_subquery()
        )

        # 3. Main Data Query (Preserves optional StudentSessions via Outer Join)
        student_data = (
            db.session.query(
                StudentsDB, StudentSessions, ClassData, Schools
            )
            .outerjoin(
                StudentSessions,
                (StudentsDB.id == StudentSessions.student_id)
                & (StudentSessions.session_id == admission_session_subquery)
            )
            .join(ClassData, ClassData.id == StudentsDB.admission_class_id)
            .join(Schools, Schools.id == StudentsDB.school_id)
            .filter(
                Schools.id == school_id,
                StudentsDB.id == student_id
            )
            .first()
        )

        if not student_data:
            logger.warning("Admission form request failed: Student ID %s not found in School ID %s", student_id, school_id)
            return jsonify({"status": "error", "message": f"Student with ID '{student_id}' was not found."}), 404

        # Unpack query result tuple
        student_obj, session_obj, class_obj, school_obj = student_data

        # 4. Siblings Query
        phone_number = getattr(student_obj, 'PHONE', None)
        siblings_list = []

        if phone_number:
            siblings = (
                db.session.query(
                    StudentsDB.STUDENTS_NAME,
                    ClassData.CLASS.label('admission_class')
                )
                .join(StudentSessions, StudentsDB.id == StudentSessions.student_id)
                .join(ClassData, ClassData.id == StudentsDB.admission_class_id)
                .filter(
                    StudentsDB.PHONE == phone_number,
                    StudentsDB.id != student_obj.id,
                    StudentSessions.session_id == current_session_id
                )
                .all()
            )
            siblings_list = [
                {"name": s.STUDENTS_NAME, "class": s.admission_class} 
                for s in siblings
            ]

        # 5. Build Flat Payload safely without key conflicts
        student_payload = {
            **to_dict(school_obj),
            **to_dict(class_obj),
            **to_dict(session_obj),  # Safely returns {} if None
            **to_dict(student_obj),
            "dob": getattr(student_obj, 'dob_indian', None),
            "admission_date": getattr(student_obj, 'admission_date_indian', None),
            "siblings": siblings_list
        }

        # 6. Render Component HTML
        rendered_html = render_template('pdf-components/admission_form.html', student=student_payload)

        return jsonify({
            "status": "success",
            "message": "Admission form generated successfully",
            "html": rendered_html
        }), 200

    except SQLAlchemyError as db_err:
        logger.error("Database query error in create_admission_form_api: %s", str(db_err), exc_info=True)
        return jsonify({"status": "error", "message": "A database error occurred while retrieving student records."}), 500

    except Exception as exc:
        logger.critical("Unexpected internal error in create_admission_form_api: %s", str(exc), exc_info=True)
        return jsonify({"status": "error", "message": "An unexpected server error occurred."}), 500