# src/controller/get_students_pdf_api.py

from collections import defaultdict
from datetime import date, datetime
from types import SimpleNamespace
from flask import jsonify, render_template, session, Blueprint
from sqlalchemy import extract, func

from src.model import StudentSessions, StudentsDB
from src.model.ClassData import ClassData
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required


get_students_pdf_api_bp = Blueprint( 'get_students_pdf_api_bp',   __name__)


@get_students_pdf_api_bp.route('/api/get_students_pdf_api', methods=["GET"])
@login_required
@permission_required('admission')
def get_students_pdf_api():

    school_id = session['school_id']

    min_session_subq = (
        db.session.query(
            StudentSessions.student_id,
            func.min(StudentSessions.session_id).label("min_session_id")
        )
        .group_by(StudentSessions.student_id)
        .subquery()
    )


    students = (
        db.session.query(
            extract('year', StudentsDB.ADMISSION_DATE).label("admission_year"),
            StudentsDB.STUDENTS_NAME,
            StudentsDB.SR,
            StudentsDB.ADMISSION_DATE,
            StudentsDB.DOB,
            StudentsDB.ADMISSION_NO,
            StudentsDB.AADHAAR,
            StudentsDB.FATHERS_NAME,
            StudentsDB.MOTHERS_NAME,
            StudentsDB.Caste_Type,
            ClassData.CLASS.label("admission_class"),
            StudentsDB.ADDRESS,

        )
        .join(min_session_subq, min_session_subq.c.student_id == StudentsDB.id)
        .join(
            StudentSessions,
            (StudentSessions.student_id == min_session_subq.c.student_id) &
            (StudentSessions.session_id == min_session_subq.c.min_session_id)
        )
        .join(ClassData, ClassData.id == StudentsDB.admission_class_id)
        .filter(StudentsDB.school_id == school_id)
        .order_by(
            "admission_year",
            StudentsDB.SR
        )
        .all()
    )

    short_class = {"Nursery/KG/PP3":"Nursery",
                 "LKG/KG1/PP2":"LKG",
                 "UKG/KG2/PP1":"UKG"}

    # --- convert SQLAlchemy rows to mutable objects, format dates, and replace class ---
    mutable_students = []
    for s in students:
        obj = SimpleNamespace(**s._asdict())  # make a mutable copy
        for attr, val in obj.__dict__.items():
            if isinstance(val, (date, datetime)):
                setattr(obj, attr, val.strftime("%d-%m-%Y") if val else "")

        # replace long class with short class if exists
        if hasattr(obj, "admission_class") and obj.admission_class in short_class:
            obj.admission_class = short_class[obj.admission_class]
        mutable_students.append(obj)


    # --- group students by year in Python ---
    grouped_students = defaultdict(list)
    for s in mutable_students:
        year = int(s.admission_year)
        grouped_students[year].append(s)


    # --- fill gaps in SR (build a new dict to avoid in-place surprises) ---
    filled_grouped_students = {}
    prev_sr = 0

    for year, student_list in grouped_students.items():
        # separate those with and without SR
        students_with_sr = [s for s in student_list if getattr(s, "SR", None) is not None]
        students_without_sr = [s for s in student_list if getattr(s, "SR", None) is None]

        # sort by integer SR
        students_with_sr.sort(key=lambda x: int(x.SR))

        filled_list = []
        

        for s in students_with_sr:
            sr = int(s.SR)
            if sr > prev_sr + 1:
                # insert blanks for missing SRs between prev_sr and sr
                for missing_sr in range(prev_sr + 1, sr):
                    blank = SimpleNamespace(
                        SR=missing_sr,
                        STUDENTS_NAME="",
                        ADMISSION_NO="",
                        AADHAAR="",
                        FATHERS_NAME="",
                        MOTHERS_NAME="",
                        Caste_Type="",
                        admission_class="",
                        ADDRESS="",
                        ADMISSION_DATE=None,
                        DOB=None,
                    )
                    filled_list.append(blank)

            filled_list.append(s)
            prev_sr = sr

        # attach those without SR at the end of this year's list
        filled_list.extend(students_without_sr)

        filled_grouped_students[year] = filled_list

    # replace original grouped_students if you want the same variable name
    grouped_students = filled_grouped_students
    # csv_file_path = 'students_report.csv'


    # with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
    #     writer = csv.writer(file)
        
    #     # Write header
        
    #     # Write data rows
    #     for year, same_year_students in grouped_students.items():
    #         writer.writerow(['STUDENTS_NAME', 'DOB', 'ADMISSION_DATE', 'ADMISSION_NO', 'SR', 'AADHAAR','FATHERS_NAME', 'MOTHERS_NAME', 'Caste_Type', "Admission Class", "ADDRESS"])

    #         for student in same_year_students:
    #             writer.writerow([
    #                 student.STUDENTS_NAME,
    #                 student.DOB.strftime('%Y-%m-%d') if student.DOB else '',
    #                 student.ADMISSION_DATE.strftime('%Y-%m-%d') if student.ADMISSION_DATE else '',
    #                 student.ADMISSION_NO,
    #                 student.SR,
    #                 str(student.AADHAAR),
    #                 student.FATHERS_NAME,
    #                 student.MOTHERS_NAME,
    #                 student.Caste_Type,
    #                 student.admission_class,
    #                 student.ADDRESS
    #             ])

    #         writer.writerow([])


    html = render_template('pdf-components/students_list_pdf.html', grouped_students = grouped_students)

    return {"html": html}
