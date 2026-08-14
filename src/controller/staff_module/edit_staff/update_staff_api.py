from datetime import datetime, timezone
import json
from flask import Blueprint, jsonify, request, session
from pydantic_core import ValidationError
from sqlalchemy import func

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.staff_module.utils import hash_password
from src.controller.staff_module.utils.class_permission_validator import staff_specific_permission, validate_class, validate_permissions
from src.controller.staff_module.utils.pydantic_verification import StaffVerification
from src.model import StaffPermissions
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.TeachersLogin import TeachersLogin
from src import db

from src import r

update_staff_api_bp = Blueprint( 'update_staff_api_bp',   __name__)

def make_str_to_list(raw_value):
    """Safely converts stringified JSON array from FormData into a Python list."""
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


@update_staff_api_bp.route('/api/update_staff_api', methods=['POST'])
@login_required
@permission_required('update_staff')
def update_staff_api():
    data = request.form
    school_id = session.get('school_id')

    staff_id = data.get('staff_id')

    if not staff_id:
        return jsonify({'error': 'Staff ID is required'}), 400

    try:
        staff_id = int(staff_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid Staff ID'}), 400

    # Get existing staff
    staff = TeachersLogin.query.filter_by(id=staff_id, school_id=school_id).first()
    if not staff:
        return jsonify({'message': 'Staff not found'}), 404

    # Normalize gender to match Pydantic Literal and DB Enum
    gender = data.get('gender')
    if isinstance(gender, str):
        gender_norm = gender.strip().title()  # male -> Male
        if gender_norm not in {"Male", "Female", "Other"}:
            gender_norm = None
    else:
        gender_norm = None

    # Resolve role_id: accept numeric id or map from role_name/value label
    role_id_raw = data.get('role_id')
    role_id = None
    if isinstance(role_id_raw, (int,)):
        role_id = role_id_raw
    elif isinstance(role_id_raw, str) and role_id_raw.isdigit():
        role_id = int(role_id_raw)
    else:
        # Try to map by role_name from payload label or value
        role_name = (data.get('role_name') or str(role_id_raw or '')).strip()
        if role_name:
            role = Roles.query.filter(func.lower(Roles.role_name) == role_name.lower()).first()
            if role:
                role_id = int(role.id)
            else:
                return jsonify({'error': {"role_id": 'Invalid role'}}), 400
        else:
            return jsonify({'error': {"role_id": 'Role name is required'}}), 400

    try:
        model = StaffVerification(**{
            'name': data.get('name'), 
            'email': data.get('email'),
            'phone': data.get('phone') or None,
            'dob': data.get('dob') or None,
            'gender': gender_norm,
            'address': data.get('address') or None,
            'username': data.get('username'),
            'password': data.get('password'),
            'date_of_joining': data.get('date_of_joining') or None,
            'qualification': data.get('qualification') or None,
            'salary': data.get('salary') or None,
            'role_id': role_id,
            'image': data.get('image') or None,
            'sign': data.get('sign') or None,
            'national_id': data.get('national_id') or None,
        })
    except ValidationError as e:
        errors = {}
        for err in e.errors():
            field = str(err["loc"][-1]) if err["loc"] else "general"
                        
            # Clean up Pydantic's default "Value error, " prefix if present
            clean_msg = err["msg"].replace("Value error, ", "")
            errors[field] = clean_msg
        return jsonify({'success': False, 'errors': errors}), 400

    # Email unique check (exclude current staff)
    if model.email and model.email != staff.email:
        existing_staff = TeachersLogin.query.filter_by(email=str(model.email)).first()
        if existing_staff and existing_staff.id != staff_id:
            return jsonify({'error': {'email': f'Email ({model.email}) already exists'}}), 400

    # Update staff data
    try:
        # Class and Permissions Validation
        assigned_classes = make_str_to_list(data.get("assigned_classes_id"))
        permission_ids = make_str_to_list(data.get('assigned_permissions_id'))
        
        
        class_validation_message, is_valid = validate_class(assigned_classes, school_id)
        if not is_valid:
            db.session.rollback()
            return jsonify({'error': {'assigned_classes_id':class_validation_message}}), 400
        
        permission_validation_message, is_valid = validate_permissions(permission_ids)
        if not is_valid:
            db.session.rollback()
            return jsonify({'error': {'assigned_permissions_id': permission_validation_message}}), 400
        

        staff.Name = model.name
        staff.email = str(model.email) if model.email else None
        staff.phone = int(model.phone) if model.phone else None
        staff.dob = model.dob if model.dob else None
        staff.gender = model.gender if model.gender else None
        staff.address = model.address if model.address else None
        staff.User = model.username if model.username else None
        staff.date_of_joining = model.date_of_joining if model.date_of_joining else None
        staff.qualification = model.qualification if model.qualification else None
        staff.salary = model.salary if model.salary else None
        staff.national_id = model.national_id if model.national_id else None
        staff.role_id = model.role_id if model.role_id else None
        # staff.image = model.image if model.image else None
        # staff.sign = model.sign if model.sign else None
        staff.permission_number = staff.permission_number + 1 if staff.permission_number is not None else 1
        if model.password:
            staff.Password = hash_password.encrypt_password(model.password)

        #delete the links with ClassAccess and StaffPermissions
        ClassAccess.query.filter_by(staff_id=staff.id).delete()
        StaffPermissions.query.filter_by(staff_id=staff.id).delete()
 

        for class_id in assigned_classes:
            db.session.add(ClassAccess(
                class_id=int(class_id),
                staff_id=staff.id,
                granted_at=datetime.now(timezone.utc).date()
            ))

        staff_specific_permissions = staff_specific_permission(permission_ids, role_id)
        for perms in staff_specific_permissions:
            db.session.add(StaffPermissions(
                permission_id=perms["permission_id"],
                staff_id=staff.id,
                is_granted=perms["isgranted"],
                created_at=datetime.now(timezone.utc).date()
            ))
        
        # updating permission no to reflect the permissions in client side instantly
        permission_no = r.get(staff.id)
        if permission_no:
            r.set(staff.id, int(permission_no) + 1)
            
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({'error': 'Error occurred while updating staff! Please contact support.', 'error': str(e)}), 500

    return jsonify({'message': 'Staff updated successfully'}), 200