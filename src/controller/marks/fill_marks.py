# src/controller/marks/fill_marks.py

from flask import render_template, session, request, jsonify, Blueprint

from src.model import Exams, StudentsDB, StudentSessions, ClassData, StudentMarks, Subjects, TeachersLogin, ClassExams
from src.model.ClassAccess import ClassAccess
from src import db

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.permissions.has_permission import has_permission


fill_marks_bp = Blueprint( 'fill_marks_bp',   __name__)

@fill_marks_bp.route('/fill_marks', methods=["GET", "POST"])
@login_required     # Only logged in users can access the fill marks page.
@permission_required('fill_marks')
def fill_marks():
    
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

    class_ids = [row.id for row in classes]

    # No preloaded subjects in the dropdown; user selects class first then we load subjects via API.
    subjects = []

    exams = (
        db.session.query(Exams.exam_name, Exams.id, Exams.is_enabled)
        .join(ClassExams, ClassExams.exam_id == Exams.id)
        .filter(ClassExams.class_id.in_(class_ids),
                Exams.school_id == school_id
        )
        .group_by(Exams.id)
        .order_by(Exams.display_order.asc())
        .all()
    )
        
    data = None

    return render_template('marks_management/fill_marks.html', data=data, classes=classes, exams=exams, subjects=subjects)


@fill_marks_bp.route('/get_marks', methods=["GET"])
@login_required     # API to fetch marks after selecting class+subject+exam combination, used to populate the marks table in the frontend.
@permission_required('fill_marks')
def get_marks():
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')
    exam_id = request.args.get('exam_id')
    school_id = session["school_id"]
    current_session_id = session["session_id"]
    user_id = session["user_id"]

    if not subject_id or not class_id or not exam_id:
        return jsonify({"error": "Missing required fields: subject, class, and exam are all required."}), 400

    try:
        class_id_int = int(class_id)
        subject_id_int = int(subject_id)
        exam_id_int = int(exam_id)
    except ValueError:
        return jsonify({"error": "Invalid class/subject/exam id"}), 400

    class_allowed = (
        db.session.query(ClassData.id)
            .join(ClassAccess, ClassAccess.class_id == ClassData.id)
            .filter(ClassData.id == class_id_int, ClassAccess.staff_id == user_id)
            .first()
    )
    if not class_allowed:
        return jsonify({"error": "Class not found or not permitted for current teacher."}), 403

    subject = (
        db.session.query(Subjects.id)
            .filter_by(
                id=subject_id_int,
                class_id=class_id_int,
                school_id=school_id,
                is_active=True
            ).first()
    )   
    if not subject:
        return jsonify({"error": "Subject not found for selected class."}), 400

    exam = (
        db.session.query(Exams.id, Exams.is_enabled)
        .filter_by(
            id=exam_id_int, 
            school_id=school_id
        ).first()
    )
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    if not exam.is_enabled and not has_permission('override_marks_lock'):
        return jsonify({"error": "This exam is disabled. You do not have permission to fill marks for disabled exams."}), 403



    marks_data = (
        db.session.query(
            StudentMarks.id.label('id'),
            StudentMarks.score,          # Student's mark (can be None)
            StudentsDB.STUDENTS_NAME,               # Name of the student
            StudentsDB.GENDER,
            StudentsDB.id.label('student_id'), 
            StudentSessions.ROLL,                   # Roll number
            ClassData.CLASS,                        # Class name or number
            Exams.id.label('exam_id'),
            Exams.exam_name,                        # e.g., "Mid Term"
            Exams.weightage,                        # Max marks for the exam
                Subjects.subject,                       # e.g., "Math", "English"
                Subjects.evaluation_type,                # e.g., "numeric" or "grading"
                Subjects.id.label('subject_id')
        )

        # Join student with their session info
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)

        # Join session info with class info
        .join(ClassData, StudentSessions.class_id == ClassData.id)

        # Join exam details — fixed value (one exam at a time) it create the colum with same values in all the table like FA1
        .join(Exams, Exams.id == exam_id_int)

        # Join subject details — fixed value (one subject at a time)
        .join(Subjects, Subjects.id == subject_id_int)

        # Outer join: get marks only if they exist
        .outerjoin(
            StudentMarks,
            (StudentMarks.student_id == StudentsDB.id) &
            (StudentMarks.exam_id == exam_id_int) &
            (StudentMarks.subject_id == Subjects.id) &
            (StudentMarks.session_id == current_session_id)   # 🔑 Important
        )

        # Filter by class, school, and session
        .filter(
            ClassData.id == class_id_int,
            StudentsDB.school_id == school_id,
            StudentSessions.session_id == current_session_id,
        )

        # Sort by roll number
        .order_by(StudentSessions.ROLL)
        .all()
    )
    
    # Render only the partial template for the marks table
    html = render_template('marks_management/fill_marks_table.html', data=marks_data)
    
    return jsonify({"html": html})


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

    return jsonify([{"id": sub.id, "subject": sub.subject} for sub in subjects])

@fill_marks_bp.route('/update_marks_api', methods=['POST'])
@login_required     # API to update or insert marks based on the presence of marks_id or existing record for student+subject+exam.
@permission_required('fill_marks')
def update_marks_api():
    data = request.json
    
    marks_id = data.get('marks_id')
    score = data.get('score')
    student_id = data.get('student_id')
    subject_id = data.get('subject_id')
    exam_id = data.get('exam_id')

    current_session_id = session.get("session_id")
    school_id = session.get("school_id")

    

    if not all([student_id, subject_id, exam_id, current_session_id, school_id]):
        return jsonify({"message": "Missing required fields"}), 400

    exam = Exams.query.filter_by(id=exam_id, school_id=school_id).first()
    if not exam:
        return jsonify({"message": "Exam not found"}), 404

    if not exam.is_enabled and not has_permission('override_marks_lock'):
        return jsonify({"message": "This exam is disabled. You do not have permission to fill marks for disabled exams."}), 403

    student_session = StudentSessions.query.filter_by(student_id=student_id, session_id=current_session_id).first()
    if not student_session:
        return jsonify({"message": "Student session not found"}), 400

    subject = Subjects.query.filter_by(id=subject_id, school_id=school_id, is_active=True).first()
    if not subject or subject.class_id != student_session.class_id:
        return jsonify({"message": "Selected subject is invalid for this student class"}), 400

    # 🟩 CASE 1: Update existing mark
    if marks_id and marks_id != "":
        
        student_marks = StudentMarks.query.filter_by(id=marks_id).first()
        if student_marks:
            student_marks.score = score
            db.session.commit()
            return jsonify({"message": "Updated marks successfully"}), 200
        else:
            return jsonify({"message": "Unable to find student record in database"}), 400

    # 🟩 CASE 2: Try to find an existing record to update (by student + subject + exam)
    existing = StudentMarks.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
        exam_id=exam_id,
        session_id=current_session_id
    ).first()

    if existing:
        existing.score = score
        db.session.commit()
        return jsonify({"message": "Updated existing marks by composite key", "new_mark_id": existing.id}), 200

    # 🟩 CASE 3: Create new record
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
        "message": "Inserted new marks successfully",
        "new_mark_id": new_mark.id
    }), 200


@fill_marks_bp.route('/get_all_exams', methods=['GET'])
@login_required # 
@permission_required('lock_marks')
def get_all_exams():
    school_id = session["school_id"]
    exams = Exams.query.filter_by(school_id=school_id).order_by(Exams.display_order).all()
    return jsonify([{'id': e.id, 'name': e.exam_name, 'enabled': e.is_enabled} for e in exams])


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
