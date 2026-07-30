# src/controller/marks/fill_marks.py

from flask import render_template, session, request, jsonify, Blueprint

from src.model import Exams, StudentsDB, StudentSessions, ClassData, StudentMarks, Subjects, TeachersLogin, ClassExams
from src.model.ClassAccess import ClassAccess
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.permissions.has_permission import has_permission


fill_marks_bp = Blueprint( 'fill_marks_bp',   __name__)

@fill_marks_bp.route('/api/fetchClassesAndExams', methods=["GET"])
@login_required
@permission_required('fill_marks')
def fetchClassesAndExams():

    user_id = session["user_id"]
    school_id = session["school_id"]

    classes = (
        db.session.query(ClassData.id, ClassData.CLASS)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .join(TeachersLogin, TeachersLogin.id == ClassAccess.staff_id)
        .filter(TeachersLogin.id == user_id)
        .order_by(ClassData.id.asc())
        .all()
    )

    class_ids = [c.id for c in classes]

    exams = (
        db.session.query(Exams.id, Exams.exam_name, Exams.is_enabled)
        .join(ClassExams, ClassExams.exam_id == Exams.id)
        .filter(
            ClassExams.class_id.in_(class_ids),
            Exams.school_id == school_id
        )
        .group_by(Exams.id)
        .order_by(Exams.display_order.asc())
        .all()
    )


    return jsonify({
        "classes": [
            {"id": c.id, "className": c.CLASS}
            for c in classes
        ],
        "exams": [
            {"id": e.id, "exam_name": e.exam_name, "is_enabled": e.is_enabled}
            for e in exams
        ]
    })

