from types import SimpleNamespace
from flask import render_template, session, request, Blueprint, jsonify

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

from src.model import StudentsDB, ClassData, StudentSessions, Schools
from src import db

get_admit_cards_api_bp = Blueprint('get_admit_cards_api_bp', __name__)


@get_admit_cards_api_bp.route('/api/admit_cards_api', methods=['POST'])
@login_required
@permission_required('admit_card')
def get_admit_cards_api():
    """Fetch students for admit cards and render `admit.html`.

    Accepts optional JSON payload (POST) or query params (GET):
      - class: class id to filter students by class
      - exam: exam name to display on cards
      - year: year to display on cards
      - quality: image size quality for GDrive images (default 200)

    Returns JSON with rendered HTML under the "html" key (consistent with other APIs).
    """

    data = request.json or {}


    admit_heading = data.get('admitHeading', '')
    scheme_heading = data.get('schemeHeading', '')
    outputType = data.get('outputType', '')
    examScheme = data.get('examScheme', '')

    school_id = session.get('school_id')
    current_session_id = session.get('session_id')

    if not school_id or not current_session_id:
        return jsonify({"message": "Missing session context (school/session)."}), 400

    class_id = data.get('class')

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
    ).join(
        StudentSessions, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, StudentSessions.class_id == ClassData.id
    ).filter(
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == current_session_id,
    ).order_by(
        ClassData.display_order,  # first order by class display order
        StudentSessions.ROLL      # then by roll number
    )


    if class_id:
        try:
            class_id = int(class_id)
            query = query.filter(StudentSessions.class_id == class_id)
        except Exception:
            pass

    students = query.all()

    # Convert rows to mutable objects and format dates
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
        student_objs.append(obj)

    # Group students into pages of 2 (1x1 layout for both admit and scheme) 
    if outputType == 'both':
        page_size = 2
    else:
        page_size = 4

    pages = [student_objs[i:i + page_size] for i in range(0, len(student_objs), page_size)]

    # Get school info for logo and name
    school = db.session.query(Schools).filter_by(id=school_id).first()
    school_name = school.School_Name if school else ''
    logo = school.Logo if school else ''

    html = render_template('admit_card/admit_pdf.html', data=pages, logo=logo, 
                           school=school_name, admit_heading=admit_heading, scheme_heading=scheme_heading, outputType=outputType, 
                           examScheme=examScheme)

    return jsonify({"html": str(html)})

