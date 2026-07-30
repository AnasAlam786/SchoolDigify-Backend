# src/controller/generate_tc_form_api.py

from flask import session, Blueprint, jsonify
from sqlalchemy import func

from src.model import StudentsDB
from src.model import StudentSessions
from src.model import TCRecords
from src import db


from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

next_tc_number_api_bp = Blueprint('next_tc_number_api_bp', __name__)


@next_tc_number_api_bp.route('/api/get-next-tc-number', methods=['POST'])
@login_required
@permission_required('tc')
def api_get_next_tc_number():
    school_id = session.get('school_id')

    highest_tc = ( 
        db.session.query(func.max(TCRecords.tc_no))
        .join(StudentSessions, TCRecords.student_session_id == StudentSessions.id)
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .filter(StudentsDB.school_id == school_id)
        .scalar() 
    )

    try:
        highest_tc = int(highest_tc) if highest_tc is not None else 0
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid TC number found in database"}), 500

    return jsonify({"next_tc_number": highest_tc + 1})