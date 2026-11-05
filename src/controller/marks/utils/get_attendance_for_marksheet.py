from datetime import timedelta

from sqlalchemy import func, or_

from src.model.AttendanceHolidays import AttendanceHolidays
from src.model.SchoolSession import SchoolSession
from src.model.Sessions import Sessions
from src.model.Attendance import Attendance
from src import db


def _set_student_field(student, field, value):
    student[field] = value
    nested_student = student.get("student")
    if isinstance(nested_student, dict):
        nested_student[field] = value


def get_attendance_for_marksheet(marksheet_data, current_session_id, school_id):
    students_with_no_attendance = [
        student
        for student in marksheet_data
        if student.get("Attendance") is None
        or (
            isinstance(student.get("Attendance"), str)
            and not student["Attendance"].strip()
        )
    ]

    student_session_ids = [
        student.get("student_session_id")
        for student in students_with_no_attendance
        if student.get("student_session_id") is not None
    ]

    if student_session_ids:
        present_counts = dict(
            db.session.query(
                Attendance.student_session_id,
                func.count(Attendance.id),
            )
            .filter(
                Attendance.student_session_id.in_(student_session_ids),
                Attendance.status == "PRESENT",
            )
            .group_by(Attendance.student_session_id)
            .all()
        )
    else:
        present_counts = {}

    class_ids = {
        student.get("class_id")
        for student in marksheet_data
        if student.get("class_id") is not None
    }

    school_session = (
        db.session.query(
            SchoolSession.working_days,
            SchoolSession.session_start_date,
            SchoolSession.session_end_date,
        )
        .filter(
            SchoolSession.school_id == school_id,
            SchoolSession.session_id == current_session_id,
        )
        .first()
    )

    fallback_working_days = school_session.working_days if school_session else None
    session_start = school_session.session_start_date if school_session else None
    session_end = school_session.session_end_date if school_session else None

    if not session_start or not session_end or session_start > session_end:
        session_dates = (
            db.session.query(Sessions.start_date, Sessions.end_date)
            .filter(Sessions.id == current_session_id)
            .first()
        )
        session_start, session_end = session_dates if session_dates else (None, None)

    holiday_rows = []
    if class_ids:
        holiday_rows = (
            AttendanceHolidays.query
            .filter(
                AttendanceHolidays.session_id == current_session_id,
                AttendanceHolidays.school_id == school_id,
                or_(
                    AttendanceHolidays.class_id.in_(class_ids),
                    AttendanceHolidays.class_id.is_(None),
                ),
            )
            .all()
        )

    school_holiday_dates = set()
    class_holiday_dates = {class_id: set() for class_id in class_ids}
    for holiday in holiday_rows:
        if holiday.class_id is None:
            school_holiday_dates.add(holiday.date)
        else:
            class_holiday_dates[holiday.class_id].add(holiday.date)

    working_days_by_class = {}
    for class_id in class_ids:
        holiday_dates = school_holiday_dates | class_holiday_dates[class_id]

        if session_start and session_end and session_start <= session_end:
            working_days = 0
            current_date = session_start
            while current_date <= session_end:
                if current_date.weekday() != 6 and current_date not in holiday_dates:
                    working_days += 1
                current_date += timedelta(days=1)
        elif fallback_working_days is not None:
            weekday_holidays = sum(
                holiday_date.weekday() != 6
                for holiday_date in holiday_dates
            )
            working_days = max(0, int(fallback_working_days) - weekday_holidays)
        else:
            working_days = None

        working_days_by_class[class_id] = working_days

        

    for student in students_with_no_attendance:
        student_session_id = student.get("student_session_id")
        if student_session_id is not None:
            _set_student_field(
                student,
                "Attendance",
                present_counts.get(student_session_id, 0),
            )

    for student in marksheet_data:
        class_id = student.get("class_id")
        _set_student_field(
            student,
            "working_days",
            working_days_by_class.get(class_id),
        )

    return marksheet_data
