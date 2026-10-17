from src import db

from src.model.ClassExams import ClassExams
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.ClassSubject import ClassSubject
from src.model.Subjects import Subjects
from src.model.Exams import Exams
from src.model.StudentMarks import StudentMarks

from flask import Blueprint, jsonify

del_after_bp = Blueprint('del_after_bp', __name__)


@del_after_bp.route("/api/result-data", methods=["GET"])
def get_result_data():
    data = result_data(
        school_id='falak',
        session_id=2025,
        class_id=4,
        student_session_ids=None,
    )

    return jsonify(data)


def result_data(
    school_id,
    session_id,
    class_id,
    student_session_ids=None,
    extra_fields=None,
):

    # =========================================================
    # 1. GET STUDENTS
    # =========================================================

    student_query = (
        db.session.query(
            StudentSessions,
            StudentsDB,
            ClassData,
        )
        .join(
            StudentsDB,
            StudentsDB.id == StudentSessions.student_id,
        )
        .join(
            ClassData,
            ClassData.id == StudentSessions.class_id,
        )
        .filter(
            StudentSessions.session_id == session_id,
            StudentSessions.class_id == class_id,
        )
    )

    if student_session_ids:
        student_query = student_query.filter(
            StudentSessions.id.in_(student_session_ids)
        )

    student_rows = student_query.all()

    if not student_rows:
        return []


    # =========================================================
    # 2. GET EXAMS
    #
    # Exams.weightage = maximum marks per subject
    # =========================================================

    exam_rows = (
        db.session.query(
            ClassExams.id.label("class_exam_id"),
            Exams.id.label("exam_id"),
            Exams.exam_code,
            Exams.weightage,
            Exams.term,
            Exams.display_order,
        )
        .join(
            Exams,
            Exams.id == ClassExams.exam_id,
        )
        .filter(
            ClassExams.class_id == class_id,
            Exams.school_id == school_id,
        )
        .filter(
            (ClassExams.start_session.is_(None))
            | (ClassExams.start_session <= session_id)
        )
        .filter(
            (ClassExams.end_session.is_(None))
            | (ClassExams.end_session >= session_id)
        )
        .order_by(
            Exams.display_order,
            Exams.id,
        )
        .all()
    )

    if not exam_rows:
        return []


    # =========================================================
    # 3. GET SUBJECTS
    # =========================================================

    subject_rows = (
        db.session.query(
            ClassSubject.id.label("class_subject_id"),
            Subjects.id.label("subject_id"),
            Subjects.subject,
            Subjects.evaluation_type,
            Subjects.display_order,
        )
        .join(
            Subjects,
            Subjects.id == ClassSubject.subject_id,
        )
        .filter(
            ClassSubject.class_id == class_id,
            Subjects.school_id == school_id,
            Subjects.is_active.is_(True),
        )
        .filter(
            (ClassSubject.start_session.is_(None))
            | (ClassSubject.start_session <= session_id)
        )
        .filter(
            (ClassSubject.end_session.is_(None))
            | (ClassSubject.end_session >= session_id)
        )
        .order_by(
            Subjects.display_order,
            Subjects.id,
        )
        .all()
    )

    if not subject_rows:
        return []


    # =========================================================
    # 4. GET ALL MARKS
    # =========================================================

    student_ids = [
        student_session.id
        for student_session, student, class_data in student_rows
    ]

    exam_ids = [
        exam.class_exam_id
        for exam in exam_rows
    ]

    subject_ids = [
        subject.class_subject_id
        for subject in subject_rows
    ]

    mark_rows = (
        db.session.query(StudentMarks)
        .filter(
            StudentMarks.student_session_id.in_(student_ids),
            StudentMarks.exm_id.in_(exam_ids),
            StudentMarks.subject_id.in_(subject_ids),
        )
        .all()
    )


    # =========================================================
    # 5. MAKE MARKS LOOKUP
    # =========================================================

    marks_lookup = {}

    for mark in mark_rows:

        key = (
            mark.student_session_id,
            mark.exm_id,
            mark.subject_id,
        )

        marks_lookup[key] = mark.score


    # =========================================================
    # 6. BUILD EXAM DEFINITIONS
    # =========================================================

    exams = []

    for exam in exam_rows:

        exams.append({
            "id": exam.class_exam_id,
            "exam_id": exam.exam_id,
            "name": exam.exam_code,
            "weightage": float(exam.weightage or 0),
            "term": exam.term,
            "display_order": exam.display_order,
        })


    # =========================================================
    # 7. BUILD STUDENT RESULTS
    # =========================================================

    results = []

    for student_session, student, class_data in student_rows:

        # -----------------------------------------------------
        # Student subjects and marks
        # -----------------------------------------------------

        subjects = []

        for subject in subject_rows:

            marks = {}

            for exam in exam_rows:

                key = (
                    student_session.id,
                    exam.class_exam_id,
                    subject.class_subject_id,
                )

                score = marks_lookup.get(key)

                marks[str(exam.class_exam_id)] = (
                    score if score is not None else ""
                )

            subjects.append({
                "id": subject.class_subject_id,
                "subject_id": subject.subject_id,
                "name": subject.subject,
                "type": subject.evaluation_type,
                "display_order": subject.display_order,
                "marks": marks,
            })


        # -----------------------------------------------------
        # Calculate each exam's total and percentage
        # -----------------------------------------------------

        exam_totals = {}

        grand_total = 0
        grand_max_total = 0

        for exam in exam_rows:

            exam_total = 0
            exam_max_total = (
                float(exam.weightage or 0) * len(subject_rows)
            )

            for subject in subject_rows:

                key = (
                    student_session.id,
                    exam.class_exam_id,
                    subject.class_subject_id,
                )

                score = marks_lookup.get(key)

                if score not in (None, ""):

                    try:
                        exam_total += float(score)
                    except (ValueError, TypeError):
                        pass


            # Exam percentage
            if exam_max_total > 0:
                exam_percentage = (
                    exam_total / exam_max_total
                ) * 100
            else:
                exam_percentage = 0.0


            exam_totals[str(exam.class_exam_id)] = {
                "total": round(exam_total, 2),
                "max_total": round(exam_max_total, 2),
                "percentage": round(exam_percentage, 2),
            }

            grand_total += exam_total
            grand_max_total += exam_max_total


        # -----------------------------------------------------
        # Calculate overall percentage
        # -----------------------------------------------------

        if grand_max_total > 0:
            overall_percentage = (
                grand_total / grand_max_total
            ) * 100
        else:
            overall_percentage = 0.0


        # -----------------------------------------------------
        # Student information
        # -----------------------------------------------------

        student_data = {
            "id": student.id,
            "session_id": student_session.id,
            "name": student.STUDENTS_NAME,
            "roll": student_session.ROLL,
            "class": class_data.CLASS,
        }


        # -----------------------------------------------------
        # Optional extra fields
        # -----------------------------------------------------

        if extra_fields:

            allowed_models = {
                "StudentsDB": student,
                "StudentSessions": student_session,
                "ClassData": class_data,
            }

            for table_name, fields in extra_fields.items():

                source = allowed_models.get(table_name)

                if source is None:
                    continue

                if not isinstance(fields, (list, tuple, set)):
                    continue

                for field in fields:

                    if field in student_data:
                        continue

                    student_data[field] = getattr(
                        source,
                        field,
                        None,
                    )


        # -----------------------------------------------------
        # Final student result
        # -----------------------------------------------------

        results.append({
            "student": student_data,
            "exams": exams,
            "subjects": subjects,
            "exam_totals": exam_totals,
            "summary": {
                "grand_total": round(grand_total, 2),
                "grand_max_total": round(grand_max_total, 2),
                "overall_percentage": round(overall_percentage, 2),
                "rank": None,
            },
        })


    # =========================================================
    # 8. CALCULATE RANK
    #
    # Rank is based on overall percentage.
    # Equal percentages receive the same rank.
    # =========================================================

    sorted_results = sorted(
        results,
        key=lambda result: result["summary"]["overall_percentage"],
        reverse=True,
    )

    previous_percentage = None
    current_rank = 0

    for position, result in enumerate(sorted_results, start=1):

        percentage = result["summary"]["overall_percentage"]

        if percentage != previous_percentage:
            current_rank = position

        result["summary"]["rank"] = current_rank
        previous_percentage = percentage


    # =========================================================
    # 9. RETURN RESULTS
    #
    # Original student order is preserved.
    # =========================================================

    return results