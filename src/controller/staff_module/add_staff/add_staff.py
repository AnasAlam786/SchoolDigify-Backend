# src/controller/staff_module/add_staff.py

from flask import jsonify, session, Blueprint

from src.model import Permissions, RolePermissions
from src.model.Roles import Roles
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model.Roles import Roles

from src.controller.staff_module.utils.icons import permission_icons, ROLE_ICONS

add_staff_bp = Blueprint( 'add_staff_bp',   __name__)

@add_staff_bp.route('/api/add_staff', methods=['GET'])
@login_required
@permission_required('add_staff')
def add_staff():
    try:
        # Retrieve user ID safely from session or current_user
        user_id = session.get("user_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User session is invalid or missing."
            }), 401

        # Query assigned classes for the logged-in user
        classes = (
            db.session.query(ClassData)
            .join(ClassAccess, ClassAccess.class_id == ClassData.id)
            .filter(ClassAccess.staff_id == user_id)
            .order_by(ClassData.id.asc())
            .all()
        )

        # Query assignable roles
        roles = (
            db.session.query(Roles.id, Roles.role_name)
            .filter(Roles.assignable.is_(True))
            .order_by(getattr(Roles, "display_order", Roles.id).asc())
            .all()
        )

        # Query assignable permissions
        permissions = (
            db.session.query(
                Permissions.id,
                Permissions.title,
                Permissions.description,
                Permissions.action,
            )
            .filter(Permissions.assignable.is_(True))
            .all()
        )

        # Build clean JSON lists with safe fallback defaults
        roles_list = []
        for r in roles:
            icon_data = ROLE_ICONS.get(r.role_name) if isinstance(ROLE_ICONS, dict) else {}
            if not isinstance(icon_data, dict):
                icon_data = {}

            roles_list.append({
                "id": r.id,
                "role_name": r.role_name,
                "icon": icon_data.get("icon", "fa-solid fa-user"),
                "color": icon_data.get("color", "gray-500"),
            })

        classes_list = [
            {
                "id": getattr(c, "id", None),
                "class_name": getattr(c, "CLASS", getattr(c, "class_name", "N/A")),
            }
            for c in classes
        ]

        permissions_list = [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "action": p.action,
                "icon": (permission_icons.get(p.title, "fas fa-cog") 
                         if isinstance(permission_icons, dict) else "fas fa-cog"),
            }
            for p in permissions
        ]

        return jsonify({
            "roles": roles_list,
            "classes": classes_list,
            "permissions": permissions_list,
        }), 200

    except Exception as e:
        # Roll back session in case DB query was mid-transaction
        db.session.rollback()
        print(f"Error fetching add_staff setup data: {str(e)}", exc_info=True)
        
        return jsonify({
            "error": "Failed to load staff setup data due to a server error."
        }), 500