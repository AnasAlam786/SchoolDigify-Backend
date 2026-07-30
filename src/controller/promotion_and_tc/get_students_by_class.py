# src/controller/prv_year_students.py

from flask import session, request, Blueprint, jsonify
from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from src.model import StudentsDB
from src.model import StudentSessions
from src.model import ClassData
from src.model import TCRecords

from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

get_students_by_class_api_bp = Blueprint('get_students_by_class_api_bp', __name__)


def get_student_state(row):
    """
    Determine the student's current promotion/TC state.
    """

    # Student has an issued TC
    if row.previous_status == "tc" or row.tc_record_status == "issued":
        return "TC_ISSUED"

    # Student has been promoted
    if row.promoted_student_id and row.promoted_status != "left":
        return "PROMOTED"

    # No action has been taken
    return "NOT_PROMOTED_NOT_TC"

@get_students_by_class_api_bp.route('/api/promote-and-tc-data', methods=["POST"])
@login_required
@permission_required('promote_student')
def get_students_by_class():
    data = request.json
    class_id = data.get('class_id')

    school_id = session["school_id"]
    current_session = int(session["session_id"])

    PromotedSession = aliased(StudentSessions)
    NextClassData = aliased(ClassData)
    TCRecord = aliased(TCRecords)
    promoted_subq = (
        select(
            PromotedSession.student_id,
            PromotedSession.id.label("promoted_student_id"),
            PromotedSession.ROLL.label("next_roll"),
            PromotedSession.class_id.label("next_class_id"),
            PromotedSession.created_at.label("promoted_date"),
            PromotedSession.status.label("promoted_status"),
        )
        .where(
            PromotedSession.session_id == current_session
        )
        .subquery()
    )

    # Main query with LEFT JOIN to promoted_subq
    rows = db.session.query(
        StudentsDB.id,
        StudentsDB.STUDENTS_NAME,
        StudentsDB.IMAGE,
        StudentsDB.GENDER,
        StudentsDB.FATHERS_NAME,
        StudentsDB.PEN,
        ClassData.CLASS.label("previous_class"),
        ClassData.is_terminal.label("current_class_is_terminal"),
        StudentSessions.id.label("student_session_id"),
        StudentSessions.ROLL.label("previous_roll"),
        StudentSessions.class_id,
        StudentSessions.status.label("previous_status"),
        TCRecord.tc_no.label("tc_number"),
        TCRecord.tc_date,
        TCRecord.status.label("tc_record_status"),

        promoted_subq.c.next_roll,
        promoted_subq.c.promoted_date,
        promoted_subq.c.promoted_student_id,
        promoted_subq.c.promoted_status,
        NextClassData.CLASS.label("next_class")
    ).join(
        StudentSessions,
        StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData,
        StudentSessions.class_id == ClassData.id
    ).outerjoin(
        promoted_subq,
        promoted_subq.c.student_id == StudentsDB.id
    ).outerjoin(
        NextClassData,
        NextClassData.id == promoted_subq.c.next_class_id
    ).outerjoin(
        TCRecord,
        TCRecord.student_session_id == StudentSessions.id
    ).filter(
        ClassData.id == class_id,
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == current_session - 1  # Previous session
    ).order_by(
        StudentSessions.ROLL
    ).all()

    students_payload = []

    students_status_stats = {
        "all": len(rows),
        "promoted": 0,
        "tc_issued": 0,
        "no_action": 0,
    }


    for row in rows:
        # Determine UI state
        state = get_student_state(row)

        if state == "PROMOTED":
            students_status_stats["promoted"] += 1

        elif state == "TC_ISSUED":
            students_status_stats["tc_issued"] += 1

        else:
            students_status_stats["no_action"] += 1

        students_payload.append({
            "id": row.id,
            "student_session_id": row.student_session_id if row.student_session_id else None,
            "student_session_prev_status": str(row.previous_status) if row.previous_status else None,
            "STUDENTS_NAME": row.STUDENTS_NAME,
            "IMAGE": row.IMAGE,
            "FATHERS_NAME": row.FATHERS_NAME,
            "PEN": row.PEN,
            "GENDER": row.GENDER,

            "previous_class": row.previous_class,
            "previous_roll": row.previous_roll,

            "new_roll": row.next_roll,
            "new_class": row.next_class,

            "promoted_date": row.promoted_date.isoformat() if row.promoted_date else None,
            "promoted_student_id": row.promoted_student_id,

            "tc_number": row.tc_number,
            "tc_date": row.tc_date.isoformat() if row.tc_date else None,

            "has_cancelled_tc": True if row.tc_record_status == 'cancelled' else False,
            "cancelled_tc_number": row.tc_number if row.tc_record_status == 'cancelled' else None,
            
            "is_terminal": bool(row.current_class_is_terminal),
            "state": state,
        })


    return jsonify({"students": students_payload, "students_status_stats": students_status_stats})