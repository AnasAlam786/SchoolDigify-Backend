# src/controller/RTE_students.py

from flask import Blueprint, render_template_string, session, redirect, url_for

from sqlalchemy import func, cast, String
from sqlalchemy.orm import aliased


from src.model import StudentsDB
from src.model import StudentSessions
from src.model import ClassData
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

RTE_students_bp = Blueprint( 'RTE_students_bp',   __name__)

@RTE_students_bp.route('/RTE_students')
@login_required
def RTE_students():

    school_id = session['school_id']
    current_session_id = session['session_id']

    AdmissionClass = aliased(ClassData)

    students = db.session.query(
        StudentsDB.id,
        StudentsDB.SR,
        StudentsDB.GENDER,
        StudentsDB.STUDENTS_NAME,
        func.to_char(StudentsDB.DOB, 'DD-MM-YY').label('DOB'),
        StudentsDB.AADHAAR,
        StudentsDB.FATHERS_NAME,
        StudentsDB.MOTHERS_NAME,
        StudentsDB.PHONE,
        StudentsDB.ADDRESS,
        StudentsDB.Free_Scheme,
        StudentsDB.ADMISSION_SESSION,
        ClassData.CLASS.label('Current_Class'),
        AdmissionClass.CLASS.label('Admission_Class')
    ).join(
        StudentSessions, StudentSessions.student_id == StudentsDB.id
    ).join(
        ClassData, StudentSessions.class_id == ClassData.id
    ).join(
        AdmissionClass, StudentsDB.admission_class_id == AdmissionClass.id
    ).filter(
        StudentSessions.session_id == current_session_id,
        StudentsDB.school_id == school_id,
        StudentsDB.Free_Scheme.isnot(None),
        cast(StudentsDB.Free_Scheme, String) != 'null',
        cast(StudentsDB.Free_Scheme, String) != '""',
        cast(StudentsDB.Free_Scheme, String) != '{}'
    ).order_by(
        ClassData.id.asc(),
    ).all()

    
    page="""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RTE Table</title>
<style>
body {
    font-family: Arial, sans-serif;
    box-sizing: border-box;
    font-size: 11px; /* Adjusted for better fitting */
}
table {
    width: 100%; /* Ensure table does not exceed the page width */
    text-align: left;
    border-collapse: collapse;
    table-layout: fixed; /* Ensures columns auto-adjust */
}
th, td {
    border: 1px solid black;
    padding: 2px;
    text-align: center;
    white-space: normal; /* Allow wrapping at natural word boundaries */
    overflow-wrap: break-word; /* Ensures text wraps to the next line */
    word-break: normal; /* Avoid breaking words unless necessary */
}
th {
    font-weight: bold;
    font-size: 9px; /* Slightly smaller header text */
}
.label-cell {
    width: 15%; /* Adjusted width for better layout */
    font-weight: bold;
}
@media print {
    body {
        margin: 0;
        padding: 0;
    }

    table {
        page-break-inside: auto;
        width: 100%;
        font-size: 11px;
        border-collapse: collapse;
    }

    tr {
        page-break-inside: avoid; /* Avoid breaking inside a row */
        page-break-after: auto;
    }

    th, td {
        border: 1px solid black;
        padding: 2px;
        text-align: center;
    }
}

}
</style>


</head>
<body>
    <div class = "print-page">
        <div class="header" style="text-align: center; font-weight: bold; margin-bottom: 10px; font-size: 24px;">
            RTE के अन्तर्गत प्रवेशित बच्चों की सूचना, नगर क्षेत्र मुरादाबाद
        </div>

        <table>
            <tr>
                <td colspan="1" class="label-cell">NAME OF DISTRICT:</td>
                <td colspan="2">MORADABAD</td>
                <td colspan="1" class="label-cell">NAME OF BLOCK:</td>
                <td colspan="2">MORADABAD CITY</td>
            </tr>
            <tr>
                <td class="label-cell">NAME OF SCHOOL WITH ADDRESS:</td>
                <td colspan="5">FALAK PUBLIC SCHOOL, JAYANTIPUR ROAD KARULA MORADABAD</td>
            </tr>
            <tr>
                <td class="label-cell">UDISE CODE OF SCHOOL:</td>
                <td colspan="1">09041404306</td>
                <td class="label-cell">School Manager Name:</td>
                <td>ISRAR AHMAD</td>
                <td class="label-cell">Mobile Number:</td>
                <td>8533998822</td>
            </tr>
            <tr>
                <td class="label-cell">School Account Name:</td>
                <td>FALAK PUBLIC SCHOOL</td>
                <td class="label-cell">Name Of Bank:</td>
                <td>CANARA BANK</td>
                <td class="label-cell">Branch Name:</td>
                <td>PARSVNATH PLAZA, MAJHOLA, MBD</td>
            </tr>
            <tr>
                <td class="label-cell">BOARD OF SCHOOL (CBSE/ICSE/OTHER):</td>
                <td>U.P BOARD</td>
                <td class="label-cell">Account Number:</td>
                <td>120003050001</td>
                <td class="label-cell">IFSC: </td>
                <td>CNRB0018826</td>
            </tr>
            <tr>
                <td class="label-cell">CATEGORY OF SCHOOL:</td>
                <td colspan="2">2 - Primary with Upper Primary</td>
                <td class="label-cell">Fee Per Month:</td>
                <td colspan="2">₹350.00</td>
            </tr>
        </table>

        <table>
            <thead style="text-align: center;">
                <tr style="text-align: center;">
                    <th>Students Name</th>
                    <th>Fathers Name</th>
                    <th style="width: 100px;">Address</th>
                    <th>Mobile No</th>
                    <th>Admission Year</th>
                    <th>कक्षा जिसमे बच्चे का प्रवेश हुआ</th>
                    <th style="width: 45px;">नामांकन पंजिका क्रमांक (S.R)</th>
                    <th>वर्तमान कक्षा</th>
                    <th style="width: 70px;">बच्चे की वर्तमान स्थिति (पढ़ रहा है अथवा ड्रॉप आउट)</th>
                    <th>DOB</th>
                    <th>Gender</th>
                    <th style="width: 70px;">Mothers Name</th>
                    <th>Name Of Act Holder</th>
                    <th>Name of Bank</th>
                    <th>Branch Name</th>
                    <th style="width: 90px;">IFSC Code</th>
                    <th style="width: 100px;">Act Number</th>
                </tr>
            </thead>
            <tbody>
                <!-- Add table rows dynamically here -->
                {% for student in students %}
                <tr>
                    <td>{{ student.STUDENTS_NAME }}</td>
                    <td>{{ student.FATHERS_NAME }}</td>
                    <td>{{ student.ADDRESS }}</td>
                    <td>{{ student.PHONE }}</td>
                    <td>{{ student.ADMISSION_SESSION }}</td>
                    <td>{{ student.Admission_Class }}</td>
                    <td>{{ student.SR }}</td>
                    <td>{{ student.Current_Class }}</td>
                    <td>STUDYING</td>
                    <td>{{ student.DOB }}</td>
                    <td>{{ student.GENDER }}</td>
                    <td>{{ student.MOTHERS_NAME }}</td>
                    <td>{{ student.Free_Scheme["AC Holder"] }}</td>
                    <td>{{ student.Free_Scheme["Bank"] }}</td>
                    <td>{{ student.Free_Scheme["Branch"] }}</td>
                    <td>{{ student.Free_Scheme["IFSC"] }}</td>
                    <td>{{ student.Free_Scheme["AC"] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    
    
    return render_template_string(page, students=students)
