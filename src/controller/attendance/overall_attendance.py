# src/controller/attendance/overall_attendance.py

from flask import render_template, session, Blueprint

from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

overall_attendance_bp = Blueprint('overall_attendance_bp', __name__)

@overall_attendance_bp.route('/overall_attendance', methods=['GET'])
@login_required
@permission_required('attendance')  # Assuming same permission, or create new one
def overall_attendance_page():
    user_id = session["user_id"]

    classes_query = (
        db.session.query(ClassData)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .filter(ClassAccess.staff_id == user_id)
        .order_by(ClassData.id.asc())
    )

    classes = classes_query.all()

    return render_template('/attendance/overall_attendance.html', classes=classes)