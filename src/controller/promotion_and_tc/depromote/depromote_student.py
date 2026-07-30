# src/controller/final_depromotion_api.py

from flask import request, jsonify, Blueprint, session

from src import db
from src.model import StudentSessions

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

depromote_student_api_bp = Blueprint('depromote_student_api_bp', __name__)

@depromote_student_api_bp.route('/api/depromote-student', methods=["POST"])
@login_required
@permission_required('promote_student')
def depromote_student():
    """
    Depromote a student by:
    1. Restoring the previous session row to 'active'.
    2. Deleting the promoted row for the current session.
    """

    data = request.json
    session_id = int(session.get("session_id"))

    # Validate input
    promoted_student_id = data.get("promoted_student_id")
    if not promoted_student_id:
        return jsonify({"error": "Missing required parameter student_session_id."}), 400

    try:
        promoted_student_id = int(promoted_student_id)
    except Exception:
        return jsonify({"message": "Invalid student_session_id format."}), 400

    try:
        # Fetch the promoted row (must exist in current session)
        promoted_row = db.session.query(StudentSessions).filter_by(
            id=promoted_student_id,
            session_id=session_id
        ).first()

        if not promoted_row:
            return jsonify({"message": "Promoted session not found in this session."}), 404

        # Determine previous session ID
        previous_session_id = session_id - 1
        if previous_session_id < 1:
            return jsonify({"message": "Invalid previous session. Cannot depromote."}), 400

        # Fetch old row from previous session
        old_row = db.session.query(StudentSessions).filter_by(
            student_id=promoted_row.student_id,
            session_id=previous_session_id
        ).first()

        if not old_row:
            return jsonify({
                "message": "Previous session record not found. Cannot depromote cleanly."
            }), 500

        if old_row.status != "promoted":
            return jsonify({"message": "This row is not promoted. cannot depromote."}), 400

        # Restore old row
        old_row.status = "active"

        # Delete the promoted row
        db.session.delete(promoted_row)

        # Commit
        db.session.commit()

        return jsonify({
            "message": "Student successfully depromoted",
            "state": "NOT_PROMOTED_NOT_TC",
            "restored_student_id": old_row.id
        }), 200

    except Exception as e:
        db.session.rollback()
        print("Error in depromote_student:", e)
        return jsonify({
            "message": "An unexpected error occurred while depromoting the student."
        }), 500
