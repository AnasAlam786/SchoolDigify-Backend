from types import SimpleNamespace
from datetime import date, datetime
from flask import render_template, session, request, Blueprint, jsonify
from sqlalchemy import and_, or_

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.controller.permissions.has_permission import has_permission

from src.model import (
    StudentsDB, ClassData, StudentSessions, Schools, RTEInfo,
    FeeData, FeeHeads, FeeSessionData, FeeStructure, FeeTransaction,
    TeachersLogin,
)
from src import db
from src.controller.fees.utils.fee_calculations import (
    aggregate_fee_allocations,
    calculate_fee_balance,
)

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
                FeeData.transaction_id,
                FeeData.paid_amount,
                FeeData.late_fee,
                FeeTransaction.paid_amount.label('transaction_paid_amount'),
                FeeTransaction.discount,
                FeeTransaction.payment_date,
                FeeTransaction.transaction_no,
            )
            .outerjoin(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
            .filter(
                FeeData.student_session_id.in_(student_session_ids),
                FeeData.fee_session_id.in_(fee_session_ids),
                or_(
                    FeeTransaction.id.is_(None),
                    and_(
                        FeeTransaction.school_id == school_id,
                        FeeTransaction.session_id == current_session_id,
                        or_(
                            FeeTransaction.is_deleted.is_(False),
                            FeeTransaction.is_deleted.is_(None),
                        ),
                    ),
                ),
            )
            .all()
        )
        payments_by_student_fee = aggregate_fee_allocations(payment_records)

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

                balance = calculate_fee_balance(
                    fee.amount,
                    payments_by_student_fee.get((
                        student.student_session_id,
                        fee.fee_session_id,
                    )),
                )
                remaining_amount = balance['remaining_amount']
                if remaining_amount <= 0:
                    continue

                due_items.append({
                    'fee_type': fee.fee_type or 'Fee',
                    'period_name': fee.period_name or '',
                    'due_date': due_date.strftime('%d-%m-%Y'),
                    'amount': float(balance['obligatory_amount']),
                    'paid_amount': float(balance['paid_amount']),
                    'due_amount': float(remaining_amount),
                })

            if due_items:
                fee_notices[student.student_session_id] = {
                    'items': due_items,
                    'total_amount': sum(item['amount'] for item in due_items),
                    'total_paid': sum(item['paid_amount'] for item in due_items),
                    'total_due': sum(item['due_amount'] for item in due_items),
                }

    has_students = bool(students)
    student_objs = []
    for student in students:
        obj = SimpleNamespace(**student._asdict())
        dob = getattr(obj, 'DOB', None)
        if dob:
            try:
                obj.DOB = dob.strftime('%d-%m-%Y')
            except Exception:
                obj.DOB = str(dob)
        else:
            obj.DOB = ''

        obj.is_RTE = bool(getattr(obj, 'is_RTE', False))
        obj.fee_notice = fee_notices.get(obj.student_session_id)
        student_objs.append(obj)

    if output_type == 'feeOnly':
        student_objs = [student for student in student_objs if student.fee_notice]

    page_size = 2 if len(selected_outputs) == 2 else 4
    pages = [
        student_objs[i:i + page_size]
        for i in range(0, len(student_objs), page_size)
    ]

    school = db.session.query(Schools).filter_by(id=school_id).first()
    school_name = school.School_Name if school else ''
    school_address = school.Address if school else ''
    school_phone = school.Phone if school else ''
    logo = school.Logo if school else ''
    principal_name = db.session.query(TeachersLogin.Name).filter_by(
        school_id=school_id,
        role_id=2,
    ).scalar() or ''

    html = render_template(
        'admit_card/admit_pdf_detailed.html',
        data=pages,
        logo=logo,
        school=school_name,
        school_address=school_address,
        school_phone=school_phone,
        principal_name=principal_name,
        admit_heading=admit_heading,
        scheme_heading=scheme_heading,
        fee_heading=fee_heading,
        outputType=output_type,
        examScheme=examScheme,
        has_fee_notices=bool(fee_notices),
        has_students=has_students,
    )

    return jsonify({"html": str(html)})