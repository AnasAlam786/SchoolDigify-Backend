# src/controller/fees/get_fee_api.py

from flask import session, request, jsonify, Blueprint

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
        students_data = fetch_fee_data(session_id=current_session, school_id=school_id, phone=phone)
    except Exception as e:
        print(e)
        return jsonify({"message": e}), 400

    return jsonify({"students_fee_data": students_data})