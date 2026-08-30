# src/controller/__init__.py

from .auth.login import login_bp
from .auth.logout import logout_bp

from .home import home_bp
from .students_list.student_list import student_list_bp
from .utils.student_modal_data_api import student_modal_data_api_bp
from .students_list.get_students_data_api import get_students_data_api_bp
from .students_list.get_students_pdf_api import get_students_pdf_api_bp
from .admit_card.get_admit_cards_api import get_admit_cards_api_bp


from .attendance.get_attendance_data_api import get_attendance_data_api_bp
from .attendance.mark_attendance_api import mark_attendance_api_bp
from .attendance.holiday_manager import holiday_manager_api_bp
from .attendance.utils.messages_api import get_message_api_bp
from .attendance.overall_attendance.get_overall_attendance_data_api import get_overall_attendance_data_api_bp
from .attendance.overall_attendance.update_overall_attendance_api import update_overall_attendance_api_bp

from .fees.students_cards.get_students_fees import get_students_fee_api_bp
from .fees.fee_actions import transaction_action_api_bp
from .fees.get_fee import get_fee_api_bp
from .fees.get_transactions import get_transactions_api_bp
from .fees.setup_fee_session_data.get_fee_session_setup_data import get_fee_session_setup_data_api_bp
from .fees.setup_fee_session_data.save_fee_session_setup import save_fee_session_setup_api_bp


from .marks.fill_marks.fill_marks import fill_marks_bp
from .marks.show_marks.show_marks import show_marks_bp
from .marks.bulk_markheet_certificate import bulk_markheet_certificate_bp

from .staff_module.show_staff.show_staff import show_staff_bp
from .staff_module.add_staff.add_staff import add_staff_bp
from .staff_module.edit_staff.update_staff import update_staff_bp
from .staff_module.edit_staff.update_staff_api import update_staff_api_bp
from .staff_module.add_staff.add_staff_api import add_staff_api_bp
from .staff_module.utils.get_role_permission import get_role_permissions_bp

from .idcard.idcard import idcard_bp

from .sessions.change_session import change_session_bp
from .RTE.RTE_students import RTE_students_bp

from .promotion_and_tc.get_students_by_class import get_students_by_class_api_bp

from .promotion_and_tc.get_promoted_student import get_promoted_student_data_api_bp

from .promotion_and_tc.promote.promote_student import promote_student_api_bp
from .promotion_and_tc.promote.get_student_promotion_data import get_student_promotion_data_api_bp
from .promotion_and_tc.promote.utils.promoted_message import generate_promoted_message_api_bp

from .promotion_and_tc.update_promoted.update_promoted import update_promoted_api_bp
from .promotion_and_tc.depromote.depromote_student import depromote_student_api_bp

from .promotion_and_tc.issue_tc.utils.next_tc_number import next_tc_number_api_bp
from .promotion_and_tc.issue_tc.utils.tc_html import get_tc_html_api_bp
from .promotion_and_tc.issue_tc.get_issue_tc_student import get_issue_tc_student_data_api_bp
from .promotion_and_tc.issue_tc.issue_or_restore_tc import issue_or_restore_tc_api_bp

from .promotion_and_tc.cancel_tc.cancel_tc import cancel_tc_api_bp

from .students.add_student.admission import admission_bp
from .students.utils.pydantic_verification_api import pydantic_verification_api_bp
from .students.add_student.final_admission_api import final_admission_api_bp
from .students.add_student.bulk_admission_api import bulk_admission_bp

from .students.update.final_student_update_api import final_update_student_api_bp
from .students.update.update_student import update_student_bp

from .students.utils.create_watsapp_message_api import create_watsapp_message_api_bp
from .students.utils.create_admission_form_api import create_admission_form_api_bp


from .utils.get_classes import get_classes_bp
from .utils.get_available_rolls import get_available_rolls_api_bp

from .question_paper.question_paper_PDF_api import question_paper_PDF_api_bp
from .question_paper.question_papers_dashboard import question_papers_dashboard_bp
from .question_paper.question_papers_editor import question_papers_editor_bp
from .tools.exam_seat_chits import get_seat_chits_bp

def register_blueprints(app):
    app.register_blueprint(login_bp)
    app.register_blueprint(logout_bp)
    app.register_blueprint(change_session_bp)

    app.register_blueprint(home_bp)
    app.register_blueprint(student_list_bp)
    app.register_blueprint(student_modal_data_api_bp)
    app.register_blueprint(get_students_data_api_bp)
    app.register_blueprint(get_students_pdf_api_bp)
    app.register_blueprint(get_admit_cards_api_bp)
    

    app.register_blueprint(final_update_student_api_bp)
    app.register_blueprint(update_student_bp)

    app.register_blueprint(get_attendance_data_api_bp)
    app.register_blueprint(mark_attendance_api_bp)
    app.register_blueprint(holiday_manager_api_bp)
    app.register_blueprint(get_message_api_bp)
    app.register_blueprint(get_overall_attendance_data_api_bp)
    app.register_blueprint(update_overall_attendance_api_bp)
    
    app.register_blueprint(get_students_fee_api_bp)
    app.register_blueprint(get_fee_api_bp)
    app.register_blueprint(get_transactions_api_bp)
    app.register_blueprint(transaction_action_api_bp)
    app.register_blueprint(get_fee_session_setup_data_api_bp)
    app.register_blueprint(save_fee_session_setup_api_bp)
    
    

    app.register_blueprint(admission_bp)
    app.register_blueprint(pydantic_verification_api_bp)
    app.register_blueprint(final_admission_api_bp)
    app.register_blueprint(bulk_admission_bp)

    app.register_blueprint(create_watsapp_message_api_bp)
    app.register_blueprint(create_admission_form_api_bp)

    app.register_blueprint(fill_marks_bp)
    app.register_blueprint(show_marks_bp)
    app.register_blueprint(bulk_markheet_certificate_bp)

    app.register_blueprint(show_staff_bp)
    app.register_blueprint(add_staff_api_bp)
    app.register_blueprint(add_staff_bp)
    app.register_blueprint(update_staff_api_bp)
    app.register_blueprint(update_staff_bp)
    app.register_blueprint(get_role_permissions_bp)

    app.register_blueprint(idcard_bp)

    app.register_blueprint(get_students_by_class_api_bp)

    app.register_blueprint(get_promoted_student_data_api_bp)

    app.register_blueprint(promote_student_api_bp)
    app.register_blueprint(get_student_promotion_data_api_bp)
    
    app.register_blueprint(update_promoted_api_bp)
    app.register_blueprint(depromote_student_api_bp)
    
    app.register_blueprint(generate_promoted_message_api_bp)

    app.register_blueprint(get_tc_html_api_bp)
    app.register_blueprint(get_issue_tc_student_data_api_bp)
    app.register_blueprint(cancel_tc_api_bp)
    app.register_blueprint(next_tc_number_api_bp)
    app.register_blueprint(issue_or_restore_tc_api_bp)

    app.register_blueprint(question_paper_PDF_api_bp)
    app.register_blueprint(question_papers_dashboard_bp)
    app.register_blueprint(question_papers_editor_bp)
    app.register_blueprint(get_seat_chits_bp)


    app.register_blueprint(get_classes_bp)
    app.register_blueprint(get_available_rolls_api_bp)

    app.register_blueprint(RTE_students_bp)
