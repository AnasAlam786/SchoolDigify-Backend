import math
import re


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

def prepare_marks_format(result):

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