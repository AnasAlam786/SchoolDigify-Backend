from datetime import datetime
import random
from flask import session, request, jsonify, Blueprint

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required

get_message_api_bp = Blueprint( 'get_message_api_bp',   __name__)


@get_message_api_bp.route('/api/get_absent_message', methods=["GET"])
@login_required
@permission_required('attendance')
def get_absent_message_api():

    student_name = request.args.get("studentName")
    father_name = request.args.get("fathersName")
    class_name = request.args.get("className")
    date_str = request.args.get("date")
    school_name = session.get("school_name")

    def parse_date(date_str):
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                pass
        return None

    try:
        date = parse_date(date_str)
        current_date = datetime.today().date()

        date_expanded = date.strftime("%A, %d %B %Y")
        

        messages = [
    f"⚠️ *Attendance Alert — {school_name}* ⚠️\n\n"
    f"👦 *Student:* {student_name}\n"
    f"👨 *Parent:* {father_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"❗ *{student_name}* was absent {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Please notify the school if this absence has a valid reason.\n\n"
    f"🙏 *Thank you for your cooperation.*",

    f"📌 *{school_name} — Attendance Notification*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"👨 *Parent:* {father_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"⚠️ {student_name} was absent {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Kindly inform the school if necessary.",

    f"📝 *Attendance Record — {school_name}*\n\n"
    f"• *Student:* {student_name}\n"
    f"• *Father:* {father_name}\n"
    f"• *Class:* {class_name}\n"
    f"• *Date:* {date_expanded}\n\n"
    f"❗ *{student_name}* did not attend school {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Please update the school if needed.",

    f"⚠️ *Absence Notice — {school_name}*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"‼️ {student_name} was absent {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Do inform the school if this absence has a genuine reason.",

    f"🔹 *{school_name} Attendance Update*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"👨 *Parent:* {father_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"⚠️ {student_name} has not attended school {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Kindly keep the school informed.",

    f"📢 *Daily Attendance — {school_name}*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"👨 *Parent:* {father_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"⚠️ Reminder: {student_name} was absent {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Please notify the school if necessary.",

    f"🔔 *Important Attendance Update — {school_name}*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"❗ {student_name} has been marked absent.\n"
    f"If this absence was due to illness or other valid reasons, kindly inform the school.",

    f"🟦 *Attendance Notice — {school_name}*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"⚠️ {student_name} did not attend school {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Please update the school if required.",

    f"📚 *{school_name} Attendance Record*\n\n"
    f"• *Student:* {student_name}\n"
    f"• *Parent:* {father_name}\n"
    f"• *Class:* {class_name}\n"
    f"• *Date:* {date_expanded}\n\n"
    f"❗ Absence recorded for {student_name}. Kindly notify the school if needed.",

    f"🔰 *Absence Report — {school_name}*\n\n"
    f"👦 *Student:* {student_name}\n"
    f"👨 *Parent:* {father_name}\n"
    f"🏫 *Class:* {class_name}\n"
    f"📅 *Date:* {date_expanded}\n\n"
    f"⚠️ {student_name} was absent {'on ' + date_expanded if date != current_date else 'today'}.\n"
    f"Please inform the school if required."
]
        
        selected_message = random.choice(messages)
    except Exception as e: 
        print(f"Error generating absent message: {e}")
        return jsonify({"message": "Failed to generate absent message"}), 500



    return jsonify({"absent_message": selected_message }), 200