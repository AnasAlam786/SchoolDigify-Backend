from flask import request, session, jsonify, Blueprint
from sqlalchemy import exists, or_

from src import db

from src.model import (
    ClassData,
    ClassExams,
    Exams,
    StudentMarks
)

from src.controller.auth.login_required import login_required


exam_setup_api_bp = Blueprint(
    "exam_setup_api_bp",
    __name__
)


# ================================================================
# GET EXAM DATA GROUPED BY EXAM
# ================================================================

@exam_setup_api_bp.route(
    "/api/get_exam_data",
    methods=["GET"]
)
@login_required
def get_exams():

    try:
        # ---------------------------------------------------------
        # 1. Get current school
        # ---------------------------------------------------------

        school_id = session["school_id"]

        # ---------------------------------------------------------
        # 2. Check whether marks exist for each exam
        #
        # If even one mark exists for an exam:
        #     editable = False
        #
        # Otherwise:
        #     editable = True
        # ---------------------------------------------------------

        has_marks = exists().where(
            StudentMarks.exam_id == Exams.id
        )

        # ---------------------------------------------------------
        # 3. Get exams + their assigned classes
        # ---------------------------------------------------------

        rows = (
            db.session.query(
                Exams.id.label("exam_id"),
                Exams.exam_name,
                Exams.exam_code,
                Exams.weightage,
                Exams.display_order,
                Exams.term,
                Exams.is_enabled,

                ClassData.id.label("class_id"),
                ClassData.CLASS.label("class_name"),
                ClassData.display_order.label("class_display_order"),

                has_marks.label("has_marks")
            )
            .join(
                ClassExams,
                ClassExams.exam_id == Exams.id
            )
            .join(
                ClassData,
                ClassData.id == ClassExams.class_id
            )
            .filter(
                Exams.school_id == school_id,
                ClassData.school_id == school_id
            )
            .order_by(
                Exams.display_order,
                ClassData.display_order
            )
            .all()
        )

        # ---------------------------------------------------------
        # 4. Group classes under each exam
        # ---------------------------------------------------------

        exams = {}

        for row in rows:

            # -----------------------------------------------------
            # Create exam only once
            # -----------------------------------------------------

            if row.exam_id not in exams:

                exams[row.exam_id] = {
                    "id": row.exam_id,

                    "exam_name": row.exam_name,

                    "exam_code": row.exam_code,

                    "weightage": (
                        float(row.weightage)
                        if row.weightage is not None
                        else None
                    ),

                    "display_order": row.display_order,

                    "term": row.term,

                    "is_enabled": row.is_enabled,

                    # If marks exist, exam cannot be edited
                    "editable": not bool(row.has_marks),

                    "classes": []
                }

            # -----------------------------------------------------
            # Add class to this exam
            # -----------------------------------------------------

            exams[row.exam_id]["classes"].append({
                "class_id": row.class_id,
                "class_name": row.class_name
            })

        # ---------------------------------------------------------
        # 5. Return response
        # ---------------------------------------------------------

        return jsonify({
            "exams": list(exams.values())
        }), 200

    except Exception as e:

        print("Error while getting school exams:", e)

        db.session.rollback()

        return jsonify({
            "error": "Unable to load school exams. Please try again later."
        }), 500



# ================================================================
# CREATE EXAM
# ================================================================

@exam_setup_api_bp.route(
    "/api/create_exam",
    methods=["POST"]
)
@login_required
def create_exam():
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

        exam_name = data.get("exam_name")
        exam_code = data.get("exam_code")
        weightage = data.get("weightage")
        display_order = data.get("display_order")
        term = data.get("term")
        is_enabled = data.get("is_enabled", True)

        class_ids = data.get("class_ids", [])

        # ---------------------------------------------------------
        # 3. Validate required fields
        # ---------------------------------------------------------

        if not exam_name:
            return jsonify({
                "error": "Exam name is required."
            }), 400

        if not exam_code:
            return jsonify({
                "error": "Exam code is required."
            }), 400

        if not isinstance(class_ids, list):
            return jsonify({
                "error": "class_ids must be a list."
            }), 400

        # Remove duplicate class IDs
        class_ids = list(set(class_ids))

        # ---------------------------------------------------------
        # 4. Check duplicate exam code
        # ---------------------------------------------------------

        existing_exam = (
            db.session.query(Exams.id)
            .filter(
                Exams.school_id == school_id,
                or_(
                    Exams.exam_name == exam_name,
                    Exams.exam_code == exam_code
                )
            )
            .first()
        )

        if existing_exam:
            return jsonify({
                "error": "An exam with this name or code already exists."
            }), 409

        # ---------------------------------------------------------
        # 5. Validate classes
        # ---------------------------------------------------------

        if class_ids:
            valid_class_ids = {
                row.id
                for row in (
                    db.session.query(ClassData.id)
                    .filter(
                        ClassData.id.in_(class_ids),
                        ClassData.school_id == school_id
                    )
                    .all()
                )
            }

            invalid_class_ids = [
                class_id
                for class_id in class_ids
                if class_id not in valid_class_ids
            ]

            if invalid_class_ids:

                return jsonify({
                    "error": "One or more classes do not belong to this school.",
                    "invalid_class_ids": invalid_class_ids
                }), 400

        # ---------------------------------------------------------
        # 6. Create exam
        # ---------------------------------------------------------

        exam = Exams(
            school_id=school_id,
            exam_name=exam_name,
            exam_code=exam_code,
            weightage=weightage,
            display_order=display_order,
            term=term,
            is_enabled=is_enabled
        )

        db.session.add(exam)

        # Get generated exam ID
        db.session.flush()

        # ---------------------------------------------------------
        # 7. Assign classes
        # ---------------------------------------------------------

        for class_id in class_ids:

            db.session.add(
                ClassExams(
                    exam_id=exam.id,
                    class_id=class_id
                )
            )

        # ---------------------------------------------------------
        # 8. Commit
        # ---------------------------------------------------------

        db.session.commit()

        return jsonify({
            "message": "Exam created successfully.",
            "exam_id": exam.id
        }), 201

    except Exception as e:

        db.session.rollback()

        print("Error while creating exam:", e)

        return jsonify({
            "error": "Unable to create exam. Please try again later."
        }), 500



