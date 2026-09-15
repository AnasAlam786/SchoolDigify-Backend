from flask import request, session, jsonify, Blueprint
from sqlalchemy import exists, func, or_

from src import db

from src.model import (
    ClassData,
    Subjects,
    StudentMarks
)

from src.controller.auth.login_required import login_required
from src.model.ClassSubject import ClassSubject


subject_setup_api_bp = Blueprint(
    "subject_setup_api_bp",
    __name__
)


# ================================================================
# GET SUBJECTS DATA
# ================================================================

@subject_setup_api_bp.route("/api/get_subjects_data", methods=["GET"])
@login_required
def get_subjects():
    try:
        school_id = session["school_id"]

        has_marks = exists().where(
            (StudentMarks.subject_id == ClassSubject.id)
            &
            (ClassSubject.subject_id == Subjects.id)
        )

        # ---------------------------------------------------------
        # Get subjects and the classes assigned to them
        # through ClassSubject.
        # ---------------------------------------------------------

        rows = (
            db.session.query(
                Subjects.id.label("subject_id"),
                Subjects.subject,
                Subjects.max_marks,
                Subjects.pass_marks,
                Subjects.display_order,
                Subjects.evaluation_type,
                Subjects.abbreviation,
                Subjects.staff_id,
                Subjects.subject_type,
                Subjects.is_active,

                ClassData.id.label("class_id"),
                ClassData.CLASS.label("class_name"),

                has_marks.label("has_marks")
            )
            .join(
                ClassSubject,
                ClassSubject.subject_id == Subjects.id
            )
            .join(
                ClassData,
                ClassData.id == ClassSubject.class_id
            )
            .filter(
                Subjects.school_id == school_id,
                ClassData.school_id == school_id
            )
            .order_by(
                Subjects.display_order,
                ClassData.display_order
            )
            .all()
        )

        # ---------------------------------------------------------
        # Group classes under each subject
        # ---------------------------------------------------------

        subjects = {}

        for row in rows:

            # Subject ID is the safest grouping key.
            subject_key = row.subject_id

            if subject_key not in subjects:

                subjects[subject_key] = {
                    "id": row.subject_id,
                    "subject": row.subject,

                    "max_marks": (
                        float(row.max_marks)
                        if row.max_marks is not None
                        else None
                    ),

                    "pass_marks": (
                        float(row.pass_marks)
                        if row.pass_marks is not None
                        else None
                    ),

                    "display_order": row.display_order,
                    "evaluation_type": row.evaluation_type,
                    "abbreviation": row.abbreviation,
                    "staff_id": row.staff_id,
                    "subject_type": row.subject_type,
                    "is_active": row.is_active,

                    "editable": not bool(row.has_marks),

                    "classes": []
                }

            subjects[subject_key]["classes"].append({
                "class_id": row.class_id,
                "class_name": row.class_name
            })

        return jsonify({
            "subjects": list(subjects.values())
        }), 200

    except Exception as e:

        print("Error while getting subjects:", e)

        db.session.rollback()

        return jsonify({
            "error": "Unable to load school subjects. Please try again later."
        }), 500

    
@subject_setup_api_bp.route(
    "/api/update_subject/<int:subject_id>",
    methods=["PUT"]
)
@login_required
def update_subject(subject_id):

    try:
        school_id = session.get("school_id")

        # ========================================================
        # Request
        # ========================================================

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "Request body is required."
            }), 400

        class_ids = data.get("class_ids")
        subject_name = str(data.get("subject", "")).strip()
        abbreviation = str(data.get("abbreviation", "")).strip()

        max_marks = data.get("max_marks")
        pass_marks = data.get("pass_marks")
        staff_id = data.get("staff_id")

        # ========================================================
        # Validation
        # ========================================================

        if not isinstance(class_ids, list) or not class_ids:
            return jsonify({
                "error": "At least one class is required."
            }), 400

        try:
            class_ids = {int(x) for x in class_ids}
        except (TypeError, ValueError):
            return jsonify({
                "error": "Invalid class ID."
            }), 400

        if not subject_name:
            return jsonify({
                "error": "Subject name is required."
            }), 400

        if not abbreviation:
            return jsonify({
                "error": "Subject abbreviation is required."
            }), 400

        # ========================================================
        # Find subject
        # ========================================================

        subject = (
            db.session.query(Subjects)
            .filter(
                Subjects.id == subject_id,
                Subjects.school_id == school_id
            )
            .first()
        )

        if not subject:
            return jsonify({
                "error": "Subject not found."
            }), 404

        has_marks = (
            db.session.query(StudentMarks.id)
            .join(
                ClassSubject,
                ClassSubject.id == StudentMarks.subject_id
            ).filter(
                ClassSubject.subject_id == subject.id
            ).first()
        )

        if has_marks:
            return jsonify({
                "error": (
                    "This subject cannot be edited because "
                    "marks have already been entered."
                ),
                "editable": False
            }), 409

        # ========================================================
        # Validate classes
        # ========================================================

        valid_class_ids = {
            row.id
            for row in (
                db.session.query(ClassData.id.label("id"))
                .filter(
                    ClassData.id.in_(class_ids),
                    ClassData.school_id == school_id
                )
                .all()
            )
        }

        if valid_class_ids != class_ids:
            return jsonify({
                "error": "One or more selected classes are invalid."
            }), 404

        # ========================================================
        # Check duplicate subject name
        # ========================================================

        duplicate = (
            db.session.query(Subjects.id)
            .join(
                ClassSubject,
                ClassSubject.subject_id == Subjects.id
            )
            .filter(
                Subjects.school_id == school_id,
                Subjects.id != subject.id,
                ClassSubject.class_id.in_(class_ids),
                func.lower(Subjects.subject) == subject_name.lower()
            )
            .first()
        )

        if duplicate:
            return jsonify({
                "error": (
                    "Another subject with this name already "
                    "exists for one of the selected classes."
                )
            }), 409

        # ========================================================
        # Update Subjects
        # ========================================================

        subject.subject = subject_name
        subject.abbreviation = abbreviation
        subject.max_marks = max_marks
        subject.pass_marks = pass_marks
        subject.staff_id = staff_id

        # ========================================================
        # Synchronize ClassSubject
        # ========================================================

        existing = (
            db.session.query(ClassSubject)
            .filter(
                ClassSubject.subject_id == subject.id
            )
            .all()
        )

        existing_by_class = {
            cs.class_id: cs
            for cs in existing
        }

        # Remove old class access
        for class_id, class_subject in existing_by_class.items():

            if class_id not in class_ids:
                db.session.delete(class_subject)

        # Add new class access
        for class_id in class_ids:

            if class_id not in existing_by_class:

                db.session.add(
                    ClassSubject(
                        class_id=class_id,
                        subject_id=subject.id
                    )
                )

        # ========================================================
        # Commit
        # ========================================================

        db.session.commit()

        return jsonify({
            "message": "Subject updated successfully.",
            "subject_id": subject.id,
            "class_ids": sorted(class_ids)
        }), 200

    except Exception as e:

        db.session.rollback()

        print("Error while updating subject:", e)

        return jsonify({
            "error": "Unable to update subject. Please try again later."
        }), 500