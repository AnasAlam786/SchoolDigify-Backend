# src/controller/fees/get_fee_api.py

from flask import session, jsonify, Blueprint

from sqlalchemy import or_, select, func, case, and_
from src.controller.permissions.permission_required import permission_required
from src.model import (ClassData, FeeData, FeeHeads, FeeSessionData, FeeStructure, FeeTransaction, RTEInfo, StudentsDB, StudentSessions)
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from datetime import date
from collections import defaultdict
from decimal import Decimal
from src.controller.fees.utils.fee_calculations import (
    ZERO,
    aggregate_fee_allocations,
    calculate_fee_balance,
    json_money,
)

from src.model.ClassAccess import ClassAccess


def build_basic_student_record(student):
    """Return the basic student payload that is safe to expose for RTE students.

    Fee-related keys are intentionally omitted here so the client receives
    only the identifying/classification fields for an RTE child.
    """
    return {
        "id": student.id,
        "student_session_id": student.student_session_id,
        "STUDENTS_NAME": student.STUDENTS_NAME,
        "FATHERS_NAME": student.FATHERS_NAME,
        "isRTE": bool(student.is_RTE),
        "SR": student.SR,
        "CLASS": student.CLASS,
        "class_id": student.class_id,
        "ROLL": student.ROLL,
        "PHONE": student.PHONE,
        "GENDER": student.GENDER,
        "IMAGE": student.IMAGE or "",
    }


get_students_fee_api_bp = Blueprint( 'get_students_fee_api_bp',   __name__)


