"""Marks processing utilities built around the normalized
StudentMarks + ClassSubject + Subjects architecture.

Compatibility wrapper `result_data()` is provided for existing controllers.

IMPORTANT:
    StudentMarks.subject_id is intentionally ignored.
    StudentMarks.sub_id is the authoritative relationship.
"""

from src import db
from src.model.ClassExams import ClassExams
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.ClassSubject import ClassSubject
from src.model.Subjects import Subjects
from src.model.Exams import Exams
from src.model.StudentMarks import StudentMarks

from sqlalchemy import func, case, cast, Float, literal
from sqlalchemy.dialects.postgresql import aggregate_order_by
from collections import OrderedDict


def result_data(school_id, session_id, class_id, student_ids=None, extra_fields=None):

    """
    Fetch detailed marks data for students in a class.

    Subject relationship:

        ClassSubject.id
              ↓
        StudentMarks.sub_id

    Subjects table contains the subject definition.
    ClassSubject contains the class-specific subject assignment.
    """

    # --------------------------------------------------
    # Normalize extra fields
    # --------------------------------------------------

    normalized = {}

    if extra_fields:
        for table_name, fields in extra_fields.items():

            if isinstance(fields, (list, tuple, set)):
                normalized[table_name] = {
                    f: f for f in fields
                }

            elif isinstance(fields, dict):
                normalized[table_name] = fields

            else:
                raise ValueError(
                    "Fields must be list/dict per table"
                )

    # --------------------------------------------------
    # Step A: Students belonging to this class/session
    # --------------------------------------------------

    all_students_subq = (
        db.session.query(
            StudentSessions.student_id
        )
        .filter(
            StudentSessions.session_id == session_id,
            StudentSessions.class_id == class_id
        )
        .subquery()
    )

    # --------------------------------------------------
    # Step B: Exams assigned to this class
    # --------------------------------------------------

    exams_subq = (
        db.session.query(
            Exams.id.label("exam_id"),
            Exams.exam_code.label("exam_name"),
            Exams.term.label("exam_term"),
            Exams.weightage,
            Exams.display_order.label("exam_display_order")
        )
        .join(
            ClassExams,
            ClassExams.exam_id == Exams.id
        )
        .filter(
            ClassExams.class_id == class_id,
            Exams.school_id == school_id
        )
        .distinct()
        .subquery()
    )

    # --------------------------------------------------
    # Step C: Subjects assigned to this class
    #
    # IMPORTANT:
    # ClassSubject.id is the subject identifier used
    # by StudentMarks.sub_id.
    # --------------------------------------------------

    subjects_subq = (
        db.session.query(
            ClassSubject.id.label("sub_id"),

            Subjects.id.label("subject_id"),

            Subjects.subject.label("subject_name"),

            Subjects.evaluation_type,

            Subjects.display_order.label(
                "subject_display_order"
            )
        )
        .join(
            Subjects,
            Subjects.id == ClassSubject.subject_id
        )
        .filter(
            # Correct class relationship
            ClassSubject.class_id == class_id,

            # Subject belongs to this school
            Subjects.school_id == school_id,

            # Only active subjects
            Subjects.is_active.is_(True),

            # ClassSubject valid for current session
            (
                (ClassSubject.start_session.is_(None)) |
                (ClassSubject.start_session <= session_id)
            ),

            (
                (ClassSubject.end_session.is_(None)) |
                (ClassSubject.end_session >= session_id)
            )
        )
        .subquery()
    )

    # --------------------------------------------------
    # Step D: Students × Exams × Subjects
    # --------------------------------------------------

    ses = (
        db.session.query(
            all_students_subq.c.student_id,

            exams_subq.c.exam_id,
            exams_subq.c.exam_name,
            exams_subq.c.weightage,
            exams_subq.c.exam_term,
            exams_subq.c.exam_display_order,

            subjects_subq.c.sub_id,
            subjects_subq.c.subject_id,
            subjects_subq.c.subject_name,
            subjects_subq.c.evaluation_type,
            subjects_subq.c.subject_display_order
        )
        .select_from(all_students_subq)

        .join(
            exams_subq,
            literal(True)
        )

        .join(
            subjects_subq,
            literal(True)
        )

        .subquery()
    )

    # --------------------------------------------------
    # Step E: Attach marks
    #
    # IMPORTANT:
    # NEVER use StudentMarks.subject_id here.
    #
    # StudentMarks.sub_id -> ClassSubject.id
    # --------------------------------------------------

    marks_with_subjects = (
        db.session.query(
            ses.c.student_id,

            ses.c.exam_id,
            ses.c.exam_name,
            ses.c.weightage,
            ses.c.exam_term,
            ses.c.exam_display_order,

            ses.c.sub_id,
            ses.c.subject_id,
            ses.c.subject_name,
            ses.c.evaluation_type,
            ses.c.subject_display_order,

            StudentMarks.score
        )
        .outerjoin(
            StudentMarks,
            (
                (StudentMarks.student_id == ses.c.student_id) &
                (StudentMarks.exam_id == ses.c.exam_id) &
                (StudentMarks.sub_id == ses.c.sub_id) &
                (StudentMarks.session_id == session_id) &
                (StudentMarks.school_id == school_id)
            )
        )
        .subquery()
    )

    # --------------------------------------------------
    # Step F: Aggregate marks per student + exam
    # --------------------------------------------------

    student_exam_totals = (
        db.session.query(
            marks_with_subjects.c.student_id,

            marks_with_subjects.c.exam_name,
            marks_with_subjects.c.weightage,
            marks_with_subjects.c.exam_term,
            marks_with_subjects.c.exam_display_order,

            # ------------------------------------------
            # Subject marks
            # ------------------------------------------

            func.jsonb_agg(
                aggregate_order_by(
                    func.jsonb_build_object(
                        marks_with_subjects.c.subject_name,
                        func.coalesce(
                            marks_with_subjects.c.score,
                            ''
                        )
                    ),
                    marks_with_subjects.c.subject_display_order.asc()
                )
            ).label("subject_marks_dict"),

            # ------------------------------------------
            # Exam total
            # ------------------------------------------

            func.sum(
                case(
                    (
                        marks_with_subjects.c.evaluation_type == "numeric",
                        cast(
                            marks_with_subjects.c.score,
                            Float
                        )
                    ),
                    else_=0
                )
            ).label("exam_total"),

            # ------------------------------------------
            # Percentage
            # ------------------------------------------

            (
                func.sum(
                    case(
                        (
                            marks_with_subjects.c.evaluation_type == "numeric",
                            cast(
                                marks_with_subjects.c.score,
                                Float
                            )
                        ),
                        else_=0
                    )
                )
                * 100.0
                /
                func.nullif(
                    marks_with_subjects.c.weightage
                    *
                    func.count(
                        case(
                            (
                                marks_with_subjects.c.evaluation_type
                                == "numeric",
                                1
                            )
                        )
                    ),
                    0
                )
            ).label("percentage")
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

    # --------------------------------------------------
    # Step G: Grand total + overall rank
    # --------------------------------------------------

    student_grand_totals = (
        db.session.query(
            student_exam_totals.c.student_id,

            func.sum(
                student_exam_totals.c.exam_total
            ).label("grand_total"),

            func.dense_rank().over(
                order_by=func.sum(
                    student_exam_totals.c.exam_total
                ).desc()
            ).label("overall_rank")
        )
        .group_by(
            student_exam_totals.c.student_id
        )
        .subquery()
    )

    # --------------------------------------------------
    # Step H: Dynamic fields
    # --------------------------------------------------

    model_map = {
        "StudentsDB": StudentsDB,
        "StudentSessions": StudentSessions,
        "ClassData": ClassData,
        "Exams": Exams,
    }

    dynamic_columns = []

    if extra_fields:

        for table_name, fields in extra_fields.items():

            # Raw SQLAlchemy expressions
            if table_name == "expr":

                for expr in fields:
                    dynamic_columns.append(expr)

                continue

            model = model_map.get(table_name)

            if not model:
                continue

            if isinstance(
                fields,
                (list, tuple, set)
            ):

                for field in fields:

                    column = getattr(
                        model,
                        field,
                        None
                    )

                    if column is not None:
                        dynamic_columns.append(column)

            elif isinstance(fields, dict):

                for field, alias in fields.items():

                    column = getattr(
                        model,
                        field,
                        None
                    )

                    if column is not None:
                        dynamic_columns.append(
                            column.label(alias)
                        )

    # --------------------------------------------------
    # Step I: Final query
    # --------------------------------------------------

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

            StudentsDB.id.label("student_id"),

            *dynamic_columns
        )

        .join(
            student_grand_totals,
            student_grand_totals.c.student_id
            == student_exam_totals.c.student_id
        )

        .join(
            StudentSessions,
            StudentSessions.student_id
            == student_exam_totals.c.student_id
        )

        .join(
            StudentsDB,
            StudentsDB.id
            == StudentSessions.student_id
        )

        .join(
            ClassData,
            ClassData.id
            == StudentSessions.class_id
        )

        .filter(
            StudentSessions.session_id == session_id
        )

        .filter(
            StudentSessions.class_id == class_id
        )
    )

    # --------------------------------------------------
    # Student filter
    #
    # Applied AFTER grand totals/ranking so ranking
    # remains based on the complete class.
    # --------------------------------------------------

    if student_ids:
        final_query = final_query.filter(
            StudentSessions.student_id.in_(student_ids)
        )

    # --------------------------------------------------
    # Ordering
    # --------------------------------------------------

    final_query = final_query.order_by(
        student_grand_totals.c.overall_rank,
        student_exam_totals.c.exam_display_order,
        StudentSessions.ROLL
    )

    # --------------------------------------------------
    # Execute
    # --------------------------------------------------

    result = final_query.all()

    # --------------------------------------------------
    # Convert JSON marks to OrderedDict
    # --------------------------------------------------

    def result_to_dict(row):

        row_dict = row._asdict()

        marks = row_dict.get(
            "subject_marks_dict"
        )

        if marks:

            ordered_marks = OrderedDict()

            for item in marks:
                ordered_marks.update(item)

            row_dict[
                "subject_marks_dict"
            ] = ordered_marks

        return row_dict

    return [
        result_to_dict(row)
        for row in result
    ]
