# src/controller/show_marks_api.py


from flask import json, session, request, jsonify, Blueprint, render_template
from sqlalchemy import exists 

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model.ClassAccess import ClassAccess
from src import db

from src.controller.marks.utils.fetch_marks import result_data
from src.controller.marks.utils.format_marks import prepare_marks_format
from src.model.ClassData import ClassData
from src.model.TeachersLogin import TeachersLogin

show_marks_bp = Blueprint('show_marks_bp',   __name__)

@show_marks_bp.route('/show_marks', methods=["GET"])
@login_required
@permission_required('show_marks')
def show_marks():
    user_id = session["user_id"]

    classes = (
        db.session.query(ClassData.id, ClassData.CLASS)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .join(TeachersLogin, TeachersLogin.id == ClassAccess.staff_id)
        .filter(TeachersLogin.id == user_id)
        .order_by(ClassData.id.asc())
        .all()
    )
    return render_template('marks_management/show_marks.html', Data=None, classes = classes)


@show_marks_bp.route('/api/show_marks', methods=["GET"])
@login_required
@permission_required('show_marks')  # Assuming same permission as single download
def show_marks_api():
    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]

    try:
        class_id = int(request.args.get("class_id"))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid class selected."}), 400

    has_access = db.session.query(
        exists().where(ClassAccess.staff_id == user_id)
    ).scalar()

    if not has_access:
        return jsonify({"message": "You are not authorized to access this class."}), 403
    
    extra_fields = {
        "StudentsDB": [
            "STUDENTS_NAME", "DOB", "FATHERS_NAME", "MOTHERS_NAME",
            "IMAGE", "PEN", "PHONE", "GENDER", "ADDRESS",
        ],
        "ClassData": ["CLASS"],
        "StudentSessions": ["ROLL", "class_id", "Attendance"]
    }

    try:
        student_marks_data = result_data(
            school_id,
            current_session_id,
            class_id,
            extra_fields=extra_fields
        )

        student_marks_data = [
            prepare_marks_format(result)
            for result in student_marks_data
        ]

    except Exception as e:
        return jsonify({"message": f"Error fetching marks data: {str(e)}"}), 500


    if not student_marks_data:
        print("No student marks data found for the given class.")
        # html = render_template('marks_management/marks_table.html', student_marks=[], class_empty=True)
        return jsonify({'error': 'No student marks data found for the given class.'}), 403

    return jsonify({"student_marks":student_marks_data})
    