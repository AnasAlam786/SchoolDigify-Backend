# src/controller/marks/bulk_certificate_results.py

import math
import re

from flask import session, request, jsonify, Blueprint, render_template

from src.model import SchoolSession
from src.model.ClassAccess import ClassAccess
from src.model.Roles import Roles
from src.model.Schools import Schools
from src.model.TeachersLogin import TeachersLogin
from src import db


from .utils.calc_grades import get_grade
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

bulk_markheet_certificate_bp = Blueprint('bulk_markheet_certificate_bp', __name__)




# =========================================================
# HELPER 1: CONVERT A VALUE TO A VALID NUMBER
# =========================================================

def get_number(value):
    if value is None or value == "":
        return None

    try:
        if isinstance(value, str) and not value.strip():
            number = 0.0
        else:
            number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def number_or_zero(value):
    number = get_number(value)

    if number is None:
        return 0.0

    return number


# =========================================================
# HELPER 2: GET ONLY VALID NUMERIC MARKS
# =========================================================

def numeric_scores(values):
    for value in values:
        number = get_number(value)

        if number is not None:
            yield number


# =========================================================
# HELPER 3: CALCULATE LETTER GRADE
# Same thresholds as React
# =========================================================

def get_result_grade(percentage):
    percentage = number_or_zero(percentage)

    if percentage >= 80:
        return "A"

    if percentage >= 60:
        return "B"

    if percentage >= 45:
        return "C"

    if percentage >= 33:
        return "D"

    return "E"


# =========================================================
# HELPER 4: FIND THE NUMBER IN A TERM
# Example: "Term 2" -> "2"
# =========================================================

def get_term_number(exam):
    term = exam.get("term")

    if term is None:
        term = ""

    match = re.search(r"\d+", str(term))

    if match:
        return match.group()

    return None


# =========================================================
# MAIN FORMATTER: PREPARE ONE STUDENT'S RESULT
# =========================================================

