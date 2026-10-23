# src/controller/get_fee.py

from datetime import datetime
from time import time
from flask import session, request, jsonify, Blueprint
from sqlalchemy import and_, or_

from src.controller.permissions.has_permission import has_permission
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

from src.model import Attendance, AttendanceHolidays, ClassData, StudentSessions
from src import db

mark_attendance_api_bp = Blueprint( 'mark_attendance_api_bp',   __name__)

@mark_attendance_api_bp.route('/api/mark_attendance', methods=["POST"])
@login_required
@permission_required('attendance')
def mark_attendance_api():
    start_time = time()  # start timer
    # --- Read Inputs ---
    data = request.json
    student_session_id = data.get("student_session_id")
    status = data.get("status")
    date_str = data.get("date")
    remark = data.get("remark") or None

    current_session = session["session_id"]
    user_id = session["user_id"]

    # --- Input Validation ---
    if not student_session_id or not date_str:
        return jsonify({"message": "studentSessionID and date are required"}), 400

    # Allowed attendance statuses
    allowed_status = {"PRESENT", "ABSENT", "HALF_DAY", "LEAVE", "HOLIDAY", None}
    if status not in allowed_status:
        return jsonify({"message": "Invalid attendance status"}), 400

    # --- Date Parsing ---
    def parse_date(date_str):
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                pass
        return None

    date = parse_date(date_str)
    if date is None:
        return jsonify({"message": "Invalid date format"}), 400
    
    current_date = datetime.today().date()
    if current_date != date:
        if not has_permission("mark_any_day_attendance"):
            return jsonify({"message": "Access denied. You are only authorized to record attendance for today only."}), 403

    # --- Validate student session and check holidays/Sundays ---
    school_id = session.get("school_id")


    # Check if the date is a holiday for the school or the specific class
    holiday = AttendanceHolidays.query.filter(
        AttendanceHolidays.school_id == school_id,
        AttendanceHolidays.date == date,
    ).first()

    if holiday:
        student_session = (
            db.session.query(StudentSessions.id, StudentSessions.class_id)
            .filter(
                and_(
                    StudentSessions.id == student_session_id,
                    StudentSessions.session_id == current_session,
                )
            ).first()
        )
        if not student_session:
            return jsonify({"message": "Invalid student session"}), 404
        
        holiday_name = getattr(holiday, 'name', None)
        class_id = student_session.class_id

        # 2. Determine if holiday applies to this student
        holiday_applies = holiday.class_id is None or holiday.class_id == class_id

        if holiday_applies:
            # 3. Build a consistent message
            if holiday_name:
                msg = (
                    f"Attendance cannot be recorded on "
                    f"{date.strftime('%A, %d %B %Y')} because it is a scheduled holiday "
                    f"({holiday_name}). If you believe this is incorrect, please contact administration."
                )
            else:
                msg = (
                    "Attendance cannot be recorded on this date because it is a "
                    "scheduled holiday. If you believe this is incorrect, please contact administration."
                )

            return jsonify({"message": msg}), 400


    # Don't allow marking attendance on Sundays (weekday(): Monday=0 ... Sunday=6)
    if date.weekday() == 6:
        return jsonify({"message": "Attendance cannot be recorded for Sundays. If this is an exception, please contact administration."}), 400
    
    # --- Check Existing Attendance ---
    attendance = Attendance.query.filter_by(
        student_session_id=student_session_id,
        date=date
    ).first()

    if not status:
        if attendance:
            db.session.delete(attendance)
            try:
                db.session.commit()
                end_time = time()  # end timer
                print(f"Attendance took {end_time - start_time:.6f} to mark")
                return jsonify({"message": "success"}), 200
            except Exception as e:
                db.session.rollback()
                print("Attendance Deletion Error:", e)
                return jsonify({"message": "Database error"}), 500

    # --- Insert or Update Attendance ---
    if attendance:
        attendance.status = status
        attendance.remark = remark
        attendance.marked_by = user_id 
    else:
        attendance = Attendance(
            student_session_id=student_session_id,
            date=date,
            status=status,
            marked_by=user_id,
            remark=remark
        )
        db.session.add(attendance)

    # --- Commit Safely ---
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Attendance Error:", e)
        return jsonify({"message": "Database error"}), 500
    
    end_time = time()  # end timer
    print(f"Attendance took {end_time - start_time:.6f} to mark")

    return jsonify({"message": "success"}), 200


@mark_attendance_api_bp.route('/api/bulk_mark_attendance', methods=["POST"])
@login_required
@permission_required('attendance')
def bulk_mark_attendance_api():
    data = request.get_json(silent=True) or {}
    class_id = data.get("class_id")
    date_str = data.get("date")
    action = data.get("action")

    if not class_id or not date_str:
        return jsonify({"message": "Class and date are required"}), 400
    if action not in {"PRESENT", "ABSENT", "UNMARK"}:
        return jsonify({"message": "Invalid bulk attendance action"}), 400

    date = None
    for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            date = datetime.strptime(date_str, date_format).date()
            break
        except (TypeError, ValueError):
            continue
    if date is None:
        return jsonify({"message": "Invalid date format"}), 400

    current_date = datetime.today().date()
    if current_date != date and not has_permission("mark_any_day_attendance"):
        return jsonify({"message": "Access denied. You are only authorized to record attendance for today only."}), 403

    school_id = session.get("school_id")
    current_session = session["session_id"]
    user_id = session["user_id"]
    class_data = ClassData.query.filter_by(id=class_id, school_id=school_id).first()
    if not class_data:
        return jsonify({"message": "Invalid class"}), 404

    holiday = AttendanceHolidays.query.filter(
        AttendanceHolidays.school_id == school_id,
        AttendanceHolidays.date == date,
        or_(AttendanceHolidays.class_id == class_id, AttendanceHolidays.class_id.is_(None)),
    ).first()
    if holiday:
        return jsonify({"message": "Attendance cannot be recorded on a scheduled holiday."}), 400
    if date.weekday() == 6:
        return jsonify({"message": "Attendance cannot be recorded for Sundays."}), 400

    student_session_ids = [row[0] for row in db.session.query(StudentSessions.id).filter(
        StudentSessions.class_id == class_id,
        StudentSessions.session_id == current_session,
    ).all()]

    if not student_session_ids:
        return jsonify({"message": "No students are enrolled in this class for the selected session.", "student_count": 0}), 200

    attendance_rows = Attendance.query.filter(
        Attendance.student_session_id.in_(student_session_ids),
        Attendance.date == date,
    ).all()

    try:
        if action == "UNMARK":
            removed_count = len(attendance_rows)
            for attendance in attendance_rows:
                db.session.delete(attendance)
            message = f"Attendance cleared for {removed_count} student(s)."
        else:
            attendance_by_student = {row.student_session_id: row for row in attendance_rows}
            for student_session_id in student_session_ids:
                attendance = attendance_by_student.get(student_session_id)
                if attendance:
                    attendance.status = action
                    attendance.marked_by = user_id
                else:
                    db.session.add(Attendance(
                        student_session_id=student_session_id,
                        date=date,
                        status=action,
                        marked_by=user_id,
                    ))
            message = f"{action.title()} attendance marked for {len(student_session_ids)} student(s)."

        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print("Bulk Attendance Error:", error)
        return jsonify({"message": "Database error while updating attendance"}), 500

    return jsonify({
        "message": message,
        "student_count": len(student_session_ids),
    }), 200