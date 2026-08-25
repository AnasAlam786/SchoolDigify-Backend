    
from datetime import date, datetime
from operator import or_

from sqlalchemy import case
from src.model.FeeSessionData import FeeSessionData
from src.model.StudentSessions import StudentSessions
from src.model.ClassData import ClassData
from src.model.FeeData import FeeData
from src.model.FeeHeads import FeeHeads
from src.model.FeeStructure import FeeStructure
from src.model.FeeTransaction import FeeTransaction
from src.model.StudentsDB import StudentsDB
from src import db


def fetch_fee_data(    
    session_id,
    school_id,
    phone=None,
    class_id=None,
    student_session_ids=None,
    student_id=None,
    selected_student_session_id=None
):
    q = (
        db.session.query(
            StudentsDB.id.label("student_id"),
            StudentsDB.STUDENTS_NAME, StudentsDB.FATHERS_NAME,
            StudentsDB.PHONE, StudentsDB.IMAGE,
            StudentSessions.id.label("student_session_id"),
            StudentSessions.class_id, StudentSessions.session_id, 
            StudentSessions.ROLL, ClassData.CLASS
        )
        .join(StudentSessions, StudentsDB.id == StudentSessions.student_id)
        .join(ClassData, ClassData.id == StudentSessions.class_id)
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
            FeeStructure.start_day, FeeStructure.start_month,
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
            FeeData.fee_payment_status,
            FeeTransaction.paid_amount, 
            FeeTransaction.transaction_no,
            FeeTransaction.payment_date
        )
        .outerjoin(FeeTransaction, FeeTransaction.id == FeeData.transaction_id)
        .filter(
            FeeData.student_session_id.in_(extracted_student_session_ids),
            or_(FeeTransaction.is_deleted != True, FeeTransaction.is_deleted == None)
        )
        .all()
    )

    students_data = build_fee_data(students, fee_structure, fee_payments, session_id)
    return True, students_data


def build_fee_data(students, fee_structure, fee_payments, current_session):

    today = date.today()
    result = []

    # Map payments by (student_session_id, fee_session_id)
    payment_map = {}
    for fee in fee_payments:
        raw_status = fee.fee_payment_status
        status_value = (
            raw_status.value if hasattr(raw_status, "value") 
            else str(raw_status) if raw_status is not None 
            else None
        )

        payment_map[(fee.student_session_id, fee.fee_session_id)] = {
            "status": status_value,
            "payment_date": fee.payment_date,
            "transaction_no": fee.transaction_no,
        }

    for idx, s in enumerate(students):
        student = {
            "id": idx,
            "student_session_id": s.student_session_id,
            "name": s.STUDENTS_NAME,
            "class": s.CLASS,
            "class_id": s.class_id,
            "rollNo": s.ROLL,
            "phone": s.PHONE,
            "image": f"https://lh3.googleusercontent.com/d/{s.IMAGE}=s50" if s.IMAGE else "",
            "monthlyFees": [],
            "otherFees": [],
            "selectedFees": [],
            "total_due_amount": 0,
            "total_due_terms": 0
        }

        i = 0
        for f in fee_structure:
            if f.class_id != s.class_id:
                continue
            
            i += 1
            due_year = int(current_session) + (f.year_increment or 0)
            due_date = date(due_year, f.start_month, f.start_day)

            key = (student["student_session_id"], f.fee_session_id)
            payment = payment_map.get(key)

            if payment:
                status = payment["status"]
                paid_date = payment["payment_date"]
                transaction_no = payment["transaction_no"]
            else:
                status = "DUE" if today > due_date else "UPCOMING"
                paid_date = None
                transaction_no = None

            amount = float(f.amount or 0)

            # Fixed: Check against upper case "DUE"
            if status == "DUE":
                student["total_due_amount"] += amount
                if f.fee_type and f.fee_type.lower() == "tuition fee":
                    student["total_due_terms"] += 1

            fee_item = {
                "id": i,
                "fee_id": f.fee_session_id,
                "fee_type": f.fee_type,
                "period_name": f.period_name,
                "amount": amount,
                "dueDate": f"{f.start_day}-{f.start_month}-{due_year}",
                "status": status,
                "paid_date": paid_date.strftime("%d-%m-%Y") if paid_date else None,
                "transaction_no": transaction_no,
            }

            if f.fee_type and f.fee_type.lower() == "tuition fee":
                student["monthlyFees"].append(fee_item)
            else:
                student["otherFees"].append(fee_item)

        result.append(student)

    return result


