# src/controller/students/student_routes.py
# Clean routes for add and edit student operations

from flask import render_template, session, Blueprint, jsonify
from sqlalchemy.orm import aliased

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

@update_student_bp.route('/update_student/<int:student_id>', methods=['GET'])
@login_required
@permission_required('update_student')
def edit_student(student_id):
    """Render the edit student form."""
    user_id = session["user_id"]
    school_id = session["school_id"]
    current_session = session["session_id"]

    # Get classes accessible to user
    classes_query = (
        db.session.query(ClassData)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .filter(ClassAccess.staff_id == user_id)
        .order_by(ClassData.id.asc())
    )
    classes = classes_query.all()
    classes_dict = {str(cls.id): cls.CLASS for cls in classes}

    # Build admission sessions
    admission_sessions = {}
    for year in session.get("all_sessions", []):
        year = int(year)
        admission_sessions[year] = f"{year}-{year+1}"

    # Query student with related data
    AdmissionClass = aliased(ClassData)
    CurrentClass = aliased(ClassData)

    student_query = (
        db.session.query(StudentsDB, StudentSessions, RTEInfo)
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(AdmissionClass, StudentsDB.Admission_Class == AdmissionClass.id)
        .join(CurrentClass, StudentSessions.class_id == CurrentClass.id)
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

    # Check if student has previous sessions (sessions other than current)
    past_sessions_count = StudentSessions.query.filter(
        StudentSessions.student_id == student_id,
        StudentSessions.session_id != current_session
    ).count()
    hasOtherSessions = past_sessions_count > 0

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
    for col in student_db.__table__.columns:
        value = getattr(student_db, col.name)
        student_data[col.name] = value

    # Create a simple object-like structure for template access
    class StudentData:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)

    student_obj = StudentData(student_data)

    return render_template(
        'student_form.html',
        mode='edit',
        student=student_obj,
        rte_info=rte_info,
        classes=classes_dict,
        admission_sessions=admission_sessions,
        current_session=current_session,
        has_other_sessions=hasOtherSessions,
        **get_enum_options()
    )
