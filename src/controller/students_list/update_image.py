import os

from flask import Blueprint, jsonify, request, session

from src import db
from src.model.Schools import Schools
from src.model.StudentsDB import StudentsDB
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.utils.upload_image import delete_image, move_image, upload_image

update_student_image_bp = Blueprint('update_student_image_bp', __name__)
DELETED_FOLDER = os.getenv("DELETED_IMAGE_FOLDER_ID")


@update_student_image_bp.route('/api/update_student_image', methods=['POST'])
@login_required
@permission_required('update_student')
def update_student_image():
    """Upload a new student image and safely replace the previous one."""
    student_id = request.form.get('student_id')
    image_file = request.files.get('image_file') or request.files.get('image')

    if not student_id:
        return jsonify({"error": "Student id is required."}), 400

    if not image_file:
        return jsonify({"error": "Image file is required."}), 400

    try:
        student_id = int(student_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Student id is invalid."}), 400

    student = StudentsDB.query.filter_by(id=student_id).first()
    if not student:
        return jsonify({"error": "Student not found."}), 404

    school_id = session.get('school_id')
    school = Schools.query.filter_by(id=school_id).first()
    if not school:
        return jsonify({"error": "School not found."}), 404

    old_image_id = student.IMAGE
    image_name = student.ADMISSION_NO if student.ADMISSION_NO not in (None, '') else str(student_id)

    try:
        new_image_id = upload_image(
            image_file,
            str(image_name),
            school.students_image_folder_id
        )
    except Exception:
        return jsonify({"error": "Failed to upload student image."}), 500

    if not new_image_id:
        return jsonify({"error": "Image upload failed, no file ID returned."}), 500

    try:
        student.IMAGE = new_image_id
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            delete_image(new_image_id)
        except Exception:
            pass
        return jsonify({"error": "Failed to save the uploaded student image."}), 500

    try:
        if old_image_id and old_image_id != new_image_id:
            move_image(old_image_id, DELETED_FOLDER, rename=f"student_{student_id}")
    except Exception:
        # Keep the new image as canonical even if the old one cannot be moved.
        pass

    image_url = f"https://lh3.googleusercontent.com/d/{new_image_id}=s200"
    return jsonify({
        "message": "Student image uploaded successfully.",
        "image_id": new_image_id,
        "image_url": image_url
    }), 200
