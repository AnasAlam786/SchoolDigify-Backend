# src/controller/marks/fill_marks.py

from flask import session, request, jsonify, Blueprint
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from src import db

from src.model import (
    Exams, StudentSubjects, StudentsDB,
    StudentSessions, ClassData,
    StudentMarks, Subjects, ClassExams,
)

from src.model.ClassAccess import ClassAccess
from src.model.ClassSubject import ClassSubject

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.permissions.has_permission import has_permission


fill_marks_bp = Blueprint(
    "fill_marks_bp",
    __name__
)

# ============================================================
# 2. GET SUBJECTS FOR CLASS
# ============================================================

@fill_marks_bp.route(
    "/api/subjects_and_exams_by_class/<int:class_id>", methods=["GET"]
)
@login_required
@permission_required("fill_marks")
def get_subjects_and_exams_by_class(class_id):

    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]

    try:
        # ----------------------------------------------------
        # Verify teacher has access to this class
        # ----------------------------------------------------

        class_allowed = (
            db.session.query(ClassData.id)
            .join(
                ClassAccess, ClassAccess.class_id == ClassData.id
            ).filter(
                ClassData.id == class_id,
                ClassData.school_id == school_id,
                ClassAccess.staff_id == user_id
            ).first()
        )

        if not class_allowed:
            return jsonify({
                "success": False,
                "error": "You do not have access to this class."
            }), 403

        subjects = (
            db.session.query(
                ClassSubject.id.label("class_subject_id"),
                Subjects.subject.label("subject_name")
            ).join(
                Subjects,
                Subjects.id == ClassSubject.subject_id
            ).filter(
                ClassSubject.class_id == class_id,
                Subjects.school_id == school_id,
                Subjects.is_active.is_(True),
                (
                    (ClassSubject.start_session.is_(None)) |
                    (ClassSubject.start_session <= current_session_id)
                ),
                (
                    (ClassSubject.end_session.is_(None)) |
                    (ClassSubject.end_session >= current_session_id)
                )
            ).order_by(
                Subjects.display_order.asc()
            ).all()
        )

        exams = (
            db.session.query(
                ClassExams.id.label("class_exam_id"),
                Exams.exam_name,
                Exams.is_enabled,
                Exams.weightage,
                Exams.term,
                Exams.display_order,
            )
            .join(
                Exams,
                Exams.id == ClassExams.exam_id
            )
            .filter(
                ClassExams.class_id == class_id,
                Exams.school_id == school_id,
                (
                    (ClassExams.start_session.is_(None)) |
                    (ClassExams.start_session <= current_session_id)
                ),
                (
                    (ClassExams.end_session.is_(None)) |
                    (ClassExams.end_session >= current_session_id)
                )
            )
            .order_by(
                Exams.display_order.asc(),
                ClassExams.id.asc()
            )
            .all()
        )

        if not subjects or not exams:
            errors = []

            if not subjects:
                errors.append("No subjects found for this class.")

            if not exams:
                errors.append("No exams found for this class.")

            return jsonify({
                "success": False, "error": " ".join(errors)
            }), 404

        
        # IMPORTANT:
        # frontend "subject_id" receives ClassSubject.id
        return jsonify({
            "subjects": [
                {
                    "id": row.class_subject_id,
                    "subjectName": row.subject_name,
                }
                for row in subjects
            ],
            "exams": [
                {
                    "id": row.class_exam_id,
                    "exam_name": row.exam_name,
                    "is_enabled": row.is_enabled,
                    "weightage": row.weightage,
                    "term": row.term,
                    "display_order": row.display_order,
                }
                for row in exams
            ],
        })

    except Exception as e:
        db.session.rollback()
        print(f"get_subjects_by_class error: {e}")
        return jsonify({
            "success": False, "error": "Failed to fetch subjects."
        }), 500


