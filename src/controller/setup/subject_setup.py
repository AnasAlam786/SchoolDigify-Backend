from flask import request, session, jsonify, Blueprint
from sqlalchemy import exists, or_

from src import db

from src.model import (
    ClassData,
    Subjects,
    StudentMarks
)

from src.controller.auth.login_required import login_required


subject_setup_api_bp = Blueprint(
    "subject_setup_api_bp",
    __name__
)


# ================================================================
# GET SUBJECTS DATA
# ================================================================

@subject_setup_api_bp.route(
    "/api/get_subjects_data",
    methods=["GET"]
)
@login_required
def get_subjects():

    try:
        # ---------------------------------------------------------
        # 1. Get current school
        # ---------------------------------------------------------

        school_id = session["school_id"]

        # ---------------------------------------------------------
        # 2. Check whether marks exist for each subject
        #
        # If at least one StudentMarks record exists for the
        # subject, editable will be False.
        # ---------------------------------------------------------

        has_marks = exists().where(
            StudentMarks.subject_id == Subjects.id
        )

        # ---------------------------------------------------------
        # 3. Get subjects with their classes
        # ---------------------------------------------------------

        rows = (
            db.session.query(
                Subjects.id.label("subject_id"),
                Subjects.subject_code,
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
                ClassData,
                ClassData.id == Subjects.class_id
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
        # 4. Group subjects
        # ---------------------------------------------------------

        subjects = {}

        for row in rows:

            # -----------------------------------------------------
            # Use subject_code as the grouping key when available.
            #
            # If subject_code is NULL, use subject name.
            # -----------------------------------------------------

            subject_key = (
                row.subject_code
                if row.subject_code
                else row.subject
            )

            # -----------------------------------------------------
            # Create subject
            # -----------------------------------------------------

            if subject_key not in subjects:

                subjects[subject_key] = {
                    "id": row.subject_id,
                    "subject_code": row.subject_code,
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

                    # If marks exist for this subject row,
                    # editing is disabled.
                    "editable": not bool(row.has_marks),

                    "classes": []
                }

            # -----------------------------------------------------
            # Add class to subject
            # -----------------------------------------------------

            subjects[subject_key]["classes"].append({
                "class_id": row.class_id,
                "class_name": row.class_name
            })

        # ---------------------------------------------------------
        # 5. Return response
        # ---------------------------------------------------------

        return jsonify({
            "subjects": list(subjects.values())
        }), 200

    except Exception as e:

        print("Error while getting subjects:", e)

        db.session.rollback()

        return jsonify({
            "error": "Unable to load school subjects. Please try again later."
        }), 500
    

# ================================================================
# CREATE SUBJECT
# ================================================================

@subject_setup_api_bp.route(
    "/api/create_subject",
    methods=["POST"]
)
@login_required
def create_subject():

    try:
        # ---------------------------------------------------------
        # 1. Get current school
        # ---------------------------------------------------------

        school_id = session["school_id"]

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "Request body is required."
            }), 400

        # ---------------------------------------------------------
        # 2. Get data
        # ---------------------------------------------------------

        class_id = data.get("class_id")

        subject_code = data.get("subject_code")
        subject_name = data.get("subject")

        max_marks = data.get("max_marks")
        pass_marks = data.get("pass_marks")
        display_order = data.get("display_order")
        evaluation_type = data.get("evaluation_type")
        abbreviation = data.get("abbreviation")
        staff_id = data.get("staff_id")
        subject_type = data.get("subject_type", "core")
        is_active = data.get("is_active", True)

        # ---------------------------------------------------------
        # 3. Validate required fields
        # ---------------------------------------------------------

        if not class_id:
            return jsonify({
                "error": "Class ID is required."
            }), 400

        if not subject_name:
            return jsonify({
                "error": "Subject name is required."
            }), 400

        if not abbreviation:
            return jsonify({
                "error": "Subject abbreviation is required."
            }), 400

        # ---------------------------------------------------------
        # 4. Check class belongs to current school
        # ---------------------------------------------------------

        class_exists = (
            db.session.query(ClassData.id)
            .filter(
                ClassData.id == class_id,
                ClassData.school_id == school_id
            )
            .first()
        )

        if not class_exists:

            return jsonify({
                "error": "Class not found."
            }), 404

        # ---------------------------------------------------------
        # 5. Check duplicate subject name or subject code
        #
        # Same subject can exist in different classes.
        # Therefore check within the same school + class.
        # ---------------------------------------------------------

        duplicate_filters = [
            Subjects.subject == subject_name
        ]

        # Only check subject_code if it was provided
        if subject_code:
            duplicate_filters.append(
                Subjects.subject_code == subject_code
            )

        existing_subject = (
            db.session.query(Subjects.id)
            .filter(
                Subjects.school_id == school_id,
                Subjects.class_id == class_id,
                or_(*duplicate_filters)
            )
            .first()
        )

        if existing_subject:

            return jsonify({
                "error": (
                    "A subject with this name or code "
                    "already exists for this class."
                )
            }), 409

        # ---------------------------------------------------------
        # 6. Create subject
        # ---------------------------------------------------------

        subject = Subjects(
            school_id=school_id,
            class_id=class_id,
            subject_code=subject_code,
            subject=subject_name,
            max_marks=max_marks,
            pass_marks=pass_marks,
            display_order=display_order,
            evaluation_type=evaluation_type,
            abbreviation=abbreviation,
            staff_id=staff_id,
            subject_type=subject_type,
            is_active=is_active
        )

        db.session.add(subject)

        # ---------------------------------------------------------
        # 7. Commit
        # ---------------------------------------------------------

        db.session.commit()

        return jsonify({
            "message": "Subject created successfully.",
            "subject_id": subject.id
        }), 201

    except Exception as e:

        db.session.rollback()

        print("Error while creating subject:", e)

        return jsonify({
            "error": "Unable to create subject. Please try again later."
        }), 500


