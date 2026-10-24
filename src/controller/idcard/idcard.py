
# src/controller/idcard/idcard.py

import os
import base64
import binascii
import calendar
from datetime import date, datetime, timedelta

from flask import session, Blueprint, jsonify, request
from sqlalchemy import and_, func, or_
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


from src.model import Schools, TeachersLogin
from src.model.StudentsDB import StudentsDB
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.ClassAccess import ClassAccess
from src.model.Attendance import Attendance
from src.model.AttendanceHolidays import AttendanceHolidays
from src.model.FeeData import FeeData
from src.model.FeeHeads import FeeHeads
from src.model.FeeSessionData import FeeSessionData
from src.model.FeeStructure import FeeStructure
from src.model.FeeTransaction import FeeTransaction
from src.model.Sessions import Sessions

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.marks.utils.fetch_marks import result_data
from src.controller.marks.utils.format_marks import prepare_marks_format

AES_KEY = bytes.fromhex(os.environ["QR_CODE_SECRET"])
cipher = AESGCM(AES_KEY)

def encrypt_student_id(student_id):
    nonce = os.urandom(12)

    encrypted = cipher.encrypt(
        nonce,
        str(student_id).encode(),
        None
    )

    token = base64.urlsafe_b64encode(
        nonce + encrypted
    ).decode().rstrip("=")

    return token


def decrypt_student_id(token):
    try:
        token += "=" * (-len(token) % 4)

        data = base64.b64decode(
            token,
            altchars=b'-_',
            validate=True
        )

        if len(data) < 28:
            raise ValueError("Invalid token")

        nonce = data[:12]
        encrypted = data[12:]

        decrypted_id = cipher.decrypt(
            nonce,
            encrypted,
            None
        ).decode()

        student_id = int(decrypted_id)

        if student_id <= 0:
            raise ValueError("Invalid student ID")

        return student_id

    except (ValueError, TypeError, binascii.Error, InvalidTag,
            UnicodeDecodeError, OverflowError):
        return None


idcard_bp = Blueprint( 'idcard_bp',   __name__)

@idcard_bp.route('/api/idcard_students/<int:class_id>', methods=['GET'])
@login_required
@permission_required('idcard')
def get_students_by_class(class_id):
    school_id = session['school_id']
    current_session = session["session_id"]
    user_id = session["user_id"]

    # Check if user has access to this class
    has_access = db.session.query(ClassAccess).filter(
        ClassAccess.staff_id == user_id,
        ClassAccess.class_id == class_id
    ).first()
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    # Query students for the specific class
    students_query = db.session.query(
        StudentsDB.STUDENTS_NAME,
        func.to_char(StudentsDB.DOB, 'Dy, DD Mon YYYY').label('dob'),
        StudentsDB.FATHERS_NAME, StudentsDB.IMAGE,
        StudentsDB.PHONE, StudentsDB.ADDRESS,
        StudentSessions.id.label("student_id"),
        StudentSessions.ROLL,
        StudentSessions.class_id,
        ClassData.CLASS, ClassData.Section,
        TeachersLogin.Sign.label('teachers_sign'),
        TeachersLogin.Name.label('teachers_name')
    ).join(
        StudentSessions, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, StudentSessions.class_id == ClassData.id
    ).outerjoin(
        TeachersLogin, ClassData.class_teacher_id == TeachersLogin.id
    ).filter(
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == current_session,
        ClassData.id == class_id
    ).order_by(
        StudentSessions.ROLL.asc()
    ).all()

    # Get school data
    school = db.session.query(
        func.upper(Schools.School_Name).label('School_Name'),
        Schools.Address,
        Schools.Phone,
        Schools.Logo,
        Schools.UDISE
    ).filter(
        Schools.id == school_id
    ).first()

    principal = db.session.query(
            TeachersLogin.Sign,
            TeachersLogin.Name
        ).filter(
            TeachersLogin.school_id == school_id,
            TeachersLogin.role_id == 2
        ).first()

    if principal:
        principal_sign, principal_name = principal
    else:
        principal_sign, principal_name = None, None

    current_session = int(current_session)
    session_year = f"{current_session}-{str(current_session + 1)[-2:]}"

    students_data = []
    for student in students_query:
        encrypted_student_id = encrypt_student_id(student.student_id)
        students_data.append({
            'student_id': student.student_id,
            'qr_value':f"https://schooldigify.com/idcard/{encrypted_student_id}",
            'student_name': student.STUDENTS_NAME,
            'dob': student.dob,
            'father_name': student.FATHERS_NAME,
            'image': student.IMAGE,
            'phone': student.PHONE,
            'address': student.ADDRESS,
            'roll': student.ROLL,
            'class': student.CLASS,
            'section': student.Section,
            'teacher_sign': student.teachers_sign,
            'teacher_name': student.teachers_name,
            'class_roll': f"{student.CLASS} - {student.ROLL}",
            'session_year': session_year
        })

    return jsonify({
        'students_data': students_data,
        'school_data': {
            'name': school.School_Name if school else '',
            'address': school.Address if school else '',
            'phone': school.Phone if school else '',
            'logo': school.Logo if school else '',
            'udise': school.UDISE if school else '',
            'principal_sign': principal_sign if principal_sign else '',
            'principal_name': principal_name if principal_name else '',
        },
        
    })