@fill_marks_bp.route("/api/get_marks", methods=["GET"])
@login_required
@permission_required("fill_marks")
def get_marks():

    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]

    class_id = request.args.get("class_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    exam_id = request.args.get("exam_id", type=int)

    # --------------------------------------------------------
    # Required parameters
    # --------------------------------------------------------

    if class_id is None or subject_id is None or exam_id is None:
        return jsonify({
            "success": False,
            "error": "Class, Subject and Exam are required."
        }), 400

    try:

        # ----------------------------------------------------
        # Verify teacher access to class
        # ----------------------------------------------------

        class_allowed = (
            db.session.query(ClassData.id)
            .join(
                ClassAccess,
                ClassAccess.class_id == ClassData.id
            )
            .filter(
                ClassData.id == class_id,
                ClassData.school_id == school_id,
                ClassAccess.staff_id == user_id
            )
            .first()
        )

        if not class_allowed:
            return jsonify({
                "success": False,
                "error": "You do not have access to this class."
            }), 403

        # ----------------------------------------------------
        # Verify ClassSubject
        # ----------------------------------------------------

        class_subject = (
            db.session.query(
                ClassSubject.id.label("class_subject_id"),
                ClassSubject.is_optional,
                Subjects.id.label("subject_db_id"),
                Subjects.subject,
                Subjects.evaluation_type,
                Subjects.max_marks,
            )
            .join(
                Subjects,
                Subjects.id == ClassSubject.subject_id
            )
            .filter(
                ClassSubject.id == subject_id,
                ClassSubject.class_id == class_id,

                Subjects.school_id == school_id,
                Subjects.is_active.is_(True),

                (
                    (ClassSubject.start_session.is_(None))
                    |
                    (ClassSubject.start_session <= current_session_id)
                ),

                (
                    (ClassSubject.end_session.is_(None))
                    |
                    (ClassSubject.end_session >= current_session_id)
                )
            )
            .first()
        )

        if not class_subject:
            return jsonify({
                "success": False,
                "error": "Subject not found."
            }), 404

        # ----------------------------------------------------
        # Verify exam as ClassExams record for this class
        # ----------------------------------------------------

        class_exam = (
            db.session.query(
                ClassExams.id.label("class_exam_id"),
                Exams.id.label("exam_db_id"),
                Exams.exam_name,
                Exams.weightage,
                Exams.is_enabled,
            )
            .join(
                Exams,
                Exams.id == ClassExams.exam_id
            )
            .filter(
                ClassExams.id == exam_id,
                ClassExams.class_id == class_id,

                Exams.school_id == school_id,

                (
                    (ClassExams.start_session.is_(None))
                    |
                    (ClassExams.start_session <= current_session_id)
                ),

                (
                    (ClassExams.end_session.is_(None))
                    |
                    (ClassExams.end_session >= current_session_id)
                )
            )
            .first()
        )

        if not class_exam:
            return jsonify({
                "success": False,
                "error": "This exam is not assigned to this class."
            }), 404

        # ----------------------------------------------------
        # Exam lock
        # ----------------------------------------------------

        if (
            not class_exam.is_enabled
            and not has_permission("override_marks_lock")
        ):
            return jsonify({
                "success": False,
                "error": (
                    "This exam is locked. "
                    "You do not have permission to fill marks."
                )
            }), 403

        # ----------------------------------------------------
        # Students + marks
        # ----------------------------------------------------

        marks_query = (
            db.session.query(
                StudentSessions.id.label("student_session_id"),
                StudentsDB.STUDENTS_NAME,
                StudentsDB.GENDER,
                StudentSessions.ROLL,
                ClassData.CLASS.label("class_name"),
                StudentMarks.id.label("mark_id"),
                StudentMarks.score,
            )
            .join(
                StudentSessions,
                StudentSessions.student_id == StudentsDB.id
            )
            .join(
                ClassData,
                StudentSessions.class_id == ClassData.id
            )

            # IMPORTANT:
            # LEFT JOIN because compulsory subjects do not
            # need a StudentSubjects row.
            .outerjoin(
                StudentSubjects,
                and_(
                    StudentSubjects.student_session_id ==
                    StudentSessions.id,

                    StudentSubjects.class_subject_id ==
                    class_subject.class_subject_id
                )
            )

            .outerjoin(
                StudentMarks,
                and_(
                    StudentMarks.student_session_id ==
                    StudentSessions.id,

                    StudentMarks.exm_id ==
                    class_exam.class_exam_id,

                    StudentMarks.subject_id ==
                    class_subject.class_subject_id
                )
            )
            .filter(
                StudentsDB.school_id == school_id,

                StudentSessions.class_id == class_id,

                StudentSessions.session_id == current_session_id,
            )
        )

        # ----------------------------------------------------
        # Optional subject
        # ----------------------------------------------------
        #
        # class_subject.is_optional is now a Python bool
        # because class_subject came from .first().
        #
        # Therefore DO NOT do:
        #
        # class_subject.is_optional.is_(False)
        #
        # Instead, decide here in Python.
        # ----------------------------------------------------

        if class_subject.is_optional:

            # Optional subject:
            # only students who selected this subject
            # should appear.

            marks_query = marks_query.filter(
                StudentSubjects.id.isnot(None)
            )

        # ----------------------------------------------------
        # Get students
        # ----------------------------------------------------

        marks_data = (
            marks_query
            .order_by(StudentSessions.ROLL.asc())
            .all()
        )

        students = [
            dict(row._mapping)
            for row in marks_data
        ]

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return jsonify({
            "success": True,
            "exam": {
                "id": class_exam.class_exam_id,
                "exam_id": class_exam.exam_db_id,
                "name": class_exam.exam_name,
                "weightage": class_exam.weightage,
                "is_enabled": class_exam.is_enabled,
            },
            "subject": {
                "id": class_subject.class_subject_id,
                "is_optional": class_subject.is_optional,
                "subject_id": class_subject.subject_db_id,
                "name": class_subject.subject,
                "evaluation_type": class_subject.evaluation_type,
                "max_marks": class_subject.max_marks,
            },
            "students": students,
        })

    except Exception as e:
        db.session.rollback()

        print(f"get_marks error: {e}")

        return jsonify({
            "success": False,
            "error": "Failed to fetch marks."
        }), 500

# ============================================================
# 4. UPDATE / INSERT MARKS
# ============================================================

@fill_marks_bp.route("/update_marks_api", methods=["POST"])
@login_required
@permission_required("fill_marks")
def update_marks_api():
    try:
        data = request.get_json() or {}

        marks_id = data.get("marks_id", data.get("mark_id"))
        score = data.get("score")

        student_session_id = data.get("student_session_id")
        class_subject_id = data.get("subject_id")
        exam_id = data.get("exam_id")
        school_id = session.get("school_id")
        current_session_id = session.get("session_id")
        user_id = session.get("user_id")

        if not all([class_subject_id, exam_id, student_session_id]):
            return jsonify({"message": "Missing required fields"}), 400

        # ----------------------------------------------------
        # Validate score
        # ----------------------------------------------------
        if score in [None, ""]:
            score = None
        else:
            try:
                numeric_score = float(score)
                if numeric_score.is_integer():
                    score = int(numeric_score)
                else:
                    score = numeric_score
            except (ValueError, TypeError):
                score = str(score).strip() if str(score).strip() else None

        # ----------------------------------------------------
        # Verify student enrollment
        # ----------------------------------------------------
        student_session = (
            StudentSessions.query
            .filter(
                StudentSessions.id == student_session_id,
                StudentSessions.session_id == current_session_id,
            )
            .first()
        )

        if not student_session:
            return jsonify({
                "success": False,
                "message": "Student session not found."
            }), 404


        student_class_id = student_session.class_id

        # ----------------------------------------------------
        # Verify teacher access to student's class
        # ----------------------------------------------------
        class_allowed = (
            db.session.query(ClassData.id)
            .join(
                ClassAccess, ClassAccess.class_id == ClassData.id
            ).filter(
                ClassData.id == student_class_id,
                ClassData.school_id == school_id,
                ClassAccess.staff_id == user_id
            ).first()
        )

        if not class_allowed:
            return jsonify({
                "success": False,
                "message": "You do not have access to this class."
            }), 403

        # ----------------------------------------------------
        # Verify ClassSubject
        # ----------------------------------------------------
        class_subject = (
            db.session.query(
                ClassSubject.id,
                ClassSubject.subject_id,
                ClassSubject.is_optional,
                Subjects.evaluation_type,
                Subjects.max_marks,
            )
            .join(
                Subjects, Subjects.id == ClassSubject.subject_id
            )
            .filter(
                ClassSubject.id == class_subject_id,
                ClassSubject.class_id == student_class_id,
                Subjects.school_id == school_id,
                Subjects.is_active.is_(True),
                (
                    (ClassSubject.start_session.is_(None)) |
                    (ClassSubject.start_session <= current_session_id)
                ),
                (
                    (ClassSubject.end_session.is_(None)) |
                    (ClassSubject.end_session >= current_session_id)
                )
            )
            .first()
        )

        if not class_subject:
            return jsonify({
                "success": False,
                "message": "Subject not found."
            }), 404

        # ----------------------------------------------------
        # Verify student is allowed to take this subject
        # ----------------------------------------------------
        if class_subject.is_optional:

            selected = (
                StudentSubjects.query
                .filter(
                    StudentSubjects.student_session_id == student_session_id,
                    StudentSubjects.class_subject_id == class_subject.id,
                )
                .first()
            )

            if not selected:
                return jsonify({
                    "success": False,
                    "message": "Student has not selected this optional subject."
                }), 400

        # ----------------------------------------------------
        # Verify exam
        # ----------------------------------------------------
        class_exam = (
            db.session.query(
                ClassExams.id.label("class_exam_id"),
                Exams.id.label("exam_db_id"),
                Exams.exam_name,
                Exams.weightage,
                Exams.is_enabled,
            )
            .join(
                Exams,
                Exams.id == ClassExams.exam_id
            )
            .filter(
                ClassExams.id == exam_id,
                ClassExams.class_id == student_class_id,
                Exams.school_id == school_id,
                (
                    (ClassExams.start_session.is_(None))
                    | (ClassExams.start_session <= current_session_id)
                ),
                (
                    (ClassExams.end_session.is_(None))
                    | (ClassExams.end_session >= current_session_id)
                )
            )
            .first()
        )

        if not class_exam:
            return jsonify({
                "success": False,
                "message": "This exam is not assigned to student's class."
            }), 400

        if not class_exam.is_enabled and not has_permission("override_marks_lock"):
            return jsonify({
                "success": False,
                "message": (
                    "This exam is disabled. "
                    "You do not have permission to fill marks."
                )
            }), 403

        # ----------------------------------------------------
        # Score range
        # ----------------------------------------------------
        if score is not None and isinstance(score, (int, float)):
            if class_exam.weightage is not None and (
                score < 0 or score > float(class_exam.weightage)
            ):
                return jsonify({
                    "success": False,
                    "message": (
                        f"Score must be between 0 and {class_exam.weightage}"
                    )
                }), 400

        # ====================================================
        # CASE 1: Update using marks_id
        # ====================================================
        if marks_id is not None:
            student_marks = (
                StudentMarks.query
                .filter(
                    StudentMarks.id == marks_id,
                    StudentMarks.student_session_id == student_session_id,
                    StudentMarks.subject_id == class_subject_id,
                    StudentMarks.exm_id == exam_id,
                )
                .first()
            )

            if not student_marks:
                return jsonify({
                    "success": False,
                    "message": "Marks record not found."
                }), 404

            student_marks.score = score
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Marks updated successfully.",
                "mark_id": student_marks.id,
                "score": student_marks.score,
            }), 200

        # ====================================================
        # CASE 2: Find existing mark
        # ====================================================
        existing = (
            StudentMarks.query
            .filter(
                StudentMarks.student_session_id == student_session_id,
                StudentMarks.subject_id == class_subject_id,
                StudentMarks.exm_id == exam_id,
            )
            .first()
        )
        if existing:
            existing.score = score
            db.session.commit()
            return jsonify({
                "success": True,
                "message": "Marks updated successfully.",
                "mark_id": existing.id,
                "score": existing.score,
            }), 200

        # ====================================================
        # CASE 3: Create new mark
        # ====================================================
        new_mark = StudentMarks(
            student_session_id=student_session_id,
            subject_id=class_subject_id,
            exm_id=exam_id,
            score=score,
        )
        db.session.add(new_mark)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Marks inserted successfully.",
            "mark_id": new_mark.id,
            "score": new_mark.score,
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": (
                "Duplicate marks record exists "
                "for this student, subject and exam."
            )
        }), 409

    except Exception as e:
        db.session.rollback()
        print(f"update_marks_api error: {e}")
        return jsonify({
            "success": False,
            "message": "Internal server error."
        }), 500


