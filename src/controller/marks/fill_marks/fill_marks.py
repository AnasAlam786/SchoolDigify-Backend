# src/controller/marks/fill_marks.py

from flask import session, request, jsonify, Blueprint
from sqlalchemy.exc import IntegrityError

from src import db

from src.model import (
    Exams,
    StudentsDB,
    StudentSessions,
    ClassData,
    StudentMarks,
    Subjects,
    ClassExams,
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
# 1. FETCH CLASSES AND EXAMS
# ============================================================

@fill_marks_bp.route(
    "/api/fetchClassesAndExams",
    methods=["GET"]
)
@login_required
@permission_required("fill_marks")
def fetchClassesAndExams():

    school_id = session["school_id"]
    user_id = session["user_id"]

    try:
        # ----------------------------------------------------
        # Classes accessible to this teacher
        # ----------------------------------------------------

        classes = (
            db.session.query(
                ClassData.id, ClassData.CLASS
            ).join(
                ClassAccess,
                ClassAccess.class_id == ClassData.id
            ).filter(
                ClassAccess.staff_id == user_id,
                ClassData.school_id == school_id
            ).order_by(
                ClassData.id.asc()
            ).all()
        )

        class_ids = [ row.id for row in classes]

        # ----------------------------------------------------
        # Exams assigned to those classes
        # ----------------------------------------------------

        exams = []
        if class_ids:
            exams = (
                db.session.query(
                    Exams.id, Exams.exam_name,
                    Exams.is_enabled, Exams.display_order
                ).join(
                    ClassExams,
                    ClassExams.exam_id == Exams.id
                ).filter(
                    ClassExams.class_id.in_(class_ids),
                    Exams.school_id == school_id
                ).distinct()
                .order_by(
                    Exams.display_order.asc()
                ).all()
            )

        return jsonify({
            "classes": [
                {
                    "id": row.id,
                    "className": row.CLASS
                } for row in classes
            ],

            "exams": [
                {
                    "id": row.id,
                    "exam_name": row.exam_name,
                    "is_enabled": row.is_enabled
                } for row in exams
            ]
        })

    except Exception as e:
        db.session.rollback()
        print(f"fetchClassesAndExams error: {e}")

        return jsonify({
            "success": False, "error": "Failed to fetch classes and exams."
        }), 500


# ============================================================
# 2. GET SUBJECTS FOR CLASS
# ============================================================

@fill_marks_bp.route(
    "/api/subjects/<int:class_id>",
    methods=["GET"]
)
@login_required
@permission_required("fill_marks")
def get_subjects_by_class(class_id):

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

        # ----------------------------------------------------
        # ClassSubject is the authoritative relationship
        # ----------------------------------------------------

        subjects = (
            db.session.query(
                ClassSubject.id.label("cls_sub_id"), Subjects.subject.label("subject_name")
            ).join(
                Subjects,
                Subjects.id == ClassSubject.subject_id
            ).filter(
                ClassSubject.class_id == class_id,
                Subjects.school_id == school_id,
                Subjects.is_active.is_(True),
                (
                    (ClassSubject.start_session.is_(None)) |
                    (
                        ClassSubject.start_session <= current_session_id
                    )
                ),
                (
                    (ClassSubject.end_session.is_(None)) |
                    (
                        ClassSubject.end_session >= current_session_id
                    )
                )
            ).order_by(
                Subjects.display_order.asc()
            ).all()
        )

        # IMPORTANT:
        # frontend "subject_id" receives ClassSubject.id

        return jsonify([
            {
                "id": row.cls_sub_id,
                "subjectName": row.subject_name
            }
            for row in subjects
        ])

    except Exception as e:

        db.session.rollback()

        print(
            f"get_subjects_by_class error: {e}"
        )

        return jsonify({
            "success": False, "error": "Failed to fetch subjects."
        }), 500


# ============================================================
# 3. GET MARKS
# ============================================================

@fill_marks_bp.route("/api/get_marks",methods=["GET"])
@login_required
@permission_required("fill_marks")
def get_marks():

    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]
    class_id = request.args.get( "class_id", type=int )
    subject_id = request.args.get( "subject_id", type=int )
    exam_id = request.args.get( "exam_id", type=int )

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

        # ----------------------------------------------------
        # Verify ClassSubject
        # ----------------------------------------------------

        class_subject = (
            db.session.query(
                ClassSubject.id.label("cls_sub_id"),
                Subjects.subject,
                Subjects.evaluation_type
            ).join(
                Subjects, Subjects.id == ClassSubject.subject_id
            ).filter(
                ClassSubject.id == subject_id,
                ClassSubject.class_id == class_id,
                Subjects.school_id == school_id,
                Subjects.is_active.is_(True),
                (
                    (ClassSubject.start_session.is_(None)) |
                    (ClassSubject.start_session <= current_session_id)
                ),
                (
                    (ClassSubject.end_session.is_(None)) |
                    (ClassSubject.end_session>= current_session_id)
                )
            ).first()
        )

        if not class_subject:
            return jsonify({
                "success": False, "error": "Subject not found."
            }), 404

        # ----------------------------------------------------
        # Verify exam
        # ----------------------------------------------------

        exam = (
            db.session.query(
                Exams.id, Exams.exam_name,
                Exams.weightage, Exams.is_enabled
            ).filter(
                Exams.id == exam_id, 
                Exams.school_id == school_id
            ).first()
        )

        if not exam:
            return jsonify({
                "success": False, "error": "Exam not found."
            }), 404

        # ----------------------------------------------------
        # Exam lock
        # ----------------------------------------------------

        if (
            not exam.is_enabled and not has_permission("override_marks_lock")
        ):

            return jsonify({
                "success": False,
                "error": (
                    "This exam is locked. "
                    "You do not have permission to fill marks."
                )
            }), 403

        # ----------------------------------------------------
        # Verify exam is assigned to this class
        # ----------------------------------------------------

        class_exam = (
            db.session.query(ClassExams)
            .filter(
                ClassExams.class_id == class_id,
                ClassExams.exam_id == exam_id
            ) .first()
        )

        if not class_exam:
            return jsonify({
                "success": False,
                "error": "This exam is not assigned to this class."
            }), 404

        # ----------------------------------------------------
        # Students + marks
        # ----------------------------------------------------

        marks_data = (
            db.session.query(
                StudentsDB.id.label("student_id"),
                StudentsDB.STUDENTS_NAME,
                StudentsDB.GENDER, StudentSessions.ROLL,
                ClassData.CLASS.label("class_name"),
                StudentMarks.id.label("mark_id"),
                StudentMarks.score,
            )
            .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
            .join(ClassData, StudentSessions.class_id == ClassData.id)
            .outerjoin(
                StudentMarks,
                (StudentMarks.student_id == StudentsDB.id)
                & (StudentMarks.exam_id == exam_id)
                & (StudentMarks.subject_id == class_subject.cls_sub_id)
                & (StudentMarks.session_id == current_session_id)
                & (StudentMarks.school_id == school_id),
            )
            .filter(
                StudentsDB.school_id == school_id,
                StudentSessions.class_id == class_id,
                StudentSessions.session_id == current_session_id,
            )
            .order_by(StudentSessions.ROLL.asc())
            .all()
        )

        students = [ dict(row._mapping) for row in marks_data ]

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return jsonify({
            "success": True,
            "exam": {
                "id": exam.id,
                "name": exam.exam_name,
                "weightage": exam.weightage,
                "is_enabled": exam.is_enabled
            },

            "subject": {
                "id": class_subject.cls_sub_id,
                "name": class_subject.subject,
                "evaluation_type":
                    class_subject.evaluation_type
            },

            "students": students
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

        marks_id = data.get("marks_id")
        score = data.get("score")

        student_id = data.get("student_id")
        subject_id = data.get("subject_id")
        exam_id = data.get("exam_id")
        school_id = session.get("school_id")
        current_session_id = session.get("session_id")
        user_id = session.get("user_id")

        
        if not all([student_id, subject_id, exam_id, current_session_id, school_id]):
            return jsonify({"message": "Missing required fields"}), 400


        # ----------------------------------------------------
        # Validate score
        # ----------------------------------------------------

        if score in [None, ""]:
            score = None
        else:
            try:
                score = float(score)

                if score.is_integer():
                    score = int(score)

            except (ValueError, TypeError):
                print("success")

        # ----------------------------------------------------
        # Verify student enrollment
        # ----------------------------------------------------

        student_session = (
            StudentSessions.query
            .filter(
                StudentSessions.student_id == student_id,
                StudentSessions.session_id == current_session_id
            ).first()
        )

        if not student_session:
            return jsonify({
                "success": False, "message": "Student session not found."
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
                "success": False, "message": "You do not have access to this class."
            }), 403

        # ----------------------------------------------------
        # Verify ClassSubject
        # ----------------------------------------------------

        class_subject = (
            db.session.query(
                ClassSubject.id, ClassSubject.subject_id
            ).join(
                Subjects, Subjects.id == ClassSubject.subject_id
            ).filter(
                ClassSubject.id == subject_id,
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
            ).first()
        )

        if not class_subject:
            return jsonify({
                "success": False, "message": "Subject not found."
            }), 404

        # ----------------------------------------------------
        # Verify exam
        # ----------------------------------------------------

        exam = Exams.query.filter(Exams.id == exam_id, Exams.school_id == school_id).first()
        if not exam:
            return jsonify({
                "success": False, "message": "Exam not found."
            }), 404

        if (not exam.is_enabled and not has_permission("override_marks_lock")):
            return jsonify({
                "success": False,
                "message": (
                    "This exam is disabled. "
                    "You do not have permission "
                    "to fill marks."
                )
            }), 403


        # ----------------------------------------------------
        # Verify exam assigned to student's class
        # ----------------------------------------------------

        class_exam = (
            db.session.query(ClassExams)
            .filter(
                ClassExams.class_id == student_class_id,
                ClassExams.exam_id  == exam_id
            ).first()
        )

        if not class_exam:
            return jsonify({
                "success": False,
                "message": (
                    "This exam is not assigned "
                    "to student's class."
                )
            }), 400


        # ----------------------------------------------------
        # Score range
        # ----------------------------------------------------

        if score is not None:
            if (
                exam.weightage is not None
                and (score < 0 or score > float(exam.weightage))
            ):

                return jsonify({
                    "success": False,
                    "message": (
                        f"Score must be between 0 "
                        f"and {exam.weightage}"
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
                    StudentMarks.student_id == student_id,
                    StudentMarks.subject_id == subject_id,
                    StudentMarks.exam_id == exam_id,
                    StudentMarks.session_id == current_session_id,
                    StudentMarks.school_id == school_id
                ).first()
            )

            if not student_marks:
                return jsonify({
                    "success": False,
                    "message": "Marks record not found."
                }), 404

            student_marks.score = score
            db.session.commit()

            return jsonify({
                "success": True, "message": "Marks updated successfully.",
                "mark_id": student_marks.id,
                "score": student_marks.score
            }), 200

        # ====================================================
        # CASE 2: Find existing mark
        # ====================================================

        existing = (
            StudentMarks.query
            .filter(
                StudentMarks.student_id == student_id,
                StudentMarks.subject_id == subject_id,
                StudentMarks.exam_id == exam_id,
                StudentMarks.session_id == current_session_id,
                StudentMarks.school_id == school_id
            ).first()
        )
        if existing:
            existing.score = score
            db.session.commit()
            return jsonify({
                "success": True, "message": "Marks updated successfully.",
                "mark_id": existing.id, "score": existing.score
            }), 200

        # ====================================================
        # CASE 3: Create new mark
        # ====================================================

        new_mark = StudentMarks(
            student_id=student_id,
            subject_id=class_subject.id,
            exam_id=exam_id,
            score=score,
            session_id=current_session_id,
            school_id=school_id
        )
        db.session.add(new_mark)
        db.session.commit()

        return jsonify({
            "success": True, "message": "Marks inserted successfully.",
            "mark_id": new_mark.id, "score": new_mark.score
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
            "success": False, "message": "Internal server error."
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
            .filter(
                Exams.school_id == school_id
            ).order_by(
                Exams.display_order.asc()
            ).all()
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