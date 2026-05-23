# src/controller/staff_module/add_staff.py

from datetime import datetime, timezone
from flask import jsonify, session, Blueprint, request
from pydantic import ValidationError
from sqlalchemy import func
from psycopg2.errors import UniqueViolation

from src.model.StaffPermissions import StaffPermissions
from src.model.TeachersLogin import TeachersLogin
from src.model.Roles import Roles
from src.model.ClassAccess import ClassAccess

from src.controller.staff_module.utils import hash_password
from src.controller.staff_module.utils.pydantic_verification import StaffVerification
from src.controller.staff_module.utils.class_permission_validator import (validate_class, 
                                                                          validate_permissions,
                                                                          staff_specific_permission)

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

add_staff_api_bp = Blueprint( 'add_staff_api_bp',   __name__)

@add_staff_api_bp.route('/api/add_staff', methods=['POST'])
@login_required
@permission_required('add_staff')
def add_staff():

    data = request.get_json(silent=True) or (request.form.to_dict() if request.form else {})
    school_id = session.get('school_id')
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
                return jsonify({'message': 'Invalid role'}), 400
        else:
            return jsonify({'message': 'Role name is required'}), 400


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
        errors = []
        for err in e.errors():
            field = err["loc"][0]
            msg = err["msg"]
            # Make error messages user-friendly
            errors.append(f"{field.capitalize()}: {msg}")
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Email unique check
    if model.email and TeachersLogin.query.filter_by(email=str(model.email)).first():
        return jsonify({'message': f'Email ({model.email}) already exists'}), 400

    # Build DB entity
    try:
        # Class and Permissions Validation
        assigned_classes = data.get("assigned_classes") or []
        permission_ids = data.get('permissions') or []

        class_validation_message, is_valid = validate_class(assigned_classes, school_id)
        if not is_valid:
            db.session.rollback()
            return jsonify({'message': class_validation_message}), 400
        
        permission_validation_message, is_valid = validate_permissions(permission_ids)
        if not is_valid:
            db.session.rollback()
            return jsonify({'message': permission_validation_message}), 400
        
        staff_specific_permissions = staff_specific_permission(permission_ids, role_id)
        
        # Adding rows to database
        teacher = TeachersLogin(
            Name=model.name, email=str(model.email) if model.email else None,
            Password=hash_password.encrypt_password(model.password), IP=None,
            User=model.username, status='active',
            school_id=session.get('school_id'), role_id=model.role_id,
            # image=model.image, Sign=model.sign,
            qualification=model.qualification,
            dob=model.dob, phone=int(model.phone) if model.phone else None,
            date_of_joining=model.date_of_joining, address=model.address,
            gender=model.gender, national_id=model.national_id,
        )    

        db.session.add(teacher)
        db.session.flush()  # 👈 flush so teacher.id is available before commit
        
        for class_id in assigned_classes:
            db.session.add(ClassAccess(
                class_id=int(class_id),
                staff_id=teacher.id,
                granted_at=datetime.now(timezone.utc).date()
            ))

        for perms in staff_specific_permissions:
            db.session.add(StaffPermissions(
                permission_id=perms["permission_id"],
                staff_id=teacher.id,
                is_granted=perms["isgranted"],
                created_at=datetime.now(timezone.utc).date()
            ))
        
       
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(e)
        if isinstance(e.orig, UniqueViolation):
            return jsonify({'message': 'Cannot add staff: duplicate record detected. Please check the data and try again. Please change User id or email'}), 400
        else:
            return jsonify({'message': 'An unexpected database error occurred while adding staff.'}), 500

    return jsonify({'message': 'Staff added successfully', 'id': teacher.id}), 200