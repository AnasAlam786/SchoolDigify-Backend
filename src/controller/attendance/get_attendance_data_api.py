# src/controller/get_fee.py

from datetime import date, datetime, timedelta
import calendar
from sqlalchemy import and_, or_
from flask import session, request, jsonify, Blueprint

from src.controller.permissions.has_permission import has_permission
from src.model import StudentsDB, StudentSessions, ClassData, Sessions
from src import db

from src.model.Attendance import Attendance
from src.model.AttendanceHolidays import AttendanceHolidays

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

def parse_date(date_str):
    possible_formats = [
        "%Y-%m-%d",  # HTML input format
        "%d/%m/%Y",  # Indian format 1
        "%d-%m-%Y",  # Indian format 2
    ]

    for fmt in possible_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue

    return None

get_attendance_data_api_bp = Blueprint( 'get_attendance_data_api_bp',   __name__)

@get_attendance_data_api_bp.route('/api/get_attendance_data', methods=["GET"])
@login_required
@permission_required('attendance')
def get_attendance_data_api():

    class_id = request.args.get("classID")
    date_str = request.args.get("date")

    current_session = session["session_id"]
    school_id = session["school_id"]
    current_date = datetime.today().date()


    date = parse_date(date_str)
    if date is None:
        return jsonify({"message": "Invalid date format. Use DD/MM/YYYY or DD-MM-YYYY"}), 400
    
    if current_date != date:
        if not has_permission("mark_any_day_attendance"):
            return jsonify({"message": "Access denied. You are only authorized to record attendance for today only."}), 403


    holiday = AttendanceHolidays.query.filter(
        AttendanceHolidays.school_id == school_id,
        AttendanceHolidays.date == date,
        or_(
            AttendanceHolidays.class_id == class_id,
            AttendanceHolidays.class_id.is_(None)
        )
    ).first()


    if holiday:
        return jsonify({
            "message": "There is a Holiday on this date.",
            "holiday": True,
            "info": f"Attendance cannot be marked on {date.strftime('%A, %d %B %Y')} as classes are not held on the occasion of {holiday.name}. If you need to record attendance for a special session, please contact your administrator."

        }), 200

    # Don't allow marking attendance on Sundays (weekday(): Monday=0 ... Sunday=6)
    if date.weekday() == 6:
        return jsonify({
            "message": "Sunday — No Classes Scheduled",
            "holiday": True,
            "info": "Attendance cannot be marked on Sundays as classes are not held. If you need to record attendance for a special session, please contact your administrator."
        }), 200
        
    
    # Build query
    attendance_data = (
        db.session.query(
            StudentsDB.STUDENTS_NAME,
            StudentsDB.FATHERS_NAME,
            StudentsDB.IMAGE, StudentsDB.PHONE,
            ClassData.CLASS,
            StudentSessions.ROLL,
            StudentSessions.id.label("student_session_id"),
            Attendance.status.label("attendance_status"),
            Attendance.remark
        )
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
        .outerjoin(
            Attendance,
            and_(
                Attendance.student_session_id == StudentSessions.id,
                Attendance.date == date
            )
        )
        .filter(
            StudentSessions.class_id == class_id,
            StudentSessions.session_id == current_session
        )
        .order_by(StudentSessions.ROLL.asc())
    ).all()

    total_students = len(attendance_data)
    present = absent = half_day = not_marked = 0

    for attendance in attendance_data:
        if attendance.attendance_status == "PRESENT":
            present +=1 
        elif attendance.attendance_status == "ABSENT":
            absent +=1 
        elif attendance.attendance_status == "HALF_DAY":
            half_day +=1 
        else:
            not_marked += 1

    attendance_data = [dict(row._mapping) for row in attendance_data]

    # Pack everything neatly into one variable
    attendance_summary = {
        "date": date.strftime("%A, %d %B %Y"),
        "total": total_students,
        "present": present,
        "absent": absent,
        "half_day": half_day,
        "not_marked": not_marked
    }
    
    return jsonify({"attendance_data": attendance_data, "attendance_summary": attendance_summary}), 200


