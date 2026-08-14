# src/controller/staff_module/update_staff.py

from flask import session, Blueprint, request, jsonify


from src.model import ClassData, Permissions, RolePermissions, StaffPermissions
from src.model.ClassAccess import ClassAccess
from src.model.TeachersLogin import TeachersLogin
from src.model.Roles import Roles

from src.controller.staff_module.utils.icons import permission_icons, ROLE_ICONS
from src.controller.staff_module.utils import hash_password

from src import db
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required


update_staff_bp = Blueprint( 'update_staff_bp',   __name__)


@update_staff_bp.route('/api/update_staff', methods=['GET'])
@permission_required('update_staff')
@login_required
def update_staff():
    # 1. Fetch & Validate staff_id parameter
    staff_id = request.args.get('id')
    
    if not staff_id:
        return jsonify({'error': 'Staff ID is required.'}), 400
        
    try:
        staff_id = int(staff_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid Staff ID format.'}), 400
    
    school_id = session.get('school_id')
    
    # 2. Query Staff Record
    staff = TeachersLogin.query.filter_by(id=staff_id, school_id=school_id).first()
    if not staff:
        return jsonify({'error': 'Staff member not found.'}), 404
    
    # 3. Query All Classes & Identify Assigned Classes
    class_rows = (
        db.session.query(
            ClassData.id.label("id"),
            ClassData.CLASS.label("class_name"),
            ClassAccess.id.label("access_id")
        )
        .outerjoin(
            ClassAccess, 
            (ClassAccess.class_id == ClassData.id) & (ClassAccess.staff_id == staff_id)
        )
        .filter(ClassData.school_id == school_id)
        .order_by(ClassData.display_order)
        .all()
    )

    all_classes = []
    assigned_classes_id = []

    for c in class_rows:
        cid_str = str(c.id)
        all_classes.append({
            "id": c.id,
            "class_name": c.class_name
        })
        if c.access_id:
            assigned_classes_id.append(cid_str)

    # 4. Query Permissions (Role-based + Staff-specific overrides)
    permissions_query = (
        db.session.query(
            Permissions.id,
            Permissions.permission_name,
            Permissions.title,
            Permissions.description,
            Permissions.action,
            RolePermissions.id.label("role_permission_id")
        )
        .outerjoin(
            RolePermissions,
            (RolePermissions.permission_id == Permissions.id) &
            (RolePermissions.role_id == staff.role_id)
        )
        .filter(Permissions.assignable.is_(True))
        .all()
    )

    staff_overrides = StaffPermissions.query.filter_by(staff_id=staff_id).all()
    override_map = {p.permission_id: p.is_granted for p in staff_overrides}

    all_permissions = []
    assigned_permissions_id = []

    for perm in permissions_query:

        role_has_permission = perm.role_permission_id is not None
        staff_override = override_map.get(perm.id)

        # Explicit override takes precedence over role default
        is_granted = staff_override if staff_override is not None else role_has_permission

        perm_id_str = str(perm.id)
        if is_granted:
            assigned_permissions_id.append(perm_id_str)

        all_permissions.append({
            "id": perm.id,
            "title": perm.title,
            "description": perm.description,
            "action": perm.action,
            "icon": permission_icons.get(perm.permission_name, "fa-cog"),
            "is_inherited_from_role": role_has_permission
        })



    # 5. Query Assignable Roles
    roles_query = (
        db.session.query(
            Roles.id,
            Roles.role_name
        )
        .filter(Roles.assignable.is_(True))
        .order_by(Roles.display_order.asc())
        .all()
    )

    all_roles = [
        {
            "id": r.id, 
            "role_name": r.role_name,
            "icon": ROLE_ICONS.get(r.role_name, {}).get("icon", "fa-solid fa-user"),
            "color": ROLE_ICONS.get(r.role_name, {}).get("color", "gray-500"),
        } 
        for r in roles_query
    ]

    # 6. Safely Decrypt Password
    try:
        decrypted_password = hash_password.decrypt_password(staff.Password) if staff.Password else ""
    except Exception:
        decrypted_password = ""

    # 7. Construct Form-Ready Staff Payload for React
    staff_data = {
        "id": staff.id,
        "name": getattr(staff, 'Name', '') or "",
        "email": getattr(staff, 'email', '') or "",
        "phone": getattr(staff, 'phone', '') or "",
        "dob": str(staff.dob) if getattr(staff, 'dob', None) else "",
        "gender": getattr(staff, 'gender', '') or "",
        "address": getattr(staff, 'address', '') or "",
        "username": getattr(staff, 'User', '') or "",
        "password": decrypted_password,
        "confirmPassword": decrypted_password,
        "date_of_joining": str(staff.date_of_joining) if getattr(staff, 'date_of_joining', None) else "",
        "qualification": getattr(staff, 'qualification', '') or "",
        "salary": str(staff.Salary) if getattr(staff, 'salary', None) else "",
        "national_id": getattr(staff, 'national_id', '') or "",
        "role_id": str(staff.role_id) if staff.role_id else "",
        "assigned_classes_id": assigned_classes_id,
        "assigned_permissions_id": assigned_permissions_id,
        "imageFile": getattr(staff, 'image', '') or "",
    }

    # 8. Return JSON Response
    return jsonify({
        "staff": staff_data,
        "roles": all_roles,
        "permissions": all_permissions,
        "classes": all_classes
    }), 200
