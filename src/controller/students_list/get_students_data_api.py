# src/controller/students_list/get_students_data_api.py

from flask import jsonify, session, Blueprint
from sqlalchemy import case, func

from src.model.RTEInfo import RTEInfo
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess

from src import db
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required


get_students_data_api_bp = Blueprint('get_students_data_api_bp', __name__)


@get_students_data_api_bp.route('/api/get_students_data', methods=['GET'])
@login_required
@permission_required('student_list')
def get_students_data():

    school_id = session['school_id']
    selected_session = session['session_id']
    user_id = session["user_id"]

    # ---------------------------------------------------
    # MAIN STUDENT QUERY
    # ---------------------------------------------------

    data = db.session.query(

        StudentsDB.id,
        StudentsDB.STUDENTS_NAME,

        # send raw DOB (format in frontend)
        StudentsDB.DOB,

        StudentsDB.AADHAAR,
        StudentsDB.FATHERS_NAME,
        StudentsDB.PEN,
        StudentsDB.GENDER,
        StudentsDB.IMAGE,
        StudentsDB.SR,
        StudentsDB.admission_session_id,
        StudentsDB.PHONE,
        StudentsDB.Free_Scheme,
        StudentsDB.ADMISSION_DATE,

        StudentSessions.ROLL,
        StudentSessions.id.label("student_session_id"),

        ClassData.CLASS,
        ClassData.id.label("class_id"),
        ClassData.display_order,

        RTEInfo.is_RTE,

        # NEW / OLD STATUS
        case(
            (StudentsDB.admission_session_id == selected_session, 'new'),
            else_='old'
        ).label('student_status')

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

        RTEInfo,
        RTEInfo.student_id == StudentsDB.id

    ).filter(

        StudentsDB.school_id == school_id,
        StudentSessions.session_id == selected_session,
        ClassAccess.staff_id == user_id

    ).order_by(

        ClassData.display_order.asc(),
        StudentSessions.ROLL.asc()

    ).all()

    # ---------------------------------------------------
    # PYTHON STATS (single loop)
    # ---------------------------------------------------

    total_students = len(data)

    new_students = 0
    old_students = 0

    for s in data:
        if s.student_status == 'new':
            new_students += 1
        else:
            old_students += 1


    # ---------------------------------------------------
    # PREVIOUS SESSION STATS
    # ---------------------------------------------------

    previous_stats = db.session.query(

        func.count(StudentsDB.id).label("total_students"),

        func.sum(
            case(
                (
                    StudentsDB.admission_session_id == (selected_session - 1),
                    1
                ),
                else_=0
            )
        ).label("new_students")

    ).join(

        StudentSessions,
        StudentSessions.student_id == StudentsDB.id

    ).join(

        ClassData,
        StudentSessions.class_id == ClassData.id

    ).join(

        ClassAccess,
        ClassAccess.class_id == ClassData.id

    ).filter(

        StudentsDB.school_id == school_id,
        StudentSessions.session_id == (selected_session - 1),
        ClassAccess.staff_id == user_id

    ).first()

    previous_year_students_total = previous_stats.total_students or 0
    new_students_prev = previous_stats.new_students or 0
    old_students_prev = previous_year_students_total - new_students_prev

    # ---------------------------------------------------
    # GROWTH CALCULATIONS
    # ---------------------------------------------------

    increased_students = total_students - previous_year_students_total

    total_growth_percentage = (
        (increased_students / previous_year_students_total) * 100
        if previous_year_students_total
        else 0
    )

    new_students_growth_percentage = (
        ((new_students - new_students_prev) / new_students_prev) * 100
        if new_students_prev
        else 0
    )

    # ---------------------------------------------------
    # CONVERT SQLAlchemy ROWS
    # ---------------------------------------------------

    students_list = []

    for s in data:

        student = s._asdict()

        # convert date safely
        if student.get("DOB"):
            student["DOB"] = student["DOB"].strftime("%a, %d %b %Y")

        if student.get("ADMISSION_DATE"):
            student["ADMISSION_DATE"] = student["ADMISSION_DATE"].strftime("%Y-%m-%d")

        students_list.append(student)

    # ---------------------------------------------------
    # FINAL RESPONSE
    # ---------------------------------------------------
    return jsonify({

        'status': 'success',

        'students': students_list,

        'total_count': total_students,

        'stats': {

            'total_students': total_students,

            'new_students': new_students,
            'old_students': old_students,

            'previous_year_students_total': previous_year_students_total,

            'new_students_prev': new_students_prev,
            'old_students_prev': old_students_prev,

            'increased_students': increased_students,

            'total_growth_percentage': round(total_growth_percentage, 2),

            'new_students_growth_percentage': round(new_students_growth_percentage, 2)

        }

    })