# src/controller/marks/fill_marks.py

from flask import session, jsonify, Blueprint

from src.model import ClassData, ClassData,TeachersLogin
from src.model.ClassAccess import ClassAccess
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required


get_classes_bp = Blueprint( 'get_classes_bp',   __name__)

@get_classes_bp.route('/api/get_classes', methods=[ "GET"])
@login_required     # Only logged in users can access the fill marks page.
@permission_required('student_list')
def get_classes():

    user_id = session["user_id"]

    try:
        classes = (
            db.session.query(ClassData.id, ClassData.CLASS)
            .join(ClassAccess, ClassAccess.class_id == ClassData.id)
            .join(TeachersLogin, TeachersLogin.id == ClassAccess.staff_id)
            .filter(TeachersLogin.id == user_id)
            .order_by(ClassData.id.asc())
            .all()
        )

        if not classes:
            return jsonify({"error": "No Classes is assigned to you!"}), 400
        
        classes_data = [
            {
                "id": c.id,
                "class_name": c.CLASS
            }
            for c in classes
        ]
    except Exception as e:
        return jsonify({"error": f"Error: {e}"}), 400

    return jsonify({"classes": classes_data}), 200