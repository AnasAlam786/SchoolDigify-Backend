# src/controller/students/students.py

from flask import session, Blueprint
from datetime import datetime, date

from src.model.StudentsDB import StudentsDB
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess
from src.model.StudentSessions import StudentSessions
from src.model.RTEInfo import RTEInfo

from src import db


students_bp = Blueprint('students_bp', __name__)

def parse_form_data(form_data):
    data = {'personal': {}, 'academic': {}, 'guardian': {}, 'contact': {}, 'additional': {}}
    for key, value in form_data.items():
        if '-' in key:
            section, field = key.split('-', 1)
            if section in data:
                data[section][field] = value
    return data



def save_student(validated_data, mode, student_id=None):
    if mode == 'add':
        # Create new student
        student = StudentsDB(
            STUDENTS_NAME=validated_data.personal.STUDENTS_NAME,
            DOB=datetime.strptime(validated_data.personal.DOB, '%d-%m-%Y').date(),
            GENDER=validated_data.personal.GENDER,
            AADHAAR=validated_data.personal.AADHAAR,
            Caste=validated_data.personal.Caste,
            Caste_Type=validated_data.personal.Caste_Type,
            RELIGION=validated_data.personal.RELIGION,
            Height=validated_data.personal.Height,
            Weight=validated_data.personal.Weight,
            BLOOD_GROUP=validated_data.personal.BLOOD_GROUP,
            FATHERS_NAME=validated_data.guardian.FATHERS_NAME,
            FATHERS_AADHAR=validated_data.guardian.FATHERS_AADHAR,
            MOTHERS_NAME=validated_data.guardian.MOTHERS_NAME,
            MOTHERS_AADHAR=validated_data.guardian.MOTHERS_AADHAR,
            FATHERS_EDUCATION=validated_data.guardian.FATHERS_EDUCATION,
            FATHERS_OCCUPATION=validated_data.guardian.FATHERS_OCCUPATION,
            MOTHERS_EDUCATION=validated_data.guardian.MOTHERS_EDUCATION,
            MOTHERS_OCCUPATION=validated_data.guardian.MOTHERS_OCCUPATION,
            ADDRESS=validated_data.contact.ADDRESS,
            PHONE=validated_data.contact.PHONE,
            ALT_MOBILE=validated_data.contact.ALT_MOBILE,
            PIN=validated_data.contact.PIN,
            Home_Distance=validated_data.contact.Home_Distance,
            EMAIL=validated_data.contact.EMAIL,
            Previous_School_Marks=validated_data.additional.Previous_School_Marks,
            Previous_School_Attendance=validated_data.additional.Previous_School_Attendance,
            Previous_School_Name=validated_data.additional.Previous_School_Name,
            Due_Amount=validated_data.additional.Due_Amount,
            is_RTE=validated_data.additional.is_RTE,
            account_number=validated_data.additional.account_number,
            RTE_registered_year=validated_data.additional.RTE_registered_year,
            ifsc=validated_data.additional.ifsc,
            bank_name=validated_data.additional.bank_name,
            bank_branch=validated_data.additional.bank_branch,
            account_holder=validated_data.additional.account_holder,
            Admission_Class=validated_data.academic.Admission_Class,
            ADMISSION_NO=validated_data.academic.ADMISSION_NO,
            SR=validated_data.academic.SR,
            ADMISSION_DATE=datetime.strptime(validated_data.academic.ADMISSION_DATE, '%d-%m-%Y').date(),
            PEN=validated_data.academic.PEN,
            APAAR=validated_data.academic.APAAR,
            school_id=session["school_id"]
        )
        db.session.add(student)
        db.session.flush()  # Get id

        session_entry = StudentSessions(
            student_id=student.id,
            session_id=validated_data.academic.admission_session_id,
            class_id=validated_data.academic.CLASS,
            Section=validated_data.academic.Section,
            ROLL=validated_data.academic.ROLL
        )
        db.session.add(session_entry)
        db.session.commit()
    else:
        # Update existing
        student = StudentsDB.query.get(student_id)
        if student:
            # Update fields, but preserve immutable
            student.STUDENTS_NAME = validated_data.personal.STUDENTS_NAME
            student.DOB = datetime.strptime(validated_data.personal.DOB, '%d-%m-%Y').date()
            student.GENDER = validated_data.personal.GENDER
            student.AADHAAR = validated_data.personal.AADHAAR
            student.Caste = validated_data.personal.Caste
            student.Caste_Type = validated_data.personal.Caste_Type
            student.RELIGION = validated_data.personal.RELIGION
            student.Height = validated_data.personal.Height
            student.Weight = validated_data.personal.Weight
            student.BLOOD_GROUP = validated_data.personal.BLOOD_GROUP
            student.FATHERS_NAME = validated_data.guardian.FATHERS_NAME
            student.FATHERS_AADHAR = validated_data.guardian.FATHERS_AADHAR
            student.MOTHERS_NAME = validated_data.guardian.MOTHERS_NAME
            student.MOTHERS_AADHAR = validated_data.guardian.MOTHERS_AADHAR
            student.FATHERS_EDUCATION = validated_data.guardian.FATHERS_EDUCATION
            student.FATHERS_OCCUPATION = validated_data.guardian.FATHERS_OCCUPATION
            student.MOTHERS_EDUCATION = validated_data.guardian.MOTHERS_EDUCATION
            student.MOTHERS_OCCUPATION = validated_data.guardian.MOTHERS_OCCUPATION
            student.ADDRESS = validated_data.contact.ADDRESS
            student.PHONE = validated_data.contact.PHONE
            student.ALT_MOBILE = validated_data.contact.ALT_MOBILE
            student.PIN = validated_data.contact.PIN
            student.Home_Distance = validated_data.contact.Home_Distance
            student.EMAIL = validated_data.contact.EMAIL
            student.Previous_School_Marks = validated_data.additional.Previous_School_Marks
            student.Previous_School_Attendance = validated_data.additional.Previous_School_Attendance
            student.Previous_School_Name = validated_data.additional.Previous_School_Name
            student.Due_Amount = validated_data.additional.Due_Amount
            student.is_RTE = validated_data.additional.is_RTE
            student.account_number = validated_data.additional.account_number
            student.RTE_registered_year = validated_data.additional.RTE_registered_year
            student.ifsc = validated_data.additional.ifsc
            student.bank_name = validated_data.additional.bank_name
            student.bank_branch = validated_data.additional.bank_branch
            student.account_holder = validated_data.additional.account_holder
            # Immutable: Admission_Class, ADMISSION_NO, SR, ADMISSION_DATE, PEN, APAAR, school_id

            session_entry = StudentSessions.query.filter_by(student_id=student_id, session_id=session["session_id"]).first()
            if session_entry:
                session_entry.class_id = validated_data.academic.CLASS
                session_entry.Section = validated_data.academic.Section
                session_entry.ROLL = validated_data.academic.ROLL
            db.session.commit()




