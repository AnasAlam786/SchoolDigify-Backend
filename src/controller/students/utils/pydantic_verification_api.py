# src/controller/students/add_student/pydantic_verification_api.py

from flask import request, jsonify, Blueprint
from pydantic import ValidationError

from src.controller.students.utils.admission_form_schema import AdmissionFormModel
from src.model.ClassData import ClassData
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required


pydantic_verification_api_bp = Blueprint('pydantic_verification_bp', __name__)


def format_pydantic_errors(e: ValidationError):
    errors = {}

    for error in e.errors():
        field = error["loc"][0]
        error_type = error["type"]

        if error_type == "string_pattern_mismatch":
            if "NAME" in field.upper():
                message = "Only letters and spaces are allowed."
            else:
                message = f"Invalid format for {field}."

        elif error_type == "greater_than":
            message = f"{field} must be greater than {error['ctx']['gt']}."

        elif error_type == "greater_than_equal":
            message = f"{field} must be at least {error['ctx']['ge']}."

        elif error_type == "value_error":
            message = f"Invalid value for {field}."

        elif "date" in error_type:
            message = "Date must be in DD-MM-YYYY format."

        else:
            message = error["msg"]

        errors[field] = message

    return errors

def Verification(data):
    try:
        model = AdmissionFormModel(**data)
        verified_data = model.model_dump(mode="json")

    except ValidationError as e:
        errors = format_pydantic_errors(e)

        return {"success":False, 'errors': errors}

    return {"success":True, 'verified_data': verified_data}

@pydantic_verification_api_bp.route('/api/pydantic_verification', methods=["POST"])
@login_required
@permission_required('admission')
def verify_admission():
    """Validate form data using Pydantic and perform basic business logic checks."""
    try:
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("JSON is not an object")
    except Exception:
        print("Error processing data")
        return jsonify({"errors": []}), 400

    result = Verification(data)

    if not result["success"]:
        return jsonify({"errors": result["errors"]}), 400
    else:
         return jsonify({
            "message": "All validations passed.", 
            "verifiedData": result['verified_data']
        }), 200


