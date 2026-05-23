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

    Args:
        verified_data: List of dicts with 'field' and 'value'
        mode: 'add' or 'update'
        student_id: Required for update mode

    Returns:
        str: Error message if conflicts found, None otherwise
    """
    values = {item["field"]: item["value"] for item in verified_data}

    school_id = session.get("school_id")
    session_id = session.get("session_id")
    if not school_id or not session_id:
        return [{'message': "Session context missing."}]
    
    # --------------------------------------------------
    # Parse Common Fields
    # --------------------------------------------------

    admission_class = parse_int(values.get("Admission_Class"))
    current_class = parse_int(values.get("CLASS"))
    roll = parse_int(values.get("ROLL"))

    student_status = str(
        values.get("student_status", "")
    ).strip().lower()

    # --------------------------------------------------
    # Required Current Class
    # --------------------------------------------------
    if current_class is None:
        return [{
            "message": "Current Class is required.",
            "field": "CLASS"
        }]
    
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
        if student_status == "new":

            if admission_class != current_class:
                return [{
                    "message": "For new students, Admission Class "
                               "must be same as Current Class.",
                    "field": "Admission_Class"
                }]

        # ----------------------------------------------
        # OLD STUDENTS
        # ----------------------------------------------
        elif student_status == "old":

            class_error = StudentService.validate_class_order(
                admission_class,
                current_class
            )

            if class_error:
                return [
                    {
                        'field': 'Admission_Class',
                        'message': class_error
                    },
                    {
                        'field': 'CLASS',
                        'message': class_error
                    }
                ]

    
    # --------------------------------------------------
    # UPDATE MODE VALIDATIONS
    # --------------------------------------------------
    if mode == 'update':

        if not student_id:
            return [{
                "message": "Student ID required for update mode.",
                "field": "student_id"
            }]

        student = StudentsDB.query.filter_by(
            id=student_id
        ).first()

        if not student:
            return [{
                "message": "Student not found.",
                "field": "student_id"
            }]

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
            if student_status == "new":
                return [{
                    "message": "Student has academic history. "
                               "Cannot mark as new.",
                    "field": "student_status"
                }]

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
                values.get("CLASS") is not None
                and str(original_class) != str(current_class)
            ):
                return [{
                    "message": "Cannot modify Current Class directly. "
                               "Use Promotion Feature.",
                    "field": "CLASS"
                }]

            # ------------------------------------------
            # Prevent Admission Session Modification
            # ------------------------------------------
            original_session = student.admission_session_id
            new_session = values.get("admission_session_id")

            if (
                new_session is not None
                and str(original_session) != str(new_session)
            ):
                return [{
                    "message": "Cannot modify Admission Session "
                               "for students with academic history.",
                    "field": "admission_session_id"
                }]


    # --------------------------------------------------
    # UNIQUE FIELD CONFLICTS
    # --------------------------------------------------
    exclude_id = student_id if mode == 'update' else None

    school_fields = ["SR", "ADMISSION_NO", "PEN", "AADHAAR", "APAAR"]

    unique_error  = StudentService.check_unique_conflicts(
        values, school_id, school_fields, exclude_student_id=exclude_id
        )
    if unique_error:
        return [{'message': unique_error}]


    # --------------------------------------------------
    # ROLL VALIDATION
    # --------------------------------------------------

    if roll is None:
        return [{'field': 'ROLL', 'message': "Roll Number is required."}]

    roll_error  = StudentService.check_roll_availability(
        current_class, session_id, roll, exclude_student_id=exclude_id
    )
    if roll_error:
        final_error = [{'field': 'ROLL', 'message': roll_error}]
        return final_error
    
    # --------------------------------------------------
    # SUCCESS
    # --------------------------------------------------

    return None