# ============================================================
# 5. GET ALL EXAMS
# ============================================================

@fill_marks_bp.route("/api/get_all_exams",methods=["GET"])
@login_required
@permission_required("lock_marks")
def get_all_exams():
    school_id = session["school_id"]

    try:
        exams = (
            Exams.query
            .filter( Exams.school_id == school_id)
            .order_by( Exams.display_order.asc())
            .all()
        )

        return jsonify([
            {
                "id": exam.id,
                "exam_name": exam.exam_name,
                "is_enabled": exam.is_enabled
            } for exam in exams
        ])

    except Exception as e:
        db.session.rollback()
        print(f"get_all_exams error: {e}")
        return jsonify({
            "success": False, "error": "Failed to fetch exams."
        }), 500


# ============================================================
# 6. UPDATE EXAM STATUS
# ============================================================

@fill_marks_bp.route("/update_exam_status",methods=["POST"])
@login_required
@permission_required("lock_marks")
def update_exam_status():
    try:
        data = request.get_json() or {}
        exam_id = data.get("exam_id")
        is_enabled = data.get("is_enabled")

        # ----------------------------------------------------
        # Validate input
        # ----------------------------------------------------

        if exam_id is None or is_enabled is None:
            return jsonify({
                "success": False, "error": "Exam ID and status are required."
            }), 400
        
        try:
            exam_id = int(exam_id)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Invalid exam ID."
            }), 400

        # ----------------------------------------------------
        # Convert boolean
        # ----------------------------------------------------

        if isinstance(is_enabled, bool):
            enabled_value = is_enabled

        elif isinstance(is_enabled, str):
            value = is_enabled.strip().lower()
            if value in ("true", "1", "yes", "on"):
                enabled_value = True

            elif value in ("false","0","no","off"):
                enabled_value = False

            else:
                return jsonify({
                    "success": False,"error": "Invalid status value."
                }), 400

        elif isinstance(is_enabled, int):
            if is_enabled not in (0, 1):
                return jsonify({
                    "success": False, "error": "Invalid status value."
                }), 400
            enabled_value = bool(is_enabled)

        else:
            return jsonify({
                "success": False, "error": "Invalid status value."
            }), 400

        # ----------------------------------------------------
        # Find exam belonging to this school
        # ----------------------------------------------------
        exam = (
            Exams.query
            .filter(
                Exams.id == exam_id, Exams.school_id == session["school_id"]
            ).first()
        )

        if not exam:
            return jsonify({
                "success": False, "error": "Exam not found."
            }), 404
        
        # ----------------------------------------------------
        # Update
        # ----------------------------------------------------
        exam.is_enabled = enabled_value
        db.session.commit()

        return jsonify({
            "success": True, "message": "Updated successfully.",
            "exam_id": exam.id, "is_enabled": exam.is_enabled
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"update_exam_status error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to update exam status."
        }), 500