# ================================================================
# UPDATE SUBJECT
# ================================================================

@subject_setup_api_bp.route(
    "/api/update_subject/<int:subject_id>",
    methods=["PUT"]
)
@login_required
def update_subject(subject_id):

    try:
        # ---------------------------------------------------------
        # 1. Get current school
        # ---------------------------------------------------------

        school_id = session["school_id"]

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "Request body is required."
            }), 400

        # ---------------------------------------------------------
        # 2. Get data
        # ---------------------------------------------------------

        class_id = data.get("class_id")

        subject_code = data.get("subject_code")
        subject_name = data.get("subject")

        max_marks = data.get("max_marks")
        pass_marks = data.get("pass_marks")
        display_order = data.get("display_order")
        evaluation_type = data.get("evaluation_type")
        abbreviation = data.get("abbreviation")
        staff_id = data.get("staff_id")
        subject_type = data.get("subject_type")
        is_active = data.get("is_active")

        # ---------------------------------------------------------
        # 3. Validate required fields
        # ---------------------------------------------------------

        if not class_id:
            return jsonify({
                "error": "Class ID is required."
            }), 400

        if not subject_name:
            return jsonify({
                "error": "Subject name is required."
            }), 400

        if not abbreviation:
            return jsonify({
                "error": "Subject abbreviation is required."
            }), 400

        # ---------------------------------------------------------
        # 4. Find subject
        #
        # school_id check prevents another school from
        # modifying this subject.
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 5. Check whether marks already exist
        #
        # If marks exist, subject cannot be modified.
        # ---------------------------------------------------------

        has_marks = (
            db.session.query(
                exists().where(
                    StudentMarks.subject_id == subject.id
                )
            )
            .scalar()
        )

        if has_marks:

            return jsonify({
                "error": (
                    "This subject cannot be modified because "
                    "marks have already been entered."
                ),
                "editable": False
            }), 409

        # ---------------------------------------------------------
        # 6. Check class belongs to current school
        # ---------------------------------------------------------

        class_exists = (
            db.session.query(ClassData.id)
            .filter(
                ClassData.id == class_id,
                ClassData.school_id == school_id
            )
            .first()
        )

        if not class_exists:

            return jsonify({
                "error": "Class not found."
            }), 404

        # ---------------------------------------------------------
        # 7. Check duplicate subject name or subject code
        #
        # Exclude the subject currently being updated.
        # ---------------------------------------------------------

        duplicate_filters = [
            Subjects.subject == subject_name
        ]

        # Only check subject_code if it was provided
        if subject_code:
            duplicate_filters.append(
                Subjects.subject_code == subject_code
            )

        existing_subject = (
            db.session.query(Subjects.id)
            .filter(
                Subjects.school_id == school_id,
                Subjects.class_id == class_id,
                Subjects.id != subject.id,
                or_(*duplicate_filters)
            )
            .first()
        )

        if existing_subject:

            return jsonify({
                "error": (
                    "Another subject with this name or code "
                    "already exists for this class."
                )
            }), 409

        # ---------------------------------------------------------
        # 8. Update subject
        # ---------------------------------------------------------

        subject.class_id = class_id
        subject.subject_code = subject_code
        subject.subject = subject_name
        subject.max_marks = max_marks
        subject.pass_marks = pass_marks
        subject.display_order = display_order
        subject.evaluation_type = evaluation_type
        subject.abbreviation = abbreviation
        subject.staff_id = staff_id
        subject.subject_type = subject_type
        subject.is_active = is_active

        # ---------------------------------------------------------
        # 9. Commit
        # ---------------------------------------------------------

        db.session.commit()

        return jsonify({
            "message": "Subject updated successfully.",
            "subject_id": subject.id
        }), 200

    except Exception as e:

        db.session.rollback()

        print("Error while updating subject:", e)

        return jsonify({
            "error": "Unable to update subject. Please try again later."
        }), 500

    