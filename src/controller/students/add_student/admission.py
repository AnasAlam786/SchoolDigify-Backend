# src/controller/admission.py

from flask import render_template, session, Blueprint
from sqlalchemy import func

from src.model.Sessions import Sessions
from src.model.StudentsDB import StudentsDB
from src.model.ClassData import ClassData
from src.model.StudentsDB import StudentsDB
from src.model.ClassAccess import ClassAccess
from src.model.enums import StudentsDBEnums

from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

from datetime import datetime

admission_bp = Blueprint( 'admission_bp',   __name__)



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



@admission_bp.route('/admission', methods=["GET", "POST"])
@login_required
@permission_required('admission')
def admission():

    """Render the add student form."""
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

    # Calculate next SR and Admission No
    current_session_year = str(current_session)[-2:] if current_session else str(datetime.now().year)[-2:]

    max_sr, max_adm = (
        db.session.query(
            func.max(StudentsDB.SR).label("max_sr"),
            func.max(StudentsDB.ADMISSION_NO).label("max_adm")
        )
        .filter(StudentsDB.school_id == school_id)
        .first()
    )


    max_sr = max_sr if max_sr is not None else 0
    if max_adm is None or str(max_adm)[:2] != current_session_year:
        max_adm = int(current_session_year + "000")
    else:
        max_adm = int(max_adm)

    new_adm = max_adm + 1
    new_sr = max_sr + 1
    current_date = datetime.now().strftime("%d-%m-%Y")

    return render_template(
        'student_form.html',
        mode='add',
        student=None,
        rte_info=None,
        classes=classes_dict,
        admission_sessions=admission_sessions,
        current_session=current_session,
        default_admission_no=new_adm,
        default_sr=new_sr,
        default_admission_date=current_date,
        is_admitted_new=True,  # New students are admitted as new by default
        **get_enum_options()
    )

    