@idcard_bp.route('/api/public/idcard/<token>', methods=['GET'])
def verify_student_idcard(token):
    student_id = decrypt_student_id(token)

    if student_id is None:
        return jsonify({'error': 'Invalid ID card'}), 404

    student_record = db.session.query(
        StudentsDB,
        StudentSessions,
        ClassData,
        Schools,
    ).join(
        StudentSessions, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, ClassData.id == StudentSessions.class_id
    ).join(
        Schools, Schools.id == StudentsDB.school_id
    ).filter(
        StudentSessions.id == student_id,
        ClassData.school_id == Schools.id,
    ).first()

    if not student_record:
        return jsonify({'error': 'Student not found'}), 404

    student, student_session, class_data, school = student_record
    current_session = int(student_session.session_id)
    session_year = f"{current_session}-{str(current_session + 1)[-2:]}"

    # Return only student-facing information; government IDs, bank details,
    # and sibling records are deliberately excluded from the public QR page.
    student_data = {
        'student_session_id': student_session.id,
        'name': student.STUDENTS_NAME,
        'STUDENTS_NAME': student.STUDENTS_NAME,
        'father_name': student.FATHERS_NAME,
        'FATHERS_NAME': student.FATHERS_NAME,
        'mother_name': student.MOTHERS_NAME,
        'MOTHERS_NAME': student.MOTHERS_NAME,
        'dob': student.dob_indian,
        'DOB': student.dob_indian,
        'gender': student.GENDER.value if hasattr(student.GENDER, 'value') else student.GENDER,
        'GENDER': student.GENDER.value if hasattr(student.GENDER, 'value') else student.GENDER,
        'blood_group': student.BLOOD_GROUP.value if hasattr(student.BLOOD_GROUP, 'value') else student.BLOOD_GROUP,
        'BLOOD_GROUP': student.BLOOD_GROUP.value if hasattr(student.BLOOD_GROUP, 'value') else student.BLOOD_GROUP,
        'height': f"{student_session.Height} cm" if student_session.Height else None,
        'Height': f"{student_session.Height} cm" if student_session.Height else None,
        'weight': f"{student_session.Weight} kg" if student_session.Weight else None,
        'Weight': f"{student_session.Weight} kg" if student_session.Weight else None,
        'image': student.IMAGE,
        'IMAGE': student.IMAGE,
        'roll': student_session.ROLL,
        'ROLL': student_session.ROLL,
        'class': class_data.CLASS,
        'CLASS': class_data.CLASS,
        'section': class_data.Section,
        'session_year': session_year,
        'SR': student.SR,
        'ADMISSION_NO': student.ADMISSION_NO,
        'ADMISSION_DATE': student.admission_date_indian,
        'ADDRESS': student.ADDRESS,
        'PHONE': student.PHONE,
        'ALT_MOBILE': student.ALT_MOBILE,
        'PIN': student.PIN,
        'EMAIL': student.EMAIL,
        'siblings': [],
        'is_RTE': False,
    }

    fee_rows = db.session.query(
        FeeSessionData,
        FeeStructure,
        FeeHeads,
        FeeData,
        FeeTransaction,
    ).join(
        FeeStructure, FeeSessionData.structure_id == FeeStructure.id
    ).outerjoin(
        FeeHeads, FeeStructure.fee_type_id == FeeHeads.id
    ).outerjoin(
        FeeData,
        and_(
            FeeData.fee_session_id == FeeSessionData.id,
            FeeData.student_session_id == student_session.id,
        ),
    ).outerjoin(
        FeeTransaction,
        and_(
            FeeTransaction.id == FeeData.transaction_id,
            FeeTransaction.school_id == school.id,
        ),
    ).filter(
        FeeSessionData.class_id == student_session.class_id,
        FeeSessionData.session_id == student_session.session_id,
        FeeStructure.school_id == school.id,
    ).order_by(
        FeeStructure.sequence_number.asc(),
        FeeTransaction.payment_date.desc(),
    ).all()

    fee_items = {}
    transaction_data = {}
    for fee_session, fee_structure, fee_head, fee_data, transaction in fee_rows:
        fee_session_id = fee_session.id
        amount = float(fee_session.amount or 0)
        fee_type = (
            fee_head.fee_type if fee_head and fee_head.fee_type
            else fee_structure.fee_type or ''
        )
        if fee_session_id not in fee_items:
            if fee_session.custom_due_date:
                due_date = fee_session.custom_due_date
            elif fee_structure.due_day and fee_structure.due_month:
                try:
                    due_date = date(
                        int(student_session.session_id) + int(fee_structure.year_increment or 0),
                        int(fee_structure.due_month),
                        int(fee_structure.due_day),
                    )
                except ValueError:
                    due_date = None
            else:
                due_date = None

            fee_items[fee_session_id] = {
                'id': fee_session_id,
                'fee_id': fee_session_id,
                'fee_type': fee_type,
                'period_name': fee_structure.period_name,
                'amount': amount,
                'dueDate': due_date.strftime('%d-%m-%Y') if due_date else 'N/A',
                'status': 'UPCOMING' if due_date is None or due_date >= date.today() else 'DUE',
                'paid_date': None,
                'transaction_no': None,
                'paid_amount': 0.0,
            }

        item = fee_items[fee_session_id]
        has_valid_payment = (
            fee_data
            and (
                not fee_data.transaction_id
                or (transaction and not transaction.is_deleted)
            )
        )
        if has_valid_payment:
            paid_amount = float(fee_data.paid_amount or 0)
            item['paid_amount'] += paid_amount
            status = fee_data.fee_payment_status
            status = status.value if hasattr(status, 'value') else str(status)
            if status == 'PAID' or item['paid_amount'] >= amount:
                item['status'] = 'PAID'
                item['amount'] = amount
            else:
                item['status'] = 'DUE'
                item['amount'] = max(amount - item['paid_amount'], 0)

            if transaction and not transaction.is_deleted:
                item['paid_date'] = (
                    transaction.payment_date.strftime('%d-%m-%Y')
                    if transaction.payment_date else None
                )
                item['transaction_no'] = transaction.transaction_no

            if transaction and not transaction.is_deleted:
                txn_id = transaction.id
                if txn_id not in transaction_data:
                    transaction_data[txn_id] = {
                        'id': txn_id,
                        'phone': None,
                        'transaction_no': transaction.transaction_no or f"TXN-{txn_id}",
                        'payment_date': transaction.payment_date.isoformat() if transaction.payment_date else None,
                        'paid_amount': float(transaction.paid_amount or 0),
                        'discount': float(transaction.discount or 0),
                        'payment_mode': transaction.payment_mode,
                        'remark': transaction.remark,
                        'is_deleted': False,
                        'siblings': [{
                            'studentName': student.STUDENTS_NAME,
                            'className': class_data.CLASS,
                            'rollNo': str(student_session.ROLL or ''),
                            'fees': {'monthly': None, 'oneTime': []},
                        }],
                    }

                fee_record = {
                    'type': fee_type,
                    'item': fee_structure.period_name,
                    'amount': float(fee_data.paid_amount or 0),
                }
                txn_fees = transaction_data[txn_id]['siblings'][0]['fees']
                if fee_type.lower() == 'tuition fee':
                    if txn_fees['monthly'] is None:
                        txn_fees['monthly'] = {'label': fee_structure.period_name, 'total': 0, 'months': []}
                    txn_fees['monthly']['total'] += fee_record['amount']
                    txn_fees['monthly']['months'].append(fee_structure.period_name)
                else:
                    txn_fees['oneTime'].append({'name': fee_structure.period_name, 'amount': fee_record['amount']})

    all_fees = list(fee_items.values())
    student_fee_data = {
        'id': student_session.id,
        'student_session_id': student_session.id,
        'name': student.STUDENTS_NAME,
        'fatherName': student.FATHERS_NAME,
        'class': class_data.CLASS,
        'rollNo': student_session.ROLL,
        'image': f"https://lh3.googleusercontent.com/d/{student.IMAGE}=s50" if student.IMAGE else '',
        'isRTE': False,
        'monthlyFees': [fee for fee in all_fees if fee['fee_type'].lower() == 'tuition fee'],
        'otherFees': [fee for fee in all_fees if fee['fee_type'].lower() != 'tuition fee'],
        'selectedFees': [],
        'total_due_amount': sum(fee['amount'] for fee in all_fees if fee['status'] == 'DUE'),
        'total_due_terms': sum(
            1 for fee in all_fees
            if fee['status'] == 'DUE' and fee['fee_type'].lower() == 'tuition fee'
        ),
    }

    try:


        marks_data = result_data(
            school_id=school.id,
            session_id=student_session.session_id,
            class_id=student_session.class_id,
            student_session_ids=[student_session.id],
        )

        marksheet = [
            prepare_marks_format(result)
            for result in marks_data
        ]


    except Exception as e:
        print(f"Error fetching marks data for student {student_session.id}: {str(e)}")
        marksheet = None



    response = jsonify({
        'student': {
            **student_data,
            'session_year': session_year,
        },
        'school': {
            'name': school.School_Name,
            'logo': school.Logo,
            'udise': school.UDISE,
        },
        'fees': student_fee_data,
        'transactions': list(transaction_data.values()),
        'marksheet': marksheet,
    })
    response.headers['Cache-Control'] = 'no-store'
    return response


