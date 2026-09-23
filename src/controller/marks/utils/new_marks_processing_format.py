from src import db

from src.model.ClassExams import ClassExams
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.ClassSubject import ClassSubject
from src.model.Subjects import Subjects
from src.model.Exams import Exams
from src.model.StudentMarks import StudentMarks


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
    # IMPORTANT:
    # display_order controls the sequence.
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
    #
    # IMPORTANT:
    # display_order controls the sequence.
    # =========================================================

    subject_rows = (
        db.session.query(
            ClassSubject.id.label("class_subject_id"),
            Subjects.id.label("subject_id"),
            Subjects.subject,
            Subjects.max_marks,
            Subjects.pass_marks,
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
    # 4. IDs FOR MARKS QUERY
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


    # =========================================================
    # 5. GET ALL MARKS
    # =========================================================

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
    # 6. MAKE MARKS LOOKUP
    #
    # (student_session_id, exam_id, subject_id)
    #                     ↓
    #                   score
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
    # 7. BUILD EXAM DEFINITIONS ONCE
    #
    # This order is exactly the order returned by
    # .order_by(Exams.display_order)
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
    # 8. BUILD RESULT
    # =========================================================

    results = []

    for student_session, student, class_data in student_rows:

        # -----------------------------------------------------
        # Student's subjects
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

                # Use string exam ID as JSON key
                marks[str(exam.class_exam_id)] = (
                    score if score is not None else ""
                )

            subjects.append({
                "id": subject.class_subject_id,
                "subject_id": subject.subject_id,
                "name": subject.subject,
                "type": subject.evaluation_type,
                "max_marks": subject.max_marks,
                "pass_marks": subject.pass_marks,
                "display_order": subject.display_order,
                "marks": marks,
            })


        # -----------------------------------------------------
        # Calculate exam totals
        # -----------------------------------------------------

        exam_totals = {}

        grand_total = 0

        for exam in exam_rows:

            exam_total = 0
            max_total = 0

            for subject in subject_rows:

                key = (
                    student_session.id,
                    exam.class_exam_id,
                    subject.class_subject_id,
                )

                score = marks_lookup.get(key)

                # -----------------------------
                # Score
                # -----------------------------

                if score not in (None, ""):

                    try:
                        exam_total += float(score)
                    except (ValueError, TypeError):
                        pass

                # -----------------------------
                # Maximum marks
                # -----------------------------

                if subject.max_marks is not None:

                    try:
                        max_total += float(
                            subject.max_marks
                        )
                    except (ValueError, TypeError):
                        pass


            # -----------------------------
            # Percentage
            # -----------------------------

            if max_total:
                percentage = (
                    exam_total / max_total
                ) * 100
            else:
                percentage = 0.0


            exam_totals[str(exam.class_exam_id)] = {
                "total": exam_total,
                "max_total": max_total,
                "percentage": round(
                    percentage,
                    2,
                ),
            }

            grand_total += exam_total


        # -----------------------------------------------------
        # Student object
        # -----------------------------------------------------

        student_data = {
            "id": student.id,
            "session_id": student_session.id,
            "name": student.STUDENTS_NAME,
            "roll": student_session.ROLL,
            "class": class_data.CLASS,
        }


        # -----------------------------------------------------
        # Extra fields
        # -----------------------------------------------------

        if extra_fields:

            allowed_models = {
                "StudentsDB": StudentsDB,
                "StudentSessions": StudentSessions,
                "ClassData": ClassData,
            }

            sources = {
                "StudentsDB": student,
                "StudentSessions": student_session,
                "ClassData": class_data,
            }

            for table_name, fields in extra_fields.items():

                model = allowed_models.get(table_name)

                if model is None:
                    continue

                if not isinstance(
                    fields,
                    (list, tuple, set),
                ):
                    continue

                source = sources.get(table_name)

                if source is None:
                    continue

                for field in fields:

                    if field in student_data:
                        continue

                    value = getattr(
                        source,
                        field,
                        None,
                    )

                    student_data[field] = value


        # -----------------------------------------------------
        # Final student result
        # -----------------------------------------------------

        results.append({
            "student": student_data,

            # Already ordered
            "exams": exams,

            # Already ordered
            "subjects": subjects,

            "exam_totals": exam_totals,

            "summary": {
                "grand_total": grand_total,
                "rank": None,
            },
        })


    # =========================================================
    # 9. CALCULATE RANK
    # =========================================================

    student_totals = []

    for index, result in enumerate(results):

        total = result["summary"]["grand_total"]

        student_totals.append({
            "index": index,
            "total": total,
        })


    # Highest total first
    sorted_totals = sorted(
        student_totals,
        key=lambda x: x["total"],
        reverse=True,
    )


    # ---------------------------------------------------------
    # Assign ranking
    # ---------------------------------------------------------

    rank_lookup = {}

    previous_total = None
    current_rank = 0

    for position, item in enumerate(
        sorted_totals,
        start=1,
    ):

        total = item["total"]

        if total != previous_total:
            current_rank = position

        rank_lookup[item["index"]] = current_rank

        previous_total = total


    # =========================================================
    # 10. PUT RANK INTO ORIGINAL RESULT
    #
    # IMPORTANT:
    # We DO NOT sort results here.
    #
    # Therefore the student order from the database is preserved.
    # =========================================================

    for index, result in enumerate(results):

        result["summary"]["rank"] = rank_lookup[index]


    # =========================================================
    # 11. RETURN
    # =========================================================

    return results