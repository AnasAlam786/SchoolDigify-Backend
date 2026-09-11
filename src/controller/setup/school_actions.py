from flask import session, request, jsonify, Blueprint
from sqlalchemy.exc import IntegrityError

from src.model import Schools
from src import db

from src.controller.auth.login_required import login_required


school_data_api_bp = Blueprint(
    "school_data_api_bp",
    __name__
)


# ================================================================
# GET SCHOOL DATA
# ================================================================

@school_data_api_bp.route(
    "/api/school_data_api_bp",
    methods=["GET"]
)
@login_required
def get_school_data():

    try:
        school_id = session["school_id"]

        # ---------------------------------------------------------
        # 1. Get school data
        # ---------------------------------------------------------

        school = (
            db.session.query(
                Schools.id, Schools.School_Name,
                Schools.Address, Schools.Logo,
                Schools.UDISE, Schools.Phone,
                Schools.WhatsApp, Schools.Email,
                Schools.Manager, Schools.school_heading_image
            )
            .filter(
                Schools.id == school_id
            )
            .first()
        )

        if not school:
            return jsonify({
                "error": "School data was not found."
            }), 404

        # ---------------------------------------------------------
        # 2. Prepare response
        # ---------------------------------------------------------

        school_data = {
            "id": school.id,
            "school_name": school.School_Name,
            "address": school.Address,
            "logo": school.Logo,
            "udise": school.UDISE,
            "phone": school.Phone,
            "whatsapp": school.WhatsApp,
            "email": school.Email,
            "manager": school.Manager,
            "school_heading_image": school.school_heading_image
        }

        return jsonify({
            "school_data": school_data
        }), 200

    except Exception as e:
        print(e)
        db.session.rollback()

        return jsonify({
            "error": "Unable to load school setup data. Please try again later."
        }), 500


# ================================================================
# UPDATE SCHOOL DATA
# ================================================================

@school_data_api_bp.route(
    "/api/update_school_data",
    methods=["PUT"]
)
@login_required
def update_school_data():

    try:
        school_id = session["school_id"]

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "No school data was provided."
            }), 400

        # ---------------------------------------------------------
        # 1. Get school
        # ---------------------------------------------------------

        school = (
            db.session.query(Schools)
            .filter(
                Schools.id == school_id
            )
            .first()
        )

        if not school:
            return jsonify({
                "error": "School data was not found."
            }), 404

        # ---------------------------------------------------------
        # 2. Update school data
        # ---------------------------------------------------------

        if "school_name" in data:
            school.School_Name = data["school_name"]

        if "address" in data:
            school.Address = data["address"]

        if "logo" in data:
            school.Logo = data["logo"]

        if "udise" in data:
            school.UDISE = data["udise"]

        if "phone" in data:
            school.Phone = data["phone"]

        if "whatsapp" in data:
            school.WhatsApp = data["whatsapp"]

        if "email" in data:
            school.Email = data["email"]

        if "manager" in data:
            school.Manager = data["manager"]

        if "school_heading_image" in data:
            school.school_heading_image = data["school_heading_image"]

        # ---------------------------------------------------------
        # 3. Commit changes
        # ---------------------------------------------------------

        db.session.commit()

        return jsonify({
            "message": "School details updated successfully."
        }), 200

    except IntegrityError as e:
        db.session.rollback()

        print(e)

        return jsonify({
            "error": "Email or UDISE already exists for another school."
        }), 409

    except Exception as e:
        print(e)
        db.session.rollback()

        return jsonify({
            "error": "Unable to update school details. Please try again later."
        }), 500