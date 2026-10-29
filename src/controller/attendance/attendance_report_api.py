from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request, session
from sqlalchemy import or_

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model import ClassAccess, ClassData, Sessions, StudentsDB, StudentSessions
from src.model.Attendance import Attendance
from src.model.AttendanceHolidays import AttendanceHolidays


attendance_report_api_bp = Blueprint("attendance_report_api_bp", __name__)


def get_report_date_limits(session_id):
    current_session = Sessions.query.filter_by(id=session_id).first()
    if not current_session or not current_session.start_date:
        return None

    today = date.today()
    end_date = min(current_session.end_date, today) if current_session.end_date else today
    if current_session.start_date > end_date:
        return None

    return {
        "start_date": current_session.start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@attendance_report_api_bp.route("/api/attendance_report_limits", methods=["GET"])
@login_required
@permission_required("attendance")
def get_attendance_report_limits():
    limits = get_report_date_limits(session["session_id"])
    if not limits:
        return jsonify({"error": "The current session has no valid attendance report date range."}), 400
    return jsonify(limits), 200


@attendance_report_api_bp.route("/api/attendance_report", methods=["POST"])
@login_required
@permission_required("attendance")
def get_attendance_report():
    data = request.get_json(silent=True) or {}
    start_date_value = data.get("start_date")
    end_date_value = data.get("end_date")
    class_ids_value = data.get("class_ids")

    if not start_date_value or not end_date_value or not isinstance(class_ids_value, list) or not class_ids_value:
        return jsonify({"error": "Start date, end date, and at least one class are required."}), 400

    try:
        start_date = datetime.strptime(start_date_value, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_value, "%Y-%m-%d").date()
        class_ids = list(dict.fromkeys(int(class_id) for class_id in class_ids_value))
    except (TypeError, ValueError):
        return jsonify({"error": "Provide valid dates and class IDs."}), 400

    if end_date < start_date:
        return jsonify({"error": "End date must be on or after start date."}), 400

    school_id = str(session["school_id"])
    session_id = session["session_id"]
    user_id = session["user_id"]
    date_limits = get_report_date_limits(session_id)
    if not date_limits:
        return jsonify({"error": "The current session has no valid attendance report date range."}), 400

    if start_date < date.fromisoformat(date_limits["start_date"]) or end_date > date.fromisoformat(date_limits["end_date"]):
        return jsonify({
            "error": "The report dates must be within the current session and cannot be after today.",
            "date_limits": date_limits,
        }), 400

    permitted_classes = (
        db.session.query(ClassData.id, ClassData.CLASS)
        .join(ClassAccess, ClassAccess.class_id == ClassData.id)
        .filter(
            ClassData.id.in_(class_ids),
            ClassData.school_id == school_id,
            ClassAccess.staff_id == user_id,
        )
        .all()
    )
    if len(permitted_classes) != len(class_ids):
        return jsonify({"error": "One or more selected classes are unavailable."}), 403

    students = (
        db.session.query(
            StudentSessions.id.label("student_session_id"),
            StudentSessions.class_id,
            StudentSessions.ROLL,
            StudentsDB.STUDENTS_NAME,
            StudentsDB.FATHERS_NAME,
        )
        .join(StudentsDB, StudentsDB.id == StudentSessions.student_id)
        .filter(
            StudentSessions.class_id.in_(class_ids),
            StudentSessions.session_id == session_id,
            StudentsDB.school_id == school_id,
        )
        .order_by(StudentSessions.class_id, StudentSessions.ROLL.asc(), StudentsDB.STUDENTS_NAME.asc())
        .all()
    )
    student_ids = [student.student_session_id for student in students]

    attendance_rows = []
    if student_ids:
        attendance_rows = (
            Attendance.query
            .filter(
                Attendance.student_session_id.in_(student_ids),
                Attendance.date >= start_date,
                Attendance.date <= end_date,
            )
            .all()
        )

    holiday_rows = (
        AttendanceHolidays.query
        .filter(
            AttendanceHolidays.school_id == school_id,
            AttendanceHolidays.session_id == session_id,
            AttendanceHolidays.date >= start_date,
            AttendanceHolidays.date <= end_date,
            or_(
                AttendanceHolidays.class_id.in_(class_ids),
                AttendanceHolidays.class_id.is_(None),
            ),
        )
        .all()
    )

    attendance_by_student = {}
    for row in attendance_rows:
        attendance_by_student.setdefault(row.student_session_id, {})[row.date] = row.status

    holiday_dates_by_class = {class_id: set() for class_id in class_ids}
    school_holiday_dates = set()
    for holiday in holiday_rows:
        if holiday.class_id is None:
            school_holiday_dates.add(holiday.date)
        else:
            holiday_dates_by_class[holiday.class_id].add(holiday.date)

    students_by_class = {class_id: [] for class_id in class_ids}
    for student in students:
        students_by_class[student.class_id].append(student)

    report_classes = []
    for class_row in permitted_classes:
        class_id = class_row.id
        holiday_dates = set(school_holiday_dates) | holiday_dates_by_class[class_id]
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() == 6:
                holiday_dates.add(current_date)
            current_date += timedelta(days=1)

        current_date = start_date
        open_dates = set()
        while current_date <= end_date:
            if current_date not in holiday_dates:
                open_dates.add(current_date)
            current_date += timedelta(days=1)

        class_students = []
        for student in students_by_class[class_id]:
            counts = {
                "present": 0,
                "absent": 0,
                "half_day": 0,
                "unmarked": 0,
                "holidays": len(holiday_dates),
                "leave": 0,
            }
            student_attendance = attendance_by_student.get(student.student_session_id, {})
            for attendance_date in open_dates:
                status = student_attendance.get(attendance_date)
                if status == "PRESENT":
                    counts["present"] += 1
                elif status == "ABSENT":
                    counts["absent"] += 1
                elif status == "HALF_DAY":
                    counts["half_day"] += 1
                elif status == "LEAVE":
                    counts["leave"] += 1
                elif status == "HOLIDAY":
                    counts["holidays"] += 1
                else:
                    counts["unmarked"] += 1

            open_days = len(open_dates)
            class_students.append({
                "student_name": student.STUDENTS_NAME,
                "fathers_name": student.FATHERS_NAME,
                "roll": student.ROLL,
                **counts,
                "school_opened": open_days,
                "present_percentage": round(counts["present"] * 100 / open_days, 1) if open_days else 0,
                "absent_percentage": round(counts["absent"] * 100 / open_days, 1) if open_days else 0,
            })

        report_classes.append({
            "class_id": class_id,
            "class_name": class_row.CLASS,
            "school_opened": len(open_dates),
            "holidays": len(holiday_dates),
            "students": class_students,
        })

    return jsonify({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "classes": report_classes,
    }), 200