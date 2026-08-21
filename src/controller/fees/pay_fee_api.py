# src/controller/pay_fee.py

from flask import request, jsonify, Blueprint, session
from sqlalchemy.exc import SQLAlchemyError

from src.model import FeeData, StudentSessions, StudentsDB
from src import db
from datetime import datetime


from src.model.FeeTransaction import FeeTransaction
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

pay_fee_api_bp = Blueprint( 'pay_fee_api_bp',   __name__)


@pay_fee_api_bp.route('/api/pay_fee', methods=["POST"])
@login_required
@permission_required('pay_fees')
def pay_fee_api():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400
    
    school_id = session["school_id"]
    session_id = session["session_id"]

    whatsapp_message = "Fees Paid Successfully!\n"
    discount = int(data.get("discount") or 0)
    payment_mode = data.get("payment_mode")
    payment_date = data.get("paymentDate")
    fee_data = data.get("students", [])
    remark = data.get("remark")

    if not payment_mode:
        return jsonify({ "message": "Payment mode cant be empty, Please select payment mode"}), 400
    
    try:
        # Validate and convert
        payment_date = datetime.strptime(payment_date, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid date format. Expected DD/MM/YYYY"}), 400
    
    # --------------------------- CALCULATE TOTAL ---------------------------
    total_paid = 0
    try:
        for fee_record in fee_data:
            for selected_fee in fee_record.get("selectedFees", []):
                total_paid += int(selected_fee["amount"])
    except (TypeError, KeyError, ValueError):
        return jsonify({"message": "Invalid students/fees format"}), 400
    
    # --------------------------- DATABASE INSERT ---------------------------
    try:
        with db.session.begin():
            # Get last seq_no for this school & session
            last_seq_row = db.session.query(FeeTransaction.seq_no)\
                .filter_by(school_id=school_id, session_id=session_id)\
                .order_by(FeeTransaction.seq_no.desc())\
                .with_for_update()\
                .first()
            last_seq = last_seq_row[0] if last_seq_row else None
            next_seq = 1 if last_seq is None else last_seq + 1
            date_str = payment_date.strftime("%d%m%Y")
            transaction_no = f"{school_id}/{session_id}/{date_str}/{next_seq}"
            
            new_txn = FeeTransaction(
                transaction_no = transaction_no,
                paid_amount    = total_paid,
                payment_date   = payment_date,
                payment_mode   = payment_mode,
                discount       = discount,
                remark         = remark or "",  
                school_id      = school_id,
                session_id     = session_id,
                seq_no         = next_seq  # Make sure to set seq_no
            )

            db.session.add(new_txn)
            db.session.flush()  # Ensures new_txn.id is available before commit

            # --------------------------- INSERT FeeData ROWS ---------------------------
            for fee_record in fee_data:
                student_session_id = fee_record.get("student_session_id")

                for selected_fee in fee_record.get("selectedFees", []):
                    fee_data_row = FeeData(
                        student_session_id = student_session_id,
                        fee_session_id = selected_fee["fee_id"],
                        payment_status = "paid",
                        transaction_id = new_txn.id,
                    )
                    db.session.add(fee_data_row)
    except SQLAlchemyError as e:
        db.session.rollback()
        print(e)
        return jsonify({
            "message": "Database error occurred",
            "error": str(e)
        }), 500
    
    try:
        # get the first student_session_id
        student_session_id = None
        for r in fee_data:
            if r.get("student_session_id"):
                student_session_id = r["student_session_id"]
                break

        if student_session_id:
            phone_number = (
                db.session.query(StudentsDB.PHONE)
                .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
                .filter(
                    StudentSessions.id == student_session_id,
                    StudentsDB.school_id == school_id
                )
                .scalar()
            )

    except SQLAlchemyError:
        phone_number = None


    return jsonify({
        "message": "Paid Successfully",
        "whatsapp_message": whatsapp_message,
        "transaction_no": transaction_no,
        "phone_number": phone_number
    }), 200