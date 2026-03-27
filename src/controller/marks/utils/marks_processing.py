"""Marks processing utilities built around the new StudentMarks model.

This module exposes a reusable query-builder that can be used across the app to
compose SQLAlchemy queries for marks with a fluent API.

Compatibility wrapper `result_data()` is provided for existing controllers.
"""

# import time
from src import db
from src.model.ClassExams import ClassExams
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.Subjects import Subjects
from src.model.Exams import Exams
from src.model.StudentMarks import StudentMarks

from sqlalchemy import func, case, cast, Float, literal, func
from sqlalchemy.dialects.postgresql import aggregate_order_by
from collections import OrderedDict


def result_data(school_id, session_id, class_id, student_ids=None, extra_fields=None):

    """
    Fetches detailed marks data for students in a class, with optional filtering and extra fields.
    extra_fields:
      - {"StudentsDB": ["DOB", "MOTHERS_NAME"]}
      - {"StudentsDB": {"DOB": "DateOfBirth"}}
      - {"expr": [func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label("FormattedDOB")]}
    """

    # Normalize fields
    normalized = {}
    if extra_fields:
        for table_name, fields in extra_fields.items():
            if isinstance(fields, (list, tuple, set)):
                normalized[table_name] = {f: f for f in fields}  # no rename
            elif isinstance(fields, dict):
                normalized[table_name] = fields  # already mapping
            else:
                raise ValueError("Fields must be list/dict per table")
    else:
        normalized = {}


    # Step A: Get all students in the class (for accurate ranking)
    all_students_subq = (
        db.session.query(StudentSessions.student_id)
        .filter(StudentSessions.session_id == session_id)
        .filter(StudentSessions.class_id == class_id)
        .subquery()
    )

    # Step B: exams for the school
    exams_subq = (
        db.session.query(
            Exams.id.label("exam_id"),
            Exams.exam_code.label("exam_name"),
            Exams.term.label("exam_term"),
            Exams.weightage,
            Exams.display_order.label("exam_display_order")
        )
        .join(ClassExams, ClassExams.exam_id == Exams.id)
        .filter(ClassExams.class_id == class_id,
                Exams.school_id == school_id)
        .distinct()
        .subquery()
    )

    # Step C: subjects for the class
    subjects_subq = (
        db.session.query(
            Subjects.id.label('subject_id'),
            Subjects.subject.label('subject_name'),
            Subjects.evaluation_type,
            Subjects.display_order.label('subject_display_order')
        )
        .filter(Subjects.class_id == class_id)
        .subquery()
    )

    # Create cross join of all students × exams × subjects
    ses = (
        db.session.query(
            all_students_subq.c.student_id,
            exams_subq.c.exam_id,
            exams_subq.c.exam_name,
            exams_subq.c.weightage,
            exams_subq.c.exam_term,
            exams_subq.c.exam_display_order,
            subjects_subq.c.subject_id,
            subjects_subq.c.subject_name,
            subjects_subq.c.evaluation_type,
            subjects_subq.c.subject_display_order
        )
        .select_from(all_students_subq)
        .join(exams_subq, literal(True))
        .join(subjects_subq, literal(True))
        .subquery()
    )

    # LEFT JOIN marks on student + exam + subject
    marks_with_subjects = (
        db.session.query(
            ses.c.student_id,
            ses.c.exam_id,
            ses.c.exam_name,
            ses.c.weightage,
            ses.c.exam_term,
            ses.c.exam_display_order,
            ses.c.subject_id,
            ses.c.subject_name,
            ses.c.evaluation_type,
            ses.c.subject_display_order,
            StudentMarks.score
        )
        .outerjoin(
            StudentMarks,
            (StudentMarks.student_id == ses.c.student_id) &
            (StudentMarks.exam_id == ses.c.exam_id) &
            (StudentMarks.subject_id == ses.c.subject_id)
        )
        .subquery()
    )

    # Step G: Aggregate per student+exam (without rank)
    student_exam_totals = (
        db.session.query(
            marks_with_subjects.c.student_id,
            marks_with_subjects.c.exam_name,
            marks_with_subjects.c.weightage,
            marks_with_subjects.c.exam_term,
            marks_with_subjects.c.exam_display_order,

            func.jsonb_agg(
                aggregate_order_by(
                    func.jsonb_build_object(
                        marks_with_subjects.c.subject_name,
                        func.coalesce(marks_with_subjects.c.score, '')
                    ),
                    marks_with_subjects.c.subject_display_order.asc()
                )
            ).label('subject_marks_dict'),

            func.sum(
                case(
                    (marks_with_subjects.c.evaluation_type == 'numeric',
                     cast(marks_with_subjects.c.score, Float)),
                    else_=0
                )
            ).label('exam_total'),

            (
                func.sum(
                    case(
                        (marks_with_subjects.c.evaluation_type == 'numeric',
                         cast(marks_with_subjects.c.score, Float)),
                        else_=0
                    )
                ) * 100.0
                / func.nullif(
                    marks_with_subjects.c.weightage *
                    func.count(
                        case(
                            (marks_with_subjects.c.evaluation_type == 'numeric', 1)
                        )
                    ),
                    0
                )
            ).label('percentage')
        )
        .group_by(
            marks_with_subjects.c.student_id,
            marks_with_subjects.c.exam_name,
            marks_with_subjects.c.weightage,
            marks_with_subjects.c.exam_term,
            marks_with_subjects.c.exam_display_order
        )
        .subquery()
    )

    # Step H: Calculate grand total and overall rank across ALL students
    student_grand_totals = (
        db.session.query(
            student_exam_totals.c.student_id,
            func.sum(student_exam_totals.c.exam_total).label('grand_total'),
            func.dense_rank().over(
                order_by=func.sum(student_exam_totals.c.exam_total).desc()
            ).label('overall_rank')
        )
        .group_by(student_exam_totals.c.student_id)
        .subquery()
    )



        # Map table name → actual model
    model_map = {
        "StudentsDB": StudentsDB,
        "StudentSessions": StudentSessions,
        "ClassData": ClassData,
        "Exams": Exams,
    }

    # Collect dynamic columns
    dynamic_columns = []
    if extra_fields:
        for table_name, fields in extra_fields.items():
            if table_name == "expr":
                # Allow raw expressions (list of SQLAlchemy expressions)
                for expr in fields:
                    dynamic_columns.append(expr)
                continue

            model = model_map.get(table_name)
            if not model:
                continue

            if isinstance(fields, (list, tuple, set)):
                for f in fields:
                    col = getattr(model, f, None)
                    if col is not None:
                        dynamic_columns.append(col)
            elif isinstance(fields, dict):
                for f, alias in fields.items():
                    col = getattr(model, f, None)
                    if col is not None:
                        dynamic_columns.append(col.label(alias))


    # Step I: Join exam details with grand totals and ranks
    final_query = (
        db.session.query(
            student_exam_totals.c.exam_name,
            student_exam_totals.c.weightage,
            student_exam_totals.c.exam_term,
            student_exam_totals.c.subject_marks_dict,
            student_exam_totals.c.exam_total,
            student_exam_totals.c.percentage,
            student_exam_totals.c.exam_display_order,
            student_grand_totals.c.grand_total,
            student_grand_totals.c.overall_rank,
            
            StudentsDB.id.label('student_id'),

            # Extra dynamic fields
            *dynamic_columns
        )
        .join(student_grand_totals, student_grand_totals.c.student_id == student_exam_totals.c.student_id)
        .join(StudentSessions, StudentSessions.student_id == student_exam_totals.c.student_id)
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
        .filter(StudentSessions.session_id == session_id)
        .filter(StudentSessions.class_id == class_id)
    )

    # Apply student filter if provided (after computing overall ranks)
    if student_ids:
        final_query = final_query.filter(StudentSessions.student_id.in_(student_ids))

    final_query = final_query.order_by(
        student_grand_totals.c.overall_rank,  # Order by overall rank first
        student_exam_totals.c.exam_display_order, 
        StudentSessions.ROLL
    )

    # start_time = time.time()  # start timer

    result = final_query.all()
    # end_time = time.time()  # end timer
    # print(f"request took {end_time - start_time:.6f} seconds to run")

    # Convert to dict with ordered marks
    def result_to_dict(row):
        row_dict = row._asdict()
        mj = row_dict.get("subject_marks_dict")
        if mj:
            ordered_marks = OrderedDict()
            for kv in mj:
                ordered_marks.update(kv)
            row_dict["subject_marks_dict"] = ordered_marks

            # if row_dict["exam_name"] == "Annual Exam":
            #     print(f"Subject Marks for Student {row_dict.get('STUDENTS_NAME')}: {ordered_marks}\n")
        return row_dict

    return [result_to_dict(r) for r in result]