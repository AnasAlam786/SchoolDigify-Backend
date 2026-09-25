
from datetime import date, timedelta

from flask import Blueprint, request, jsonify, session
from sqlalchemy import func, or_

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model import (
    FeeTransaction, FeeData, FeeSessionData,
    StudentSessions, ClassData, FeeStructure, RTEInfo,
)


def get_summary(session_id, school_id):
    today = date.today()
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    summary_data = {
        "today": 0,
        "yesterday": 0,
        "this_week": 0,
        "this_month": 0,
        "this_year": 0,
        "total": 0,
    }

    daily_collections = (
        db.session.query(
            FeeTransaction.payment_date,
            func.coalesce(
                func.sum(FeeTransaction.paid_amount), 0
            ).label("total_amount"),
            func.count(FeeTransaction.id).label("transaction_count"),
        )
        .filter(
            FeeTransaction.session_id == session_id,
            FeeTransaction.school_id == school_id,
            FeeTransaction.payment_date.isnot(None),
            or_(
                FeeTransaction.is_deleted.is_(False),
                FeeTransaction.is_deleted.is_(None)
            )
        )
        .group_by(FeeTransaction.payment_date)
        .order_by(FeeTransaction.payment_date)
        .all()
    )

    # --------------------------------------------------
    # SUMMARY CALCULATIONS
    # --------------------------------------------------

    for daily_collection in daily_collections:
        transaction_date = daily_collection.payment_date
        total_amount = float(daily_collection.total_amount or 0)

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

    # --------------------------------------------------
    # CREATE COMPLETE DAILY TIME SERIES
    # --------------------------------------------------

    serializable_daily_collections = []

    if daily_collections:
        # First date for which we have collection data
        start_date = daily_collections[0].payment_date

        # Create lookup dictionary
        collection_map = {
            daily_collection.payment_date: {
                "total_amount": float(
                    daily_collection.total_amount or 0
                ),
                "transaction_count": (
                    daily_collection.transaction_count or 0
                ),
            }
            for daily_collection in daily_collections
        }

        current_date = start_date

        while current_date <= today:

            day_data = collection_map.get(
                current_date,
                {
                    "total_amount": 0,
                    "transaction_count": 0,
                }
            )

            serializable_daily_collections.append({
                "payment_date": current_date.isoformat(),
                "total_amount": round(
                    day_data["total_amount"],
                    2
                ),
                "transaction_count": day_data["transaction_count"],
            })

            current_date += timedelta(days=1)

    # --------------------------------------------------
    # RETURN
    # --------------------------------------------------

    return {
        "today": round(summary_data["today"], 2),
        "yesterday": round(summary_data["yesterday"], 2),
        "this_week": round(summary_data["this_week"], 2),
        "this_month": round(summary_data["this_month"], 2),
        "this_year": round(summary_data["this_year"], 2),
        "total": round(summary_data["total"], 2),
    }, serializable_daily_collections

def get_class_analysis(session_id, school_id):
    """
    Return class-wise fee collection data.

    Outstanding is computed only for fee items whose due date is on or before
    today. If a custom due date exists on FeeSessionData, use it; otherwise use
    the default due date from FeeStructure.
    """

    today = date.today()

    student_rows = (
        db.session.query(
            StudentSessions.id.label("student_session_id"),
            StudentSessions.class_id.label("class_id"),
        )
        .outerjoin(RTEInfo, RTEInfo.student_id == StudentSessions.student_id)
        .filter(
            StudentSessions.session_id == session_id,
            or_(RTEInfo.is_RTE.is_(False), RTEInfo.is_RTE.is_(None)),
        )
        .all()
    )

    student_ids_by_class = {}
    for row in student_rows:
        student_ids_by_class.setdefault(row.class_id, []).append(row.student_session_id)

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

    payments = (
        db.session.query(
            FeeData.student_session_id,
            FeeData.fee_session_id,
            FeeData.paid_amount,
        )
        .outerjoin(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
        .filter(
            FeeData.student_session_id.in_(
                [sid for ids in student_ids_by_class.values() for sid in ids]
            ),
            or_(
                FeeTransaction.is_deleted.is_(False),
                FeeTransaction.is_deleted.is_(None),
            ),
        )
        .all()
    )

    paid_by_pair = {}
    for payment in payments:
        key = (payment.student_session_id, payment.fee_session_id)
        paid_by_pair[key] = float(payment.paid_amount or 0) + paid_by_pair.get(key, 0)

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
        class_id = row.class_id
        student_ids = student_ids_by_class.get(class_id, [])
        class_fee_rows = [fee for fee in fee_rows if fee.class_id == class_id]

        total_due = 0.0
        collected = 0.0
        outstanding = 0.0

        for fee in class_fee_rows:
            fee_amount = float(fee.amount or 0)
            total_due += fee_amount * max(len(student_ids), 0)

            for student_session_id in student_ids:
                collected += paid_by_pair.get((student_session_id, fee.fee_session_id), 0)

                due_date = fee.custom_due_date
                if due_date is None:
                    due_year = int(session_id) + int(fee.year_increment or 0)
                    due_month = int(fee.due_month or 1)
                    due_day = int(fee.due_day or 1)
                    due_date = date(due_year, due_month, due_day)

                if due_date <= today:
                    paid_amount = paid_by_pair.get((student_session_id, fee.fee_session_id), 0)
                    outstanding += max(fee_amount - paid_amount, 0)

        collection_percentage = (collected / total_due * 100) if total_due > 0 else 0

        result.append({
            "class_id": class_id,
            "class_name": row.class_name,
            "total_due": round(total_due, 2),
            "collected": round(collected, 2),
            "outstanding": round(outstanding, 2),
            "collection_percentage": round(collection_percentage, 2),
        })

    return result


# ============================================================
# MAIN DASHBOARD API
# ============================================================

fees_dashboard_api_bp = Blueprint('fees_dashboard_api_bp', __name__)


@login_required
@permission_required('pay_fees')
@fees_dashboard_api_bp.get("/api/fee-dashboard")
def fees_dashboard():

    try:
        current_session = 2026
        school_id = 'falak'

        summary, daily_collections = get_summary(current_session, school_id)

        class_analysis = get_class_analysis(current_session, school_id)


        payload = {
            "summary": summary,
            "daily_collections": daily_collections,
            "class_analysis": class_analysis,
        }

        return jsonify(payload), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        db.session.rollback()
        print("Fee dashboard error:", repr(e))
        return jsonify({"error": "Unable to load fee dashboard."}), 500

