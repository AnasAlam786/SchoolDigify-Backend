from flask import Blueprint, jsonify, request, session

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.fees.utils.fee_summary import (
    get_daily_collections,
    get_fee_summary,
    get_class_analysis,
)

fees_dashboard_api_bp = Blueprint('fees_dashboard_api_bp', __name__)


def _dashboard_response(get_data, response_key, **data_kwargs):
    try:
        current_session = session.get("session_id")
        school_id = session.get("school_id")
        if not current_session or not school_id:
            return jsonify({"error": "Invalid or expired session"}), 401

        return jsonify({
            response_key: get_data(current_session, school_id, **data_kwargs),
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