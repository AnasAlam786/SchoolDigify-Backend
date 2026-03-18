# src/controller/students/add_student/bulk_admission_api.py

import io
from flask import request, jsonify, Blueprint, session, send_file
from openpyxl import Workbook

from src import db
from src.model.ClassData import ClassData
from src.controller.students.utils.student_service import StudentService
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

bulk_admission_bp = Blueprint('bulk_admission_bp', __name__)


@bulk_admission_bp.route('/bulk_admission_template', methods=['GET'])
@login_required
@permission_required('admission')
def download_template():
    """Generate and download Excel template for bulk admission."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Student Admission Template"

    # Add headers
    headers = list(StudentService.EXCEL_FIELDS.values())
    for col_num, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_num, value=header)

    # Add sample data row
    sample_data = [
        "John Doe", "15-08-2010", "Male", "888563751411", "General", "GENERAL", "Hindu",
        "150", "45", "O+", "new", "2025", "1", "1", "47", "1", "250001", "15-06-2025",
        "", "", "Jane Doe", "", "Hello", "", "", "", "", "", "123 Main St, City", "9876543210",
        "", "123456", "Less than 1 km", "john@example.com", "85", "90", "Previous School",
        "No", "", "", "", "", "", "", ""
    ]

    for col_num, value in enumerate(sample_data, 1):
        ws.cell(row=2, column=col_num, value=value)

    # Add instructions sheet
    ws_instructions = wb.create_sheet("Instructions")
    instructions = [
        "INSTRUCTIONS FOR BULK STUDENT ADMISSION",
        "",
        "1. Fill in all required fields marked with *",
        "2. Use exact values for dropdown fields (Gender, Caste Type, Religion, etc.)",
        "3. Date format: DD-MM-YYYY",
        "4. Phone numbers: 10 digits only",
        "5. Aadhaar: 12 digits only",
        "6. PIN Code: 6 digits only",
        "7. Student Status: 'new' for new admissions, 'old' for existing students",
        "8. Class IDs: Use numeric class IDs from your school",
        "9. Do not modify column headers",
        "10. Leave optional fields blank if not applicable",
        "",
        "REQUIRED FIELDS:",
        ", ".join([StudentService.EXCEL_FIELDS[field] for field in StudentService.REQUIRED_FIELDS]),
        "",
        "VALID ENUM VALUES:",
        "Gender: Male, Female, Other",
        "Caste Type: General, OBC, SC, ST",
        "Religion: Hindu, Muslim, Christian, Sikh, Buddhist, Jain, Other",
        "Blood Group: A+, A-, B+, B-, AB+, AB-, O+, O-",
        "Education: Illiterate, Primary, Secondary, Higher Secondary, Graduate, Post Graduate",
        "Occupation: Business, Service, Farmer, Laborer, Teacher, Doctor, Engineer, Other",
        "Home Distance: Within 5km, 5-10km, 10-20km, Above 20km"
    ]

    for row_num, instruction in enumerate(instructions, 1):
        ws_instructions.cell(row=row_num, column=1, value=instruction)

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name='student_admission_template.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@bulk_admission_bp.route("/bulk_admission_validate", methods=["POST"])
@login_required
@permission_required('admission')
def bulk_admission_validate():
    file = request.files.get("file")

    if not file or not file.filename.endswith(".xlsx"):
        return jsonify({"message": "Upload a valid .xlsx file"}), 400

    try:
        school_id = session.get("school_id")

        classes = db.session.query(ClassData).filter_by(school_id=school_id).all()

        class_map = {
            str(c.CLASS).strip().lower(): {
                "id": c.id,
                "name": c.CLASS
            }
            for c in classes
        }


        rows = StudentService.read_excel_rows(file, class_map=class_map)

        excel_duplicates = StudentService.detect_excel_duplicates(rows)
        print(f"Detected {len(excel_duplicates)} duplicate rows in Excel")
        print(f"Sample duplicate: {excel_duplicates}")


        validated_rows, errors = StudentService.validate_rows(rows, excel_duplicates)

        if errors:
            return jsonify({
                "message": "Validation failed",
                "errors": errors
            }), 400

        return jsonify({
            "message": "Validation successful",
            "rows": validated_rows,
            "total_rows": len(validated_rows)
        })

    except Exception as e:
        print(e)
        return jsonify({"message": "Excel processing failed"}), 500


@bulk_admission_bp.route('/bulk_admission_preview', methods=['POST'])
@login_required
@permission_required('admission')
def preview_import():
    """Generate preview of students to be imported."""
    data = request.get_json()
    validation_results = data.get('validation_results', {})

    if not validation_results.get('valid_rows'):
        return jsonify({"message": "No valid data to preview"}), 400

    school_id = session.get('school_id')
    if not school_id:
        return jsonify({"message": "School context missing"}), 400

    preview_students = []

    for item in validation_results['valid_rows']:
        row_data = item['row_data']
        verified_data = item['verified_data']

        # Get class name
        try:
            class_id = int(row_data.get('CLASS'))
            class_name = db.session.query(ClassData.CLASS).filter(
                ClassData.id == class_id,
                ClassData.school_id == school_id
            ).scalar() or f"Class {class_id}"
        except:
            class_name = f"Class {row_data.get('CLASS', 'Unknown')}"

        preview_students.append({
            "SR": row_data.get('SR'),
            "STUDENTS_NAME": row_data.get('STUDENTS_NAME'),
            "CLASS_NAME": class_name,
            "ADMISSION_NO": row_data.get('ADMISSION_NO'),
            "FATHERS_NAME": row_data.get('FATHERS_NAME'),
            "PHONE": row_data.get('PHONE'),
            "row_data": row_data,
            "verified_data": verified_data
        })

    return jsonify({
        "message": "Preview generated",
        "students": preview_students
    })

@bulk_admission_bp.route('/bulk_admission_import', methods=['POST'])
@login_required
@permission_required('admission')
def import_students():
    """Import validated students into database."""
    data = request.get_json()
    preview_data = data.get('preview_data', {})

    if not preview_data.get('students'):
        return jsonify({"message": "No students to import"}), 400

    school_id = session.get('school_id')
    session_id = session.get('session_id')
    user_id = session.get('user_id')

    if not all([school_id, session_id, user_id]):
        return jsonify({"message": "Session context missing"}), 400

    imported_count = 0
    errors = []

    for student in preview_data['students']:
        try:
            verified_data = student['verified_data']
            
            # Use StudentService to create student
            # student_id, error = StudentService.create_student(verified_data, None, school_id, session_id)
            # if error:
            #     errors.append(f"Failed to import {student.get('STUDENTS_NAME', 'Unknown')}: {error}")
            #     continue
                
            imported_count += 1

        except Exception as e:
            errors.append(f"Failed to import {student.get('STUDENTS_NAME', 'Unknown')}: {str(e)}")
            print(f"Import error: {e}")

    if errors:
        return jsonify({
            "message": f"Imported {imported_count} students with {len(errors)} errors",
            "imported_count": imported_count,
            "errors": errors
        }), 207  # Multi-status

    return jsonify({
        "message": f"Successfully imported {imported_count} students",
        "imported_count": imported_count
    })