def get_student_data(student_id, current_session, user_id):
    classes_query = (
        db.session.query(ClassData)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .filter(ClassAccess.staff_id == user_id)
        .order_by(ClassData.id.asc())
    )
    class_ids = [cls.id for cls in classes_query.all()]

    AdmissionClass = db.aliased(ClassData)
    CurrentClass = db.aliased(ClassData)

    student_query = (
        db.session.query(StudentsDB, StudentSessions, RTEInfo)
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(AdmissionClass, StudentsDB.Admission_Class == AdmissionClass.id)
        .join(CurrentClass, StudentSessions.class_id == CurrentClass.id)
        .outerjoin(RTEInfo, RTEInfo.student_id == StudentsDB.id)
        .filter(
            StudentsDB.id == student_id,
            StudentSessions.session_id == current_session,
            CurrentClass.id.in_(class_ids)
        )
        .first()
    )

    if not student_query:
        return None

    student_db, student_session, rte_info = student_query

    student_data = {}
    for col in student_db.__table__.columns:
        value = getattr(student_db, col.name)
        if isinstance(value, date):
            value = value.strftime('%d-%m-%Y')
        student_data[col.name] = value

    for col in student_session.__table__.columns:
        student_data[col.name] = getattr(student_session, col.name)

    if rte_info:
        for col in rte_info.__table__.columns:
            student_data[col.name] = getattr(rte_info, col.name)

    student_data['id'] = student_db.id
    student_data['image_url'] = f"https://lh3.googleusercontent.com/d/{student_db.IMAGE}" if student_db.IMAGE else ''
    student_data['CLASS'] = student_data.get('class_id')
    return student_data