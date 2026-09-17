from datetime import datetime, timezone
import json
import logging

from flask import Blueprint, jsonify, request, session
from pydantic_core import ValidationError
from sqlalchemy import func

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.staff_module.utils import hash_password
from src.controller.staff_module.utils.class_permission_validator import (
    staff_specific_permission,
    validate_class,
    validate_permissions,
)
from src.controller.staff_module.utils.pydantic_verification import (
    StaffVerification,
)
from src.controller.utils.upload_image import (
    delete_image,
    upload_image,
)

from src.model import Schools, StaffPermissions
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.TeachersLogin import TeachersLogin


logger = logging.getLogger(__name__)
add_staff_api_bp = Blueprint( "add_staff_api_bp",  __name__,)

def make_str_to_list(raw_value):
    """

    Examples:
        '["1", "2"]' -> (["1", "2"], True)
        ''            -> ([], True)
        None          -> ([], True)
        'invalid'     -> ([], False)
        '{}'          -> ([], False)
    """

    if raw_value is None or raw_value == "":
        return [], True

    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return [], False

    if not isinstance(parsed, list):
        return [], False

    return parsed, True


def normalize_gender(value):
    if not isinstance(value, str):
        return None

    value = value.strip().title()
    if value in {"Male", "Female", "Other"}:
        return value

    return None


def resolve_role_id(role_id_raw, role_name_raw):

    if role_id_raw is not None:
        role_id_raw = str(role_id_raw).strip()

        if role_id_raw.isdigit():

            role_id = int(role_id_raw)
            role = Roles.query.filter_by( id=role_id ).first()

            if not role:
                return None, {
                    "error": { "role_id": "Invalid role" }
                }

            return role.id, None

    role_name = (role_name_raw or "").strip()

    if not role_name:
        return None, {
            "error": { "role_id": "Role name is required" }
        }

    role = Roles.query.filter(
        func.lower(Roles.role_name) == role_name.lower()
    ).first()

    if not role:
        return None, {
            "error": { "role_id": "Invalid role" }
        }

    return role.id, None


# =========================================================
# API
# =========================================================

