# src/controller/students/student_modal_data_api.py

from flask import render_template, session, request, Blueprint, jsonify

from sqlalchemy import func, case
from sqlalchemy.orm import aliased

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model import StudentsDB
from src.model import ClassData
from src.model import StudentSessions
from src.model import RTEInfo

from src import db

student_modal_data_api_bp = Blueprint( 'student_modal_data_api_bp',   __name__)



@student_modal_data_api_bp.route('/api/student_modal_data', methods=["POST"])
@login_required
@permission_required('student_details')
def student_modal_data_api():
    data = request.json
    
    student_id = int(data.get('student_id'))
    phone = data.get('phone')  #replace by familyID

    AdmissionClass = aliased(ClassData)
    CurrentClass = aliased(ClassData)

    student = db.session.query(
            StudentsDB.id, StudentsDB.STUDENTS_NAME, StudentsDB.AADHAAR,
            StudentsDB.IMAGE, StudentsDB.GENDER, StudentsDB.RELIGION,
            StudentsDB.BLOOD_GROUP, StudentsDB.Caste, StudentsDB.Caste_Type,
            StudentSessions.Height, StudentSessions.Weight,
            func.to_char(StudentsDB.DOB, 'Dy, DD Month YYYY').label('DOB'),

            StudentsDB.FATHERS_NAME, StudentsDB.MOTHERS_NAME, StudentsDB.FATHERS_AADHAR, StudentsDB.MOTHERS_AADHAR,
            StudentsDB.FATHERS_EDUCATION, StudentsDB.MOTHERS_EDUCATION,
            StudentsDB.FATHERS_OCCUPATION, StudentsDB.MOTHERS_OCCUPATION,

            StudentsDB.PHONE, StudentsDB.ALT_MOBILE, StudentsDB.Home_Distance, StudentsDB.EMAIL,
            StudentsDB.ADDRESS, StudentsDB.PIN, 

            func.to_char(StudentsDB.ADMISSION_DATE, 'DD-MM-YYYY').label('ADMISSION_DATE'),
            StudentsDB.admission_session_id, StudentsDB.SR, StudentsDB.PEN, 
            StudentsDB.ADMISSION_NO, CurrentClass.CLASS, StudentSessions.ROLL,
            StudentsDB.APAAR, AdmissionClass.CLASS.label("Admission_Class"),  # StudentsDB.Admission_Class actual value

            StudentsDB.Previous_School_Name, StudentsDB.Previous_School_Attendance, StudentsDB.Previous_School_Marks,

            RTEInfo.is_RTE, RTEInfo.RTE_registered_year, RTEInfo.account_number, 
            RTEInfo.ifsc, RTEInfo.bank_name, RTEInfo.account_holder, RTEInfo.bank_branch,
            RTEInfo.registration_no
            
            
        ).join(
            StudentSessions, StudentSessions.student_id == StudentsDB.id  # Join using the foreign key
        ).join(
            CurrentClass, StudentSessions.class_id == CurrentClass.id  # Join using the foreign key
        ).outerjoin(
            AdmissionClass, StudentsDB.admission_class_id == AdmissionClass.id
        ).outerjoin(
            RTEInfo, StudentsDB.id == RTEInfo.student_id
        ).filter(
            StudentsDB.PHONE == phone,
            StudentSessions.session_id == session["session_id"],
        ).order_by(
        case(
            (StudentsDB.id == student_id, 0),  # Place the matched student_id at the top
            else_=1
        )
    ).all()

    if not student:
        return jsonify({"success": False, "message": "Student not found"}), 404
    
    def format_aadhaar(aadhaar: str) -> str:
        """
        Formats a 12-digit Aadhaar number into XXXX-XXXX-XXXX.
        Returns empty string if aadhaar is None or invalid length.
        """
        if not aadhaar or len(aadhaar) != 12:
            return ""
        return f"{aadhaar[:4]}-{aadhaar[4:8]}-{aadhaar[8:12]}"

    
    # Convert to dict for JSON response
    students_data = []
    for s in student:
        students_data.append({
            "id": s.id,
            "STUDENTS_NAME": s.STUDENTS_NAME,
            "DOB": s.DOB,
            "AADHAAR": format_aadhaar(s.AADHAAR),
            "IMAGE": s.IMAGE,
            "GENDER": s.GENDER,
            "BLOOD_GROUP": s.BLOOD_GROUP,
            "Caste": s.Caste if s.Caste else "N/A",
            "Caste_Type": s.Caste_Type,
            "RELIGION": s.RELIGION,
            "Weight": f"{s.Weight} kg" if s.Weight else None,
            "Height": f"{s.Height} cm" if s.Height else None,

            "FATHERS_NAME": s.FATHERS_NAME,
            "MOTHERS_NAME": s.MOTHERS_NAME,
            "FATHERS_AADHAR": format_aadhaar(s.FATHERS_AADHAR),
            "MOTHERS_AADHAR": format_aadhaar(s.MOTHERS_AADHAR),
            "FATHERS_EDUCATION": s.FATHERS_EDUCATION,
            "MOTHERS_EDUCATION": s.MOTHERS_EDUCATION,
            "FATHERS_OCCUPATION": s.FATHERS_OCCUPATION,
            "MOTHERS_OCCUPATION": s.MOTHERS_OCCUPATION,

            "PHONE": s.PHONE,
            "ALT_MOBILE": s.ALT_MOBILE,
            "Home_Distance": s.Home_Distance,
            "ADDRESS": s.ADDRESS,
            "PIN": s.PIN,
            "EMAIL": s.EMAIL,

            "ADMISSION_DATE": s.ADMISSION_DATE,
            "ADMISSION_NO": s.ADMISSION_NO,
            "Admission_Class": s.Admission_Class,
            "SR": s.SR,
            "PEN": s.PEN,
            "CLASS": s.CLASS,
            "ROLL": s.ROLL,
            "APAAR": s.APAAR,
            "admission_session_id": f'{s.admission_session_id}-{s.admission_session_id+1}',

            "is_RTE": s.is_RTE,
            "account_number": s.account_number,
            "ifsc": s.ifsc.upper() if s.ifsc else None,
            "bank_name": s.bank_name,
            "bank_branch": s.bank_branch,
            "account_holder": s.account_holder,
            "RTE_registered_year": s.RTE_registered_year,
            "registration_no": s.registration_no,



            "Previous_School_Name": s.Previous_School_Name,
            "Previous_School_Marks": f"{s.Previous_School_Marks}%" if s.Previous_School_Marks else None,
            "Previous_School_Attendance": f"{s.Previous_School_Attendance} Days" if s.Previous_School_Attendance else None
        })
    
    return jsonify({"success": True, "students": students_data})