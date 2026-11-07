
from flask import jsonify, session, Blueprint, request, current_app
from sqlalchemy import case, exists, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import aliased

from src.model.ClassAccess import ClassAccess
from src.model.RTEInfo import RTEInfo
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData

from src import db
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from src.controller.students_list.student_query import (
    PAGE_SIZE,
    StudentQueryError,
    parse_params,
    apply_filters,
    apply_sorting,
)


get_students_data_api_bp = Blueprint('get_students_data_api_bp', __name__)


@get_students_data_api_bp.route('/api/get_students_data', methods=['GET'])
@login_required
@permission_required('student_list')
def get_students_data():
    try:
        params = parse_params(request.args)

        school_id = session["school_id"]
        selected_session = session["session_id"]
        user_id = session["user_id"]

        # Create base query
        query = db.session.query(
            StudentsDB.id, StudentsDB.STUDENTS_NAME,
            StudentsDB.DOB, StudentsDB.AADHAAR,
            StudentsDB.FATHERS_NAME, StudentsDB.PEN,
            StudentsDB.GENDER, StudentsDB.IMAGE,
            StudentsDB.SR, StudentsDB.admission_session_id,
            StudentsDB.PHONE, StudentsDB.Free_Scheme,
            StudentsDB.ADMISSION_DATE,

            StudentSessions.ROLL,
            StudentSessions.id.label("student_session_id"),

            ClassData.CLASS,
            ClassData.id.label("class_id"),
            ClassData.display_order,

            exists().where(
                RTEInfo.student_id == StudentsDB.id,
                RTEInfo.is_RTE.is_(True)
            ).label("is_RTE"),

            case(
                (StudentsDB.admission_session_id == selected_session, "new"),
                else_="old"
            ).label("student_status")

        ).join(
            StudentSessions,
            StudentSessions.student_id == StudentsDB.id
        ).join(
            ClassData,
            ClassData.id == StudentSessions.class_id
        )

        # Apply filters
        query = apply_filters(
            query, params, selected_session, school_id, user_id
        )

        student_count = query.order_by(None).count()

        # Apply sorting
        query = apply_sorting(query, params)

        

        # Apply pagination
        offset = (params["page"] - 1) * PAGE_SIZE

        rows = query.limit(PAGE_SIZE + 1).offset(offset).all()

        has_more = len(rows) > PAGE_SIZE
        students = rows[:PAGE_SIZE]

        # Convert rows into dictionaries
        students = [
            {
                **row._asdict(),
                "DOB": row.DOB.strftime("%a, %d %b %Y") if row.DOB else None,
                "ADMISSION_DATE": row.ADMISSION_DATE.strftime("%Y-%m-%d") if row.ADMISSION_DATE else None,
            }
            for row in students
        ]

        return jsonify({
            "students": students,
            "total_count": student_count,
            "page": params["page"],
            "has_more": has_more,
        })

    except StudentQueryError as error:
        return jsonify({"error": str(error)}), 400

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Failed to load student list page")
        return jsonify({"error": "Unable to load students."}), 500


@get_students_data_api_bp.route('/api/get_students_stats', methods=['GET'])
@login_required
@permission_required('students_stats')
def get_students_stats():
    try:
        school_id = session["school_id"]
        selected_session = session["session_id"]

        def get_stats(session_id):

            query = db.session.query(
                func.count(StudentsDB.id).label("total_students"),

                func.coalesce(
                    func.sum(
                        case(
                            (StudentsDB.admission_session_id == session_id, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("new_students"),

            ).join(
                StudentSessions,
                StudentSessions.student_id == StudentsDB.id,
            ).join(
                ClassData,
                StudentSessions.class_id == ClassData.id,
            ).filter(
                StudentsDB.school_id == school_id,
                StudentSessions.session_id == session_id,
            )

            return query.one()

        current_stats = get_stats(selected_session)
        previous_stats = get_stats(selected_session - 1)

        total_students = current_stats.total_students or 0
        new_students = current_stats.new_students or 0

        previous_year_students_total = previous_stats.total_students or 0
        new_students_prev = previous_stats.new_students or 0

        increased_students = total_students - previous_year_students_total

        return jsonify({
            "total_students": total_students,
            "new_students": new_students,
            "old_students": total_students - new_students,

            "previous_year_students_total": previous_year_students_total,
            "new_students_prev": new_students_prev,
            "old_students_prev": previous_year_students_total - new_students_prev,

            "increased_students": increased_students,

            "total_growth_percentage": round(
                increased_students / previous_year_students_total * 100,
                2,
            ) if previous_year_students_total else 0,

            "new_students_growth_percentage": round(
                (new_students - new_students_prev) / new_students_prev * 100,
                2,
            ) if new_students_prev else 0,
        })

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Failed to load student statistics")
        return jsonify({"error": "Unable to load student statistics."}), 500


@get_students_data_api_bp.route('/api/get_students_print_data', methods=['GET'])
@login_required
@permission_required('student_list')
def get_students_print_data():
    school_id = session['school_id']
    selected_session = session['session_id']
    user_id = session['user_id']
    admission_class = aliased(ClassData)

    students = db.session.query(
        StudentsDB.STUDENTS_NAME,
        ClassData.CLASS.label("CLASS"),
        StudentSessions.ROLL,
        StudentsDB.DOB,
        StudentsDB.AADHAAR,
        StudentsDB.FATHERS_NAME,
        StudentsDB.MOTHERS_NAME,
        StudentsDB.PHONE,
        StudentsDB.ADMISSION_DATE,
        StudentsDB.SR,
        StudentsDB.ADDRESS,
        admission_class.CLASS.label("ADMISSION_CLASS"),
        ClassData.id.label("class_id"),
        ClassData.display_order,
    ).join(
        StudentSessions,
        StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData,
        StudentSessions.class_id == ClassData.id
    ).join(
        ClassAccess,
        ClassAccess.class_id == ClassData.id
    ).outerjoin(
        admission_class,
        admission_class.id == StudentsDB.admission_class_id
    ).filter(
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == selected_session,
        ClassAccess.staff_id == user_id
    ).distinct().order_by(
        ClassData.display_order.asc(),
        ClassData.CLASS.asc(),
        StudentSessions.ROLL.asc(),
        StudentsDB.STUDENTS_NAME.asc()
    ).all()

    student_data = []
    for student in students:
        record = student._asdict()
        for field in ("DOB", "ADMISSION_DATE"):
            value = record[field]
            record[field] = value.strftime("%d-%m-%Y") if value else ""
        student_data.append(record)

    return jsonify({"status": "success", "students": student_data})