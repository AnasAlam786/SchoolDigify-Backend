# src/controller/students/utils/student_service.py

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError

from src import db
from src.model import StudentsDB, StudentSessions, ClassData, RTEInfo, Schools
from src.controller.utils.upload_image import upload_image, delete_image, move_image



class StudentService:


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
    def create_student(verified_data: List[Dict], image_blob: Optional[str], school_id: int, session_id: int) -> Tuple[Optional[int], Optional[str]]:
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
            if image_blob:
                school = Schools.query.filter_by(id=school_id).first()
                if school:
                    image_id = upload_image(image_blob, verified_data.get("STUDENTS_NAME"), school.students_image_folder_id)
                    new_student.IMAGE = image_id
            db.session.commit()

            return new_student.id, None
        except IntegrityError as e:
            print(e)
            db.session.rollback()
            return None, "Database integrity error. Possible duplicate data."
        except Exception as e:
            db.session.rollback()
            if 'image_id' in locals():
                delete_image(image_id)
            return None, f"Failed to create student: {str(e)}"

    @staticmethod
    def update_student(student_id: int, verified_data: Dict[str, Any], file_blob: Optional[str], image_status: str, school_id: int, session_id: int) -> Optional[str]:
        """Update an existing student."""
        student = StudentsDB.query.filter_by(id=student_id).first()
        if not student:
            return "Student not found."


        # Handle admitted_as_new to set admission_session_id appropriately
        admitted_as_new = verified_data.get('admitted_as_new')
        if admitted_as_new:
            # New student - set admission_session_id to current session
            verified_data['admission_session_id'] = session_id
        elif not admitted_as_new:
            # Old student - keep existing admission_session_id (don't override)
            if 'admission_session_id' in verified_data:
                del verified_data["admission_session_id"]

        studentsdb_updates = {k: v for k, v in verified_data.items() if k in StudentsDB.__table__.columns}
        sessions_updates = {k: v for k, v in verified_data.items() if k in StudentSessions.__table__.columns}
        rte_updates = {k: v for k, v in verified_data.items() if k in RTEInfo.__table__.columns}

        # Convert dates
        for field in ["DOB", "ADMISSION_DATE"]:
            if field in studentsdb_updates and isinstance(studentsdb_updates[field], str):
                try:
                    studentsdb_updates[field] = datetime.strptime(studentsdb_updates[field], "%d-%m-%Y").date()
                except ValueError:
                    return f"Invalid date format for {field}."

        # Special mappings
        if "class_id" in verified_data:
            sessions_updates["class_id"] = verified_data.get("class_id")
        if "Section" in verified_data:
            sessions_updates["Section"] = verified_data.get("Section")
        if "ROLL" in verified_data:
            sessions_updates["ROLL"] =verified_data.get("ROLL")

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
            deleted_folder = os.getenv("DELETED_IMAGE_FOLDER_ID")
            school = Schools.query.filter_by(id=school_id).first()
            if not school:
                return "School not found."

            if image_status == "changed" and file_blob:
                image_id = upload_image(file_blob, student.ADMISSION_NO, school.students_image_folder_id)
                if student.IMAGE:
                    move_image(student.IMAGE, deleted_folder, rename=str(student_id))
                student.IMAGE = image_id
            elif image_status == "removed" and student.IMAGE:
                old_id = student.IMAGE
                student.IMAGE = None
                move_image(old_id, deleted_folder, rename=str(student_id))
            db.session.commit()
            return None
        except IntegrityError:
            print('Update failed due to data conflicts.')
            db.session.rollback()
            return "Update failed due to data conflicts."
        except Exception as e:
            print(f"Update failed: {str(e)}")
            db.session.rollback()
            return f"Update failed: {str(e)}"



