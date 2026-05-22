# src/controller/final_promotion_api.py

from flask import current_app, session, request, jsonify, Blueprint
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from src import db
from src.model import StudentSessions
from src.model import ClassData

import datetime
from src.controller.utils.get_gapped_rolls import get_gapped_rolls
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

promote_student_api_bp = Blueprint('promote_student_api_bp', __name__)

@promote_student_api_bp.route('/api/promote/student', methods=["POST"])
@login_required
@permission_required('promote_student')
def promote_student():
    """
    Promote a student into the current session while enforcing a simple state
    machine:

    NOT_PROMOTED_NOT_TC -> promote -> PROMOTED
"state": "PROMOTED"
    - Blocks promotion if TC is already issued.
    - Blocks duplicate promotions.
    - Validates roll uniqueness.
    - Returns the new state payload for instant UI updates.
    """
    try:
        school_id = session.get("school_id")
        current_session = int(session["session_id"])
    except (KeyError, ValueError):
        return jsonify({"message": "Session data is missing or corrupted. Please logout and login again!"}), 500


    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing JSON payload"}), 400

    required_fields = ["student_id", "promoted_roll", "promoted_date", "promoted_class_id"]
    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"Missing required parameter: {field}"}), 400

    try:
        student_id = int(data.get('student_id'))
        promoted_roll = int(data.get('promoted_roll'))
        promoted_class_id = int(data.get('promoted_class_id'))
    except (TypeError, ValueError):
        return jsonify({"message": "Student, promoted roll, or promoted class is not valid!"}), 400

    promoted_date = data.get('promoted_date')
    if promoted_date:
        try:
            promoted_date = datetime.datetime.strptime(promoted_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Invalid promotion date format. Use 'year-month-day'."}), 400
    else:
        return jsonify({"message": "Please enter promotion date."}), 400
    

    available_roll = get_gapped_rolls(promoted_class_id, current_session)
    final_rolls = available_roll['gapped_rolls'] + [available_roll['next_roll']]

    if promoted_roll not in final_rolls:
        allowed_rolls = ", ".join(map(str, final_rolls))
        return jsonify({
            "message": f"Roll no already assigned. You can only assign one of these rolls: {allowed_rolls}."
        }), 400


    # check if the student exist in previous session.
    previous_session_row = StudentSessions.query.filter_by(
        student_id=student_id,
        session_id=current_session - 1
    ).first()
    if not previous_session_row:
        return jsonify({"message": "Student not found in previous session."}), 404


    # --- Check if already exists in current session ---
    already_promoted = StudentSessions.query.filter_by(
        student_id=student_id,
        session_id=current_session
    ).first()

    # =========================================================
    # 🚨 SOFT RECOVERY (SAFE VERSION)
    # =========================================================
    if previous_session_row.status == "promoted" and not already_promoted:
        current_app.logger.error(
            f"[DATA INCONSISTENCY] Student {student_id} marked promoted in session "
            f"{current_session - 1} but no row in session {current_session}"
        )
        # NOTE: do NOT modify DB here (outside transaction)
        recovered_status = "active"
    else:
        recovered_status = previous_session_row.status
    # =========================================================


    # --- State validation (use recovered_status) ---
    if recovered_status == "tc":
        return jsonify({"message": "TC already issued. Promotion not allowed."}), 400

    if recovered_status == "promoted":
        return jsonify({"message": "Already promoted cannot promote again."}), 400

    if recovered_status not in ("active", None, ""):
        return jsonify({"message": "Promotion not allowed."}), 400
    
    # --- Prevent duplicate ---
    if already_promoted and already_promoted.status != "left":
        return jsonify({
            "message": "Student already has an active entry in this session."
        }), 400

    # Validate that the selected class exists and is valid
    selected_class = ClassData.query.filter_by(
        id=promoted_class_id,
        school_id=school_id
    ).first()
    
    if not selected_class:
        return jsonify({"message": "Selected class does not exist or is not available."}), 400
    
    # Get current class grade_level
    current_class = ClassData.query.filter_by(id=previous_session_row.class_id).first()
    if not current_class:
        return jsonify({"message": "Current class information not found."}), 404
    
    # Validate that selected class is current class or above
    if (selected_class.grade_level is not None and 
        current_class.grade_level is not None and
        selected_class.grade_level < current_class.grade_level):
        return jsonify({"message": "Cannot promote to a lower class."}), 400
    
    class_to_promote = promoted_class_id

    # Check for existing roll number in the target class and session
    roll_conflict = StudentSessions.query.filter_by(
        session_id=current_session,
        class_id=promoted_class_id,
        ROLL=promoted_roll
    ).first()

    if roll_conflict:
        return jsonify({"message": "This roll number is already in use in the target class and session."}), 400

    # --- Create new session ---
    new_session = StudentSessions(
        student_id=student_id,
        session_id=current_session,
        ROLL=promoted_roll,
        class_id=class_to_promote,
        created_at=promoted_date,
        status="active"
    )

    

    # =========================================================
    # 🔒 FINAL TRANSACTION (ONLY ONE PLACE)
    # =========================================================
    try:
        previous_session_row.status = "promoted"
        db.session.add(new_session)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "message": "Failed to promote student due to a roll/class conflict."
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database error during promotion: {str(e)}")
        return jsonify({
            "message": "Failed to promote student due to a database error."
        }), 500

    return jsonify({
        "message": "Student promoted successfully",
        "state": "PROMOTED",
        "promoted_session_id": new_session.id,
        "next_roll": new_session.ROLL,
        "next_class_id": new_session.class_id,
        "next_class": selected_class.CLASS,  # ✅ added
        "created_at": promoted_date.isoformat()
    }), 200
