# src/controller/promote_student.py

from collections import defaultdict
import csv
from flask import render_template, session, url_for, redirect, Blueprint
from sqlalchemy import extract, func

from src.model import StudentSessions, StudentsDB
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess
from src.model.TeachersLogin import TeachersLogin
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required


promote_student_bp = Blueprint( 'promote_student_bp',   __name__)


@promote_student_bp.route('/promote_student', methods=["GET", "POST"])
@login_required
@permission_required('promote_student')
def promoteStudent():

    user_id = session["user_id"]

    classes = (
        db.session.query(ClassData.id, ClassData.CLASS)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .join(TeachersLogin, TeachersLogin.id == ClassAccess.staff_id)
        .filter(TeachersLogin.id == user_id)
        .order_by(ClassData.id.asc())
        .all()
    )

    try:
        school_id = session["school_id"]
        current_session = int(session["session_id"])
        previous_session = current_session - 1
    except (KeyError, ValueError):
        previous_session = None
        school_id = None

    overall_all = 0
    overall_promoted = 0
    overall_tc = 0
    overall_none = 0

    if school_id is not None and previous_session is not None:
        overall_all = (
            db.session.query(func.count(StudentSessions.id))
            .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
            .filter(
                StudentSessions.session_id == previous_session,
                StudentsDB.school_id == school_id
            )
            .scalar() or 0
        )

        overall_tc = (
            db.session.query(func.count(StudentSessions.id))
            .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
            .filter(
                StudentSessions.session_id == previous_session,
                StudentsDB.school_id == school_id,
                StudentSessions.status == 'tc'
            )
            .scalar() or 0
        )

        overall_promoted = (
            db.session.query(func.count(StudentSessions.id))
            .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
            .filter(
                StudentSessions.session_id == current_session,
                StudentsDB.school_id == school_id,
                StudentSessions.status == 'promoted'
            )
            .scalar() or 0
        )

        overall_none = max(overall_all - overall_promoted - overall_tc, 0)

    return render_template(
        'promote_student/main.html',
        classes=classes,
        overall_all=overall_all,
        overall_promoted=overall_promoted,
        overall_tc=overall_tc,
        overall_none=overall_none
    )

