# src/controller/show_marks_api.py


from flask import session, request, jsonify, Blueprint, render_template
from sqlalchemy import exists 

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model.ClassAccess import ClassAccess
from src import db

from src.controller.marks.utils.marks_processing import result_data
from src.controller.marks.utils.process_marks import process_marks
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


@show_marks_bp.route('/show_marks_api', methods=["POST"])
@login_required
@permission_required('show_marks')  # Assuming same permission as single download
def show_marks_api():
    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]

    try:
        class_id = int(request.json.get("class_id"))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid class selected."}), 400

    if not school_id or not current_session_id or not user_id:
        return jsonify({"message": "Unable to get session data, Please try to logout and login again!"}), 403

    has_access = db.session.query(
        exists().where(ClassAccess.staff_id == user_id)
    ).scalar()

    if not has_access:
        return jsonify({"message": "You are not authorized to access this class."}), 403
    
    extra_fields = {
        "StudentsDB": ["STUDENTS_NAME", "DOB", "FATHERS_NAME", "FATHERS_NAME"],
        "ClassData": ["CLASS"],
        "StudentSessions": ["ROLL", "class_id"]
    }

    try:
        student_marks_data = result_data(school_id, current_session_id, class_id, 
                                     extra_fields=extra_fields)        
    except Exception as e:
        return jsonify({"message": f"Error fetching marks data: {str(e)}"}), 500


    if not student_marks_data:
        # no students found for this class – render UI with a special flag
        print("No student marks data found for the given class.")
        html = render_template('marks_management/marks_table.html', student_marks=[], class_empty=True)
        return jsonify({"html": str(html)})
    
    student_marks = process_marks(student_marks_data, add_grades_flag=False, add_grand_total_flag=True)

    html = render_template("marks_management/marks_table.html", student_marks=student_marks)

    return jsonify({"html":str(html)})
    