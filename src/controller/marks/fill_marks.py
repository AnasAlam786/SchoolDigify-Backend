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
@login_required
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

        
    subjects = (
        db.session.query(Subjects.id, Subjects.subject, Subjects.display_order)
        .filter(
            Subjects.school_id == school_id,
            Subjects.is_active == True,
            Subjects.class_id.in_(class_ids)
        )
        .order_by(Subjects.display_order.asc())
        .all()
    )

    # Build a list of unique subjects by name, but keep an associated id for frontend selection
    unique_subjects = []
    seen = set()
    for s in subjects:
        if s.subject not in seen:
            seen.add(s.subject)
            unique_subjects.append({"id": s.id, "subject": s.subject})


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

    return render_template('marks_management/fill_marks.html', data=data, classes=classes, exams = exams, subjects = unique_subjects)


@fill_marks_bp.route('/get_marks', methods=["GET"])
@login_required
@permission_required('fill_marks')
def get_marks():
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')
    exam_id = request.args.get('exam_id')
    school_id = session["school_id"]
    current_session_id = session["session_id"]
    

    if not subject_id or not class_id or not exam_id:
        return jsonify({"error": "Missing required fields: subject, class, and exam are all required."}), 400
        
    exam = Exams.query.filter_by(id=exam_id, school_id=school_id).first()
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    if not exam.is_enabled and not has_permission('override_marks_lock'):
        return jsonify({"error": "This exam is disabled. You do not have permission to fill marks for disabled exams."}), 403

    # validate subject id
    try:
        subject_id_int = int(subject_id)
    except Exception:
        return jsonify({"error": "Invalid subject id"}), 400
    

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
        .join(Exams, Exams.id == exam_id)

        # Join subject details — fixed value (one subject at a time)
        .join(Subjects, Subjects.id == subject_id_int)

        # Outer join: get marks only if they exist
        .outerjoin(
            StudentMarks,
            (StudentMarks.student_id == StudentsDB.id) &
            (StudentMarks.exam_id == exam_id) &
            (StudentMarks.subject_id == Subjects.id) &
            (StudentMarks.session_id == current_session_id)   # 🔑 Important
        )

        # Filter by class, school, and session
        .filter(
            ClassData.id == class_id,
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


@fill_marks_bp.route('/get_all_exams', methods=['GET'])
@login_required
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
