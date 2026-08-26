# src/controller/students/student_routes.py
# Clean routes for add and edit student operations

from flask import session, Blueprint, jsonify
from sqlalchemy.orm import aliased
from datetime import date, datetime
from sqlalchemy import inspect



from src.model.StudentsDB import StudentsDB
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess
from src.model.StudentSessions import StudentSessions
from src.model.RTEInfo import RTEInfo
from src.model.enums import StudentsDBEnums

from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

update_student_bp = Blueprint('update_student_bp', __name__)

def get_enum_options():
    """Get all enum options for select fields."""
    return {
        'gender_options': list(StudentsDBEnums.GENDER.enums),
        'caste_type_options': list(StudentsDBEnums.CASTE_TYPE.enums),
        'religion_options': list(StudentsDBEnums.RELIGION.enums),
        'blood_group_options': list(StudentsDBEnums.BLOOD_GROUP.enums),
        'education_options': list(StudentsDBEnums.EDUCATION_TYPE.enums),
        'fathers_occupation_options': list(StudentsDBEnums.FATHERS_OCCUPATION.enums),
        'mothers_occupation_options': list(StudentsDBEnums.MOTHERS_OCCUPATION.enums),
        'home_distance_options': list(StudentsDBEnums.HOME_DISTANCE.enums),
    }

@update_student_bp.route('/api/update_student/<int:student_id>', methods=['GET'])
@login_required
@permission_required('update_student')
def edit_student(student_id):
    """Render the edit student form."""
    user_id = session["user_id"]
    current_session = session["session_id"]

    # Get classes accessible to user
    classes_query = (
        db.session.query(ClassData)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .filter(ClassAccess.staff_id == user_id)
        .order_by(ClassData.id.asc())
    )

    classes = [
        {
            "id": cls.id,
            "class_name": cls.CLASS
        }
        for cls in classes_query.all()
    ]

    # Build admission sessions
    admission_sessions = [
        {
            "id": int(year),
            "label": f"{int(year)}-{int(year)+1}"
        }
        for year in session.get("all_sessions", [])
    ]

    # Query student with related data
    AdmissionClass = aliased(ClassData)
    CurrentClass = aliased(ClassData)

    student_query = (
        db.session.query(StudentsDB, StudentSessions, RTEInfo)
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(CurrentClass, StudentSessions.class_id == CurrentClass.id)
        .outerjoin(AdmissionClass, StudentsDB.admission_class_id == AdmissionClass.id)
        .outerjoin(RTEInfo, RTEInfo.student_id == StudentsDB.id)
        .filter(
            StudentsDB.id == student_id,
            StudentSessions.session_id == current_session
        )
        .first()
    )

    if not student_query:
        return jsonify({"message": "Student not found"}), 404

    student_db, student_session, rte_info = student_query

    # print(f"Student DB: {student_db.__dict__}")
    # print(f"Student Session: {student_session.__dict__}")
    # print(f"RTE Info: {rte_info.__dict__ if rte_info else 'No RTE Info'}")

    if student_db.is_admitted_new:
        # NEW student for current session
        has_other_session_records = False
    else:
        # Check if student has previous sessions (sessions other than current)
        past_sessions_count = StudentSessions.query.filter(
            StudentSessions.student_id == student_id,
            StudentSessions.session_id != current_session
        ).count()
        has_other_session_records = past_sessions_count > 0

    # Merge student data
    student_data = {}
    
    # Add StudentSessions data
    for col in student_session.__table__.columns:
        value = getattr(student_session, col.name)
        if col.name == 'class_id':
            student_data['class_id'] = value
        elif col.name == 'ROLL':
            student_data['ROLL'] = value
        else:
            student_data[col.name] = value

    # Add StudentsDB data
    for col in inspect(StudentsDB).mapper.column_attrs:
        value = getattr(student_db, col.key)
        student_data[col.key] = value

    # Add RTEInfo data directly into student_data
    if rte_info:
        for col in rte_info.__table__.columns:
            # Don't overwrite student_id if you already have it
            if col.name != "student_id":
                student_data[col.name] = getattr(rte_info, col.name)


    for key, value in student_data.items():
        if isinstance(value, (date, datetime)):
            student_data[key] = value.strftime("%d-%m-%Y")


    return jsonify({
        "student": student_data,
        "classes": classes,
        "admission_sessions": admission_sessions,
        "current_session": current_session,
        "has_other_sessions": has_other_session_records,
        **get_enum_options()
    })