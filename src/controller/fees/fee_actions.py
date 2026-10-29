# src/controller/fees/transaction_action_api.py

from flask import session, request, jsonify, Blueprint
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from src.model import StudentSessions, StudentsDB, FeeTransaction, FeeData, FeeSessionData, FeeStructure, Sessions
from src.model.FeeData import FeePaymentStatus
from src import db

from src.controller.fees.utils.fetch_fee_data import fetch_fee_data

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from src.controller.fees.utils.fee_calculations import (
    aggregate_fee_allocations,
    calculate_fee_balance,
)

transaction_action_api_bp = Blueprint('transaction_action_api_bp', __name__)

def parse_date(value):
    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise ValueError("Invalid date type")

    value = value.strip()

    formats = [
        "%Y-%m-%d",   # 2026-08-24
        "%d-%m-%Y",   # 24-08-2026
        "%d/%m/%Y",   # 24/08/2026
        "%Y/%m/%d",   # 2026/08/24
        "%m/%d/%Y",   # 08/24/2026
        "%d.%m.%Y",   # 24.08.2026
    ]

    for fmt in formats:
        try:
            
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {value}")

@transaction_action_api_bp.route('/api/delete_fee_transaction', methods=["POST"])
@login_required
@permission_required('pay_fees')
def delete_fee_transaction():
    """
    Soft delete a fee transaction (mark as deleted without removing from DB)
    Sets is_deleted = True to hide transaction from user view
    
    Expected JSON body:
        - transaction_id: ID of the transaction to delete
    
    Returns:
        JSON with success message and updated transaction data
    """
    data = request.get_json()
    
    if not data or not data.get("transaction_id"):
        return jsonify({"message": "transaction_id is required"}), 400
    
    try:
        school_id = session["school_id"]
        transaction_id = data.get("transaction_id")
        
        # Verify transaction exists and belongs to this school
        transaction = db.session.query(FeeTransaction).filter(
            and_(
                FeeTransaction.id == transaction_id,
                FeeTransaction.school_id == school_id
            )
        ).first()
        
        if not transaction:
            return jsonify({"message": "Transaction not found"}), 404
        
        # Check if already deleted
        if transaction.is_deleted is True:
            return jsonify({
                "message": "Transaction is already deleted",
                "transaction_id": transaction_id
            }), 400
        
        # Soft delete: Set is_deleted flag to True
        transaction.is_deleted = True
        db.session.commit()
        
        return jsonify({
            "message": "Transaction deleted successfully",
            "transaction_id": transaction_id,
            "is_deleted": True
        }), 200
        
    except Exception as e:
        print(f"Error deleting transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"message": f"Error deleting transaction: {str(e)}"}), 500


@transaction_action_api_bp.route('/api/restore_fee_transaction', methods=["POST"])
@login_required
@permission_required('pay_fees')
def restore_fee_transaction():
    """
    Restore a soft-deleted fee transaction
    Sets is_deleted = False to show transaction to user again
    
    Expected JSON body:
        - transaction_id: ID of the transaction to restore
    
    Returns:
        JSON with success message and updated transaction data
    """
    data = request.get_json()
    
    if not data or not data.get("transaction_id"):
        return jsonify({"error": "transaction_id is required"}), 400
    
    try:
        school_id = session["school_id"]
        transaction_id = data.get("transaction_id")
        
        # Verify transaction exists and belongs to this school
        transaction = db.session.query(FeeTransaction).filter(
            and_(
                FeeTransaction.id == transaction_id,
                FeeTransaction.school_id == school_id
            )
        ).first()
        
        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404
        
        # Check if not deleted
        if transaction.is_deleted is not True:
            return jsonify({
                "error": "Transaction is not deleted",
                "transaction_id": transaction_id
            }), 400
        
        # Soft restore: Set is_deleted flag to False
        transaction.is_deleted = False
        db.session.commit()
        
        return jsonify({
            "message": "Transaction restored successfully",
            "transaction_id": transaction_id,
            "is_deleted": False
        }), 200
        
    except Exception as e:
        print(f"Error restoring transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"Error restoring transaction: {str(e)}"}), 500


@transaction_action_api_bp.route('/api/pay_fee', methods=["POST"])
@login_required
@permission_required('pay_fees')
def pay_fee_api():
    # 1. Session Validation
    school_id = session.get("school_id")
    session_id = session.get("session_id")
    if not school_id or not session_id:
        return jsonify({"message": "Invalid or expired session"}), 401

    # 2. Input Extraction & Validation
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400

    payment_mode = data.get("payment_mode")
    raw_payment_date = data.get("payment_date")
    new_fee_data = data.get("new_fee_data", [])
    try:
        discount = Decimal(str(data.get("discount") or 0))
    except InvalidOperation:
        return jsonify({"message": "Invalid discount amount"}), 400
    if not discount.is_finite() or discount < 0:
        return jsonify({"message": "Invalid discount amount"}), 400
    remark = data.get("remark", "")

    if not payment_mode:
        return jsonify({"message": "Payment mode cannot be empty"}), 400

    if not raw_payment_date:
        return jsonify({"message": "Payment date cannot be empty"}), 400

    try:
        payment_date = parse_date(raw_payment_date)
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid date format. Expected DD/MM/YYYY"}), 400

    # 3. Calculate Total
    payment_items = []
    try:
        for fee_record in new_fee_data:
            for selected_fee in fee_record.get("selectedFees", []):
                student_session_id = fee_record.get("student_session_id")
                fee_session_id = selected_fee.get("fee_id")
                payment_amount = Decimal(str(
                    selected_fee.get("payment_amount", selected_fee.get("amount"))
                ))
                if (
                    not student_session_id
                    or not fee_session_id
                    or not payment_amount.is_finite()
                    or payment_amount < 1
                ):
                    raise ValueError
                payment_items.append((student_session_id, fee_session_id, payment_amount))
    except (TypeError, ValueError, InvalidOperation, AttributeError):
        return jsonify({"message": "Invalid students/fees format"}), 400

    if not payment_items:
        return jsonify({"message": "Select at least one fee to pay"}), 400

    selected_fee_total = sum((item[2] for item in payment_items), Decimal("0"))
    actual_paid = selected_fee_total - discount

    if actual_paid < 0:
        return jsonify({
            "message": "Discount cannot be greater than the selected fee amount"
        }), 400


    # 4. Database Transaction
    try:
        with db.session.begin():
            locked_session_id = db.session.query(Sessions.id).filter(
                Sessions.id == session_id
            ).with_for_update().scalar()
            if not locked_session_id:
                raise ValueError("Academic session is not available")

            paid_by_fee = {}
            for student_session_id, fee_session_id, payment_amount in payment_items:
                student = (
                    db.session.query(StudentSessions)
                    .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
                    .filter(
                        StudentSessions.id == student_session_id,
                        StudentSessions.session_id == session_id,
                        StudentsDB.school_id == school_id,
                    )
                    .with_for_update()
                    .first()
                )
                if not student:
                    raise ValueError("Student or fee is not available for this session")

                configured_amount = (
                    db.session.query(FeeSessionData.amount)
                    .join(FeeStructure, FeeStructure.id == FeeSessionData.structure_id)
                    .filter(
                        FeeSessionData.id == fee_session_id,
                        FeeSessionData.class_id == student.class_id,
                        FeeSessionData.session_id == session_id,
                        FeeStructure.school_id == school_id,
                    )
                    .with_for_update()
                    .scalar()
                )
                if configured_amount is None:
                    raise ValueError("Student or fee is not available for this session")

                key = (student_session_id, fee_session_id)
                if key in paid_by_fee:
                    raise ValueError("A fee term can only be selected once")

                existing_allocations = db.session.query(
                    FeeData.student_session_id,
                    FeeData.fee_session_id,
                    FeeData.transaction_id,
                    FeeData.paid_amount,
                    FeeData.late_fee,
                    FeeTransaction.paid_amount.label("transaction_paid_amount"),
                    FeeTransaction.discount,
                    FeeTransaction.payment_date,
                    FeeTransaction.transaction_no,
                ).outerjoin(
                    FeeTransaction, FeeTransaction.id == FeeData.transaction_id
                ).filter(
                    FeeData.student_session_id == student_session_id,
                    FeeData.fee_session_id == fee_session_id,
                    or_(
                        FeeData.transaction_id.is_(None),
                        and_(
                            FeeTransaction.school_id == school_id,
                            FeeTransaction.session_id == session_id,
                            or_(
                                FeeTransaction.is_deleted.is_(False),
                                FeeTransaction.is_deleted.is_(None),
                            ),
                        ),
                    ),
                ).all()

                existing_payment_totals = aggregate_fee_allocations(existing_allocations)
                balance = calculate_fee_balance(
                    configured_amount,
                    existing_payment_totals.get(key),
                )

                if payment_amount > balance["remaining_amount"]:
                    raise ValueError("Payment amount exceeds the remaining fee for a selected term")

                paid_by_fee[key] = (payment_amount, balance["remaining_amount"])

            last_seq_row = db.session.query(FeeTransaction.seq_no)\
                .filter_by(school_id=school_id, session_id=session_id)\
                .order_by(FeeTransaction.seq_no.desc())\
                .with_for_update()\
                .first()

            last_seq = last_seq_row[0] if last_seq_row else 0
            next_seq = last_seq + 1
            date_str = payment_date.strftime("%d%m%Y")
            transaction_no = f"{school_id}/{session_id}/{date_str}/{next_seq}"

            new_txn = FeeTransaction(
                transaction_no=transaction_no,
                paid_amount=actual_paid,
                payment_date=payment_date,
                payment_mode=payment_mode,
                discount=discount,
                remark=remark,
                school_id=school_id,
                session_id=session_id,
                seq_no=next_seq
            )

            db.session.add(new_txn)
            db.session.flush()

            for (student_session_id, fee_session_id), (payment_amount, existing_remaining) in paid_by_fee.items():
                payment_status = (
                    FeePaymentStatus.PAID
                    if payment_amount >= existing_remaining
                    else FeePaymentStatus.PARTIAL
                )
                db.session.add(FeeData(
                    student_session_id=student_session_id,
                    fee_session_id=fee_session_id,
                    fee_payment_status=payment_status,
                    paid_amount=payment_amount,
                    transaction_id=new_txn.id,
                ))
    except ValueError as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            "message": "Database error occurred",
            "error": str(e)
        }), 500

    # 5. Fetch Associated Student Phone Number
    phone_number = None
    first_student_session_id = next(
        (r.get("student_session_id") for r in new_fee_data if r.get("student_session_id")), 
        None
    )

    if first_student_session_id:
        try:
            phone_number = (
                db.session.query(StudentsDB.PHONE)
                .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
                .filter(
                    StudentSessions.id == first_student_session_id,
                    StudentsDB.school_id == school_id
                )
                .scalar()
            )
        except SQLAlchemyError:
            phone_number = None

    # 6. Fetch Post-Payment Data
    try:
        is_success, updated_fee = fetch_fee_data(
            session_id=session_id, 
            school_id=school_id, 
            user_id=session["user_id"],
            phone=phone_number
        )
    except Exception:
        return jsonify({
            "message": "Payment recorded, but unable to fetch updated fee data", 
            "fees_paid": True 
        }), 500

    if not is_success:
        return jsonify({
            "message": "Payment recorded, but unable to fetch updated fee data", 
            "fees_paid": True 
        }), 200

    return jsonify({
        "message": "Paid Successfully",
        "whatsapp_message": "Fees Paid Successfully!\n",
        "transaction_no": transaction_no,
        "students_fee_data": updated_fee,
        "phone_number": phone_number,
    }), 200