# ================================================================
# UPDATE EXAM
# ================================================================

@exam_setup_api_bp.route(
    "/api/update_exam/<int:exam_id>",
    methods=["PUT"]
)
@login_required
def update_exam(exam_id):
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

        exam_name = data.get("exam_name")
        exam_code = data.get("exam_code")
        weightage = data.get("weightage")
        display_order = data.get("display_order")
        term = data.get("term")
        is_enabled = data.get("is_enabled")

        class_ids = data.get("class_ids", [])

        # ---------------------------------------------------------
        # 3. Validate required fields
        # ---------------------------------------------------------

        if not exam_name:
            return jsonify({
                "error": "Exam name is required."
            }), 400

        if not exam_code:
            return jsonify({
                "error": "Exam code is required."
            }), 400

        if not isinstance(class_ids, list):
            return jsonify({
                "error": "class_ids must be a list."
            }), 400

        # Remove duplicate class IDs
        class_ids = list(set(class_ids))

        # ---------------------------------------------------------
        # 4. Find exam
        #
        # school_id check is important for security.
        # ---------------------------------------------------------

        exam = (
            db.session.query(Exams)
            .filter(
                Exams.id == exam_id,
                Exams.school_id == school_id
            )
            .first()
        )

        if not exam:

            return jsonify({
                "error": "Exam not found."
            }), 404

        # ---------------------------------------------------------
        # 5. Check whether marks already exist
        # ---------------------------------------------------------

        has_marks = (
            db.session.query(
                exists().where(
                    StudentMarks.exam_id == exam.id
                )
            )
            .scalar()
        )

        if has_marks:

            return jsonify({
                "error": (
                    "This exam cannot be modified because "
                    "marks have already been entered."
                ),
                "editable": False
            }), 409

        # ---------------------------------------------------------
        # 6. Check duplicate exam code
        # ---------------------------------------------------------

        existing_exam = (
            db.session.query(Exams.id)
            .filter(
                Exams.school_id == school_id,
                Exams.id != exam.id,
                or_(
                    Exams.exam_name == exam_name,
                    Exams.exam_code == exam_code
                )
            )
            .first()
        )

        if existing_exam:

            return jsonify({
                "error": "Another exam with this name or code already exists."
            }), 409

        # ---------------------------------------------------------
        # 7. Validate classes
        # ---------------------------------------------------------

        if class_ids:

            valid_class_ids = {
                row.id
                for row in (
                    db.session.query(ClassData.id)
                    .filter(
                        ClassData.id.in_(class_ids),
                        ClassData.school_id == school_id
                    )
                    .all()
                )
            }

            invalid_class_ids = [
                class_id
                for class_id in class_ids
                if class_id not in valid_class_ids
            ]

            if invalid_class_ids:

                return jsonify({
                    "error": "One or more classes do not belong to this school.",
                    "invalid_class_ids": invalid_class_ids
                }), 400

        # ---------------------------------------------------------
        # 8. Update exam
        # ---------------------------------------------------------

        exam.exam_name = exam_name
        exam.exam_code = exam_code
        exam.weightage = weightage
        exam.display_order = display_order
        exam.term = term
        exam.is_enabled = is_enabled

        # ---------------------------------------------------------
        # 9. Replace class assignments
        # ---------------------------------------------------------

        (
            db.session.query(ClassExams)
            .filter(
                ClassExams.exam_id == exam.id
            )
            .delete(
                synchronize_session=False
            )
        )

        for class_id in class_ids:

            db.session.add(
                ClassExams(
                    exam_id=exam.id,
                    class_id=class_id
                )
            )

        # ---------------------------------------------------------
        # 10. Commit
        # ---------------------------------------------------------

        db.session.commit()

        return jsonify({
            "message": "Exam updated successfully.",
            "exam_id": exam.id
        }), 200

    except Exception as e:

        db.session.rollback()

        print("Error while updating exam:", e)

        return jsonify({
            "error": "Unable to update exam. Please try again later."
        }), 500 



    