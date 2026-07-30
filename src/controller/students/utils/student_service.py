# src/controller/students/utils/student_service.py

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from openpyxl import Workbook, load_workbook
from flask import session
from pydantic import ValidationError

from src import db
from src.model import StudentsDB, StudentSessions, ClassData, RTEInfo, Schools
from src.controller.students.utils.upload_image import upload_image, delete_image, move_image
from src.controller.utils.get_gapped_rolls import get_gapped_rolls
import time


class StudentService:
    EXCEL_FIELDS = {
        'STUDENTS_NAME': 'Student Name',
        'DOB': 'Date of Birth (DD-MM-YYYY)',
        'GENDER': 'Gender',
        'AADHAAR': 'Aadhaar Number',
        'Caste': 'Caste',
        'Caste_Type': 'Caste Type',
        'RELIGION': 'Religion',
        'Height': 'Height (cm)',
        'Weight': 'Weight (kg)',
        'BLOOD_GROUP': 'Blood Group',
        'admitted_as_new': 'Student Status (new/old)',
        'admission_session_id': 'Admission Session',
        'Admission_Class': 'Admission Class',
        'CLASS': 'Current Class',
        'ROLL': 'Roll Number',
        'SR': 'SR Number',
        'ADMISSION_NO': 'Admission Number',
        'ADMISSION_DATE': 'Admission Date (DD-MM-YYYY)',
        'PEN': 'PEN Number',
        'APAAR': 'APAAR Number',
        'FATHERS_NAME': "Father's Name",
        'FATHERS_AADHAR': "Father's Aadhaar",
        'MOTHERS_NAME': "Mother's Name",
        'MOTHERS_AADHAR': "Mother's Aadhaar",
        'FATHERS_EDUCATION': "Father's Education",
        'FATHERS_OCCUPATION': "Father's Occupation",
        'MOTHERS_EDUCATION': "Mother's Education",
        'MOTHERS_OCCUPATION': "Mother's Occupation",
        'ADDRESS': 'Address',
        'PHONE': 'Phone Number',
        'ALT_MOBILE': 'Alternate Mobile',
        'PIN': 'PIN Code',
        'Home_Distance': 'Home Distance',
        'EMAIL': 'Email',
        'Previous_School_Marks': 'Previous School Marks (%)',
        'Previous_School_Attendance': 'Previous School Attendance (%)',
        'Previous_School_Name': 'Previous School Name',
        'is_RTE': 'Is RTE Student (Yes/No)',
        'account_number': 'Bank Account Number',
        'RTE_registered_year': 'RTE Registered Year',
        'ifsc': 'IFSC Code',
        'bank_name': 'Bank Name',
        'bank_branch': 'Bank Branch',
        'account_holder': 'Account Holder Name',
        'registration_no': 'Registration Number'
    }

    REQUIRED_FIELDS = [
        'STUDENTS_NAME', 'DOB', 'GENDER', 'Caste_Type', 'RELIGION',
        'admission_session_id', 'admission_class_id', 'class_id', 'ROLL', 'SR', 'ADMISSION_NO', 'ADMISSION_DATE',
        'FATHERS_NAME', 'MOTHERS_NAME', 'ADDRESS', 'PHONE', 'PIN'
    ]

    ROMAN_MAP = {
        "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
        "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
        "xi": "11", "xii": "12"
    }

    @staticmethod
    def str_to_date(value) -> date | None:
        if isinstance(value, date):
            return value

        if not value:
            return None

        formats = ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y")
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def validate_class_order(adm_class_id: int, cur_class_id: int) -> Optional[str]:
        """Ensure admission class display_order < current class display_order."""
        orders = db.session.query(ClassData.id, ClassData.display_order).filter(
            ClassData.id.in_([adm_class_id, cur_class_id])
        ).all()
        order_map = {row.id: row.display_order or 0 for row in orders}
        if order_map.get(adm_class_id, 0) > order_map.get(cur_class_id, 0):
            return "Admission Class must be same or lower than Current Class."
        return None


    @staticmethod
    def check_unique_conflicts(
        values: Dict[str, str],
        school_id: int,
        school_fields: List[str],
        exclude_student_id: Optional[int] = None
    ) -> Tuple[List[str], Optional[StudentsDB]]:
        """Check for unique field conflicts."""

        school_filters = [
            getattr(StudentsDB, field) == values[field]
            for field in school_fields
            if values.get(field)
        ]

        if not school_filters:
            return [], None

        query = db.session.query(StudentsDB).filter(
            StudentsDB.school_id == school_id,
            or_(*school_filters)
        )

        if exclude_student_id is not None:
            query = query.filter(StudentsDB.id != exclude_student_id)

        duplicate_student = query.first()

        if not duplicate_student:
            return [], None
        
        
        duplicate_fields = []
        for field in school_fields:
            value = values.get(field)

            # Skip empty values
            if value in (None, ""):
                continue

            if getattr(duplicate_student, field) == value:
                duplicate_fields.append(field)
                
        return duplicate_fields, duplicate_student
    

    @staticmethod
    def check_roll_availability(class_id: int, session_id: int, roll: int, exclude_student_id: Optional[int] = None) -> Optional[str]:
        """Check if roll is available in the class for the session."""
        available = get_gapped_rolls(class_id, session_id)
        gapped = available.get("gapped_rolls", [])
        next_r = available.get("next_roll")

        available_rolls = set(gapped)
        if next_r is not None:
            available_rolls.add(next_r)

        if exclude_student_id:
            # Allow keeping existing roll
            existing_roll = db.session.query(StudentSessions.ROLL).filter(
                StudentSessions.student_id == exclude_student_id,
                StudentSessions.session_id == session_id
            ).scalar()
            if existing_roll is not None:
                available_rolls.add(existing_roll)
                if existing_roll == roll:
                    return None

        if roll not in available_rolls:
            return f"Roll {roll} is not available. Available: {sorted(available_rolls)}"

        return None

    @staticmethod
    def create_student(verified_data: List[Dict], image_b64: Optional[str], school_id: int, session_id: int) -> Tuple[Optional[int], Optional[str]]:
        """Create a new student with all related data."""

        # Prepare data
        studentsdb_data = {k: v for k, v in verified_data.items() if k in StudentsDB.__table__.columns}
        sessions_data = {k: v for k, v in verified_data.items() if k in StudentSessions.__table__.columns}
        rte_data = {k: v for k, v in verified_data.items() if k in RTEInfo.__table__.columns}

        # Convert dates
        for field in ["DOB", "ADMISSION_DATE"]:
            if field in studentsdb_data and isinstance(studentsdb_data[field], str):
                try:
                    studentsdb_data[field] = datetime.strptime(studentsdb_data[field], "%d-%m-%Y").date()
                except ValueError:
                    return None, f"Invalid date format for {field}."

        studentsdb_data["school_id"] = school_id
        studentsdb_data["admission_class_id"] = verified_data.get("class_id")
        studentsdb_data["admitted_as_new"] = verified_data.get('admitted_as_new')

        sessions_data["class_id"] = verified_data.get("class_id")
        sessions_data["session_id"] = session_id
        sessions_data["created_at"] = datetime.now()
        sessions_data["promoted_on"] = studentsdb_data["ADMISSION_DATE"]

        try:
            new_student = StudentsDB(**studentsdb_data)
            db.session.add(new_student)
            db.session.flush()

            session_row = StudentSessions(student_id=new_student.id, **sessions_data)
            rte_row = RTEInfo(student_id=new_student.id, **rte_data)
            db.session.add(session_row)
            db.session.add(rte_row)

            # Handle image
            if image_b64:
                school = Schools.query.filter_by(id=school_id).first()
                if school:
                    encoded = image_b64.split(",")[1]
                    image_id = upload_image(encoded, verified_data.get("ADMISSION_NO"), school.students_image_folder_id)
                    new_student.IMAGE = image_id
            db.session.commit()

            return new_student.id, None
        except IntegrityError as e:
            db.session.rollback()
            return None, "Database integrity error. Possible duplicate data."
        except Exception as e:
            db.session.rollback()
            if 'image_id' in locals():
                delete_image(image_id)
            return None, f"Failed to create student: {str(e)}"

    @staticmethod
    def update_student(student_id: int, verified_data: List[Dict], image_b64: Optional[str], image_status: str, school_id: int, session_id: int) -> Optional[str]:
        """Update an existing student."""
        student = StudentsDB.query.filter_by(id=student_id).first()
        if not student:
            return "Student not found."

        data = {item["field"]: item["value"] for item in verified_data}

        # Handle admitted_as_new to set admission_session_id appropriately
        admitted_as_new = data.get('admitted_as_new')
        if admitted_as_new:
            # New student - set admission_session_id to current session
            data['admission_session_id'] = session_id
        elif not admitted_as_new:
            # Old student - keep existing admission_session_id (don't override)
            if 'admission_session_id' in data:
                del data['admission_session_id']

        studentsdb_updates = {k: v for k, v in data.items() if k in StudentsDB.__table__.columns}

        sessions_updates = {k: v for k, v in data.items() if k in StudentSessions.__table__.columns}
        rte_updates = {k: v for k, v in data.items() if k in RTEInfo.__table__.columns}

        # Convert dates
        for field in ["DOB", "ADMISSION_DATE"]:
            if field in studentsdb_updates and isinstance(studentsdb_updates[field], str):
                try:
                    studentsdb_updates[field] = datetime.strptime(studentsdb_updates[field], "%d-%m-%Y").date()
                except ValueError:
                    return f"Invalid date format for {field}."

        # Special mappings
        if "CLASS" in data:
            sessions_updates["class_id"] = data["CLASS"]
        if "Section" in data:
            sessions_updates["Section"] = data["Section"]
        if "ROLL" in data:
            sessions_updates["ROLL"] = data["ROLL"]

        try:
            # Update StudentsDB
            for k, v in studentsdb_updates.items():
                setattr(student, k, v)

            # Update or create session row
            session_row = StudentSessions.query.filter_by(student_id=student_id, session_id=session_id).first()
            if not session_row:
                session_row = StudentSessions(student_id=student_id, session_id=session_id)
                db.session.add(session_row)
            for k, v in sessions_updates.items():
                setattr(session_row, k, v)

            # Update or create RTE row
            rte_row = RTEInfo.query.filter_by(student_id=student_id).first()
            if not rte_row:
                rte_row = RTEInfo(student_id=student_id)
                db.session.add(rte_row)
            for k, v in rte_updates.items():
                setattr(rte_row, k, v)

            # Image handling
            deleted_folder = "1e8iHskcj2Vtv_Mg_Mtp4BzdHocuhLd_f"
            school = Schools.query.filter_by(id=school_id).first()
            if not school:
                return "School not found."

            if image_status == "updated" and image_b64:
                encoded = image_b64.split(",")[1]
                image_id = upload_image(encoded, student.ADMISSION_NO, school.students_image_folder_id)
                if student.IMAGE:
                    move_image(student.IMAGE, deleted_folder, rename=str(student_id))
                student.IMAGE = image_id
            elif image_status == "removed" and student.IMAGE:
                old_id = student.IMAGE
                student.IMAGE = None
                move_image(old_id, deleted_folder, rename=str(student_id))
            start = time.perf_counter()
            db.session.commit()
            end = time.perf_counter()
            print(f"Update student time: {end - start:.6f} seconds")
            return None
        except IntegrityError:
            db.session.rollback()
            return "Update failed due to data conflicts."
        except Exception as e:
            db.session.rollback()
            return f"Update failed: {str(e)}"


    # Bulk Admission Utilities
    @classmethod
    def resolve_class(cls, value, class_map):

        if not value:
            return None

        raw = str(value).strip().lower()
        candidates = set()

        candidates.add(raw)

        candidates.add(raw.replace("class", "").strip())

        candidates.add(re.sub(r"(st|nd|rd|th)$", "", raw))

        if raw in cls.ROMAN_MAP:
            candidates.add(cls.ROMAN_MAP[raw])

        if raw in cls.EXTRA_MAP:
            candidates.add(cls.EXTRA_MAP[raw])

        for c in candidates:
            key = c.strip().lower()
            if key in class_map:
                return class_map[key]

        return None

    
    @staticmethod
    def read_excel_rows(file, class_map, field_map=None):

        if field_map is None:
            field_map = StudentService.EXCEL_FIELDS

        wb = load_workbook(file)
        ws = wb.active

        headers = [c.value for c in ws[1] if c.value]

        reverse_map = {v: k for k, v in field_map.items()}
        field_headers = [reverse_map.get(h, h) for h in headers]

        rows = []

        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):

            if all(v is None or str(v).strip() == "" for v in row):
                continue

            row_dict = {}

            for i, value in enumerate(row):

                if i >= len(field_headers):
                    break

                field = field_headers[i]

                if value is None or str(value).strip() == "":
                    row_dict[field] = None
                    continue

                val = str(value).strip()

                if field in ("CLASS", "Admission_Class"):

                    resolved = StudentService.resolve_class(val, class_map)

                    if resolved:
                        row_dict[field] = resolved["id"]
                        row_dict[field + "_name"] = resolved["name"]
                    else:
                        row_dict[field] = None
                        row_dict[field + "_raw"] = val

                else:
                    row_dict[field] = val

            row_dict["_row_number"] = idx

            rows.append(row_dict)

        return rows
    
    
    @staticmethod
    def detect_excel_duplicates(rows):
        seen_sr = {}
        seen_admission = {}
        seen_class_roll = {}
        duplicates = {}

        for row in rows:
            row_no = row.get("_row_number")
            sr = row.get("SR")
            adm = row.get("ADMISSION_NO")
            cls = row.get("CLASS")
            roll = row.get("ROLL")

            if sr:
                if sr in seen_sr:
                    duplicates[row_no] = "Duplicate SR number in Excel"
                else:
                    seen_sr[sr] = row_no

            if adm:
                if adm in seen_admission:
                    duplicates[row_no] = "Duplicate Admission Number in Excel"
                else:
                    seen_admission[adm] = row_no

            if cls and roll:
                key = (cls, roll)
                if key in seen_class_roll:
                    duplicates[row_no] = "Duplicate Class + Roll in Excel"
                else:
                    seen_class_roll[key] = row_no

        return duplicates

    @staticmethod
    def validate_rows(rows, excel_duplicates):
        valid_rows = []
        errors = []

        for row in rows:
            row_no = row.get("_row_number")

            if row_no is None:
                continue


            # Excel duplicate check
            if row_no in excel_duplicates:
                errors.append({"row": row_no, "error": excel_duplicates[row_no]})
                continue

            # class mapping error
            if "_class_error" in row:
                errors.append({ "row": row_no, "error": f"Invalid class: {row['_class_error']}" })
                continue

            missing = [f for f in StudentService.REQUIRED_FIELDS if not row.get(f)]
            if missing:
                errors.append({"row": row_no, "error": f"Missing fields: {', '.join(missing)}"})
                continue


            try:
                from src.controller.students.utils.admission_form_schema import AdmissionFormModel
                from src.controller.students.utils.conflict_verification import verify_conflicts

                model = AdmissionFormModel(**row)
                verified = model.to_verified_data()

                conflict = verify_conflicts(verified, mode="add")
                if conflict:
                    message = conflict[0].get("message") if isinstance(conflict, list) else "Conflict detected"
                    errors.append({"row": row_no, "error": message})
                    continue

                valid_rows.append({"row_data": row, "verified_data": verified})

            except ValidationError as e:
                msg = "; ".join(f"{err['loc'][0]}: {err['msg']}" for err in e.errors())
                errors.append({"row": row_no, "error": msg})

        return valid_rows, errors
