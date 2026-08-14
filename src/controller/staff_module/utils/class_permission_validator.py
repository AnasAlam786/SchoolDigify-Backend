from flask import jsonify, session
from src.model import Permissions
from src.model.ClassData import ClassData
from src import db
from src.model.RolePermissions import RolePermissions

def validate_class(class_ids, school_id):

    if not class_ids:
        return "No classes provided", True 
    if not isinstance(class_ids, list):
        return "Invalid input type. Expected a list in assigned classes.", False
    
    # validate each class_id
    assignable_classes =( 
        ClassData.query.with_entities(ClassData.id)
        .filter_by(school_id=school_id).all()
    )
    valid_class_ids = { c.id for c in assignable_classes }

    for class_id in class_ids:
        try:
            class_id_int = int(class_id)
        except ValueError:
            return f'Invalid class_id: {class_id}. Please relode and try again', False

        if class_id_int not in valid_class_ids:
            return f'class_id {class_id_int} does not exist. Please relode and try again', False

    return "Classes validated successfully", True


def validate_permissions(permission_ids):
    if not isinstance(permission_ids, list):
        return "Invalid input type. Expected a list in permissions.", False
    if not permission_ids:
        return "No permissions provided", True

    assignable_permissions = Permissions.query.with_entities(Permissions.id).filter_by(assignable=True).all()
    valid_permission_ids = { c.id for c in assignable_permissions }


    for permission_id in permission_ids:
        try:
            permission_id_int = int(permission_id)
        except ValueError:
            return f'Invalid permission ids: {permission_id}. Please relode and try again', False

        if permission_id_int not in valid_permission_ids:
            perm = Permissions.query.with_entities(Permissions.title).filter_by(id=permission_id_int).first()
            if perm:
                msg = f'The permission "{perm.title}" is not assignable.'
            else: 
                msg = f'Permission ID {permission_id_int} does not exist.'

            return msg, False
        
    return "Permissions validated successfully", True

def staff_specific_permission(permission_ids, role_id):
    """
    This function compares a staff member's manually assigned permissions
    with the default permissions of their role and returns a list of
    permission changes (granted or revoked).

    The staff may have some custom permissions (added or removed).
    This function finds the difference between the two:
        ✅ If staff has something extra → mark it as isgranted=True.
        ❌ If role has something but staff doesn’t → mark it as isgranted=False.
    """

    try:
        permission_ids = [int(permission_id) for permission_id in permission_ids]
    except ValueError:
        return f'Invalid permission id. Please reload and try again.', False


    permissions = (
        db.session.query(Permissions.id)
        .join(RolePermissions, RolePermissions.permission_id == Permissions.id)
        .filter(
            RolePermissions.role_id == role_id,  # Match permissions for this role
            Permissions.assignable.is_(True)      # Only include assignable permissions
        )
        .all()
    )


    role_permission_ids = [p.id for p in permissions]
    staff_specific_ids = []

    # 4️⃣ Check for permissions that the staff has but the role does not
    # → These are **extra permissions** given to the staff individually
    for permission_id in permission_ids:

        if permission_id not in role_permission_ids:
            staff_specific_ids.append({
                "permission_id": permission_id,
                "isgranted": True  # Mark as granted individually
            })

    # 5️⃣ Check for permissions that the role has but the staff does not
    # → These are **permissions removed** from this specific staff
    for role_permission_id in role_permission_ids:
        if role_permission_id not in permission_ids:
            staff_specific_ids.append({
                "permission_id": role_permission_id,
                "isgranted": False  # Mark as revoked individually
            })
            
    return staff_specific_ids
