# src/controller/students/utils/conflict_verification.py

from flask import session
from src.controller.students.utils.student_service import StudentService
from src.model import StudentsDB, StudentSessions


def parse_int(value):
    """
    Safely parse integer.
    Empty strings and None return None.
    """

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    try:
        return int(value)
        

    except (ValueError, TypeError):
        return None


def verify_conflicts(verified_data, mode='add', student_id=None):
    """
    Unified conflict verification for student admission and update.

    Returns:
        str: Error message if conflicts found, None otherwise
    """

    school_id = session.get("school_id")
    session_id = session.get("session_id")
    
    # --------------------------------------------------
    # Parse Common Fields
    # --------------------------------------------------

    admission_class = parse_int(verified_data.get("admission_class_id"))
    
    current_class = parse_int(verified_data.get("class_id"))
    roll = parse_int(verified_data.get("ROLL"))

    admitted_as_new = verified_data.get("admitted_as_new")

    # --------------------------------------------------
    # Required Current Class
    # --------------------------------------------------
    if current_class is None:
        return {
            "class_id": "Current Class is required.",
        }
    
    # --------------------------------------------------
    # Admission Class Validation (OPTIONAL FIELD)
    # --------------------------------------------------
    # Only validate if Admission_Class exists.
    # This supports:
    # - legacy imports
    # - incomplete historical records
    # - migrated data
    # --------------------------------------------------
    if admission_class is not None:

        # ----------------------------------------------
        # NEW STUDENTS
        # ----------------------------------------------
        if admitted_as_new:

            if admission_class != current_class:
                return {
                    "admission_class_id": "For new students, Admission Class "
                               "must be same as Current Class.",
                }

        # ----------------------------------------------
        # OLD STUDENTS
        # ----------------------------------------------
        elif not admitted_as_new:

            class_error = StudentService.validate_class_order(
                admission_class,
                current_class
            )

            if class_error:
                return { 'admission_class_id': class_error, 'class_id': class_error },
                

    
    # --------------------------------------------------
    # UPDATE MODE VALIDATIONS
    # --------------------------------------------------
    if mode == 'update':

        if not student_id:
            return { "student_id": "Student ID required for update mode." }

        student = StudentsDB.query.filter_by(
            id=student_id
        ).first()

        if not student:
            return { "student_id": "Student not found.", }

        # ----------------------------------------------
        # Academic History Check
        # ----------------------------------------------

        has_past_records = (
            StudentSessions.query.filter(
                StudentSessions.student_id == student_id,
                StudentSessions.session_id != session_id
            ).first() is not None
        )

        # ----------------------------------------------
        # Students with Academic History
        # ----------------------------------------------

        if has_past_records:

            # Prevent marking historical students as new
            if admitted_as_new:
                return {
                    "admitted_as_new": "Student has academic history! Cannot mark as new. "
                }

            # ------------------------------------------
            # Prevent direct class modification
            # ------------------------------------------

            original_class = (
                StudentSessions.query
                .with_entities(StudentSessions.class_id)
                .filter_by(
                    student_id=student_id,
                    session_id=session_id
                )
                .scalar()
            )

            if (
                verified_data.get("CLASS") is not None
                and str(original_class) != str(current_class)
            ):
                return {
                    "CLASS": "Cannot modify Current Class directly. "
                               "Use Promotion Feature.",
                }

            # ------------------------------------------
            # Prevent Admission Session Modification
            # ------------------------------------------
            original_session = student.admission_session_id
            new_session = verified_data.get("admission_session_id")

            if (
                new_session is not None
                and str(original_session) != str(new_session)
            ):
                return {
                    "admission_session_id": "Cannot modify Admission Session "
                               "for students with academic history.",
                }


    # --------------------------------------------------
    # UNIQUE FIELD CONFLICTS
    # --------------------------------------------------
    exclude_id = student_id if mode == 'update' else None

    school_fields = ["SR", "ADMISSION_NO", "PEN", "AADHAAR", "APAAR"]

    duplicate_fields, duplicate_student  = StudentService.check_unique_conflicts(
        verified_data, school_id, school_fields, exclude_student_id=exclude_id
        )
    if duplicate_fields:
        return {
            field: (
                f"This {field.replace('_', ' ').title()} "
                f"is already used by '{duplicate_student.STUDENTS_NAME}'."
            )
            for field in duplicate_fields
        }


    # --------------------------------------------------
    # ROLL VALIDATION
    # --------------------------------------------------

    if roll is None:
        return {'ROLL': "Roll Number is required."}

    roll_error  = StudentService.check_roll_availability(
        current_class, session_id, roll, exclude_student_id=exclude_id
    )
    if roll_error:
        final_error = {'ROLL': roll_error}
        return final_error
    
    # --------------------------------------------------
    # SUCCESS
    # --------------------------------------------------

    return None