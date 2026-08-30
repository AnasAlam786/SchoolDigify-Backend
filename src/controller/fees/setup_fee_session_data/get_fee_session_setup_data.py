from datetime import date

from flask import session, jsonify, Blueprint

from src.model import ClassData, FeeHeads, FeeSessionData, FeeStructure
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required


get_fee_session_setup_data_api_bp = Blueprint(
    "get_fee_session_setup_data_api_bp",
    __name__
)


@get_fee_session_setup_data_api_bp.route(
    "/api/get_fee_session_setup_data",
    methods=["GET"]
)
@login_required
@permission_required("setup_session_fees_data")
def get_fee_session_setup():

    try:
        current_session_id = int(session["session_id"])
        school_id = session["school_id"]

        previous_session_id = int(current_session_id - 1)

        # ---------------------------------------------------------
        # 1. Get all classes
        # ---------------------------------------------------------
        classes = (
            db.session.query(
                ClassData.id.label("class_id"),
                ClassData.CLASS
            )
            .filter(
                ClassData.school_id == school_id
            )
            .order_by(
                ClassData.display_order.asc()
            )
            .all()
        )

        if not classes:
            return jsonify({
                "error": "No classes are available. Please add at least one class before setting up session fees."
            }), 404

        # ---------------------------------------------------------
        # 2. Get permanent fee structure
        # ---------------------------------------------------------

        structures = (
            db.session.query(
                FeeStructure.id.label("structure_id"),
                FeeStructure.sequence_number,
                FeeStructure.period_name,
                FeeStructure.fee_type_id,
                FeeStructure.due_day,
                FeeStructure.due_month,
                FeeStructure.year_increment,
                FeeHeads.fee_type
            )
            .join(
                FeeHeads,
                FeeHeads.id == FeeStructure.fee_type_id
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
                "error": "Fee structure is not configured. Please set up the fee structure before configuring session fees."
            }), 404

        # ---------------------------------------------------------
        # 3. Get previous session fee data
        # ---------------------------------------------------------

        previous_data = {}
        if previous_session_id > 0:

            previous_rows = (
                db.session.query(
                    FeeSessionData.structure_id,
                    FeeSessionData.class_id,
                    FeeSessionData.amount,
                    FeeSessionData.custom_due_date
                )
                .filter(
                    FeeSessionData.session_id == previous_session_id
                )
                .all()
            )

            previous_data = {
                (row.class_id, row.structure_id): row
                for row in previous_rows
            }


        # ---------------------------------------------------------
        # 4. Prepare response
        # ---------------------------------------------------------

        result = []

        # Assumes session_id represents the starting year.
        previous_year = current_session_id

        for class_row in classes:

            terms = []

            for structure in structures:

                previous = previous_data.get(
                    (class_row.class_id, structure.structure_id)
                )

                # Amount from previous session
                amount = previous.amount if previous else None

                # -------------------------------------------------
                # Due date
                # -------------------------------------------------


                is_due_date_mandatory = True
                if previous and previous.custom_due_date:

                    due_date = previous.custom_due_date
                    is_due_date_mandatory = False

                elif structure.due_day and structure.due_month:

                    due_year = (
                        previous_year +
                        (structure.year_increment or 0)
                    )

                    due_date = date(
                        due_year,
                        structure.due_month,
                        structure.due_day
                    )
                    is_due_date_mandatory = False

                else:
                    due_date = None
                    is_due_date_mandatory = True

                terms.append({
                    "is_due_date_mandatory":is_due_date_mandatory, 
                    "structure_id": structure.structure_id,
                    "period_name": structure.period_name,
                    "fee_type": structure.fee_type,
                    "amount": amount,
                    "due_date": (
                        due_date.isoformat()
                        if due_date
                        else None
                    )
                })

            result.append({
                "class_id": class_row.class_id,
                "class_name": class_row.CLASS,
                "terms": terms
            })

        return jsonify({
            "fee_setup_data": result
        }), 200

    except Exception as e:
        print(e)
        db.session.rollback()

        # Use your application's logger here
        # logger.exception("Failed to load fee session setup data")

        return jsonify({
            "error": "Unable to load the fee session setup. Please try again later."
        }), 500