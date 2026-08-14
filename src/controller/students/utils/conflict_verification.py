# src/controller/students/utils/conflict_verification.py

from flask import session
from src.controller.students.utils.student_service import StudentService
from src.model import StudentsDB, StudentSessions
from src.controller.utils.get_available_rolls import get_available_rolls

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

    admission_class_id = parse_int(verified_data.get("admission_class_id"))
    current_class_id = parse_int(verified_data.get("class_id"))
    roll = parse_int(verified_data.get("ROLL"))
    admitted_as_new = verified_data.get("admitted_as_new")


    # --------------------------------------------------
    # Required Current Class
    # --------------------------------------------------
    if current_class_id is None:
        return {
            "class_id": "Current Class is required.",
        }
    
    # --------------------------------------------------
    # Admission Class Validation (OPTIONAL FIELD)
    # --------------------------------------------------
    # Only validate if admission_class_id exists.
    # This supports:
    # - legacy imports
    # - incomplete historical records
    # - migrated data
    # --------------------------------------------------
    
    if admission_class_id is not None:

        # ----------------------------------------------
        # NEW STUDENTS
        # ----------------------------------------------
        if admitted_as_new:

            if admission_class_id != current_class_id:
                return {
                    "admission_class_id": "For new students, Admission Class "
                               "must be same as Current Class.",
                }

        # ----------------------------------------------
        # OLD STUDENTS
        # ----------------------------------------------
        elif not admitted_as_new:

            class_error = StudentService.validate_class_order(
                admission_class_id,
                current_class_id
            )


            print(class_error)

            if class_error:
                return {'admission_class_id': class_error}
                
    # --------------------------------------------------
    # UPDATE MODE VALIDATIONS
    # --------------------------------------------------
    
    if mode == 'update':

        student = StudentsDB.query.filter_by(
            id=student_id
        ).first()

        if not student:
            return { "STUDENTS_NAME": "Student not found.", }

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
                verified_data.get("class_id") is not None
                and str(original_class) != str(current_class_id)
            ):
                return {
                    "class_id": "Cannot modify Current Class directly. "
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

    available_rolls = get_available_rolls(
        current_class_id, session_id, excluded_student_id=exclude_id
    )["available_rolls"]

    if roll not in available_rolls:
        return {
            "ROLL": (
                f"Roll number {roll} is not available. "
                f"Available roll numbers: {', '.join(map(str, available_rolls))}."
            )
        }
    
    # --------------------------------------------------
    # SUCCESS
    # --------------------------------------------------
    
    return None