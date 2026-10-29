    
from datetime import date, datetime
from operator import or_

from sqlalchemy import and_, case, or_
from src.model import RTEInfo
from src.model.FeeSessionData import FeeSessionData
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.FeeData import FeeData
from src.model.FeeHeads import FeeHeads
from src.model.FeeStructure import FeeStructure
from src.model.FeeTransaction import FeeTransaction
from src.model.StudentsDB import StudentsDB
from src.model.ClassAccess import ClassAccess
from src import db
from src.controller.fees.utils.fee_calculations import (
    ZERO,
    aggregate_fee_allocations,
    calculate_fee_balance,
    json_money,
)


def fetch_fee_data(    
    session_id, school_id, user_id,
    phone=None, class_id=None,
    student_session_ids=None, student_id=None,
    selected_student_session_id=None
):
    q = (
        db.session.query(
            StudentsDB.id.label("student_id"),
            StudentsDB.STUDENTS_NAME,
            StudentsDB.FATHERS_NAME,
            StudentsDB.PHONE, StudentsDB.IMAGE,
            StudentSessions.id.label("student_session_id"),
            StudentSessions.class_id,
            StudentSessions.session_id,
            StudentSessions.ROLL,
            ClassData.CLASS,
            RTEInfo.is_RTE
        )
        .join(
            StudentSessions,
            StudentsDB.id == StudentSessions.student_id
        )
        .join(
            ClassData,
            ClassData.id == StudentSessions.class_id
        )
        .outerjoin(
            RTEInfo,
            RTEInfo.student_id == StudentsDB.id
        )
        .filter(
            StudentSessions.class_id.in_(
                db.session.query(ClassAccess.class_id).filter(
                    ClassAccess.staff_id == user_id
                )
            )
        )
    )

    if phone:
        q = q.filter(StudentsDB.PHONE == phone)
    if class_id:
        q = q.filter(StudentSessions.class_id == class_id)
    if student_session_ids:
        q = q.filter(StudentSessions.id.in_(student_session_ids))
    if student_id:
        # Handle both single integer ID and list of IDs cleanly
        ids = student_id if isinstance(student_id, (list, tuple, set)) else [student_id]
        q = q.filter(StudentsDB.id.in_(ids))
    if session_id:
        q = q.filter(StudentSessions.session_id == session_id)
    if school_id:
        q = q.filter(StudentsDB.school_id == school_id)

    # Requested student first
    if selected_student_session_id:
        q = q.order_by(
            case(
                (StudentSessions.id == int(selected_student_session_id), 0),
                else_=1
            )
        )

    students = q.all()
    if not students:
        return True, []

    class_ids = list({s.class_id for s in students})
    fee_structure = (
        db.session.query(
            FeeHeads.fee_type,
            FeeStructure.id.label("structure_id"),
            FeeStructure.period_name, FeeStructure.year_increment,
            FeeStructure.due_day, FeeStructure.due_month,
            FeeSessionData.custom_due_date,
            FeeSessionData.amount, FeeSessionData.class_id,
            FeeSessionData.id.label("fee_session_id"), 
        )
        .outerjoin(FeeHeads, FeeStructure.fee_type_id == FeeHeads.id)
        .outerjoin(FeeSessionData, FeeSessionData.structure_id == FeeStructure.id)
        .filter(
            FeeSessionData.class_id.in_(class_ids),
            FeeStructure.school_id == school_id,
            FeeSessionData.session_id == session_id
        )
        .order_by(FeeStructure.sequence_number.asc())
        .all()
    )

    if not fee_structure:
        return False, {"NO_FEE_SESSION_DATA": True}

    extracted_student_session_ids = list({s.student_session_id for s in students})
    fee_payments = (
        db.session.query(
            FeeData.fee_session_id,
            FeeData.student_session_id,
            FeeData.paid_amount,
            FeeData.late_fee,
            FeeData.transaction_id,
            FeeTransaction.paid_amount.label("transaction_paid_amount"),
            FeeTransaction.discount,
            FeeTransaction.transaction_no,
            FeeTransaction.payment_date
        )
        .outerjoin(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
        .filter(
            FeeData.student_session_id.in_(extracted_student_session_ids),
            or_(
                FeeData.transaction_id.is_(None),
                and_(
                    FeeTransaction.school_id == school_id,
                    FeeTransaction.session_id == session_id,
                    or_(
                        FeeTransaction.is_deleted.is_(False),
                        FeeTransaction.is_deleted.is_(None),
                    ),
                ),
            ),
        )
        .all()
    )

    students_data = build_fee_data(students, fee_structure, fee_payments, session_id)
    return True, students_data


def build_fee_data(students, fee_structure, fee_payments, current_session):

    today = date.today()
    result = []

    payment_map = aggregate_fee_allocations(fee_payments)

    for idx, s in enumerate(students):
        student = {
            "id": idx,
            "student_session_id": s.student_session_id,
            "name": s.STUDENTS_NAME,
            "fatherName": s.FATHERS_NAME,
            "isRTE": s.is_RTE,

            "class": s.CLASS,
            "class_id": s.class_id,
            "rollNo": s.ROLL,
            "phone": s.PHONE,
            "image": f"https://lh3.googleusercontent.com/d/{s.IMAGE}=s50" if s.IMAGE else "",
            "monthlyFees": [],
            "otherFees": [],
            "selectedFees": [],
            "total_paid_amount": ZERO,
            "total_remaining_amount": ZERO,
            "total_due_amount": ZERO,
            "total_upcoming_amount": ZERO,
            "total_overpaid_amount": ZERO,
            "total_due_terms": 0
        }

        i = 0
        for f in fee_structure:
            if f.class_id != s.class_id:
                continue
            
            i += 1

            # Determine due date: use custom_due_date if present, else build dynamically
            if f.custom_due_date:
                # Ensure custom_due_date is formatted as a date object if it comes as a string/datetime
                if isinstance(f.custom_due_date, datetime):
                    due_date = f.custom_due_date.date()
                elif isinstance(f.custom_due_date, str):
                    due_date = datetime.strptime(f.custom_due_date, "%Y-%m-%d").date()
                else:
                    due_date = f.custom_due_date
            else:
                due_year = int(current_session) + int(f.year_increment or 0)
                due_date = date(due_year, int(f.due_month), int(f.due_day))

            key = (student["student_session_id"], f.fee_session_id)
            payment = payment_map.get(key)

            balance = calculate_fee_balance(f.amount, payment)
            amount = balance["obligatory_amount"]
            remaining_amount = balance["remaining_amount"]
            payment_status = balance["status"]
            is_due = due_date <= today
            display_status = (
                payment_status if payment_status != "UNPAID"
                else "DUE" if is_due else "UPCOMING"
            )

            paid_date = payment["payment_date"] if payment else None
            transaction_no = payment["transaction_no"] if payment else None

            student["total_paid_amount"] += balance["paid_amount"]
            student["total_remaining_amount"] += max(remaining_amount, ZERO)
            student["total_overpaid_amount"] += max(-remaining_amount, ZERO)
            if is_due:
                student["total_due_amount"] += max(remaining_amount, ZERO)
            else:
                student["total_upcoming_amount"] += max(remaining_amount, ZERO)

            if payment_status in ("UNPAID", "PARTIAL", "OVERPAID") and is_due:
                if f.fee_type and f.fee_type.lower() == "tuition fee":
                    student["total_due_terms"] += 1

            fee_item = {
                "id": i,
                "fee_id": f.fee_session_id,
                "fee_type": f.fee_type,
                "period_name": f.period_name,
                "amount": json_money(amount),
                "obligatory_amount": json_money(amount),
                "paid_amount": json_money(balance["paid_amount"]),
                "discount_amount": json_money(balance["discount_amount"]),
                "settled_amount": json_money(balance["settled_amount"]),
                "late_fee": json_money(balance["late_fee"]),
                "remaining_amount": json_money(remaining_amount),
                "payment_status": payment_status,
                "is_overpaid": payment_status == "OVERPAID",
                "dueDate": due_date.strftime("%d-%m-%Y"),
                "due_status": "DUE" if is_due else "UPCOMING",
                "status": display_status,
                "paid_date": paid_date.strftime("%d-%m-%Y") if paid_date else None,
                "transaction_no": transaction_no,
            }

            if f.fee_type and f.fee_type.lower() == "tuition fee":
                student["monthlyFees"].append(fee_item)
            else:
                student["otherFees"].append(fee_item)

        for field in (
            "total_paid_amount",
            "total_remaining_amount",
            "total_due_amount",
            "total_upcoming_amount",
            "total_overpaid_amount",
        ):
            student[field] = json_money(student[field])

        result.append(student)

    return result