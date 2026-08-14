# src/controller/promoted_student_modal_api.py

from flask import request, jsonify, Blueprint, session

from sqlalchemy import func
from sqlalchemy.orm import aliased

from src import db
from src.model import StudentsDB
from src.model import StudentSessions
from src.model import ClassData

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required


get_promoted_student_data_api_bp = Blueprint('get_promoted_student_data_api_bp', __name__)


@get_promoted_student_data_api_bp.route('/api/get_promoted_student_data', methods=["POST"])
@login_required
@permission_required('promote_student')
def get_promoted_student_data():
    """
    Returns details required for the Depromote Student modal.

    Request:
    {
        "promoted_student_id": 123
    }
    """

    data = request.get_json() or {}
    school_id = session.get("school_id")

    try:
        promoted_student_id = int(data["promoted_student_id"])
        print(promoted_student_id)
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid student ID."}), 400

    try:

        PromotedSession = aliased(StudentSessions)

        promoted_student = (
            db.session.query(
                StudentsDB.id.label("student_id"),
                StudentsDB.STUDENTS_NAME, StudentsDB.IMAGE,
                StudentsDB.FATHERS_NAME, StudentsDB.PHONE,

                PromotedSession.id.label("promoted_student_id"),
                PromotedSession.class_id.label("promoted_class_id"),
                PromotedSession.ROLL.label("promoted_roll"),
                PromotedSession.created_at.label("promoted_created_at"),

                ClassData.CLASS.label("promoted_class"),
                ClassData.grade_level.label("promoted_grade_level"),
            )
            .join(
                PromotedSession,
                PromotedSession.student_id == StudentsDB.id
            )
            .join(
                ClassData,
                ClassData.id == PromotedSession.class_id
            )
            .filter(
                PromotedSession.id == promoted_student_id,
                StudentsDB.school_id == school_id
            )
            .first()
        )

        if promoted_student is None:
            return jsonify({"error": "Student not found."}), 404

        PreviousSession = aliased(StudentSessions)
        PreviousClass = aliased(ClassData)

        previous_session = (
            db.session.query(
                PreviousSession.id.label("previous_student_session_id"),
                PreviousSession.class_id.label("previous_class_id"),
                PreviousSession.ROLL.label("previous_roll"),

                PreviousClass.CLASS.label("previous_class"),
                PreviousClass.grade_level.label("previous_grade_level"),
            )
            .join(
                PreviousClass,
                PreviousClass.id == PreviousSession.class_id
            )
            .filter(
                PreviousSession.student_id == promoted_student.student_id,
                PreviousSession.id != promoted_student_id,
            )
            .order_by(
                PreviousClass.grade_level.desc(),
                PreviousSession.created_at.desc()
            )
            .first()
        )

        if previous_session is None:
            return jsonify({
                "error": "Previous session not found."
            }), 404

        available_classes = (
            db.session.query(
                ClassData.id,
                ClassData.CLASS,
                ClassData.grade_level
            )
            .filter(
                ClassData.school_id == school_id,
                ClassData.grade_level >= previous_session.previous_grade_level
            )
            .order_by(ClassData.grade_level.asc())
            .all()
        )

        result = {
            "student_id": promoted_student.student_id,
            "student_name": promoted_student.STUDENTS_NAME,
            "image": promoted_student.IMAGE,
            "father_name": promoted_student.FATHERS_NAME,
            "phone": promoted_student.PHONE,

            "promoted_student_id": promoted_student.promoted_student_id,
            "promoted_class_id": promoted_student.promoted_class_id,
            "promoted_class": promoted_student.promoted_class,
            "promoted_roll": promoted_student.promoted_roll,
            "promoted_date": promoted_student.promoted_created_at.strftime("%Y-%m-%d"),

            "previous_student_session_id": previous_session.previous_student_session_id,
            "previous_class_id": previous_session.previous_class_id,
            "previous_class": previous_session.previous_class,
            "previous_roll": previous_session.previous_roll,
            "previous_grade_level": previous_session.previous_grade_level,
        }

        available_classes = [
                {
                    "id": c.id,
                    "name": c.CLASS,
                    "grade_level": c.grade_level
                }
                for c in available_classes
            ]

        return jsonify({
            "student_data":result, 
            "available_classes":available_classes
        }), 200

    except Exception as e:
        print(e)
        return jsonify({
            "error": "An error occurred while fetching student details."
        }), 500