def prepare_result_for_template(result):

    # -----------------------------------------------------
    # PART 1: GET THE STUDENT'S DATA
    # -----------------------------------------------------

    student = dict(result.get("student") or {})
    exams = result.get("exams") or []
    subjects = result.get("subjects") or []
    exam_totals = result.get("exam_totals") or {}
    summary = result.get("summary") or {}

    marks = {}


    # -----------------------------------------------------
    # PART 2: FORMAT EACH INDIVIDUAL EXAM
    # -----------------------------------------------------

    for exam in exams:

        exam_id = str(exam["id"])
        exam_name = exam["name"]

        totals = exam_totals.get(exam_id) or {}

        subject_marks = {}

        # Get the marks of every subject for this exam
        for subject in subjects:

            subject_name = subject["name"]
            all_subject_marks = subject.get("marks") or {}

            mark = all_subject_marks.get(exam_id, "")

            if mark is None:
                mark = ""

            subject_marks[subject_name] = mark

        # Save this exam's information
        marks[exam_name] = {
            "weightage": exam.get("weightage"),
            "exam_display_order": exam.get("display_order"),
            "exam_total": totals.get("total"),
            "percentage": totals.get("percentage"),
            "subject_marks_dict": subject_marks,
        }


    # -----------------------------------------------------
    # PART 3: GROUP EXAMS BY TERM
    # -----------------------------------------------------

    term_groups = {}

    for exam in exams:

        term_number = get_term_number(exam)

        # Exams without a numbered term are handled later
        if term_number is None:
            continue

        if term_number not in term_groups:
            term_groups[term_number] = []

        term_groups[term_number].append(exam)


    # -----------------------------------------------------
    # PART 4: SORT TERMS AND CALCULATE TERM TOTALS
    # -----------------------------------------------------

    exam_order = []

    term_numbers = list(term_groups.keys())

    # Sort Term 1, Term 2, Term 3, and so on
    term_numbers.sort(key=lambda term: int(term))

    for term_number in term_numbers:

        term_exams = term_groups[term_number]

        # Sort exams within the current term
        term_exams.sort(
            key=lambda exam: number_or_zero(exam.get("display_order"))
        )

        # Add individual exam names first
        for exam in term_exams:
            exam_order.append(exam["name"])


        # Calculate the term's total marks
        term_total = 0
        term_max_total = 0
        term_weightage = 0

        for exam in term_exams:

            exam_id = str(exam["id"])
            totals = exam_totals.get(exam_id) or {}

            term_total += number_or_zero(totals.get("total"))
            term_max_total += number_or_zero(totals.get("max_total"))
            term_weightage += number_or_zero(exam.get("weightage"))


        # Calculate the total marks for each subject
        term_subject_marks = {}

        for subject in subjects:

            subject_name = subject["name"]
            all_subject_marks = subject.get("marks") or {}

            subject_scores = []

            for exam in term_exams:

                exam_id = str(exam["id"])
                mark = all_subject_marks.get(exam_id)

                if mark is None or mark == "":
                    continue

                number = get_number(mark)

                if number is not None:
                    subject_scores.append(number)

            if subject_scores:
                term_subject_marks[subject_name] = sum(subject_scores)
            else:
                term_subject_marks[subject_name] = ""


        # Calculate the term percentage
        term_percentage = 0

        if term_max_total > 0:
            term_percentage = float(
                f"{(term_total / term_max_total * 100):.2f}"
            )

        # Match JavaScript Math.round(total * 10) / 10
        term_total = math.floor(term_total * 10 + 0.5) / 10

        # Save the term's total row
        term_name = term_number + " Total"

        marks[term_name] = {
            "weightage": term_weightage,
            "exam_total": term_total,
            "percentage": term_percentage,
            "subject_marks_dict": term_subject_marks,
        }

        # Place the term total after its exams
        exam_order.append(term_name)


    # -----------------------------------------------------
    # PART 5: ADD EXAMS WITHOUT A NUMBERED TERM
    # -----------------------------------------------------

    other_exams = []

    for exam in exams:

        term_number = get_term_number(exam)

        if term_number is None:
            other_exams.append(exam)

    # Sort these exams by display order
    other_exams.sort(
        key=lambda exam: number_or_zero(exam.get("display_order"))
    )

    # Add their names after all numbered terms
    for exam in other_exams:
        exam_order.append(exam["name"])


    # -----------------------------------------------------
    # PART 6: CALCULATE GRAND TOTAL
    # -----------------------------------------------------

    grand_total_subject_marks = {}

    for subject in subjects:

        subject_name = subject["name"]
        all_subject_marks = subject.get("marks") or {}

        subject_scores = []

        # Add this subject's marks across every exam
        for exam in exams:

            exam_id = str(exam["id"])
            mark = all_subject_marks.get(exam_id)

            if mark is None or mark == "":
                continue

            number = get_number(mark)

            if number is not None:
                subject_scores.append(number)

        if subject_scores:
            grand_total_subject_marks[subject_name] = sum(subject_scores)
        else:
            grand_total_subject_marks[subject_name] = ""


    # Save the grand-total row
    grand_total_name = "G. Total"

    marks[grand_total_name] = {
        "weightage": summary.get("grand_max_total"),
        "exam_total": summary.get("grand_total"),
        "percentage": summary.get("overall_percentage"),
        "subject_marks_dict": grand_total_subject_marks,
    }

    exam_order.append(grand_total_name)


    # -----------------------------------------------------
    # PART 7: CALCULATE OVERALL GRADE AND SUBJECT GRADES
    # -----------------------------------------------------

    overall_percentage = number_or_zero(
        summary.get("overall_percentage")
    )

    overall_grade = get_result_grade(overall_percentage)

    subject_grades = {}

    # Maximum marks for one subject across all exams
    max_subject_marks = 0

    for exam in exams:
        max_subject_marks += number_or_zero(exam.get("weightage"))


    for subject in subjects:

        subject_name = subject["name"]

        # Grading-type subjects do not get letter grades
        if subject.get("type") == "grading":
            subject_grades[subject_name] = "-"
            continue

        all_subject_marks = subject.get("marks") or {}

        subject_scores = []

        # Collect this subject's numeric marks
        for exam in exams:

            exam_id = str(exam["id"])
            mark = all_subject_marks.get(exam_id)

            if mark is None or mark == "":
                continue

            number = get_number(mark)

            if number is not None:
                subject_scores.append(number)

        # No marks or no possible marks means no grade
        if not subject_scores or max_subject_marks <= 0:
            subject_grades[subject_name] = "-"
            continue

        # Calculate the subject's percentage
        subject_total = sum(subject_scores)

        subject_percentage = (
            subject_total / max_subject_marks
        ) * 100

        subject_grades[subject_name] = get_result_grade(
            subject_percentage
        )


    # Save the grades row
    marks["Grades"] = {
        "weightage": "",
        "exam_total": overall_grade,
        "percentage": "-",
        "subject_marks_dict": subject_grades,
    }

    exam_order.append("Grades")


    # -----------------------------------------------------
    # PART 8: PREPARE COLUMNS FOR THE HTML TEMPLATE
    # -----------------------------------------------------

    exam_columns = []

    for exam_name in exam_order:

        exam_data = marks[exam_name]

        exam_columns.append({
            "name": exam_name,
            "weightage": exam_data["weightage"],
            "exam_total": exam_data["exam_total"],
            "percentage": exam_data["percentage"],
            "subject_marks": exam_data["subject_marks_dict"],
        })


    # -----------------------------------------------------
    # PART 9: FORMAT STUDENT INFORMATION
    # -----------------------------------------------------

    dob = student.get("DOB")

    if hasattr(dob, "strftime"):
        student["DOB"] = dob.strftime("%a, %d %b %Y")


    # -----------------------------------------------------
    # PART 10: RETURN THE RESULT
    # Keep nested fields for Jinja and formatted fields
    # for React.
    # -----------------------------------------------------

    formatted_result = dict(student)
    formatted_result.update(result)

    formatted_result["student"] = student
    formatted_result["marks"] = marks
    formatted_result["exam_order"] = exam_order

    formatted_result["subject_order"] = [
        subject["name"] for subject in subjects
    ]

    formatted_result["exam_columns"] = exam_columns

    # Match the fields returned by React
    formatted_result["student_id"] = student.get("id")
    formatted_result["student_session_id"] = student.get("session_id")
    formatted_result["STUDENTS_NAME"] = student.get("name")
    formatted_result["ROLL"] = student.get("roll")
    formatted_result["CLASS"] = student.get("class")
    formatted_result["overall_rank"] = summary.get("rank")

    return formatted_result



@bulk_markheet_certificate_bp.route('/api/bulk_download_results', methods=["POST"])
@login_required
@permission_required('get_result')  # Assuming same permission as single download
def bulk_download_results():
    payload = request.get_json(silent=True) or {}
    students_data = payload.get("students_data")

    try:
        class_id = int(payload.get("class_id"))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid class selected."}), 400

    if not isinstance(students_data, list) or not students_data:
        return jsonify({"message": "Invalid student data."}), 400

    if any(not isinstance(student, dict) for student in students_data):
        return jsonify({"message": "Invalid student data."}), 400

    school_id = session["school_id"]
    current_session_id = session["session_id"]

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
    html = render_template('pdf-components/tall_result.html', students=students_data, 
                            attandance_out_of=attandance_out_of, 
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