@get_attendance_data_api_bp.route('/api/get_student_attendance_month', methods=["GET"])
@login_required
@permission_required('attendance')
def get_student_attendance_month_api():
    student_session_id = request.args.get('student_session_id')
    year = request.args.get('year')
    month = request.args.get('month')

    if not student_session_id or not year or not month:
        return jsonify({"error": "student_session_id, year, and month are required"}), 400

    try:
        year = int(year)
        month = int(month)
    except ValueError:
        return jsonify({"error": "Year and month must be numeric"}), 400

    if month < 1 or month > 12 or year < 1900 or year > 2100:
        return jsonify({"error": "Invalid year or month"}), 400

    current_session = session["session_id"]
    school_id = session["school_id"]

    student_record = (
        db.session.query(
            StudentsDB.STUDENTS_NAME,
            ClassData.CLASS,
            StudentSessions.id.label('student_session_id'),
            StudentSessions.class_id.label('class_id')
        )
        .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
        .filter(
            StudentSessions.id == student_session_id,
            StudentSessions.session_id == current_session,
            StudentsDB.school_id == school_id
        )
        .first()
    )

    if not student_record:
        return jsonify({"error": "Student session record not found"}), 404

    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    attendance_rows = (
        Attendance.query
        .filter(
            Attendance.student_session_id == student_session_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        )
        .all()
    )

    holiday_rows = (
        AttendanceHolidays.query
        .filter(
            AttendanceHolidays.school_id == school_id,
            AttendanceHolidays.session_id == current_session,
            AttendanceHolidays.date >= start_date,
            AttendanceHolidays.date <= end_date,
            or_(
                AttendanceHolidays.class_id == student_record.class_id,
                AttendanceHolidays.class_id.is_(None)
            )
        )
        .all()
    )

    attendance_map = {row.date: row.status for row in attendance_rows}
    holiday_dates = {row.date for row in holiday_rows}

    records = []
    for day in range(1, end_date.day + 1):
        current_date = date(year, month, day)
        if current_date in attendance_map:
            status = attendance_map[current_date]
        elif current_date.weekday() == 6 or current_date in holiday_dates:
            status = 'HOLIDAY'
        else:
            status = 'UNMARKED'

        records.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'status': status
        })

    monthly_summary = {
        'present': 0,
        'absent': 0,
        'half_day': 0,
        'leave': 0,
        'holiday': 0,
        'unmarked': 0
    }
    for record in records:
        key = record['status'].lower()
        if key == 'half_day':
            monthly_summary['half_day'] += 1
        elif key == 'unmarked':
            monthly_summary['unmarked'] += 1
        elif key == 'holiday':
            monthly_summary['holiday'] += 1
        elif key == 'leave':
            monthly_summary['leave'] += 1
        elif key == 'present':
            monthly_summary['present'] += 1
        elif key == 'absent':
            monthly_summary['absent'] += 1
        else:
            monthly_summary['unmarked'] += 1

    session_row = Sessions.query.filter_by(id=current_session).first()
    session_start = session_row.start_date if session_row and session_row.start_date else start_date
    session_end = session_row.end_date if session_row and session_row.end_date else end_date
    if session_start > session_end:
        session_start, session_end = start_date, end_date

    session_attendance_rows = (
        Attendance.query
        .filter(
            Attendance.student_session_id == student_session_id,
            Attendance.date >= session_start,
            Attendance.date <= session_end
        )
        .all()
    )

    session_holiday_rows = (
        AttendanceHolidays.query
        .filter(
            AttendanceHolidays.school_id == school_id,
            AttendanceHolidays.session_id == current_session,
            AttendanceHolidays.date >= session_start,
            AttendanceHolidays.date <= session_end,
            or_(
                AttendanceHolidays.class_id == student_record.class_id,
                AttendanceHolidays.class_id.is_(None)
            )
        )
        .all()
    )

    session_attendance_map = {row.date: row.status for row in session_attendance_rows}
    session_holiday_dates = {row.date for row in session_holiday_rows}

    total_session_days = (session_end - session_start).days + 1
    session_summary = {
        'present': 0,
        'absent': 0,
        'half_day': 0,
        'leave': 0,
        'holiday': 0,
        'unmarked': 0,
        'range': f"{session_start.strftime('%d %b %Y')} - {session_end.strftime('%d %b %Y')}"
    }

    for offset in range(total_session_days):
        current_date = session_start + timedelta(days=offset)
        if current_date in session_attendance_map:
            status = session_attendance_map[current_date]
        elif current_date.weekday() == 6 or current_date in session_holiday_dates:
            status = 'HOLIDAY'
        else:
            status = 'UNMARKED'

        key = status.lower()
        if key == 'half_day':
            session_summary['half_day'] += 1
        elif key == 'unmarked':
            session_summary['unmarked'] += 1
        elif key == 'holiday':
            session_summary['holiday'] += 1
        elif key == 'leave':
            session_summary['leave'] += 1
        elif key == 'present':
            session_summary['present'] += 1
        elif key == 'absent':
            session_summary['absent'] += 1
        else:
            session_summary['unmarked'] += 1

    session_summary['present_percent'] = round((session_summary['present'] / total_session_days) * 100, 1) if total_session_days else 0

    return jsonify({
        'student_name': student_record.STUDENTS_NAME,
        'class_name': student_record.CLASS,
        'records': records,
        'monthly_summary': monthly_summary,
        'session_summary': session_summary
    }), 200