@get_students_fee_api_bp.route("/api/get_students_fees", methods=["GET"])
@login_required
@permission_required("view_fee_data")
def get_students_fees_api():

    try:
        # ---------------------------------------------------------
        # 1. Session / school information
        # ---------------------------------------------------------

        school_id = session["school_id"]
        current_session_id = session["session_id"]

        # Your current system appears to use the session ID as
        # the starting academic year, e.g. 2026 -> session 2026-27.
        current_session_year = int(current_session_id)

        today = date.today()

        ZERO = Decimal("0")

        # ---------------------------------------------------------
        # 2. Get students in current session
        # ---------------------------------------------------------

        user_id = session["user_id"]
        authorized_class_ids = db.session.query(ClassAccess.class_id).filter(
            ClassAccess.staff_id == user_id
        )

        students = (
            db.session.query(
                StudentsDB.id,
                StudentsDB.STUDENTS_NAME,
                StudentsDB.FATHERS_NAME,
                StudentsDB.SR, StudentsDB.PHONE,
                StudentsDB.GENDER, StudentsDB.IMAGE,

                StudentSessions.id.label("student_session_id"),
                StudentSessions.ROLL, StudentSessions.class_id,

                ClassData.CLASS,

                func.coalesce(
                    RTEInfo.is_RTE,
                    False
                ).label("is_RTE"),
            )
            .join(
                StudentSessions,
                StudentSessions.student_id == StudentsDB.id,
            )
            .join(
                ClassData,
                ClassData.id == StudentSessions.class_id,
            )
            .outerjoin(
                RTEInfo,
                RTEInfo.student_id == StudentsDB.id,
            )
            .filter(
                StudentsDB.school_id == school_id,
                StudentSessions.session_id == current_session_id,
                StudentSessions.class_id.in_(authorized_class_ids),
            )
            .all()
        )

        if not students:
            return jsonify({
                "ERROR_CODE":"NO_STUDENTS",
                "error": "No students have been added for this session yet. Add students to get started."
            }), 404



        # Determine whether any fee calculations are actually needed.
        # RTE students should be represented through their basic student
        # payload only and must not trigger the fee-setup or fee-payment
        # dependency checks in this route.
        non_rte_students = [
            student for student in students
            if not bool(student.is_RTE)
        ]

        fee_sessions = []
        fees_by_class = defaultdict(list)
        paid_fees_by_student = {}

        if non_rte_students:
            # ---------------------------------------------------------
            # 3. Get fee structure for current session
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
                    FeeStructure.id == FeeSessionData.structure_id,
                )
                .outerjoin(
                    FeeHeads,
                    FeeHeads.id == FeeStructure.fee_type_id,
                )
                .filter(
                    FeeSessionData.session_id == current_session_id,
                    FeeStructure.school_id == school_id,
                    FeeSessionData.class_id.in_(authorized_class_ids),
                )
                .all()
            )
            if not fee_sessions:
                return jsonify({
                    "ERROR_CODE":"NO_SESSION_FEE_SETUP",
                    "error": "Fee Session is not setup. Please set up the fee session data before start paying fees."
                }), 404

            # ---------------------------------------------------------
            # 4. Group fee structure by class
            # ---------------------------------------------------------

            for fee in fee_sessions:
                fees_by_class[fee.class_id].append(fee)

            # ---------------------------------------------------------
            # 5. Get payment records
            # ---------------------------------------------------------

            student_session_ids = [
                student.student_session_id
                for student in non_rte_students
            ]

            if student_session_ids:

                fee_records = (
                    db.session.query(
                        FeeData.student_session_id,
                        FeeData.fee_session_id,
                        FeeData.transaction_id,
                        FeeData.paid_amount,
                        FeeData.late_fee,

                        FeeTransaction.paid_amount.label("transaction_paid_amount"),
                        FeeTransaction.discount,
                        FeeTransaction.payment_date,
                    )
                    .outerjoin(
                        FeeTransaction,
                        FeeTransaction.id == FeeData.transaction_id,
                    )
                    .filter(
                        FeeData.student_session_id.in_(student_session_ids),
                        or_(
                            FeeTransaction.id.is_(None),
                            and_(
                                FeeTransaction.school_id == school_id,
                                FeeTransaction.session_id == current_session_id,
                                or_(
                                    FeeTransaction.is_deleted.is_(False),
                                    FeeTransaction.is_deleted.is_(None),
                                ),
                            ),
                        ),
                    )
                    .all()
                )
                paid_fees_by_student = aggregate_fee_allocations(fee_records)

        # ---------------------------------------------------------
        # 6. Build student response
        # ---------------------------------------------------------

        data = []

        for student in students:

            # RTE students must only return the base profile payload and
            # omit all fee-derived fields such as payable, paid, due, and
            # status. This keeps the response consistent with the request.
            if bool(student.is_RTE):
                data.append(build_basic_student_record(student))
                continue

            # -----------------------------------------------------
            # Fee structure for this student's class
            # -----------------------------------------------------

            class_fees = fees_by_class.get(
                student.class_id,
                [],
            )

            # -----------------------------------------------------
            # Payment records for this student
            # -----------------------------------------------------

            student_payment_map = {
                fee_id: payment
                for (student_session_id, fee_id), payment in paid_fees_by_student.items()
                if student_session_id == student.student_session_id
            }

            # -----------------------------------------------------
            # Separate tuition and one-time fees
            # -----------------------------------------------------

            tuition_fees = [
                fee for fee in class_fees
                if fee.fee_type == "Tuition Fee"
            ]

            one_time_fees = [
                fee for fee in class_fees
                if fee.fee_type != "Tuition Fee"
            ]

            # -----------------------------------------------------
            # Total configured fee
            # -----------------------------------------------------

            total_payable = sum(
                (
                    fee.amount or ZERO
                    for fee in class_fees
                ),
                ZERO,
            )

            total_tuition_fee = sum(
                (
                    fee.amount or ZERO
                    for fee in tuition_fees
                ),
                ZERO,
            )

            total_one_time_fee = sum(
                (
                    fee.amount or ZERO
                    for fee in one_time_fees
                ),
                ZERO,
            )

            # -----------------------------------------------------
            # Actual amount paid by this student
            #
            # IMPORTANT:
            # Use FeeData.paid_amount, not FeeTransaction.paid_amount.
            #
            # One transaction can belong to multiple siblings.
            # -----------------------------------------------------

            total_settled_amount = ZERO
            total_overpaid_amount = ZERO

            # -----------------------------------------------------
            # Paid tuition / one-time amounts
            # -----------------------------------------------------

            paid_tuition_fee = ZERO
            paid_one_time_fee = ZERO

            for fee in class_fees:

                balance = calculate_fee_balance(
                    fee.amount,
                    student_payment_map.get(fee.id),
                )
                settled_amount = balance["paid_amount"]
                total_settled_amount += settled_amount
                total_overpaid_amount += max(-balance["remaining_amount"], ZERO)

                if fee.fee_type == "Tuition Fee":
                    paid_tuition_fee += settled_amount
                else:
                    paid_one_time_fee += settled_amount

            # -----------------------------------------------------
            # Tuition months
            # -----------------------------------------------------

            total_months = len(tuition_fees)

            tuition_fee_ids = {
                fee.id
                for fee in tuition_fees
            }

            paid_tuition_fee_ids = set()
            for fee in tuition_fees:
                balance = calculate_fee_balance(
                    fee.amount,
                    student_payment_map.get(fee.id),
                )
                if balance["status"] in ("PAID", "OVERPAID"):
                    paid_tuition_fee_ids.add(fee.id)

            paid_months = len(
                paid_tuition_fee_ids
            )

            # -----------------------------------------------------
            # Calculate due / upcoming
            # -----------------------------------------------------

            due_amount = ZERO
            upcoming_amount = ZERO

            due_months = 0
            upcoming_months = 0

            for fee in class_fees:

                fee_amount = fee.amount or ZERO

                balance = calculate_fee_balance(
                    fee_amount,
                    student_payment_map.get(fee.id),
                )
                remaining_amount = balance["remaining_amount"]

                # Completely paid
                if remaining_amount <= ZERO:
                    continue

                # -------------------------------------------------
                # Determine due date
                # -------------------------------------------------

                if fee.custom_due_date:

                    due_date = fee.custom_due_date

                else:

                    due_year = (
                        current_session_year
                        + int(fee.year_increment or 0)
                    )

                    due_date = date(
                        due_year,
                        int(fee.due_month),
                        int(fee.due_day),
                    )

                # -------------------------------------------------
                # Past/today = due
                # Future = upcoming
                # -------------------------------------------------

                if due_date <= today:

                    due_amount += remaining_amount

                    if fee.fee_type == "Tuition Fee":
                        due_months += 1

                else:

                    upcoming_amount += remaining_amount

                    if fee.fee_type == "Tuition Fee":
                        upcoming_months += 1

            # -----------------------------------------------------
            # Last payment date
            # -----------------------------------------------------

            payment_dates = [
                payment["payment_date"]
                for payment in student_payment_map.values()
                if payment["payment_date"]
            ]

            last_payment_date = (
                max(payment_dates)
                if payment_dates
                else None
            )

            if last_payment_date:
                last_payment_date = (
                    last_payment_date.strftime("%d %b %Y")
                )

            # -----------------------------------------------------
            # Overall fee status
            # -----------------------------------------------------

            if due_amount > ZERO:

                fee_status = "Due"

            elif upcoming_amount > ZERO:

                fee_status = "Upcoming"

            else:

                fee_status = "Paid"

            # -----------------------------------------------------
            # Final student object
            # -----------------------------------------------------

            data.append({
                **build_basic_student_record(student),

                # Overall
                "totalPayable": json_money(total_payable),
                "totalSettledAmount": json_money(total_settled_amount),
                "overpaidAmount": json_money(total_overpaid_amount),
                "lastPaymentDate": last_payment_date,

                # Due / upcoming
                "dueAmount": json_money(due_amount),
                "upcomingAmount": json_money(upcoming_amount),

                # Tuition
                "totalTuitionFee": json_money(total_tuition_fee),
                "paidTuitionFee": json_money(paid_tuition_fee),

                # One-time
                "totalOneTimeFee": json_money(total_one_time_fee),
                "paidOneTimeFee": json_money(paid_one_time_fee),

                # Tuition months
                "totalMonths": total_months,
                "paidMonths": paid_months,
                "dueMonths": due_months,
                "upcomingMonths": upcoming_months,

                "feeStatus": fee_status,
            })

        # ---------------------------------------------------------
        # 7. Total discount given by school
        #
        # This queries FeeTransaction directly.
        # Therefore a transaction shared by siblings is counted
        # exactly once.
        # ---------------------------------------------------------

        total_discount = (
            db.session.query(
                func.coalesce(
                    func.sum(FeeTransaction.discount),
                    0,
                )
            )
            .filter(
                FeeTransaction.school_id == school_id,
                FeeTransaction.session_id == current_session_id,

                # NULL = not deleted
                func.coalesce(
                    FeeTransaction.is_deleted,
                    False, ) == False,
            )
            .scalar()
        ) or ZERO

        # ---------------------------------------------------------
        # 8. Return response
        # ---------------------------------------------------------

        return jsonify({
            "total_discount_given_by_school": json_money(total_discount),
            "students_fee_data": data,
        }), 200

    # -------------------------------------------------------------
    # Missing session information
    # -------------------------------------------------------------

    except KeyError as e:

        return jsonify({
            "error": f"Missing session information: {str(e)}",
        }), 400

    # -------------------------------------------------------------
    # Unexpected error
    # -------------------------------------------------------------

    except Exception as e:

        db.session.rollback()

        # Replace print with proper application logging in production.
        print(
            "Error in get_students_fees_api:",
            e,
        )

        return jsonify({
            "error": "Unable to get students fee data.",
        }), 500


      
    