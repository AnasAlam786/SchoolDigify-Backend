from flask import request, Blueprint, session, current_app
from datetime import datetime, timedelta

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required
from src.model.AttendanceHolidays import AttendanceHolidays
from src.model.ClassData import ClassData
from src import db


holiday_manager_api_bp = Blueprint('holiday_manager_api_bp', __name__)


@holiday_manager_api_bp.route('/api/add-holiday', methods=["POST"])
@login_required
@permission_required('mark_holiday')
def add_holiday():
    """Add holiday(s) to AttendanceHolidays. Supports date range (inclusive).

    Expects form fields: holiday_name, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), apply_to (empty for all or class id)
    """
    current_session_id = session["session_id"]
    school_id =session['school_id']

    data = request.json

    holiday_name = data.get('holiday_name')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    apply_to = data.get('apply_to')  # empty for entire school or class.id


    print(holiday_name, start_date, end_date, apply_to)
    if not holiday_name:
        return {"error": "Please Enter Holiday Name!"}, 400
    if not start_date:
        return {"error": "Please Enter Start Date!"}, 400
    if not end_date:
        return {"error": "Please Enter End Date!"}, 400

    # Determine class_id
    if apply_to == "" or apply_to is None:
        class_id = None
    else:
        try:
            class_id = int(apply_to)
        except Exception:
            return {"error": "Invalid class id"}, 400

    # Parse dates
    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}, 400

    if e_date < s_date:
        return {"error": "End date must be same or after start date."}, 400

    # Use a single created_at for the batch so we can group/edit/delete later
    created_at_batch = datetime.utcnow()

    # Create holiday rows for each date in range, avoid duplicates
    added = 0
    cur = s_date
    while cur <= e_date:
        exists = db.session.query(AttendanceHolidays).filter(
            AttendanceHolidays.school_id == str(school_id),
            AttendanceHolidays.session_id == current_session_id,
            AttendanceHolidays.date == cur,
            (AttendanceHolidays.class_id == class_id if class_id is not None else AttendanceHolidays.class_id.is_(None))
        ).first()

        if not exists:
            holiday = AttendanceHolidays(
                school_id=str(school_id),
                date=cur,
                name=holiday_name,
                class_id=class_id,
                session_id=current_session_id,
                created_at=created_at_batch
            )
            db.session.add(holiday)
            added += 1

        cur = cur + timedelta(days=1)

    try:
        if added > 0:
            db.session.commit()
        else:
            # nothing new added, still return success but note 0
            db.session.rollback()
    except Exception as e:
        current_app.logger.exception('Failed to add holiday(s)')
        db.session.rollback()
        return {"error": "Database error while saving holiday."}, 500

    return {"success": True, "message": f"Added {added} holiday(s).", "added": added}


@holiday_manager_api_bp.route('/api/get_holidays', methods=["GET"])
@login_required
def list_holidays():
    """Return grouped holiday batches for current school (grouped by created_at).

    Response: { batches: [ { batch_id, name, class_id, class_name, start_date, end_date, days, entries: [{id,date}] } ] }
    """
    school_id = session.get('school_id')
    current_session_id = session.get('session_id')

    rows = (
        db.session.query(AttendanceHolidays)
            .filter(AttendanceHolidays.school_id == str(school_id),
                    AttendanceHolidays.session_id == current_session_id)
            .order_by(AttendanceHolidays.created_at.desc(), AttendanceHolidays.date.asc())
            .all()
        )
    
    batches = {}
    for r in rows:
        batch_id = r.created_at.isoformat()
        ent = {"id": r.id, "date": r.date.isoformat()}
        if batch_id not in batches:
            # try to get class name
            class_name = None
            if r.class_id:
                c = db.session.query(ClassData).filter(ClassData.id == r.class_id).first()
                class_name = c.CLASS if c else None
            batches[batch_id] = {
                "batch_id": batch_id, "holiday_name": r.name, 
                "class_id": r.class_id, "class_name": class_name, 
                "entries": [ent], "dates": [r.date]
            }
        else:
            batches[batch_id]["entries"].append(ent)
            batches[batch_id]["dates"].append(r.date)

    result = []
    for k, v in batches.items():
        dates = sorted(v["dates"]) if v["dates"] else []
        start = dates[0].isoformat() if dates else None
        end = dates[-1].isoformat() if dates else None
        days = len(dates)
        result.append({
            "batch_id": v["batch_id"], "holiday_name": v["holiday_name"], 
            "class_id": v["class_id"], "class_name": v.get("class_name"), 
            "start_date": start, "end_date": end, "days": days, "entries": v["entries"]
        })
    return {"holidays": result}


@holiday_manager_api_bp.route('/api/holidays/<path:batch_id>', methods=["PUT"])
@login_required
@permission_required('mark_holiday')
def update_holiday(batch_id):
    """Update a holiday batch identified by batch_id (created_at iso). Recreate rows for provided date range."""
    school_id = session.get('school_id') or request.form.get('school_id')
    current_session_id = session.get('session_id')
    if not school_id:
        return {"error": "Missing school context (school_id)"}, 400

    holiday_name = request.form.get('holiday_name')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    apply_to = request.form.get('apply_to')

    if not holiday_name or not start_date or not end_date:
        return {"error": "Missing required fields"}, 400

    try:
        created_at_dt = datetime.fromisoformat(batch_id)
    except Exception:
        return {"error": "Invalid batch id"}, 400

    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}, 400

    if e_date < s_date:
        return {"error": "End date must be same or after start date."}, 400

    if apply_to == "" or apply_to is None:
        class_id = None
    else:
        try:
            class_id = int(apply_to)
        except Exception:
            return {"error": "Invalid class id"}, 400

    try:
        # delete existing rows for this batch (also filter by session)
        db.session.query(AttendanceHolidays).filter(
            AttendanceHolidays.school_id == str(school_id),
            AttendanceHolidays.session_id == current_session_id,
            AttendanceHolidays.created_at == created_at_dt
        ).delete()

        # recreate rows for new range with same created_at and proper session_id
        cur = s_date
        added = 0
        while cur <= e_date:
            holiday = AttendanceHolidays(
                school_id=str(school_id),
                date=cur,
                name=holiday_name,
                class_id=class_id,
                session_id=current_session_id,
                created_at=created_at_dt
            )
            db.session.add(holiday)
            added += 1
            cur = cur + timedelta(days=1)

        db.session.commit()
    except Exception as e:
        current_app.logger.exception('Failed to update holiday batch')
        db.session.rollback()
        return {"error": "Database error while updating holiday."}, 500

    return {"success": True, "message": f"Updated holiday batch, {added} day(s).", "added": added}


@holiday_manager_api_bp.route('/api/delete_holiday/<path:batch_id>', methods=["POST"])
@login_required
@permission_required('mark_holiday')
def delete_holiday(batch_id):
    school_id = session.get('school_id')
    current_session_id = session.get('session_id')
    print(batch_id)

    try:
        created_at_dt = datetime.fromisoformat(batch_id)
    except Exception:
        return {"error": "Invalid batch id"}, 400

    try:
        deleted = db.session.query(AttendanceHolidays).filter(
            AttendanceHolidays.school_id == str(school_id),
            AttendanceHolidays.session_id == current_session_id,
            AttendanceHolidays.created_at == created_at_dt
        ).delete()
        db.session.commit()
    except Exception as e:
        print(e)
        db.session.rollback()
        return {"error": "Database error while deleting holiday."}, 500

    return {"success": True, "message": f"Deleted {deleted} holiday(s).", "deleted": deleted}
