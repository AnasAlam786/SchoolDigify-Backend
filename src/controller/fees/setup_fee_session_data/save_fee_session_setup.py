from datetime import date
from decimal import Decimal, InvalidOperation

from flask import session, jsonify, Blueprint, request

from src.model import ClassData, FeeSessionData, FeeStructure
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required


save_fee_session_setup_api_bp = Blueprint(
    "save_fee_session_setup_api_bp",
    __name__
)

@save_fee_session_setup_api_bp.route(
    "/api/save_fee_session_setup",
    methods=["POST"]
)
@login_required
@permission_required("setup_session_fees_data")
def save_fee_session_setup():

    try:
        school_id = session["school_id"]
        session_id = int(session["session_id"])

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "error": "Invalid request data."
            }), 400

        classes_data = data.get("classes")

        if not isinstance(classes_data, list) or not classes_data:
            return jsonify({
                "error": "No fee setup data was submitted."
            }), 400

        # =========================================================
        # 1. Check whether this session has already been configured
        # =========================================================

        already_exists = (
            db.session.query(FeeSessionData.id)
            .filter(
                FeeSessionData.session_id == session_id
            ).first()
        )

        if already_exists:
            return jsonify({
                "error": (
                    "Fee setup for this session has already been completed."
                )
            }), 409

        # =========================================================
        # 2. Get classes belonging to this school
        # =========================================================

        school_classes = (
            db.session.query(
                ClassData.id,
                ClassData.CLASS
            ).filter(
                ClassData.school_id == school_id
            ).all()
        )

        class_map = {
            row.id: row.CLASS
            for row in school_classes
        }

        if not class_map:
            return jsonify({
                "error": (
                    "No classes are available. "
                    "Please add classes before setting up session fees."
                )
            }), 400

        # =========================================================
        # 3. Validate submitted classes
        # =========================================================

        submitted_class_ids = []

        for class_data in classes_data:

            if not isinstance(class_data, dict):
                return jsonify({
                    "error": "Invalid class data."
                }), 400

            class_id = class_data.get("class_id")

            try:
                class_id = int(class_id)
            except (TypeError, ValueError):
                return jsonify({
                    "error": "Invalid class ID."
                }), 400

            if class_id not in class_map:
                return jsonify({
                    "error": "One or more selected classes are invalid."
                }), 400

            submitted_class_ids.append(class_id)

        # Duplicate classes
        if len(submitted_class_ids) != len(set(submitted_class_ids)):
            return jsonify({
                "error": "Duplicate class data was submitted."
            }), 400

        # =========================================================
        # 4. Get permanent fee structure
        # =========================================================

        structures = (
            db.session.query(
                FeeStructure.id,
                FeeStructure.period_name,
                FeeStructure.due_day,
                FeeStructure.due_month,
                FeeStructure.year_increment
            )
            .filter(
                FeeStructure.school_id == school_id
            )
            .order_by(
                FeeStructure.sequence_number
            )
            .all()
        )

        if not structures:
            return jsonify({
                "error": (
                    "Fee structure is not configured. "
                    "Please set up the fee structure first."
                )
            }), 400

        structure_map = {
            row.id: row
            for row in structures
        }

        required_structure_ids = set(structure_map)

        # =========================================================
        # 5. Validate every class
        # =========================================================

        fee_rows = []
        submitted_pairs = set()

        for class_data in classes_data:

            class_id = int(class_data["class_id"])
            class_name = class_map[class_id]

            terms = class_data.get("terms")

            if not isinstance(terms, list):
                return jsonify({
                    "error": (
                        f"Invalid fee terms for {class_name}."
                    )
                }), 400

            # -----------------------------------------------------
            # Get submitted structure IDs
            # -----------------------------------------------------

            submitted_structure_ids = set()

            for term in terms:

                if not isinstance(term, dict):
                    return jsonify({
                        "error": (
                            f"Invalid fee term data for {class_name}."
                        )
                    }), 400

                structure_id = term.get("structure_id")

                try:
                    structure_id = int(structure_id)
                except (TypeError, ValueError):
                    return jsonify({
                        "error": (
                            f"Invalid fee structure for {class_name}."
                        )
                    }), 400

                # Structure must belong to this school
                if structure_id not in structure_map:
                    return jsonify({
                        "error": (
                            f"Invalid fee structure submitted "
                            f"for {class_name}."
                        )
                    }), 400

                # Duplicate term
                if structure_id in submitted_structure_ids:
                    return jsonify({
                        "error": (
                            f"Duplicate fee term submitted "
                            f"for {class_name}."
                        )
                    }), 400

                submitted_structure_ids.add(structure_id)

            # -----------------------------------------------------
            # Every permanent structure must be submitted
            # -----------------------------------------------------

            missing_structure_ids = (
                required_structure_ids - submitted_structure_ids
            )

            if missing_structure_ids:

                missing_periods = [
                    structure_map[structure_id].period_name
                    for structure_id in missing_structure_ids
                ]

                return jsonify({
                    "error": (
                        f"Fee setup is incomplete for {class_name}. "
                        f"Missing: {', '.join(missing_periods)}."
                    )
                }), 400

            # -----------------------------------------------------
            # Process terms
            # -----------------------------------------------------

            for term in terms:

                structure_id = int(term["structure_id"])
                structure = structure_map[structure_id]

                pair = (class_id, structure_id)

                if pair in submitted_pairs:
                    return jsonify({
                        "error": (
                            f"Duplicate fee term submitted "
                            f"for {class_name}."
                        )
                    }), 400

                submitted_pairs.add(pair)

                # =================================================
                # Amount
                # =================================================

                amount_value = term.get("amount")

                if amount_value is None or amount_value == "":
                    return jsonify({
                        "error": (
                            f"Fee amount is required for "
                            f"{class_name} — "
                            f"{structure.period_name}."
                        )
                    }), 400

                try:
                    amount = Decimal(str(amount_value))
                except (InvalidOperation, ValueError):
                    return jsonify({
                        "error": (
                            f"Invalid fee amount for "
                            f"{class_name} — "
                            f"{structure.period_name}."
                        )
                    }), 400

                if not amount.is_finite():
                    return jsonify({
                        "error": (
                            f"Invalid fee amount for "
                            f"{class_name} — "
                            f"{structure.period_name}."
                        )
                    }), 400

                if amount < 0:
                    return jsonify({
                        "error": (
                            f"Fee amount cannot be negative for "
                            f"{class_name} — "
                            f"{structure.period_name}."
                        )
                    }), 400

                # =================================================
                # Due date
                # =================================================

                due_date_value = term.get("due_date")

                # -----------------------------------------------
                # Mandatory date check
                #
                # If FeeStructure doesn't contain a default date,
                # the user MUST provide one.
                # -----------------------------------------------

                if not due_date_value:

                    if not (
                        structure.due_day
                        and structure.due_month
                    ):
                        return jsonify({
                            "error": (
                                f"Due date is required for "
                                f"{class_name} — "
                                f"{structure.period_name}."
                            )
                        }), 400

                    due_date = None

                else:

                    try:
                        due_date = date.fromisoformat(
                            due_date_value
                        )
                    except (TypeError, ValueError):
                        return jsonify({
                            "error": (
                                f"Invalid due date for "
                                f"{class_name} — "
                                f"{structure.period_name}."
                            )
                        }), 400

                # =================================================
                # Create database row
                # =================================================

                fee_rows.append(
                    FeeSessionData(
                        structure_id=structure_id,
                        amount=amount,
                        custom_due_date=due_date,
                        custom_start_date=None,
                        class_id=class_id,
                        session_id=session_id
                    )
                )

        # =========================================================
        # 6. Save everything in one transaction
        # =========================================================

        db.session.add_all(fee_rows)
        db.session.commit()

        return jsonify({
            "message": "Fee session setup saved successfully.",
            "rows_saved": len(fee_rows)
        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "Error while saving fee session setup:",
            repr(e)
        )

        return jsonify({
            "error": (
                "Unable to save the fee session setup "
                "due to a server error. Please try again later."
            )
        }), 500