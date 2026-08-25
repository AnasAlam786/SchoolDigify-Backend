# src/controller/pay_fee.py

from flask import request, jsonify, Blueprint, session
from sqlalchemy.exc import SQLAlchemyError

from src.controller.fees.utils.fetch_fee_data import fetch_fee_data
from src.model import FeeData, StudentSessions, StudentsDB
from src import db
from datetime import datetime

from src.model.FeeData import FeePaymentStatus
from src.model.FeeTransaction import FeeTransaction
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

pay_fee_api_bp = Blueprint( 'pay_fee_api_bp',   __name__)

from datetime import datetime, date

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


@pay_fee_api_bp.route('/api/pay_fee', methods=["POST"])
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
    discount = int(data.get("discount") or 0)
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
    total_paid = 0
    try:
        for fee_record in new_fee_data:
            for selected_fee in fee_record.get("selectedFees", []):
                total_paid += int(selected_fee["amount"])
    except (TypeError, KeyError, ValueError):
        return jsonify({"message": "Invalid students/fees format"}), 400

    # 4. Database Transaction
    try:
        with db.session.begin():
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
                paid_amount=total_paid,
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

            for fee_record in new_fee_data:
                student_session_id = fee_record.get("student_session_id")
                for selected_fee in fee_record.get("selectedFees", []):
                    fee_data_row = FeeData(
                        student_session_id=student_session_id,
                        fee_session_id=selected_fee["fee_id"],
                        fee_payment_status=FeePaymentStatus.PAID,
                        transaction_id=new_txn.id,
                    )
                    db.session.add(fee_data_row)
    except SQLAlchemyError as e:
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