from flask import session, request, jsonify, Blueprint

from src import db
from src.model import StudentSessions
from src.model import TCRecords

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

revert_tc_api_bp = Blueprint('revert_tc_api_bp', __name__)


@revert_tc_api_bp.route('/api/tc/revert', methods=['POST'])
@login_required
@permission_required('tc')
def revert_tc():
    """
    Undo TC: clear tc fields and revert the student back to NOT_PROMOTED_NOT_TC.
    """
    payload = request.get_json() or {}
    student_session_id = payload.get("student_session_id")

    if not student_session_id:
        return jsonify({"message": "Student session ID is required."}), 400

    try:
        student_session_id = int(student_session_id)
    except (TypeError, ValueError):
        return jsonify({"message": "Session information is invalid. Please login again."}), 400

    student_session = StudentSessions.query.filter_by(
        id=student_session_id,
    ).first()

    if not student_session or student_session.status != "tc":
        return jsonify({"message": "No TC record found to cancel."}), 404

    tc_record = TCRecords.query.filter_by(student_session_id=student_session_id, status='issued').order_by(TCRecords.id.desc()).first()
    if not tc_record:
        return jsonify({"message": "No issued TC record found to cancel."}), 404

    student_session.status = "active"
    student_session.tc_number = None
    student_session.tc_date = None
    student_session.left_reason = None
    tc_record.status = "cancelled"

    db.session.commit()

    # Return cancelled TC details so frontend can show cancelled TC info immediately
    cancelled_tc_no = None
    try:
        cancelled_tc_no = int(tc_record.tc_no) if tc_record and tc_record.tc_no is not None else None
    except Exception:
        cancelled_tc_no = tc_record.tc_no if tc_record else None

    return jsonify({
        "message": "TC cancelled successfully.",
        "state": "CANCELLED_TC",
        "cancelled_tc_number": cancelled_tc_no,
    }), 200


