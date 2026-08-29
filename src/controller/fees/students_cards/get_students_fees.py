# src/controller/fees/get_fee_api.py

from flask import session, request, jsonify, Blueprint

from sqlalchemy import select, func, case, and_
from src.controller.permissions.permission_required import permission_required
from src.model import (ClassData, FeeData, FeeHeads, FeeSessionData, FeeStructure, FeeTransaction, StudentsDB, StudentSessions)
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

get_students_fee_api_bp = Blueprint( 'get_students_fee_api_bp',   __name__)


from datetime import date


@get_students_fee_api_bp.route('/api/get_students_fees', methods=["GET"])
@login_required
@permission_required('view_fee_data')
def get_students_fees_api():

    try:
        current_session_id = session['session_id']
        school_id = session['school_id']

        # Starting year of current academic session.
        # Example: 2026 for session 2026-27
        current_session_year = int(session['session_id'])

        today = date.today()

        # ---------------------------------------------------------
        # 1. Get all students in current session
        # ---------------------------------------------------------

        students = (
            db.session.query(
                StudentsDB.id,
                StudentsDB.STUDENTS_NAME,
                StudentsDB.FATHERS_NAME,
                StudentsDB.SR,
                StudentsDB.PHONE,
                StudentsDB.GENDER,
                StudentsDB.IMAGE,

                StudentSessions.id.label("student_session_id"),
                StudentSessions.ROLL,
                StudentSessions.class_id,

                ClassData.CLASS,
                ClassData.display_order,
            )
            .join(
                StudentSessions,
                StudentSessions.student_id == StudentsDB.id
            )
            .join(
                ClassData,
                ClassData.id == StudentSessions.class_id
            )
            .filter(
                StudentsDB.school_id == school_id,
                StudentSessions.session_id == current_session_id,
            )
            .order_by(
                ClassData.display_order.asc(),
                StudentSessions.ROLL.asc()
            )
            .all()
        )

        # ---------------------------------------------------------
        # 2. Get all fee-session records
        # ---------------------------------------------------------

        fee_sessions = (
            db.session.query(
                FeeSessionData.id,
                FeeSessionData.class_id,
                FeeSessionData.amount,

                FeeStructure.due_day,
                FeeStructure.due_month,
                FeeStructure.year_increment,

                FeeSessionData.custom_due_date,

                FeeHeads.fee_type.label("fee_type"),
            )
            .join(
                FeeStructure,
                FeeStructure.id == FeeSessionData.structure_id
            )
            .outerjoin(
                FeeHeads,
                FeeHeads.id == FeeStructure.fee_type_id
            )
            .filter(
                FeeSessionData.session_id == current_session_id,
                FeeStructure.school_id == school_id
            )
            .all()
        )

        # ---------------------------------------------------------
        # 3. Get processed fee records
        # ---------------------------------------------------------

        student_session_ids = [
            student.student_session_id
            for student in students
        ]

        fee_records = []

        if student_session_ids:

            fee_records = (
                db.session.query(
                    FeeData.student_session_id,
                    FeeData.fee_session_id,
                    FeeData.transaction_id,
                    FeeData.paid_amount,
                    FeeData.fee_payment_status,

                    FeeTransaction.payment_date,
                    FeeTransaction.paid_amount.label("transaction_paid"),
                    FeeTransaction.discount,
                )
                .outerjoin(
                    FeeTransaction,
                    FeeTransaction.id == FeeData.transaction_id
                )
                .filter(
                    FeeData.student_session_id.in_(student_session_ids),
                    func.coalesce(FeeTransaction.is_deleted, False) == False
                )
                .all()
            )

        # ---------------------------------------------------------
        # 4. Group fee-session records by class
        # ---------------------------------------------------------

        fees_by_class = {}

        for fee in fee_sessions:

            fees_by_class.setdefault(
                fee.class_id, []
            ).append(fee)

        # ---------------------------------------------------------
        # 5. Group processed fees by student
        # ---------------------------------------------------------

        paid_fees_by_student = {}

        for fee in fee_records:

            paid_fees_by_student.setdefault(
                fee.student_session_id, []
            ).append(fee)

        # ---------------------------------------------------------
        # 6. Build student data
        # ---------------------------------------------------------

        data = []

        for student in students:

            class_fees = fees_by_class.get(
                student.class_id, []
            )

            paid_fees = paid_fees_by_student.get(
                student.student_session_id, []
            )

            # -----------------------------------------------------
            # Make lookup of paid fee records by fee_session_id
            # -----------------------------------------------------

            paid_fee_map = {}

            for fee in paid_fees:

                fee_session_id = fee.fee_session_id

                if fee_session_id not in paid_fee_map:
                    paid_fee_map[fee_session_id] = []

                paid_fee_map[fee_session_id].append(fee)

            # -----------------------------------------------------
            # Total fee
            # -----------------------------------------------------

            total_payable = sum(
                float(fee.amount or 0)
                for fee in class_fees
            )

            # -----------------------------------------------------
            # Separate tuition and one-time fees
            # -----------------------------------------------------

            tuition_fees = [
                fee
                for fee in class_fees
                if fee.fee_type == "Tuition Fee"
            ]

            one_time_fees = [
                fee
                for fee in class_fees
                if fee.fee_type != "Tuition Fee"
            ]

            total_tuition_fee = sum(
                float(fee.amount or 0)
                for fee in tuition_fees
            )

            total_one_time_fee = sum(
                float(fee.amount or 0)
                for fee in one_time_fees
            )

            # -----------------------------------------------------
            # Actual money paid
            # -----------------------------------------------------

            transaction_data = {}

            for fee in paid_fees:

                transaction_id = fee.transaction_id

                if transaction_id is not None:

                    transaction_data[transaction_id] = {
                        "paid": float(
                            fee.transaction_paid or 0
                        ),
                        "discount": float(
                            fee.discount or 0
                        )
                    }

            actual_paid_amount = sum(
                transaction["paid"]
                for transaction in transaction_data.values()
            )

            total_discount = sum(
                transaction["discount"]
                for transaction in transaction_data.values()
            )

            # -----------------------------------------------------
            # Paid tuition / one-time amounts
            # -----------------------------------------------------

            paid_tuition_fee = 0
            paid_one_time_fee = 0

            for fee in class_fees:

                student_fee_records = paid_fee_map.get(
                    fee.id, []
                )

                settled_amount = sum(
                    float(record.paid_amount or 0)
                    for record in student_fee_records
                )

                if fee.fee_type == "Tuition Fee":
                    paid_tuition_fee += settled_amount
                else:
                    paid_one_time_fee += settled_amount

            # -----------------------------------------------------
            # Tuition months
            # -----------------------------------------------------

            total_months = len(tuition_fees)

            paid_tuition_fee_ids = {
                fee_id
                for fee_id, records in paid_fee_map.items()
                if fee_id in {
                    tuition_fee.id
                    for tuition_fee in tuition_fees
                }
                and any(
                    record.fee_payment_status == "PAID"
                    for record in records
                )
            }

            paid_months = len(
                paid_tuition_fee_ids
            )

            # -----------------------------------------------------
            # Calculate due and upcoming fees
            # -----------------------------------------------------

            due_amount = 0
            upcoming_amount = 0

            due_months = 0
            upcoming_months = 0

            for fee in class_fees:

                student_fee_records = paid_fee_map.get(
                    fee.id, []
                )

                is_paid = any(
                    record.fee_payment_status == "PAID"
                    for record in student_fee_records
                )

                # Already paid → not due/upcoming
                if is_paid: continue

                # -------------------------------------------------
                # Determine due date
                # -------------------------------------------------

                if fee.custom_due_date:
                    due_date = fee.custom_due_date

                else:

                    due_year = (
                        current_session_year + int(fee.year_increment or 0)
                    )

                    due_date = date(
                        due_year, int(fee.due_month), int(fee.due_day)
                    )

                # -------------------------------------------------
                # Past/today = due
                # Future = upcoming
                # -------------------------------------------------

                if due_date <= today:

                    due_amount += float(
                        fee.amount or 0
                    )

                    if fee.fee_type == "Tuition Fee":
                        due_months += 1

                else:

                    upcoming_amount += float(
                        fee.amount or 0
                    )

                    if fee.fee_type == "Tuition Fee":
                        upcoming_months += 1

            # -----------------------------------------------------
            # Last payment date
            # -----------------------------------------------------

            payment_dates = [
                fee.payment_date
                for fee in paid_fees
                if fee.payment_date
            ]

            last_payment_date = (
                max(payment_dates)
                if payment_dates
                else None
            )

            if last_payment_date:

                last_payment_date = (
                    last_payment_date.strftime(
                        "%d %b %Y"
                    )
                )

            # -----------------------------------------------------
            # Fee status
            # -----------------------------------------------------

            if due_amount > 0:
                fee_status = "Due"

            elif upcoming_amount > 0:
                fee_status = "Upcoming"

            else:
                fee_status = "Paid"

            # -----------------------------------------------------
            # Final student object
            # -----------------------------------------------------

            data.append({

                "id": student.id,
                "student_session_id": student.student_session_id,

                "STUDENTS_NAME": student.STUDENTS_NAME,
                "FATHERS_NAME": student.FATHERS_NAME,
                "SR": student.SR,

                "CLASS": student.CLASS,
                "class_display_order": student.display_order,
                "ROLL": student.ROLL,

                "PHONE": student.PHONE,
                "GENDER": student.GENDER,
                "IMAGE": student.IMAGE or "",

                # Overall
                "totalPayable": total_payable,
                "actualPaidAmount": actual_paid_amount,
                "discount": total_discount,
                "lastPaymentDate": last_payment_date,


                # Due / upcoming
                "dueAmount": due_amount,
                "upcomingAmount": upcoming_amount,

                # Tuition
                "totalTuitionFee": total_tuition_fee,
                "paidTuitionFee": paid_tuition_fee,

                # One-time
                "totalOneTimeFee": total_one_time_fee,
                "paidOneTimeFee": paid_one_time_fee,

                # Tuition months
                "totalMonths": total_months,
                "paidMonths": paid_months,
                "dueMonths": due_months,
                "upcomingMonths": upcoming_months,

                

                "feeStatus": fee_status,
            })

        # ---------------------------------------------------------
        # 7. Return response
        # ---------------------------------------------------------

        return jsonify({
            "students_fee_data": data
        }), 200

    except KeyError as e:

        return jsonify({
            "error": f"Missing session information: {str(e)}"
        }), 400

    except Exception as e:

        db.session.rollback()

        print("Database error:", e)

        return jsonify({
            "error": "Unable to get students fee data because of a database error."
        }), 500

    except Exception as e:

        db.session.rollback()

        print("Error in get_students_fees_api:", e)

        return jsonify({
            "error": "Unable to get students fee data."
        }), 500

      
    