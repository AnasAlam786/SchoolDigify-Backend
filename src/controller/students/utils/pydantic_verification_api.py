# src/controller/students/add_student/pydantic_verification_api.py

from flask import request, jsonify, Blueprint
from pydantic import ValidationError

from src.controller.students.utils.admission_form_schema import AdmissionFormModel
from src.model.ClassData import ClassData
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required


pydantic_verification_api_bp = Blueprint('pydantic_verification_bp', __name__)


def format_pydantic_errors(validation_error: ValidationError) -> list[dict]:
    """Format Pydantic validation errors into user-friendly messages."""
    errors = []
    for error in validation_error.errors():
        field = error['loc'][0] if error['loc'] else 'unknown'
        msg = error['msg']
        # Customize messages for better UX
        if 'pattern' in msg.lower() and 'name' in field.lower():
            msg = "Name should contain only letters and spaces, no numbers or special characters."
        elif 'constr' in msg and 'pattern' in msg:
            if 'name' in field.lower():
                msg = "Name must be alphabetic with spaces only."
            else:
                msg = f"Invalid format for {field.replace('_', ' ').title()}."
        elif 'conint' in msg:
            if 'gt' in msg:
                msg = f"{field.replace('_', ' ').title()} must be greater than {error['ctx']['gt']}."
            elif 'ge' in msg:
                msg = f"{field.replace('_', ' ').title()} must be at least {error['ctx']['ge']}."
        elif 'EmailStr' in msg:
            msg = "Please enter a valid email address."
        elif 'date' in msg.lower():
            msg = f"{field.replace('_', ' ').title()} must be a valid date in DD-MM-YYYY format."
        else:
            msg = msg.replace('_', ' ').capitalize()
        errors.append({"field": field, "message": msg})
    return errors


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
    
    try:
        model = AdmissionFormModel(**data)
        verified_data = model.model_dump(mode="json")

    except ValidationError as e:
        errors = format_pydantic_errors(e)
        print(errors)
        return jsonify({"errors": errors}), 400
    
    return jsonify({"message": "All validations passed.", "verifiedData": verified_data}), 200