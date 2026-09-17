from datetime import datetime, timezone
import json
import logging

from flask import Blueprint, jsonify, request, session
from pydantic_core import ValidationError
from sqlalchemy import func

from src import db, r
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.staff_module.utils import hash_password
from src.controller.staff_module.utils.class_permission_validator import (
    staff_specific_permission,
    validate_class,
    validate_permissions,
)
from src.controller.staff_module.utils.pydantic_verification import StaffVerification
from src.controller.utils.upload_image import (
    delete_image,
    move_image,
    upload_image,
)

from src.model import Schools, StaffPermissions
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.TeachersLogin import TeachersLogin


# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)


# =========================================================
# BLUEPRINT
# =========================================================

update_staff_api_bp = Blueprint(
    "update_staff_api_bp",
    __name__,
)


DELETED_FOLDER = "1e8iHskcj2Vtv_Mg_Mtp4BzdHocuhLd_f"


# =========================================================
# HELPERS
# =========================================================

def make_str_to_list(raw_value):
    """
    Convert a JSON-encoded list from FormData into a Python list.

    Returns:
        tuple[list, bool]
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
    """
    Normalize gender to values accepted by StaffVerification.
    """

    if not isinstance(value, str):
        return None

    value = value.strip().title()

    if value in {"Male", "Female", "Other"}:
        return value

    return None


def resolve_role_id(role_id_raw, role_name_raw):
    """
    Resolve role ID from either role_id or role_name.

    Returns:
        tuple[int | None, dict | None]
    """

    if role_id_raw is not None:

        role_id_raw = str(role_id_raw).strip()

        if role_id_raw.isdigit():

            role_id = int(role_id_raw)

            role = Roles.query.filter_by(
                id=role_id
            ).first()

            if not role:
                return None, {
                    "error": {
                        "role_id": "Invalid role"
                    }
                }

            return role.id, None

    role_name = (role_name_raw or "").strip()

    if not role_name:
        return None, {
            "error": {
                "role_id": "Role name is required"
            }
        }

    role = Roles.query.filter(
        func.lower(Roles.role_name) == role_name.lower()
    ).first()

    if not role:
        return None, {
            "error": {
                "role_id": "Invalid role"
            }
        }

    return role.id, None


# =========================================================
# API
# =========================================================

@update_staff_api_bp.route(
    "/api/update_staff_api",
    methods=["POST"]
)
@login_required
@permission_required("update_staff")
def update_staff_api():

    data = request.form
    school_id = session.get("school_id")

    uploaded_new_image_id = None

    # =====================================================
    # 1. VALIDATE STAFF ID
    # =====================================================

    staff_id_raw = data.get("staff_id")

    if not staff_id_raw:
        return jsonify({
            "error": "Staff ID is required"
        }), 400

    try:
        staff_id = int(staff_id_raw)

    except (ValueError, TypeError):

        return jsonify({
            "error": "Invalid Staff ID"
        }), 400

    # =====================================================
    # 2. FIND STAFF
    # =====================================================

    try:

        staff = TeachersLogin.query.filter_by(
            id=staff_id,
            school_id=school_id
        ).first()

    except Exception:

        logger.exception(
            "Database error while finding staff. staff_id=%s",
            staff_id
        )

        db.session.rollback()

        return jsonify({
            "error": "Error occurred while updating staff! Please contact support."
        }), 500

    if not staff:
        return jsonify({
            "error": "Staff not found"
        }), 404

    if staff.status == "deleted":
        return jsonify({
            "error": "Cannot update deleted staff!"
        }), 400

    # =====================================================
    # 3. VALIDATE SCHOOL
    # =====================================================

    try:

        school = Schools.query.filter_by(
            id=school_id
        ).first()

    except Exception:

        logger.exception(
            "Database error while finding school. school_id=%s",
            school_id
        )

        db.session.rollback()

        return jsonify({
            "error": "Error occurred while updating staff! Please contact support."
        }), 500

    if not school:
        return jsonify({
            "error": "School not found."
        }), 404

    # =====================================================
    # 4. RESOLVE ROLE
    # =====================================================

    try:

        role_id, role_error = resolve_role_id(
            data.get("role_id"),
            data.get("role_name")
        )

    except Exception:

        logger.exception(
            "Database error while resolving role. staff_id=%s",
            staff_id
        )

        db.session.rollback()

        return jsonify({
            "error": "Error occurred while updating staff! Please contact support."
        }), 500

    if role_error:
        return jsonify(role_error), 400

    # =====================================================
    # 5. PARSE ASSIGNED CLASSES
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
    # 6. PARSE PERMISSIONS
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
    
    try:

        class_validation_message, is_valid = validate_class(
            assigned_classes,school_id
        )

    except Exception:

        logger.exception(
            "Error while validating classes. staff_id=%s",staff_id
        )

        db.session.rollback()

        return jsonify({
            "error": "Error occurred while updating staff! Please contact support."
        }), 500

    if not is_valid:
        return jsonify({
            "error": {
                "assigned_classes_id": class_validation_message
            }
        }), 400

    # 8. VALIDATE PERMISSIONS
    try:
        permission_validation_message, is_valid = validate_permissions(
            permission_ids
        )

    except Exception:

        logger.exception(
            "Error while validating permissions. staff_id=%s", staff_id
        )

        db.session.rollback()

        return jsonify({
            "error": "Error occurred while updating staff! Please contact support."
        }), 500

    if not is_valid:
        return jsonify({
            "error": {
                "assigned_permissions_id": permission_validation_message
            }
        }), 400

    # 9. PYDANTIC VALIDATION
    gender = normalize_gender(data.get("gender"))
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
                str(err["loc"][-1])
                if err["loc"] else "general"
            )

            clean_msg = err["msg"].replace(
                "Value error, ", ""
            )

            errors[field] = clean_msg

        return jsonify({
            "success": False, "errors": errors
        }), 400


    if model.email and str(model.email) != str(staff.email):
        try:
            existing_staff = TeachersLogin.query.filter(
                TeachersLogin.email == str(model.email),
                TeachersLogin.id != staff_id
            ).first()

        except Exception:
            logger.exception(
                "Database error during email uniqueness check. staff_id=%s",
                staff_id
            )
            db.session.rollback()

            return jsonify({
                "error": "Error occurred while updating staff! Please contact support."
            }), 500

        if existing_staff:

            return jsonify({
                "error": {
                    "email": f"Email ({model.email}) already exists"
                }
            }), 400

    # 11. IMAGE VALIDATION

    image_status = data.get("image_status","unchanged")
    image = request.files.get("image")

    if image_status not in {"unchanged","changed","removed"}:
        return jsonify({
            "error": {"image_status": "Invalid image status"}
        }), 400

    if image_status == "changed" and not image:

        return jsonify({
            "error": {"image": "Image file is required"}
        }), 400


    old_image_id = staff.image
    old_permission_number = (staff.permission_number or 0)
    new_permission_number = (old_permission_number + 1)

    if image_status == "changed":
        try:
            uploaded_new_image_id = upload_image(
                image, model.username, school.students_image_folder_id
            )

            if not uploaded_new_image_id:
                raise RuntimeError("Image upload failed")

        except Exception:
            logger.exception(
                "Image upload failed. staff_id=%s",staff_id
            )

            if uploaded_new_image_id:
                try:
                    delete_image(uploaded_new_image_id)
                except Exception:
                    logger.exception(
                        "Failed to cleanup uploaded image after upload failure. "
                        "staff_id=%s image_id=%s",
                        staff_id, uploaded_new_image_id
                    )

            db.session.rollback()

            return jsonify({
                "error": "Error occurred while updating staff! Please contact support."
            }), 500

    try:
        staff.Name = model.name

        staff.email = (
            str(model.email)
            if model.email else None
        )

        staff.phone = (
            int(model.phone)
            if model.phone else None
        )

        staff.dob = model.dob
        staff.gender = model.gender
        staff.address = model.address
        staff.User = model.username
        staff.date_of_joining = (model.date_of_joining)
        staff.qualification = (model.qualification)
        staff.salary = model.salary
        staff.national_id = (model.national_id)
        staff.role_id = model.role_id

        if image_status == "changed":

            staff.image = (
                uploaded_new_image_id
            )

        elif image_status == "removed":

            staff.image = None

        else:

            # unchanged
            staff.image = old_image_id


        staff.permission_number = (
            new_permission_number
        )

        if model.password:
            staff.Password = (
                hash_password.encrypt_password(
                    model.password
                )
            )

        # DELETE OLD CLASS ACCESS
        ClassAccess.query.filter_by(
            staff_id=staff.id
        ).delete(
            synchronize_session=False
        )

        # DELETE OLD STAFF PERMISSIONS
        StaffPermissions.query.filter_by(
            staff_id=staff.id
        ).delete(
            synchronize_session=False
        )


        now = datetime.now( timezone.utc ).date()

        # ADD CLASS ACCESS
        for class_id in assigned_classes:

            db.session.add(
                ClassAccess(
                    class_id=int(class_id),
                    staff_id=staff.id,
                    granted_at=now
                )
            )

        # RESOLVE STAFF-SPECIFIC PERMISSIONS
        staff_specific_permissions = (
            staff_specific_permission(
                permission_ids,
                role_id
            )
        )

        # ADD PERMISSIONS
        for permission in staff_specific_permissions:
            db.session.add(
                StaffPermissions(
                    permission_id=permission["permission_id"],
                    staff_id=staff.id,
                    is_granted=permission["isgranted"],
                    created_at=now
                )
            )

        db.session.flush()
        db.session.commit()

    except Exception:
        logger.exception(
            "Database transaction failed while updating staff. "
            "staff_id=%s", staff_id
        )

        db.session.rollback()
        if uploaded_new_image_id:
            try:
                delete_image(uploaded_new_image_id)
            except Exception:
                logger.exception(
                    "CRITICAL: Failed to cleanup new image "
                    "after database rollback. "
                    "staff_id=%s image_id=%s",
                    staff_id, uploaded_new_image_id
                )

        return jsonify({
            "error": "Error occurred while updating staff! Please contact support."
        }), 500


    if (
        image_status == "changed" and old_image_id
        and old_image_id != uploaded_new_image_id
    ):
        try:
            move_image(
                old_image_id, DELETED_FOLDER, rename=f"staff_{str(staff.id)}"
            )

        except Exception:
            logger.exception(
                "Failed to move old staff image after successful "
                "database update. staff_id=%s old_image_id=%s",
                staff_id, old_image_id
            )

    elif (image_status == "removed" and old_image_id):
        try:
            move_image(
                old_image_id, DELETED_FOLDER,
                rename=f"staff_{str(staff.id)}"
            )

        except Exception:
            logger.exception(
                "Failed to move removed staff image after successful "
                "database update. staff_id=%s old_image_id=%s",
                staff_id, old_image_id
            )

    try:
        permission_no = r.get( staff.id )
        if permission_no is not None:
            r.set(staff.id, int(permission_no) + 1)

    except Exception:
        logger.exception(
            "Redis update failed after successful staff update. "
            "staff_id=%s",staff_id
        )

    return jsonify({
        "message": "Staff updated successfully"
    }), 200