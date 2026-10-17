# src/controller/marks/bulk_certificate_results.py

import re

from flask import session, request, jsonify, Blueprint, render_template

from src.model import SchoolSession
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.Schools import Schools
from src.model.TeachersLogin import TeachersLogin
from src import db


from .utils.new_marks_processing_format import result_data
from .utils.calc_grades import get_grade
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

bulk_markheet_certificate_bp = Blueprint('bulk_markheet_certificate_bp', __name__)


def numeric_scores(values):
    for value in values:
        if value in (None, ""):
            continue
        try:
            yield float(value)
        except (TypeError, ValueError):
            continue


def prepare_result_for_template(result):
    exams = result["exams"]
    subjects = result["subjects"]
    exam_totals = result["exam_totals"]
    summary = result["summary"]
    exam_columns = []
    terms = {}

    for exam in exams:
        totals = exam_totals[str(exam["id"])]
        column = {
            "name": exam["name"],
            "weightage": exam["weightage"],
            "exam_total": totals["total"],
            "percentage": totals["percentage"],
            "subject_marks": {
                subject["name"]: subject["marks"].get(str(exam["id"]), "")
                for subject in subjects
            },
        }
        exam_columns.append(column)

        term_number_match = re.search(r"\d+", str(exam["term"] or ""))
        if term_number_match:
            terms.setdefault(int(term_number_match.group()), []).append((exam, column))

    ordered_columns = []
    for term_number, term_exams in sorted(terms.items()):
        ordered_columns.extend(column for _, column in term_exams)

        term_total = round(sum(float(column["exam_total"] or 0) for _, column in term_exams), 1)
        term_max = sum(
            float(exam["weightage"] or 0) * len(subjects)
            for exam, _ in term_exams
        )
        term_subject_marks = {}
        for subject in subjects:
            scores = numeric_scores(
                column["subject_marks"].get(subject["name"])
                for _, column in term_exams
            )
            scores = list(scores)
            term_subject_marks[subject["name"]] = round(sum(scores), 1) if scores else ""

        ordered_columns.append({
            "name": f"{term_number} Total",
            "weightage": sum(float(exam["weightage"] or 0) for exam, _ in term_exams),
            "exam_total": term_total,
            "percentage": round(term_total / term_max * 100, 2) if term_max else 0,
            "subject_marks": term_subject_marks,
        })

    ordered_columns.extend(
        column
        for exam, column in zip(exams, exam_columns)
        if not re.search(r"\d+", str(exam["term"] or ""))
    )

    all_subject_marks = {}
    for subject in subjects:
        scores = list(numeric_scores(
            column["subject_marks"].get(subject["name"])
            for column in exam_columns
        ))
        all_subject_marks[subject["name"]] = round(sum(scores), 1) if scores else ""

    ordered_columns.extend([
        {
            "name": "G. Total",
            "weightage": summary["grand_max_total"],
            "exam_total": summary["grand_total"],
            "percentage": summary["overall_percentage"],
            "subject_marks": all_subject_marks,
        },
    ])

    grade, _ = get_grade(summary["overall_percentage"])
    ordered_columns.append({
        "name": "Grades",
        "weightage": "",
        "exam_total": grade,
        "percentage": "-",
        "subject_marks": {subject["name"]: grade for subject in subjects},
    })

    result["exam_columns"] = ordered_columns
    dob = result["student"].get("DOB")
    if hasattr(dob, "strftime"):
        result["student"]["DOB"] = dob.strftime("%a, %d %b %Y")
    return result