@idcard_bp.route('/api/public/idcard/<token>/attendance', methods=['GET'])
def get_public_idcard_attendance(token):
    student_session_id = decrypt_student_id(token)
    if student_session_id is None:
        return jsonify({'error': 'Invalid ID card'}), 404

    student_record = db.session.query(
        StudentSessions,
        StudentsDB.school_id,
        ClassData.school_id,
    ).join(
        StudentsDB, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, StudentSessions.class_id == ClassData.id
    ).filter(
        StudentSessions.id == student_session_id,
        StudentsDB.school_id == ClassData.school_id,
    ).first()
    if not student_record:
        return jsonify({'error': 'Student not found'}), 404

    student_session, school_id, _ = student_record
    try:
        year = int(request.args.get('year', datetime.today().year))
        month = int(request.args.get('month', datetime.today().month))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid year or month'}), 400
    if month < 1 or month > 12 or year < 1900 or year > 2100:
        return jsonify({'error': 'Invalid year or month'}), 400

    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])
    attendance_rows = Attendance.query.filter(
        Attendance.student_session_id == student_session.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date,
    ).all()
    holiday_rows = AttendanceHolidays.query.filter(
        AttendanceHolidays.school_id == school_id,
        AttendanceHolidays.session_id == student_session.session_id,
        AttendanceHolidays.date >= start_date,
        AttendanceHolidays.date <= end_date,
        or_(
            AttendanceHolidays.class_id == student_session.class_id,
            AttendanceHolidays.class_id.is_(None),
        ),
    ).all()

    attendance_map = {row.date: row.status for row in attendance_rows}
    holiday_dates = {row.date for row in holiday_rows}
    records = []
    monthly_summary = {
        'present': 0, 'absent': 0, 'half_day': 0,
        'leave': 0, 'holiday': 0, 'unmarked': 0,
    }
    for day in range(1, end_date.day + 1):
        current_date = date(year, month, day)
        if current_date in attendance_map:
            status = attendance_map[current_date]
        elif current_date.weekday() == 6 or current_date in holiday_dates:
            status = 'HOLIDAY'
        else:
            status = 'UNMARKED'
        records.append({'date': current_date.isoformat(), 'status': status})
        summary_key = status.lower()
        if summary_key in monthly_summary:
            monthly_summary[summary_key] += 1
        else:
            monthly_summary['unmarked'] += 1

    session_row = Sessions.query.filter_by(id=student_session.session_id).first()
    session_start = session_row.start_date if session_row and session_row.start_date else start_date
    session_end = session_row.end_date if session_row and session_row.end_date else end_date
    if session_start > session_end:
        session_start, session_end = start_date, end_date

    session_attendance = Attendance.query.filter(
        Attendance.student_session_id == student_session.id,
        Attendance.date >= session_start,
        Attendance.date <= session_end,
    ).all()
    session_holidays = AttendanceHolidays.query.filter(
        AttendanceHolidays.school_id == school_id,
        AttendanceHolidays.session_id == student_session.session_id,
        AttendanceHolidays.date >= session_start,
        AttendanceHolidays.date <= session_end,
        or_(
            AttendanceHolidays.class_id == student_session.class_id,
            AttendanceHolidays.class_id.is_(None),
        ),
    ).all()
    attendance_by_date = {row.date: row.status for row in session_attendance}
    holiday_set = {row.date for row in session_holidays}
    session_summary = {
        'present': 0, 'absent': 0, 'half_day': 0,
        'leave': 0, 'holiday': 0, 'unmarked': 0,
        'range': f"{session_start.strftime('%d %b %Y')} - {session_end.strftime('%d %b %Y')}",
    }
    for offset in range((session_end - session_start).days + 1):
        current_date = session_start + timedelta(days=offset)
        status = attendance_by_date.get(current_date)
        if status is None:
            status = 'HOLIDAY' if current_date.weekday() == 6 or current_date in holiday_set else 'UNMARKED'
        summary_key = status.lower()
        if summary_key in session_summary:
            session_summary[summary_key] += 1
        else:
            session_summary['unmarked'] += 1
    total_marked_days = sum(
        session_summary[key] for key in ('present', 'absent', 'half_day', 'leave')
    )
    session_summary['present_percent'] = (
        round(session_summary['present'] * 100 / total_marked_days, 2)
        if total_marked_days else 0
    )

    response = jsonify({
        'records': records,
        'monthly_summary': monthly_summary,
        'session_summary': session_summary,
    })
    response.headers['Cache-Control'] = 'no-store'
    return response
