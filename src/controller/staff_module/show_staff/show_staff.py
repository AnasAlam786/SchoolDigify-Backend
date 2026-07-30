from collections import Counter

from flask import Blueprint, jsonify, session
from sqlalchemy import distinct, func

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model.ClassAccess import ClassAccess
from src.model.ClassData import ClassData
from src.model.Roles import Roles
from src.model.TeachersLogin import TeachersLogin

show_staff_bp = Blueprint("show_staff_bp", __name__)


@show_staff_bp.route("/api/get_all_staff", methods=["GET"])
@login_required
@permission_required("show_staff")
def get_staff():

    school_id = session["school_id"]

    teachers = (
        db.session.query(
            TeachersLogin,
            Roles.role_name.label("role_name"),
            func.array_remove(
                func.array_agg(distinct(ClassData.CLASS)), None
            ).label("accessible_classes"),
            func.count(distinct(ClassData.id)).label("total_accessible_classes"),
        )
        .join(Roles, TeachersLogin.role_id == Roles.id)
        .outerjoin(ClassAccess, TeachersLogin.id == ClassAccess.staff_id)
        .outerjoin(ClassData, ClassAccess.class_id == ClassData.id)
        .filter(TeachersLogin.school_id == school_id)
        .group_by(TeachersLogin.id, Roles.role_name)
        .order_by(TeachersLogin.role_id)
        .all()
    )

    total_classes = (
        db.session.query(func.count(ClassData.id))
        .filter(ClassData.school_id == school_id)
        .scalar()
    )

    role_names = [role for (_, role, _, _) in teachers]
    counts = Counter(role_names)

    admin_roles = {"Manager", "Principal", "Vice Principal", "Admin"}

    teachers_count = counts.get("Teacher", 0)
    administrator_count = sum(counts.get(r, 0) for r in admin_roles)
    helper_staff_count = len(teachers) - teachers_count - administrator_count

    staff = []

    for teacher, role_name, accessible_classes, total_accessible_classes in teachers:

        image = (
            f"https://lh3.googleusercontent.com/d/{teacher.image}=s100"
            if teacher.image
            else None
        )

        staff.append(
            {
                "id": teacher.id,
                "name": teacher.Name,
                "email": teacher.email,
                "gender": teacher.gender,
                "qualification": teacher.qualification,
                "status": teacher.status,
                "role": role_name,
                "image": image,
                "accessible_classes": accessible_classes or [],
                "total_accessible_classes": total_accessible_classes,
            }
        )

    return jsonify(
        {
            "summary": {
                "total_staff": len(staff),
                "teachers": teachers_count,
                "administrators": administrator_count,
                "support_staff": helper_staff_count,
                "total_classes": total_classes,
            },
            "staff": staff,
        }
    )