@bulk_markheet_certificate_bp.route('/api/bulk_download_results', methods=["POST"])
@login_required
@permission_required('get_result')  # Assuming same permission as single download
def bulk_download_results():

    current_session_id = session["session_id"]
    user_id = session["user_id"]
    school_id = session["school_id"]

    try:
        student_session_ids = request.json.get("student_session_id", [])
        class_id = int(request.json.get("class_id"))
        if not isinstance(student_session_ids, list) or not student_session_ids:
            return jsonify({"message": "Invalid student IDs."}), 400
        student_session_ids = [int(sid) for sid in student_session_ids]
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid input."}), 400

    # Session checks
    if not student_session_ids or not current_session_id or not user_id:
        return jsonify({"message": "Session data missing. Please logout and login again!"}), 403

    extra_fields = {
        "StudentsDB": ["STUDENTS_NAME", "DOB", "FATHERS_NAME", "IMAGE",
                       "MOTHERS_NAME", "ADDRESS", "PHONE", "GENDER", "PEN"],
        "ClassData": ["CLASS"],
        "StudentSessions": ["ROLL", "class_id", "Attendance"],
    }


    try:
        student_marks_data = result_data(
            school_id, current_session_id, class_id, 
            student_session_ids=student_session_ids,
            extra_fields=extra_fields)
        student_marks_data = [
            prepare_result_for_template(result)
            for result in student_marks_data
        ]
    except Exception as e:
        print(e)
        return jsonify({"error": "Some error to fetch marks"}), 400

    if not student_marks_data:
        return jsonify({"message": "No Data Found"}), 400


    school = (
        db.session.query(
            Schools.Logo,
            Schools.school_heading_image
        )
        .filter(Schools.id == school_id)
        .first()
    )

    rows = (
        db.session.query(
            TeachersLogin.Sign,
            TeachersLogin.Name,
            Roles.role_name,
            ClassAccess.class_id
        )
        .join(Roles, Roles.id == TeachersLogin.role_id)
        .outerjoin(ClassAccess, ClassAccess.staff_id == TeachersLogin.id)
        .filter(
            TeachersLogin.school_id == school_id,
            Roles.role_name.in_(["Principal", "Teacher"])
        )
        .all()
    )

    principal_sign = None
    teacher_sign = None
    principal_name = ""
    teacher_name = ""

    for sign, name, role, cls_id in rows:
        if role == "Principal":
            principal_sign = sign
            principal_name = name.split(" ")[0]
            
        elif role == "Teacher" and cls_id == class_id:
            teacher_sign = sign
            teacher_name = name.split(" ")[0]


    working_days = (
        db.session.query(SchoolSession.working_days)
        .filter(SchoolSession.school_id == school_id,
                SchoolSession.session_id == current_session_id)
        .scalar()
    )
    attandance_out_of = working_days if working_days else "N/A"



    current_session = int(current_session_id)
    session_year = f"{current_session}-{str(current_session + 1)[-2:]}"

    # Generate HTML for bulk results
    html = render_template('pdf-components/tall_result.html', students=student_marks_data, 
                            attandance_out_of = attandance_out_of, 
                            principle_sign=principal_sign, teacher_sign=teacher_sign, 
                            principal_name=principal_name, teacher_name=teacher_name,
                            school_logo=school.Logo, school_heading_image=school.school_heading_image,
                            sesion_year=session_year)

    return jsonify({"html": html})


# bulk route kept for backward support; same as single route expects student list
@bulk_markheet_certificate_bp.route('/api/bulk_print_certificate', methods=["POST"])
@login_required
@permission_required('get_result')
def bulk_print_certificate_api():
    payload = request.json or {}
    students_data = payload.get('students_data')
    school_name = session.get('school_name')


    if not students_data:
        return jsonify({'message': 'students data is required!.'}), 400


    school_logo = session.get('logo') or ''
    session_year = 'N/A'
    current_session_id = session.get('session_id')
    if isinstance(current_session_id, int):
        session_year = f"{current_session_id}-{str(current_session_id + 1)[-2:]}"

    html = render_template('pdf-components/certificates/certificate.html',
                           students=students_data,
                           session_year=session_year,
                           school_logo=school_logo, school_name=school_name)
    return jsonify({'html': str(html)})
