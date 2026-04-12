# src/controller/prv_year_students.py

from flask import session, request, Blueprint, jsonify
from sqlalchemy import select
from sqlalchemy.orm import aliased

from src.model import StudentsDB
from src.model import StudentSessions
from src.model import ClassData

from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

get_students_by_class_api_bp = Blueprint('get_students_by_class_api_bp', __name__)


@get_students_by_class_api_bp.route('/api/promote/students-by-class', methods=["POST"])
@login_required
@permission_required('promote_student')
def get_students_by_class():
    data = request.json
    class_id = data.get('class_id')

    school_id = session["school_id"]
    current_session = int(session["session_id"])

    PromotedSession = aliased(StudentSessions)
    NextClassData = aliased(ClassData)
    promoted_subq = (
        select(
            PromotedSession.student_id,
            PromotedSession.id.label("promoted_session_id"),
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
        StudentsDB.ADMISSION_NO,
        StudentsDB.IMAGE,
        StudentsDB.GENDER,
        StudentsDB.FATHERS_NAME,
        StudentsDB.PHONE,
        StudentsDB.ADMISSION_DATE,
        ClassData.CLASS.label("previous_class"),
        ClassData.is_terminal.label("current_class_is_terminal"),
        StudentSessions.id.label("student_session_id"),
        StudentSessions.ROLL.label("previous_roll"),
        StudentSessions.class_id,
        StudentSessions.status.label("previous_status"),
        StudentSessions.tc_number,
        StudentSessions.tc_date,
        StudentSessions.left_reason,

        promoted_subq.c.next_roll,
        promoted_subq.c.promoted_date,
        promoted_subq.c.promoted_session_id,
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
    ).filter(
        ClassData.id == class_id,
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == current_session - 1  # Previous session
    ).order_by(
        StudentSessions.ROLL
    ).all()

    students_payload = []
    for row in rows:
        # Determine UI state
        state = "NOT_PROMOTED_NOT_TC"
        if str(row.previous_status) == "tc":
            state = "TC_ISSUED"
        elif row.promoted_session_id and str(row.promoted_status) != "left":
            state = "PROMOTED"

        students_payload.append({
            "id": row.id,
            "student_session_id": row.student_session_id if row.student_session_id else None,
            "student_session_prev_status": str(row.previous_status) if row.previous_status else None,
            "STUDENTS_NAME": row.STUDENTS_NAME,
            "ADMISSION_NO": row.ADMISSION_NO,
            "IMAGE": row.IMAGE,
            "GENDER": row.GENDER,
            "FATHERS_NAME": row.FATHERS_NAME,
            "PHONE": row.PHONE,
            "ADMISSION_DATE": row.ADMISSION_DATE.isoformat() if row.ADMISSION_DATE else None,
            "previous_class": row.previous_class,
            "previous_roll": row.previous_roll,
            "next_roll": row.next_roll,
            "promoted_date": row.promoted_date.isoformat() if row.promoted_date else None,
            "promoted_session_id": row.promoted_session_id,
            "next_class": row.next_class,
            "tc_number": row.tc_number,
            "tc_date": row.tc_date.isoformat() if row.tc_date else None,
            "left_reason": row.left_reason,
            "is_terminal": bool(row.current_class_is_terminal),
            "can_promote": not bool(row.current_class_is_terminal) and state == "NOT_PROMOTED_NOT_TC",
            "state": state,
        })

    return jsonify({"students": students_payload})
