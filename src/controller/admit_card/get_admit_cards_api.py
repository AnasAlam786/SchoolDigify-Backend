from types import SimpleNamespace
from datetime import date, datetime
from decimal import Decimal
from flask import render_template, session, request, Blueprint, jsonify
from sqlalchemy import func

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.permissions.has_permission import has_permission

from src.model import (
    StudentsDB, ClassData, StudentSessions, Schools, RTEInfo,
    FeeData, FeeHeads, FeeSessionData, FeeStructure, FeeTransaction,
)
from src import db

get_admit_cards_api_bp = Blueprint('get_admit_cards_api_bp', __name__)


@get_admit_cards_api_bp.route('/api/admit_cards_api', methods=['POST'])
@login_required
@permission_required('admit_card')
def get_admit_cards_api():
    """Render admit cards, exam schemes, fee due notices, or supported pairs."""

    data = request.json or {}


    admit_heading = data.get('admitHeading', '')
    scheme_heading = data.get('schemeHeading', '')
    output_type = data.get('outputType', '')
    examScheme = data.get('examScheme', '')
    fee_heading = data.get('feeHeading', 'Fee Due Notice')

    output_types = {
        'admitOnly': {'admit'},
        'SchemeOnly': {'scheme'},
        'feeOnly': {'fee'},
        'admitScheme': {'admit', 'scheme'},
        'admitFee': {'admit', 'fee'},
        'schemeFee': {'scheme', 'fee'},
    }
    selected_outputs = output_types.get(output_type)
    if not selected_outputs:
        return jsonify({"message": "Select one or two valid print items."}), 400

    school_id = session.get('school_id')
    current_session_id = session.get('session_id')

    if not school_id or not current_session_id:
        return jsonify({"message": "Missing session context (school/session)."}), 400

    class_id = data.get('class')
    try:
        class_id = int(class_id)
    except (TypeError, ValueError):
        return jsonify({"message": "A valid class is required."}), 400

    if 'fee' in selected_outputs and not has_permission('view_fee_data'):
        return jsonify({
            "message": "You do not have permission to view fee notices."
        }), 403

    # Build base query for students in the current session and school
    query = db.session.query(
        StudentsDB.id,
        StudentsDB.STUDENTS_NAME,
        StudentsDB.IMAGE,
        StudentsDB.FATHERS_NAME,
        StudentsDB.MOTHERS_NAME,
        StudentsDB.DOB,
        StudentsDB.PHONE,
        ClassData.CLASS.label('CLASS'),
        StudentSessions.ROLL,
        db.session.query(RTEInfo.id).filter(
            RTEInfo.student_id == StudentsDB.id,
            RTEInfo.is_RTE.is_(True),
        ).exists().label('is_RTE'),
        StudentSessions.id.label('student_session_id'),
    ).join(
        StudentSessions, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, StudentSessions.class_id == ClassData.id
    ).filter(
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == current_session_id,
        StudentSessions.class_id == class_id,
    ).order_by(
        ClassData.display_order,
        StudentSessions.ROLL
    )


    students = query.all()

    fee_notices = {}
    if 'fee' in selected_outputs and students:
        current_session_year = int(current_session_id)
        today = date.today()
        student_session_ids = [student.student_session_id for student in students]

        fee_structures = (
            db.session.query(
                FeeSessionData.id.label('fee_session_id'),
                FeeSessionData.amount,
                FeeSessionData.custom_due_date,
                FeeStructure.period_name,
                FeeStructure.due_day,
                FeeStructure.due_month,
                FeeStructure.year_increment,
                FeeHeads.fee_type,
            )
            .join(FeeStructure, FeeStructure.id == FeeSessionData.structure_id)
            .outerjoin(FeeHeads, FeeHeads.id == FeeStructure.fee_type_id)
            .filter(
                FeeSessionData.session_id == current_session_id,
                FeeSessionData.class_id == class_id,
                FeeStructure.school_id == school_id,
            )
            .order_by(FeeStructure.sequence_number.asc())
            .all()
        )

        if not fee_structures:
            return jsonify({
                "message": "Fee details are not set up for this class and session. Set them up in Fee Management, then try again."
            }), 400

        fee_session_ids = [fee.fee_session_id for fee in fee_structures]

        payment_records = (
            db.session.query(
                FeeData.student_session_id,
                FeeData.fee_session_id,
                FeeData.paid_amount,
                FeeData.fee_payment_status,
            )
            .outerjoin(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
            .filter(
                FeeData.student_session_id.in_(student_session_ids),
                FeeData.fee_session_id.in_(fee_session_ids),
                func.coalesce(FeeTransaction.is_deleted, False) == False,
            )
            .all()
        )

        payments_by_student_fee = {}

        for payment in payment_records:
            key = (
                payment.student_session_id,
                payment.fee_session_id
            )

            payments_by_student_fee.setdefault(key, []).append(payment)

        for student in students:
            if bool(student.is_RTE):
                continue

            due_items = []

            for fee in fee_structures:

                if fee.custom_due_date:
                    due_date = fee.custom_due_date

                    if isinstance(due_date, datetime):
                        due_date = due_date.date()

                else:
                    if not fee.due_month or not fee.due_day:
                        return jsonify({
                            "message": "A fee due date is missing from this class's fee setup. Please correct it in Fee Management."
                        }), 400

                    try:
                        due_date = date(
                            current_session_year + int(fee.year_increment or 0),
                            int(fee.due_month),
                            int(fee.due_day),
                        )

                    except ValueError:
                        return jsonify({
                            "message": "A fee due date is invalid in this class's fee setup. Please correct it in Fee Management."
                        }), 400

                if due_date > today:
                    continue

                payments = payments_by_student_fee.get(
                    (
                        student.student_session_id,
                        fee.fee_session_id
                    ),
                    [],
                )

                if any(
                    getattr(
                        payment.fee_payment_status,
                        'value',
                        payment.fee_payment_status
                    ) == 'PAID'
                    for payment in payments
                ):
                    continue

                paid_amount = sum(
                    (
                        Decimal(str(payment.paid_amount or 0))
                        for payment in payments
                    ),
                    Decimal('0'),
                )

                amount = Decimal(str(fee.amount or 0))

                balance = max(
                    amount - paid_amount,
                    Decimal('0')
                )

                if balance <= 0:
                    continue

                due_items.append({
                    'fee_type': fee.fee_type or 'Fee',
                    'period_name': fee.period_name or '',
                    'due_date': due_date.strftime('%d-%m-%Y'),
                    'amount': float(amount),
                    'paid_amount': float(
                        min(paid_amount, amount)
                    ),
                    'due_amount': float(balance),
                })

            if due_items:
                fee_notices[student.student_session_id] = {
                    'items': due_items,
                    'total_amount': sum(
                        item['amount']
                        for item in due_items
                    ),
                    'total_paid': sum(
                        item['paid_amount']
                        for item in due_items
                    ),
                    'total_due': sum(
                        item['due_amount']
                        for item in due_items
                    ),
                }

    # Convert rows to mutable objects and format dates
    has_students = bool(students)
    student_objs = []

    for s in students:
        obj = SimpleNamespace(**s._asdict())

        dob = getattr(obj, 'DOB', None)

        if dob:
            try:
                obj.DOB = dob.strftime('%d-%m-%Y')
            except Exception:
                obj.DOB = str(dob)
        else:
            obj.DOB = ''

        obj.is_RTE = bool(
            getattr(obj, 'is_RTE', False)
        )

        obj.fee_notice = fee_notices.get(
            obj.student_session_id
        )

        student_objs.append(obj)

    if output_type == 'feeOnly':
        student_objs = [
            student
            for student in student_objs
            if student.fee_notice
        ]

    # Every standalone output uses the same 2 × 2 A4 grid.
    #
    # 1 output per student:
    #     4 students per A4 page
    #
    # 2 outputs per student:
    #     2 students per A4 page
    #     because every student occupies 2 grid cells.
    if len(selected_outputs) == 2:
        page_size = 2
    else:
        page_size = 4

    pages = [
        student_objs[i:i + page_size]
        for i in range(0, len(student_objs), page_size)
    ]

    # Get school info for logo and name
    school = db.session.query(Schools).filter_by(
        id=school_id
    ).first()

    school_name = school.School_Name if school else ''
    logo = school.Logo if school else ''


    html = render_template(
        'admit_card/admit_pdf.html',
        data=pages,
        logo=logo,
        school=school_name,
        admit_heading=admit_heading,
        scheme_heading=scheme_heading,
        fee_heading=fee_heading,
        outputType=output_type,
        examScheme=examScheme,
        has_fee_notices=bool(fee_notices),
        has_students=has_students,
    )

    return jsonify({"html": str(html)})