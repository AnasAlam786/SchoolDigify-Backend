# src/controller/admission.py

from flask import jsonify, session, Blueprint
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



@admission_bp.route('/api/admission', methods=["GET", "POST"])
@login_required
@permission_required('admission')
def admission_data():

    """Render the add student form."""
    user_id = session["user_id"]
    school_id = session["school_id"]
    current_session = session["session_id"]

    # Get classes accessible to user

    try:
        classes_query = (
            db.session.query(ClassData)
            .join(ClassAccess, ClassAccess.class_id == ClassData.id)
            .filter(ClassAccess.staff_id == user_id)
            .order_by(ClassData.id.asc())
        )
        classes = classes_query.all()
        classes_dict = [ 
            {
                "id": cls.id,
                "class_name": cls.CLASS
            }
            for cls in classes
        ]

    except Exception as e:
        return jsonify({'error': 'Error fetching classes!'}), 404

    # Build admission sessions
    admission_sessions = [
        {
            "id": int(year),
            "label": f"{int(year)}-{int(year)+1}"
        }
        for year in session.get("all_sessions", [])
    ]

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

    max_sr = max_sr or 0
    if max_adm is None or str(max_adm)[:2] != current_session_year:
        max_adm = int(current_session_year + "000")
    else:
        max_adm = int(max_adm)

    current_date = datetime.now().strftime("%d-%m-%Y")

    response = {
        "mode": "add",
        "student": None,
        "rte_info": None,
        "classes": classes_dict,
        "admission_sessions": admission_sessions,
        "current_session": str(current_session),
        "default_admission_no": max_adm + 1,
        "default_sr": max_sr + 1,
        "default_admission_date": current_date,
        "is_admitted_new": True,
        **get_enum_options()
    }

    return jsonify(response)

    