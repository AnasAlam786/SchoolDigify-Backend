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
# GET EXAMS DATA
# ================================================================

@exam_setup_api_bp.route("/api/get_exam_data", methods=["GET"])
@login_required
def get_exams():

    try:
        school_id = session.get("school_id")
        # ========================================================
        # Check whether marks already exist for each exam
        # ========================================================

        has_marks = exists().where(
            StudentMarks.exam_id == Exams.id
        )

        # ========================================================
        # Get exams and their assigned classes
        # through ClassExams
        # ========================================================

        rows = (
            db.session.query(
                Exams.id.label("exam_id"),
                Exams.exam_name,
                Exams.exam_code,
                Exams.weightage,
                Exams.display_order,
                Exams.term,
                ClassData.id.label("class_id"),
                ClassData.CLASS.label("class_name"),
                ClassData.display_order.label(
                    "class_display_order"
                ),
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
        exams = {}
        for row in rows:
            exam_key = row.exam_id

            if exam_key not in exams:

                exams[exam_key] = {
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
                    "editable": not bool(row.has_marks),
                    "classes": []
                }

            # ----------------------------------------------------
            # Add class
            # ----------------------------------------------------

            exams[exam_key]["classes"].append({
                "class_id": row.class_id,
                "class_name": row.class_name
            })

        # ========================================================
        # Response
        # ========================================================

        return jsonify({
            "exams": list(exams.values())
        }), 200

    except Exception as e:
        db.session.rollback()
        print("Error while getting exams:", e)
        return jsonify({
            "error": (
                "Unable to load school exams. "
                "Please try again later."
            )
        }), 500


# ================================================================
# CREATE EXAM
# ================================================================

@exam_setup_api_bp.route("/api/create_exam", methods=["POST"])
@login_required
def create_exam():
    try:
        school_id = session.get("school_id")
        if not school_id:
            return jsonify({
                "error": "School session not found."
            }), 401

        # ========================================================
        # Request
        # ========================================================

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "Request body is required."
            }), 400

        # ========================================================
        # Read data
        # ========================================================

        exam_name = str(
            data.get("exam_name", "")
        ).strip()

        exam_code = str(
            data.get("exam_code", "")
        ).strip()

        weightage = data.get("weightage")
        display_order = data.get("display_order")
        term = data.get("term")

        class_ids = data.get("class_ids")

        # ========================================================
        # Validate required fields
        # ========================================================

        if not exam_name:
            return jsonify({
                "error": "Exam name is required."
            }), 400

        if not exam_code:
            return jsonify({
                "error": "Exam code is required."
            }), 400

        if weightage is None:
            return jsonify({
                "error": "Weightage is required."
            }), 400

        if display_order is None:
            return jsonify({
                "error": "Display order is required."
            }), 400

        if term is None:
            return jsonify({
                "error": "Term is required."
            }), 400

        # ========================================================
        # Validate class_ids
        # ========================================================

        if not isinstance(class_ids, list) or not class_ids:
            return jsonify({
                "error": "At least one class is required."
            }), 400

        try:

            class_ids = {
                int(class_id)
                for class_id in class_ids
            }

        except (TypeError, ValueError):

            return jsonify({
                "error": "Invalid class ID."
            }), 400

        # ========================================================
        # Validate numeric values
        # ========================================================

        try:
            weightage = float(weightage)
        except (TypeError, ValueError):
            return jsonify({
                "error": "Weightage must be numeric."
            }), 400

        try:
            display_order = int(display_order)
        except (TypeError, ValueError):

            return jsonify({
                "error": "Display order must be an integer."
            }), 400

        try:
            term = int(term)
        except (TypeError, ValueError):

            return jsonify({
                "error": "Term must be an integer."
            }), 400

        # ========================================================
        # Find duplicate exam
        #
        # Same school:
        #     exam name cannot duplicate
        #     exam code cannot duplicate
        # ========================================================

        duplicate = (
            db.session.query(Exams.id)
            .filter(
                Exams.school_id == school_id,
                or_(
                    Exams.exam_name.ilike(exam_name),
                    Exams.exam_code.ilike(exam_code)
                )
            )
            .first()
        )

        if duplicate:
            return jsonify({
                "error": (
                    "An exam with this name or code "
                    "already exists."
                )
            }), 409

        # ========================================================
        # Validate classes
        # ========================================================

        valid_class_ids = {
            row.id
            for row in (
                db.session.query(
                    ClassData.id.label("id")
                )
                .filter(
                    ClassData.id.in_(class_ids),
                    ClassData.school_id == school_id
                )
                .all()
            )
        }

        if valid_class_ids != class_ids:

            return jsonify({
                "error": (
                    "One or more selected classes "
                    "are invalid."
                )
            }), 404

        # ========================================================
        # Create exam
        # ========================================================

        exam = Exams(
            school_id=school_id,
            exam_name=exam_name,
            exam_code=exam_code,
            weightage=weightage,
            display_order=display_order,
            term=term,
        )

        db.session.add(exam)

        # Get generated ID
        db.session.flush()

        # ========================================================
        # Create ClassExams relationships
        # ========================================================

        for class_id in sorted(class_ids):

            db.session.add(
                ClassExams(
                    exam_id=exam.id,
                    class_id=class_id
                )
            )

        # ========================================================
        # Commit
        # ========================================================

        db.session.commit()

        return jsonify({
            "message": "Exam created successfully.",
            "exam_id": exam.id,
            "class_ids": sorted(class_ids)
        }), 201

    except Exception as e:

        db.session.rollback()

        print("Error while creating exam:", e)

        return jsonify({
            "error": (
                "Unable to create exam. "
                "Please try again later."
            )
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
        school_id = session.get("school_id")
        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "Request body is required."
            }), 400

        # ========================================================
        # Read data
        # ========================================================

        exam_name = str(
            data.get("exam_name", "")
        ).strip()

        exam_code = str(
            data.get("exam_code", "")
        ).strip()

        weightage = data.get("weightage")
        display_order = data.get("display_order")
        term = data.get("term")

        class_ids = data.get("class_ids")

        # ========================================================
        # Validate required fields
        # ========================================================

        if not exam_name:
            return jsonify({
                "error": "Exam name is required."
            }), 400

        if not exam_code:
            return jsonify({
                "error": "Exam code is required."
            }), 400

        if weightage is None:
            return jsonify({
                "error": "Weightage is required."
            }), 400

        if display_order is None:
            return jsonify({
                "error": "Display order is required."
            }), 400

        if term is None:
            return jsonify({
                "error": "Term is required."
            }), 400

        # ========================================================
        # Validate class_ids
        # ========================================================

        if not isinstance(class_ids, list) or not class_ids:

            return jsonify({
                "error": "At least one class is required."
            }), 400

        try:

            class_ids = {
                int(class_id)
                for class_id in class_ids
            }

        except (TypeError, ValueError):

            return jsonify({
                "error": "Invalid class ID."
            }), 400

        # ========================================================
        # Validate numeric values
        # ========================================================

        try:

            weightage = float(weightage)

        except (TypeError, ValueError):

            return jsonify({
                "error": "Weightage must be numeric."
            }), 400

        try:

            display_order = int(display_order)

        except (TypeError, ValueError):

            return jsonify({
                "error": "Display order must be an integer."
            }), 400

        try:

            term = int(term)

        except (TypeError, ValueError):

            return jsonify({
                "error": "Term must be an integer."
            }), 400

        # ========================================================
        # Find exam
        #
        # school_id check is essential for multi-school security.
        # ========================================================

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

        # ========================================================
        # Check whether marks exist
        #
        # If marks exist, the exam becomes immutable.
        # ========================================================

        has_marks = (
            db.session.query(StudentMarks.id)
            .filter(
                StudentMarks.exam_id == exam.id
            )
            .first()
        )

        if has_marks:

            return jsonify({
                "error": (
                    "This exam cannot be edited because "
                    "marks have already been entered."
                ),
                "editable": False
            }), 409

        # ========================================================
        # Check duplicate exam
        # ========================================================

        duplicate = (
            db.session.query(Exams.id)
            .filter(
                Exams.school_id == school_id,
                Exams.id != exam.id,
                or_(
                    Exams.exam_name.ilike(exam_name),
                    Exams.exam_code.ilike(exam_code)
                )
            )
            .first()
        )

        if duplicate:

            return jsonify({
                "error": (
                    "Another exam with this name or code "
                    "already exists."
                )
            }), 409

        # ========================================================
        # Validate classes
        # ========================================================

        valid_class_ids = {
            row.id
            for row in (
                db.session.query(
                    ClassData.id.label("id")
                )
                .filter(
                    ClassData.id.in_(class_ids),
                    ClassData.school_id == school_id
                )
                .all()
            )
        }

        if valid_class_ids != class_ids:

            return jsonify({
                "error": (
                    "One or more selected classes "
                    "are invalid."
                )
            }), 404

        # ========================================================
        # Update Exams
        # ========================================================

        exam.exam_name = exam_name
        exam.exam_code = exam_code
        exam.weightage = weightage
        exam.display_order = display_order
        exam.term = term

        # ========================================================
        # Synchronize ClassExams
        #
        # Same pattern as your Subject Setup API:
        #
        # Existing:
        #     Class 1
        #     Class 2
        #
        # New:
        #     Class 2
        #     Class 3
        #
        # Result:
        #     Class 1 -> removed
        #     Class 2 -> retained
        #     Class 3 -> added
        # ========================================================

        existing = (
            db.session.query(ClassExams)
            .filter(
                ClassExams.exam_id == exam.id
            )
            .all()
        )

        existing_by_class = {
            class_exam.class_id: class_exam
            for class_exam in existing
        }

        # --------------------------------------------------------
        # Remove old class assignments
        # --------------------------------------------------------

        for class_id, class_exam in existing_by_class.items():
            if class_id not in class_ids:
                db.session.delete(class_exam)

        # --------------------------------------------------------
        # Add new class assignments
        # --------------------------------------------------------

        for class_id in class_ids:
            if class_id not in existing_by_class:
                db.session.add(
                    ClassExams(
                        exam_id=exam.id,
                        class_id=class_id
                    )
                )

        # ========================================================
        # Commit
        # ========================================================

        db.session.commit()

        return jsonify({
            "message": "Exam updated successfully.",
            "exam_id": exam.id,
            "class_ids": sorted(class_ids)
        }), 200

    except Exception as e:

        db.session.rollback()

        print("Error while updating exam:", e)

        return jsonify({
            "error": (
                "Unable to update exam. "
                "Please try again later."
            )
        }), 500