@get_attendance_data_api_bp.route('/api/get_absent_students', methods=["GET"])
@login_required
@permission_required('attendance')
def get_absent_students():
    class_id = request.args.get('classID')
    date = request.args.get('date')

    if not class_id or not date:
        return jsonify({"message": "Class ID and date are required"}), 400

    current_session = session["session_id"]
    school_id = session["school_id"]
    current_date = datetime.today().date()

    # Parse date
    date_obj = parse_date(date)
    if date_obj is None:
        return jsonify({"message": "Invalid date format. Use DD/MM/YYYY or DD-MM-YYYY"}), 400
    
    # Permission check for non-current dates
    if current_date != date_obj:
        if not has_permission("mark_any_day_attendance"):
            return jsonify({"message": "Access denied. You are only authorized to record attendance for today only."}), 403

    try:
        # Get class name
        class_record = ClassData.query.filter_by(
            id=class_id, 
            school_id=school_id
        ).first()
        
        if not class_record:
            return jsonify({"message": "Class not found"}), 404

        class_name = class_record.CLASS

        # Get absent students with attendance status ABSENT
        attendance_query = (
            db.session.query(
                StudentsDB.STUDENTS_NAME,
                # StudentsDB.FATHERS_NAME,
                StudentSessions.ROLL,
            )
            .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
            .join(Attendance, and_(
                Attendance.student_session_id == StudentSessions.id,
                Attendance.date == date_obj,
                Attendance.status == "ABSENT"
            ))
            .filter(
                StudentSessions.class_id == class_id,
                StudentSessions.session_id == current_session
            )
            .order_by(StudentSessions.ROLL.asc())
            .all()
        )

        absent_students = [dict(row._mapping) for row in attendance_query]

        # also fetch unmarked students (no attendance record for that date)
        unmarked_query = (
            db.session.query(
                StudentsDB.STUDENTS_NAME,
                StudentSessions.ROLL,
            )
            .join(StudentSessions, StudentSessions.student_id == StudentsDB.id)
            .outerjoin(Attendance, and_(
                Attendance.student_session_id == StudentSessions.id,
                Attendance.date == date_obj
            ))
            .filter(
                StudentSessions.class_id == class_id,
                StudentSessions.session_id == current_session,
                Attendance.id.is_(None)
            )
            .order_by(StudentSessions.ROLL.asc())
            .all()
        )
        unmarked_students = [dict(row._mapping) for row in unmarked_query]

        # total students count for class
        total_students = StudentSessions.query.filter_by(
            class_id=class_id,
            session_id=current_session
        ).count()

        # Format date for display
        formatted_date = date_obj.strftime('%A, %d %B %Y')

        return jsonify({
            'success': True,
            'class_name': class_name,
            'date': formatted_date,
            'total_students': total_students,
            'absent_students': absent_students,
            'unmarked_students': unmarked_students
        })

    except Exception as e:
        print(f"Error fetching absent students: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error fetching absent students: {str(e)}'
        }), 500