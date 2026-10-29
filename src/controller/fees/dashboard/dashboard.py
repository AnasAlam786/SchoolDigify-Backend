from datetime import date, timedelta, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, session
from sqlalchemy import exists, func, or_

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.fees.utils.fee_calculations import (
    ZERO,
    aggregate_fee_allocations,
    calculate_fee_balance,
)
from src.model import (
    FeeTransaction, FeeData, FeeSessionData,
    StudentSessions, ClassData, FeeStructure, RTEInfo,
)
from src.model.StudentsDB import StudentsDB


def get_summary(session_id, school_id):
    today = date.today()
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    summary_data = {
        "today": ZERO,
        "yesterday": ZERO,
        "this_week": ZERO,
        "this_month": ZERO,
        "this_year": ZERO,
        "total": ZERO,
    }

    rte_payment_totals = (
        db.session.query(
            FeeData.transaction_id.label("transaction_id"),
            func.sum(FeeData.paid_amount).label("rte_paid_amount"),
        )
        .join(StudentSessions, FeeData.student_session_id == StudentSessions.id)
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .join(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
        .filter(
            StudentSessions.session_id == session_id,
            StudentsDB.school_id == school_id,
            FeeTransaction.school_id == school_id,
            FeeTransaction.session_id == session_id,
            or_(FeeTransaction.is_deleted.is_(False), FeeTransaction.is_deleted.is_(None)),
            exists().where(
                RTEInfo.student_id == StudentSessions.student_id,
                RTEInfo.is_RTE.is_(True),
            ),
        )
        .group_by(FeeData.transaction_id)
        .subquery()
    )

    daily_collections = (
        db.session.query(
            FeeTransaction.payment_date,
            func.coalesce(
                func.sum(
                    FeeTransaction.paid_amount
                    - func.coalesce(rte_payment_totals.c.rte_paid_amount, 0)
                ),
                0,
            ).label("total_amount"),
            func.count(FeeTransaction.id).label("transaction_count"),
        )
        .outerjoin(
            rte_payment_totals,
            rte_payment_totals.c.transaction_id == FeeTransaction.id,
        )
        .filter(
            FeeTransaction.session_id == session_id,
            FeeTransaction.school_id == school_id,
            or_(FeeTransaction.is_deleted.is_(False), FeeTransaction.is_deleted.is_(None)),
        )
        .group_by(FeeTransaction.payment_date)
        .order_by(FeeTransaction.payment_date)
        .all()
    )

    for collection in daily_collections:
        transaction_date = collection.payment_date
        total_amount = Decimal(str(collection.total_amount or 0))
        if transaction_date == today:
            summary_data["today"] += total_amount
        if transaction_date == yesterday:
            summary_data["yesterday"] += total_amount
        if start_of_week <= transaction_date <= today:
            summary_data["this_week"] += total_amount
        if start_of_month <= transaction_date <= today:
            summary_data["this_month"] += total_amount
        if start_of_year <= transaction_date <= today:
            summary_data["this_year"] += total_amount
        summary_data["total"] += total_amount

    serializable_daily_collections = []
    if daily_collections:
        start_date = daily_collections[0].payment_date
        collection_map = {
            collection.payment_date: {
                "total_amount": Decimal(str(collection.total_amount or 0)),
                "transaction_count": collection.transaction_count or 0,
            }
            for collection in daily_collections
        }
        current_date = start_date
        while current_date <= today:
            day_data = collection_map.get(
                current_date,
                {"total_amount": ZERO, "transaction_count": 0},
            )
            serializable_daily_collections.append({
                "payment_date": current_date.isoformat(),
                "total_amount": round(float(day_data["total_amount"]), 2),
                "transaction_count": day_data["transaction_count"],
            })
            current_date += timedelta(days=1)

    return {
        key: round(float(value), 2)
        for key, value in summary_data.items()
    }, serializable_daily_collections


def get_class_analysis(session_id, school_id):
    today = date.today()
    student_rows = (
        db.session.query(
            StudentSessions.id.label("student_session_id"),
            StudentSessions.class_id.label("class_id"),
        )
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .outerjoin(RTEInfo, RTEInfo.student_id == StudentSessions.student_id)
        .filter(
            StudentSessions.session_id == session_id,
            StudentsDB.school_id == school_id,
            or_(RTEInfo.is_RTE.is_(False), RTEInfo.is_RTE.is_(None)),
        )
        .all()
    )

    student_ids_by_class = {}
    student_session_ids = []
    for row in student_rows:
        student_ids_by_class.setdefault(row.class_id, []).append(row.student_session_id)
        student_session_ids.append(row.student_session_id)

    fee_rows = (
        db.session.query(
            FeeSessionData.id.label("fee_session_id"),
            FeeSessionData.class_id,
            FeeSessionData.amount,
            FeeSessionData.custom_due_date,
            FeeStructure.due_day,
            FeeStructure.due_month,
            FeeStructure.year_increment,
        )
        .join(FeeStructure, FeeStructure.id == FeeSessionData.structure_id)
        .filter(
            FeeSessionData.session_id == session_id,
            FeeStructure.school_id == school_id,
        )
        .all()
    )

    payments = []
    if student_session_ids:
        payments = (
            db.session.query(
                FeeData.student_session_id,
                FeeData.fee_session_id,
                FeeData.transaction_id,
                FeeData.paid_amount,
                FeeData.late_fee,
                FeeTransaction.paid_amount.label("transaction_paid_amount"),
                FeeTransaction.discount,
                FeeTransaction.payment_date,
                FeeTransaction.transaction_no,
            )
            .outerjoin(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
            .filter(
                FeeData.student_session_id.in_(student_session_ids),
                or_(
                    FeeTransaction.id.is_(None),
                    (FeeTransaction.school_id == school_id)
                    & (FeeTransaction.session_id == session_id)
                    & or_(FeeTransaction.is_deleted.is_(False), FeeTransaction.is_deleted.is_(None)),
                ),
            )
            .all()
        )
    paid_by_pair = aggregate_fee_allocations(payments)

    class_rows = (
        db.session.query(
            ClassData.id.label("class_id"),
            ClassData.CLASS.label("class_name"),
            ClassData.display_order,
        )
        .filter(ClassData.school_id == school_id)
        .order_by(ClassData.display_order)
        .all()
    )

    result = []
    for row in class_rows:
        student_ids = student_ids_by_class.get(row.class_id, [])
        class_fee_rows = [fee for fee in fee_rows if fee.class_id == row.class_id]
        total_due = ZERO
        collected = ZERO
        outstanding = ZERO
        overpaid = ZERO

        for fee in class_fee_rows:
            fee_amount = Decimal(str(fee.amount or 0))
            total_due += fee_amount * len(student_ids)
            for student_session_id in student_ids:
                balance = calculate_fee_balance(
                    fee.amount,
                    paid_by_pair.get((student_session_id, fee.fee_session_id)),
                )
                collected += balance["paid_amount"]
                overpaid += max(-balance["remaining_amount"], ZERO)

                due_date = fee.custom_due_date
                if due_date is None:
                    due_date = date(
                        int(session_id) + int(fee.year_increment or 0),
                        int(fee.due_month or 1),
                        int(fee.due_day or 1),
                    )
                if isinstance(due_date, datetime):
                    due_date = due_date.date()
                if due_date <= today:
                    outstanding += max(balance["remaining_amount"], ZERO)

        collection_percentage = (
            collected / total_due * Decimal("100")
            if total_due > ZERO else ZERO
        )
        result.append({
            "class_id": row.class_id,
            "class_name": row.class_name,
            "total_due": round(float(total_due), 2),
            "collected": round(float(collected), 2),
            "outstanding": round(float(outstanding), 2),
            "overpaid": round(float(overpaid), 2),
            "collection_percentage": round(float(collection_percentage), 2),
        })
    return result


fees_dashboard_api_bp = Blueprint('fees_dashboard_api_bp', __name__)


@login_required
@permission_required('pay_fees')
@fees_dashboard_api_bp.get("/api/fee-dashboard")
def fees_dashboard():
    try:
        current_session = session.get("session_id")
        school_id = session.get("school_id")
        if not current_session or not school_id:
            return jsonify({"error": "Invalid or expired session"}), 401

        summary, daily_collections = get_summary(current_session, school_id)
        class_analysis = get_class_analysis(current_session, school_id)
        return jsonify({
            "summary": summary,
            "daily_collections": daily_collections,
            "class_analysis": class_analysis,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print("Fee dashboard error:", repr(e))
        return jsonify({"error": "Unable to load fee dashboard."}), 500