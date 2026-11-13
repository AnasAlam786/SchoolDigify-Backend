from datetime import date

from flask import Blueprint, jsonify, request, session

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.fees.utils.fee_summary import (
    get_daily_collections,
    get_fee_summary,
    get_class_analysis,
    get_transactions_data
)

fees_dashboard_api_bp = Blueprint('fees_dashboard_api_bp', __name__)


def _dashboard_response(get_data, response_key, response_formatter=None, **data_kwargs):
    try:
        current_session = session.get("session_id")
        school_id = session.get("school_id")
        if not current_session or not school_id:
            return jsonify({"error": "Invalid or expired session"}), 401

        data = get_data(current_session, school_id, **data_kwargs)
        additional_data = {}
        if response_formatter:
            data, additional_data = response_formatter(data)

        return jsonify({
            response_key: data,
            **additional_data,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print("Fee dashboard error:", repr(e))
        return jsonify({"error": "Unable to load fee dashboard."}), 500


@login_required
@permission_required('pay_fees')
@fees_dashboard_api_bp.get("/api/fee-dashboard/summary")
def fees_dashboard_summary():
    raw_class_ids = request.args.getlist("class_ids")
    try:
        class_ids = [
            int(class_id.strip())
            for value in raw_class_ids
            for class_id in value.split(",")
            if class_id.strip()
        ] or None
    except ValueError:
        return jsonify({"error": "class_ids must contain integers"}), 400

    search_query = request.args.get("search_query", "").strip() or None
    return _dashboard_response(
        get_fee_summary,
        "summary",
        class_ids=class_ids,
        search_query=search_query,
    )


@login_required
@permission_required('pay_fees')
@fees_dashboard_api_bp.get("/api/fee-dashboard/daily-collections")
def fees_dashboard_daily_collections():
    return _dashboard_response(get_daily_collections, "daily_collections")


@login_required
@permission_required('pay_fees')
@fees_dashboard_api_bp.get("/api/fee-dashboard/class-analysis")
def fees_dashboard_class_analysis():
    return _dashboard_response(get_class_analysis, "class_analysis")


@login_required
@permission_required('pay_fees')
@fees_dashboard_api_bp.get("/api/fee-dashboard/transactions-data")
def fees_dashboard_transactions_data():
    try:
        offset = int(request.args.get("offset", "0"))
        if offset < 0:
            raise ValueError("offset must be a non-negative integer")

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        start_date = date.fromisoformat(start_date) if start_date else None
        end_date = date.fromisoformat(end_date) if end_date else None
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return _dashboard_response(
        get_transactions_data,
        "transactions_data",
        response_formatter=lambda page: (
            page[0][:10],
            {
                "has_more": len(page[0]) > 10,
                "offset": offset,
                "limit": 10,
                "total_count": page[1],
            },
        ),
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=11,
        include_total=True,
    )