@add_staff_api_bp.route( "/api/add_staff", methods=["POST"] )
@login_required
@permission_required("add_staff")
def add_staff():

    data = request.form
    school_id = session.get("school_id")
    uploaded_image_id = None

    if not school_id:
        return jsonify({ "error": "School ID is required"}), 400

    # =====================================================
    # 2. FIND SCHOOL
    # =====================================================

    try:

        school = Schools.query.filter_by( id=school_id ).first()

    except Exception:
        logger.exception(
            "Database error while finding school. school_id=%s", school_id
        )

        db.session.rollback()

        return jsonify({
            "error": (
                "Error occurred while adding staff! Please contact support."
            )
        }), 500

    if not school:
        return jsonify({ "error": "School not found." }), 404

    # =====================================================
    # 3. RESOLVE ROLE
    # =====================================================

    try:

        role_id, role_error = resolve_role_id(
            data.get("role_id"), data.get("role_name")
        )

    except Exception:

        logger.exception(
            "Database error while resolving role. school_id=%s", school_id
        )

        db.session.rollback()

        return jsonify({
            "error": (
                "Error occurred while adding staff! " "Please contact support."
            )
        }), 500

    if role_error:
        return jsonify(role_error), 400

    # =====================================================
    # 4. PARSE ASSIGNED CLASSES
    # =====================================================

    assigned_classes, classes_valid = make_str_to_list(
        data.get("assigned_classes_id")
    )

    if not classes_valid:

        return jsonify({
            "error": {
                "assigned_classes_id": "Invalid class list"
            }
        }), 400

    # =====================================================
    # 5. PARSE PERMISSIONS
    # =====================================================

    permission_ids, permissions_valid = make_str_to_list(
        data.get("assigned_permissions_id")
    )

    if not permissions_valid:

        return jsonify({
            "error": {
                "assigned_permissions_id": "Invalid permission list"
            }
        }), 400

    # =====================================================
    # 6. VALIDATE CLASSES
    # =====================================================

    try:

        class_validation_message, is_valid = validate_class(
            assigned_classes, school_id
        )

    except Exception:

        logger.exception(
            "Error while validating classes. school_id=%s",
            school_id
        )

        db.session.rollback()

        return jsonify({
            "error": (
                "Error occurred while adding staff! "
                "Please contact support."
            )
        }), 500

    if not is_valid:

        return jsonify({
            "error": {
                "assigned_classes_id": class_validation_message
            }
        }), 400

    # =====================================================
    # 7. VALIDATE PERMISSIONS
    # =====================================================

    try:

        permission_validation_message, is_valid = validate_permissions(
            permission_ids
        )

    except Exception:

        logger.exception(
            "Error while validating permissions. school_id=%s", school_id
        )

        db.session.rollback()

        return jsonify({
            "error": (
                "Error occurred while adding staff! "
                "Please contact support."
            )
        }), 500

    if not is_valid:

        return jsonify({
            "error": {
                "assigned_permissions_id": permission_validation_message
            }
        }), 400

    # =====================================================
    # 8. PYDANTIC VALIDATION
    # =====================================================

    gender = normalize_gender( data.get("gender") )

    try:

        model = StaffVerification(
            name=data.get("name"),
            email=data.get("email"),
            phone=data.get("phone") or None,
            dob=data.get("dob") or None,
            gender=gender,
            address=data.get("address") or None,
            username=data.get("username"),
            password=data.get("password"),
            date_of_joining=data.get("date_of_joining") or None,
            qualification=data.get("qualification") or None,
            salary=data.get("salary") or None,
            role_id=role_id,
            image=data.get("image") or None,
            sign=data.get("sign") or None,
            national_id=data.get("national_id") or None,
        )

    except ValidationError as e:

        errors = {}

        for err in e.errors():

            field = (
                str(err["loc"][-1]) if err["loc"] else "general"
            )

            clean_msg = err["msg"].replace(
                "Value error, ", ""
            )

            errors[field] = clean_msg

        return jsonify({
            "success": False,
            "errors": errors
        }), 400

    # =====================================================
    # 9. EMAIL UNIQUENESS
    # =====================================================

    if model.email:

        try:

            existing_staff = TeachersLogin.query.filter(
                TeachersLogin.email == str(model.email)
            ).first()

        except Exception:

            logger.exception(
                "Database error during email uniqueness check. school_id=%s", school_id
            )

            db.session.rollback()
            return jsonify({
                "error": (
                    "Error occurred while adding staff! Please contact support."
                )
            }), 500

        if existing_staff:

            return jsonify({
                "error": {
                    "email": ( f"Email ({model.email}) already exists" )
                }
            }), 400


    # =====================================================
    # 11. RESOLVE STAFF-SPECIFIC PERMISSIONS
    # =====================================================

    try:

        staff_specific_permissions = (
            staff_specific_permission(
                permission_ids,
                role_id
            )
        )

    except Exception:

        logger.exception(
            "Error while resolving staff-specific permissions. "
            "school_id=%s role_id=%s", school_id, role_id
        )

        db.session.rollback()

        return jsonify({
            "error": (
                "Error occurred while adding staff! Please contact support."
            )
        }), 500

    # =====================================================
    # 12. UPLOAD IMAGE
    # =====================================================
    image = request.files.get("image")

    if image:

        try:

            uploaded_image_id = upload_image(
                image, model.username, school.students_image_folder_id
            )

            if not uploaded_image_id:
                raise RuntimeError( "Image upload failed" )

        except Exception:

            logger.exception(
                f"Image upload failed while adding staff. school_id={school_id} username={model.username}"
            )

            if uploaded_image_id:
                try:
                    delete_image( uploaded_image_id )
                except Exception:

                    logger.exception(
                        "Failed to cleanup uploaded image after upload failure."
                        f"school_id={school_id} image_id={uploaded_image_id}"
                    )

            db.session.rollback()

            return jsonify({
                "error": (
                    "Error occurred while adding staff! "
                    "Please contact support."
                )
            }), 500

    # =====================================================
    # 13. DATABASE TRANSACTION
    # =====================================================

    try:

        today = datetime.now( timezone.utc ).date()

        # -------------------------------------------------
        # CREATE STAFF
        # -------------------------------------------------

        teacher = TeachersLogin(
            Name=model.name,

            email=(
                str(model.email) if model.email else None
            ),

            Password=(
                hash_password.encrypt_password(
                    model.password
                ) 
                if model.password else None
            ),

            IP=None,
            User=model.username,
            status="active",
            school_id=school_id,
            role_id=model.role_id,
            qualification=model.qualification,
            dob=model.dob,
            phone=( int(model.phone) if model.phone else None ),
            date_of_joining=model.date_of_joining,
            address=model.address,
            gender=model.gender,
            national_id=model.national_id,
            image=uploaded_image_id,
        )

        db.session.add(teacher)
        db.session.flush()

        # -------------------------------------------------
        # CLASS ACCESS
        # -------------------------------------------------

        for class_id in assigned_classes:

            db.session.add(
                ClassAccess(
                    class_id=int(class_id),
                    staff_id=teacher.id,
                    granted_at=today
                )
            )

        # -------------------------------------------------
        # STAFF PERMISSIONS
        # -------------------------------------------------

        for permission in staff_specific_permissions:

            db.session.add(
                StaffPermissions(
                    permission_id=(
                        permission["permission_id"]
                    ),

                    staff_id=teacher.id,

                    is_granted=(
                        permission["isgranted"]
                    ),

                    created_at=today
                )
            )

        db.session.commit()

    except Exception:

        logger.exception(
            "Database transaction failed while adding staff. "
            "school_id=%s username=%s",
            school_id,
            model.username
        )

        db.session.rollback()

        if uploaded_image_id:
            try:
                delete_image(uploaded_image_id)
            except Exception:
                logger.exception(
                    "CRITICAL: Failed to cleanup uploaded "
                    "image after database rollback. "
                    "school_id=%s image_id=%s",
                    school_id,
                    uploaded_image_id
                )

        return jsonify({
            "error": (
                "Error occurred while adding staff! "
                "Please contact support."
            )
        }), 500


    return jsonify({
        "message": "Staff added successfully",
        "id": teacher.id
    }), 201