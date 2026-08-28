from flask import session, request, jsonify, Blueprint
from sqlalchemy import desc
from decimal import Decimal


from src.model import StudentSessions, StudentsDB, FeeTransaction, FeeData, ClassData, FeeStructure, FeeHeads
from src import db
from src.model.FeeSessionData import FeeSessionData

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

get_transactions_api_bp = Blueprint('get_transactions_api_bp', __name__)


def _num(v):
    """Convert Decimal/SQLAlchemy numeric -> python int/float for JSON."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        # if whole number, return int else float
        if v == v.to_integral_value():
            return int(v)
        return float(v)
    try:
        return float(v)
    except Exception:
        return v


@get_transactions_api_bp.route('/api/get_fee_transactions', methods=["GET"])
@login_required
@permission_required('view_fee_data')
def get_fee_transactions():

    
    student_session_id = request.args.get("student_session_id")
    phone = request.args.get("phone")

    current_session = session["session_id"]
    school_id = session["school_id"]

    if not phone and not student_session_id:
        return jsonify({
            "error": "Please provide either student_session_id or phone number!"
        }), 400

    if not phone:
        phone = (
            db.session.query(StudentsDB.PHONE)
                .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
                .filter(StudentSessions.id == student_session_id)
                .scalar()
        )

    student_session_ids = (
        db.session.query(StudentSessions.id)
        .join(StudentsDB, StudentSessions.student_id == StudentsDB.id)
        .filter(
            StudentsDB.PHONE == phone,
            StudentsDB.school_id == school_id,
            StudentSessions.session_id == current_session,
        )
        .all()
    )

    student_session_ids = [row[0] for row in student_session_ids]

    if not student_session_ids:
        return jsonify({"error": "student_session_ids are required"}), 400

    # cast to ints and validate
    try:
        student_session_ids = [int(x) for x in student_session_ids]
    except ValueError:
        return jsonify({"error": "student_session_ids must be integers"}), 400

    try:
        school_id = session["school_id"]
        current_session_id = session["session_id"]

        # ---------------------------------------------------------------------
        # Query:
        #  - select FeeData rows for requested student_session_ids
        #  - bring in FeeTransaction (header), FeeSessionData (amount, custom dates),
        #    FeeStructure (fee_type, period_name), FeeHeads (fee name),
        #    StudentSessions, StudentsDB, ClassData
        # ---------------------------------------------------------------------
        fee_rows = (
            db.session.query(
                FeeData,
                FeeTransaction,
                FeeSessionData,
                FeeStructure,
                FeeHeads,
                StudentSessions,
                StudentsDB,
                ClassData
            )
            .join(FeeTransaction, FeeData.transaction_id == FeeTransaction.id)
            .join(FeeSessionData, FeeData.fee_session_id == FeeSessionData.id)
            .join(FeeStructure, FeeSessionData.structure_id == FeeStructure.id)
            .outerjoin(FeeHeads, FeeStructure.fee_type_id == FeeHeads.id)
            .join(StudentSessions, FeeData.student_session_id == StudentSessions.id)
            .join(StudentsDB, StudentSessions.student_id == StudentsDB.id)
            .join(ClassData, StudentSessions.class_id == ClassData.id)
            .filter(
                FeeData.student_session_id.in_(student_session_ids),
                FeeTransaction.school_id == school_id,
                FeeSessionData.session_id == current_session_id
            )
            .order_by(desc(FeeTransaction.created_at), FeeTransaction.id, FeeData.id)
            .all()
        )

        if not fee_rows:
            return jsonify({"error": "No transactions found", "transactions": []}), 200

        # ---------------------------------------------------------------------
        # Aggregate into desired JSON structure
        # ---------------------------------------------------------------------
        transactions = {}

        for (fee_data, txn, fee_session, fee_structure, fee_head, student_session, student, classdata) in fee_rows:
            txn_id = txn.id

            # Transaction header init
            if txn_id not in transactions:
                transactions[txn_id] = {
                    "id": txn_id,
                    "phone": getattr(student, "PHONE", None),
                    "transaction_no": txn.transaction_no or f"TXN-{txn_id}",
                    "payment_date": txn.payment_date.isoformat() if getattr(txn, "payment_date", None) else None,
                    "paid_amount": _num(getattr(txn, "paid_amount", None)),
                    "discount": _num(getattr(txn, "discount", None)),
                    "payment_mode": getattr(txn, "payment_mode", None),
                    "remark": getattr(txn, "remark", None),
                    "is_deleted": bool(getattr(txn, "is_deleted", False)),
                    "siblings": {}  # keyed by student_session_id while building
                }

            # Build sibling key and basic info
            sid = fee_data.student_session_id
            if sid not in transactions[txn_id]["siblings"]:
                # Build className similar to "Grade 10-A" if Section available
                class_name = str(classdata.CLASS) if getattr(classdata, "CLASS", None) else None
                
                transactions[txn_id]["siblings"][sid] = {
                    "studentName": getattr(student, "STUDENTS_NAME", None),
                    "className": class_name,
                    "rollNo": str(getattr(student_session, "ROLL", "") or ""),
                    "fees": {
                        "monthly": {
                            "label": "Tuition Fees",   # fallback; you can customize per fee head/type
                            "total": 0,
                            "months": []
                        },
                        "oneTime": []
                    }
                }

            sibling = transactions[txn_id]["siblings"][sid]

            # Determine fee_type, amount, labels robustly (prefer FeeData fields, then FeeStructure/FeeSessionData)
            fee_type = getattr(fee_data, "fee_type", None) or getattr(fee_structure, "fee_type", None)
            # The 'name' of the fee: prefer explicit fee_name on FeeData, else FeeHeads.fee_name, else FeeStructure.period_name
            fee_name = getattr(fee_data, "fee_name", None) or (getattr(fee_head, "fee_name", None) if fee_head else None) or getattr(fee_structure, "period_name", None)
            # month label could be stored on FeeData (month_label) or as period_name on FeeStructure
            month_label = getattr(fee_data, "month_label", None) or getattr(fee_structure, "period_name", None)
            # amount: prefer FeeData.amount (paid amount for the line), else FeeSessionData.amount
            amount = getattr(fee_data, "amount", None)
            if amount is None:
                amount = getattr(fee_session, "amount", None)
            amount = _num(amount)

            # Process monthly vs one-time
            if fee_type and fee_type.lower() == "monthly":
                # accumulate total
                sibling["fees"]["monthly"]["total"] = _num(Decimal(sibling["fees"]["monthly"]["total"]) + (Decimal(str(amount)) if amount is not None else Decimal(0)))
                if month_label and month_label not in sibling["fees"]["monthly"]["months"]:
                    sibling["fees"]["monthly"]["months"].append(month_label)
            else:
                sibling["fees"]["oneTime"].append({
                    "name": fee_name,
                    "amount": amount
                })

        # Convert siblings dict to list and produce final list ordered by txn created_at desc
        final_output = []
        # keep the original ordering from the query
        # transactions dict may not preserve DB order, so sort by txn.created_at if needed
        # we have only txn id keys in transactions; fetch created_at map from fee_rows
        txn_order = []
        seen_txn = set()
        for fee_data, txn, *_ in fee_rows:
            if txn.id not in seen_txn:
                txn_order.append(txn.id)
                seen_txn.add(txn.id)

        for tid in txn_order:
            data = transactions.get(tid)
            if not data:
                continue
            # convert monthly total to numeric type if Decimal
            data["siblings"] = list(data["siblings"].values())
            # ensure monthly.total numeric conversion
            for s in data["siblings"]:
                s["fees"]["monthly"]["total"] = _num(s["fees"]["monthly"]["total"])
            final_output.append(data)

        return jsonify({
            "message": "Transactions retrieved successfully",
            "transactions": final_output
        }), 200

    except Exception as e:
        # keep logs for debugging
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error fetching transactions: {str(e)}"}), 500