@fill_marks_bp.route('/api/get_marks', methods=["GET"])
@login_required
@permission_required('fill_marks')
def get_marks():

    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]

    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    exam_id = request.args.get('exam_id', type=int)

    if not all([class_id, subject_id, exam_id]):
        return jsonify({
            "success": False,
            "error": "Class, Subject and Exam are required."
        }), 400

    try:

        # --------------------------------------------------
        # Verify teacher has access to class
        # --------------------------------------------------

        class_allowed = (
            db.session.query(ClassData.id)
            .join(ClassAccess, ClassAccess.class_id == ClassData.id)
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

        # --------------------------------------------------
        # Verify subject
        # --------------------------------------------------

        subject = (
            db.session.query(
                Subjects.id,
                Subjects.subject,
                Subjects.evaluation_type
            )
            .filter(
                Subjects.id == subject_id,
                Subjects.class_id == class_id,
                Subjects.school_id == school_id,
                Subjects.is_active == True
            )
            .first()
        )

        if not subject:
            return jsonify({
                "success": False,
                "error": "Subject not found."
            }), 404

        # --------------------------------------------------
        # Verify exam
        # --------------------------------------------------

        exam = (
            db.session.query(
                Exams.id,
                Exams.exam_name,
                Exams.weightage,
                Exams.is_enabled
            )
            .filter(
                Exams.id == exam_id,
                Exams.school_id == school_id
            )
            .first()
        )

        if not exam:
            return jsonify({
                "success": False,
                "error": "Exam not found."
            }), 404

        if not exam.is_enabled and not has_permission('override_marks_lock'):
            return jsonify({
                "success": False,
                "error": "This exam is locked. You do not have permission to fill marks."
            }), 403

        # --------------------------------------------------
        # Fetch students + marks
        # --------------------------------------------------

        marks_data = (
            db.session.query(
                StudentsDB.id.label("student_id"),
                StudentsDB.STUDENTS_NAME,
                StudentsDB.GENDER,

                StudentSessions.ROLL,

                StudentMarks.id.label("mark_id"),
                StudentMarks.score
            )

            .join(
                StudentSessions,
                StudentSessions.student_id == StudentsDB.id
            )

            .outerjoin(
                StudentMarks,
                (StudentMarks.student_id == StudentsDB.id)
                & (StudentMarks.exam_id == exam_id)
                & (StudentMarks.subject_id == subject_id)
                & (StudentMarks.session_id == current_session_id)
            )

            .filter(
                StudentsDB.school_id == school_id,
                StudentSessions.class_id == class_id,
                StudentSessions.session_id == current_session_id,
            )

            .order_by(StudentSessions.ROLL)

            .all()
        )

        students = [
            dict(row._mapping)
            for row in marks_data
        ]

        return jsonify({
            "success": True,

            "exam": {
                "id": exam.id,
                "name": exam.exam_name,
                "weightage": exam.weightage,
                "is_enabled": exam.is_enabled
            },

            "subject": {
                "id": subject.id,
                "name": subject.subject,
                "evaluation_type": subject.evaluation_type
            },

            "students": students
        })

    except Exception as e:

        print(f"Error fetching marks: {e}")

        return jsonify({
                "success": False,
                "error": "Failed to fetch marks."
            }), 500


@fill_marks_bp.route('/api/subjects/<int:class_id>', methods=['GET'])
@login_required   # Get subjects for the dropdown based on selected class in the frontend.
@permission_required('fill_marks')
def get_subjects_by_class(class_id):
    school_id = session["school_id"]

    subjects = Subjects.query.filter_by(
        class_id=class_id,
        school_id=school_id,
        is_active=True
    ).order_by(Subjects.display_order.asc()).all()

    return jsonify([{"id": sub.id, "subjectName": sub.subject} for sub in subjects])

from sqlalchemy.exc import IntegrityError

@fill_marks_bp.route('/update_marks_api', methods=['POST'])
@login_required
@permission_required('fill_marks')
def update_marks_api():
    try:
        data = request.get_json() or {}

        marks_id = data.get('marks_id')
        score = data.get('score')
        student_id = data.get('student_id')
        subject_id = data.get('subject_id')
        exam_id = data.get('exam_id')

        current_session_id = session.get("session_id")
        school_id = session.get("school_id")

        # --------------------------------------------------
        # Validate required fields
        # --------------------------------------------------

        if not all([
            student_id, subject_id, exam_id, current_session_id, school_id
        ]):
            return jsonify({
                "success": False,
                "message": "Missing required fields"
            }), 400

        # --------------------------------------------------
        # Validate score
        # --------------------------------------------------

        if score not in [None, ""]:
            try:
                score = float(score)
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "message": "Invalid score value"
                }), 400

        # --------------------------------------------------
        # Validate exam
        # --------------------------------------------------

        exam = Exams.query.filter_by( id=exam_id, school_id=school_id ).first()
        if not exam:
            return jsonify({
                "success": False,
                "message": "Exam not found"
            }), 404

        if (not exam.is_enabled and not has_permission('override_marks_lock')):
            return jsonify({
                "success": False,
                "message": (
                    "This exam is disabled. "
                    "You do not have permission to fill marks."
                )
            }), 403

        # --------------------------------------------------
        # Validate score range
        # --------------------------------------------------

        if score not in [None, ""]:
            if score < 0 or score > exam.weightage:
                return jsonify({
                    "success": False,
                    "message":
                        f"Score must be between 0 and {exam.weightage}"
                }), 400

        # --------------------------------------------------
        # Validate session enrollment
        # --------------------------------------------------

        student_session = StudentSessions.query.filter_by(
            student_id=student_id,
            session_id=current_session_id
        ).first()

        if not student_session:
            return jsonify({
                "success": False,
                "message": "Student session not found"
            }), 400

        # --------------------------------------------------
        # Validate subject
        # --------------------------------------------------

        subject = Subjects.query.filter_by(
            id=subject_id,
            school_id=school_id,
            is_active=True
        ).first()

        if not subject:
            return jsonify({
                "success": False,
                "message": "Subject not found"
            }), 404

        if subject.class_id != student_session.class_id:
            return jsonify({
                "success": False,
                "message":
                    "Selected subject does not belong to student's class"
            }), 400

        # --------------------------------------------------
        # CASE 1: Update using marks_id
        # --------------------------------------------------

        if marks_id not in [None, ""]:

            student_marks = StudentMarks.query.filter_by(
                id=marks_id,
                school_id=school_id,
                session_id=current_session_id
            ).first()

            if not student_marks:
                return jsonify({
                    "success": False,
                    "message": "Marks record not found"
                }), 404

            student_marks.score = score

            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Marks updated successfully",
                "mark_id": student_marks.id,
                "score": student_marks.score
            }), 200

        # --------------------------------------------------
        # CASE 2: Update existing record
        # --------------------------------------------------

        existing = StudentMarks.query.filter_by(
            student_id=student_id,
            subject_id=subject_id,
            exam_id=exam_id,
            session_id=current_session_id,
            school_id=school_id
        ).first()

        if existing:

            existing.score = score

            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Marks updated successfully",
                "mark_id": existing.id,
                "score": existing.score
            }), 200

        # --------------------------------------------------
        # CASE 3: Create new record
        # --------------------------------------------------

        new_mark = StudentMarks(
            student_id=student_id,
            subject_id=subject_id,
            exam_id=exam_id,
            score=score,
            session_id=current_session_id,
            school_id=school_id
        )

        db.session.add(new_mark)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Marks inserted successfully",
            "mark_id": new_mark.id,
            "score": new_mark.score
        }), 201

    except IntegrityError:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message":
                "Duplicate marks record exists for this student, subject and exam."
        }), 409

    except Exception as e:

        db.session.rollback()

        print(f"Error updating marks: {e}")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500


@fill_marks_bp.route('/api/get_all_exams', methods=['GET'])
@login_required # 
@permission_required('lock_marks')
def get_all_exams():
    school_id = session["school_id"]
    exams = Exams.query.filter_by(school_id=school_id).order_by(Exams.display_order).all()
    return jsonify([{'id': e.id, 'exam_name': e.exam_name, 'is_enabled': e.is_enabled} for e in exams])


@fill_marks_bp.route('/update_exam_status', methods=['POST'])
@login_required
@permission_required('lock_marks')
def update_exam_status():
    data = request.json
    exam_id = data.get('exam_id')
    is_enabled = data.get('is_enabled')
    exam = Exams.query.filter_by(id=exam_id, school_id=session["school_id"]).first()
    if not exam:
        return jsonify({'error': 'Exam not found'}), 404
    exam.is_enabled = is_enabled
    db.session.commit()
    return jsonify({'message': 'Updated successfully'})
