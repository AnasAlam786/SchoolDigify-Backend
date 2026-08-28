# src/controller/fees/get_fee_api.py

from flask import session, request, jsonify, Blueprint

from src.controller.fees.handle_no_fee_session import get_fee_structure
from src.controller.fees.utils.fetch_fee_data import fetch_fee_data
from src.controller.permissions.permission_required import permission_required
from src.model import (StudentsDB, StudentSessions)
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

get_fee_api_bp = Blueprint( 'get_fee_api_bp',   __name__)


@get_fee_api_bp.route('/api/get_student_fee_data', methods=["GET"])
@login_required
@permission_required('view_fee_data')
def get_fee_api():

    phone = request.args.get("phone")
    student_session_id = request.args.get("student_session_id")

    if not student_session_id:
        return jsonify({"message": "student_session_id is required"}), 400
    if not phone:
        phone = (
            db.session.query(StudentsDB.PHONE)
                .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
                .filter(StudentSessions.id == student_session_id)
                .scalar()
        )

    current_session = session["session_id"]
    school_id = session["school_id"]
    try:
        isSuccess, result = fetch_fee_data(
            session_id=current_session,
            school_id=school_id,
            phone=phone,
            selected_student_session_id=student_session_id
        )
    except Exception as e:
        print(e)
        return jsonify({
            "error": "Unable to fetch fee of this student!"
        }), 500

    if isSuccess:
        return jsonify({
            "students_fee_data": result
        }), 200

    elif result.get("NO_FEE_SESSION_DATA"):
        try:
            fee_structure = get_fee_structure(school_id)
        except Exception as e:
            print(e)
            return jsonify({
                "error": "Unable to get fee structure of your school!"
            }), 500

        return jsonify({
            "NO_FEE_SESSION_DATA": True,
            "error": "First you have to add the fee details of this session before paying the fee!",
            "fee_structure": fee_structure
        }), 400