# src/controller/__init__.py

from .auth.login import login_bp
from .auth.logout import logout_bp

from .home import home_bp
from .students_list.student_list import student_list_bp
from .students_list.student_modal_data_api import student_modal_data_api_bp
from .students_list.get_students_data_api import get_students_data_api_bp
from .students_list.get_students_pdf_api import get_students_pdf_api_bp
from .students_list.get_admit_cards_api import get_admit_cards_api_bp
from .students_list.admit_card_view import admit_card_view_bp




from .attendance.attendance import attendance_bp
from .attendance.get_attendance_data_api import get_attendance_data_api_bp
from .attendance.mark_attendance_api import mark_attendance_api_bp
from .attendance.add_holiday_api import add_holiday_api_bp
from .attendance.messages_api import get_message_api_bp


from .fees.pay_fee_api import pay_fee_api_bp
from .fees.get_fee_api import get_fee_api_bp
from .fees.get_transactions_api import get_transactions_api_bp
from .fees.transaction_action_api import transaction_action_api_bp
from .fees.demand_fee_message_api import demand_fee_message_bp
from .fees.transaction_watsapp_message_api import transaction_whatsapp_message_bp

from .marks.fill_marks import fill_marks_bp
from .marks.update_marks_api import update_marks_api_bp
from .marks.show_marks import show_marks_bp
from .marks.get_marks_api import get_marks_api_bp
from .marks.get_result_api import get_result_api_bp
from .marks.bulk_download_results import bulk_download_results_bp

from .staff_module.show_staff import show_staff_bp
from .staff_module.add_staff import add_staff_bp
from .staff_module.update_staff import update_staff_bp
from .staff_module.update_staff_api import update_staff_api_bp
from .staff_module.add_staff_api import add_staff_api_bp
from .staff_module.utils.get_role_permission import get_role_permissions_bp

from .idcard.idcard import idcard_bp

from .sessions.change_session import change_session_bp
from .RTE.RTE_students import RTE_students_bp

from .promote.promote_student import promote_student_bp
from .promote.get_students_by_class_api import get_students_by_class_api_bp
from .promote.get_promotion_student_data_api import get_student_promotion_data_api_bp
from .promote.get_promoted_student_data_api import get_promoted_student_data_api_bp

from .promote.promote_student_api import promote_student_api_bp
from .promote.update_promotion_api import update_promotion_api_bp
from .promote.depromote_student_api import depromote_student_api_bp
from .promote.promotion_message_api import generate_promotion_message_api_bp
from .promote.get_available_rolls_for_class_api import get_available_rolls_for_class_api_bp

from .tc.generate_tc_form_api import generate_and_save_tc_api_bp
from .tc.redo_tc_api import revert_tc_api_bp
from .tc.reprint_tc_api import reprint_tc_api_bp

from .students.add_student.admission import admission_bp
from .students.utils.pydantic_verification_api import pydantic_verification_api_bp
from .students.utils.get_new_roll_api import get_new_roll_api_bp
from .students.add_student.final_admission_api import final_admission_api_bp

from .students.update.final_student_update_api import final_update_student_api_bp
from .students.update.update_student import update_student_bp

from .students.utils.create_watsapp_message_api import create_watsapp_message_api_bp
from .students.utils.create_admission_form_api import create_admission_form_api_bp


from .temp.temp_page import temp_page_bp
from .temp.fill_colums_api import fill_colums_api_bp

from .tools.question_paper_PDF_api import question_paper_PDF_api_bp
from .tools.question_papers_dashboard import question_papers_dashboard_bp
from .tools.question_papers_editor import question_papers_editor_bp
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
    app.register_blueprint(admit_card_view_bp)
    

    app.register_blueprint(final_update_student_api_bp)
    app.register_blueprint(update_student_bp)

    app.register_blueprint(attendance_bp)
    app.register_blueprint(get_attendance_data_api_bp)
    app.register_blueprint(mark_attendance_api_bp)
    app.register_blueprint(add_holiday_api_bp)
    app.register_blueprint(get_message_api_bp)
    
    app.register_blueprint(pay_fee_api_bp)
    app.register_blueprint(get_fee_api_bp)
    app.register_blueprint(get_transactions_api_bp)
    app.register_blueprint(transaction_action_api_bp)
    app.register_blueprint(demand_fee_message_bp)
    app.register_blueprint(transaction_whatsapp_message_bp)

    app.register_blueprint(admission_bp)
    app.register_blueprint(pydantic_verification_api_bp)
    app.register_blueprint(get_new_roll_api_bp)
    app.register_blueprint(final_admission_api_bp)

    app.register_blueprint(create_watsapp_message_api_bp)
    app.register_blueprint(create_admission_form_api_bp)

    app.register_blueprint(fill_marks_bp)
    app.register_blueprint(update_marks_api_bp)
    app.register_blueprint(show_marks_bp)
    app.register_blueprint(get_marks_api_bp)
    app.register_blueprint(get_result_api_bp)
    app.register_blueprint(bulk_download_results_bp)

    app.register_blueprint(show_staff_bp)
    app.register_blueprint(add_staff_api_bp)
    app.register_blueprint(add_staff_bp)
    app.register_blueprint(update_staff_api_bp)
    app.register_blueprint(update_staff_bp)
    app.register_blueprint(get_role_permissions_bp)

    app.register_blueprint(idcard_bp)

    app.register_blueprint(promote_student_bp)
    app.register_blueprint(get_students_by_class_api_bp)
    app.register_blueprint(get_student_promotion_data_api_bp)
    app.register_blueprint(get_promoted_student_data_api_bp)

    app.register_blueprint(promote_student_api_bp)
    app.register_blueprint(update_promotion_api_bp)
    app.register_blueprint(depromote_student_api_bp)
    app.register_blueprint(generate_promotion_message_api_bp)
    app.register_blueprint(get_available_rolls_for_class_api_bp)

    app.register_blueprint(generate_and_save_tc_api_bp)
    app.register_blueprint(revert_tc_api_bp)
    app.register_blueprint(reprint_tc_api_bp)

    app.register_blueprint(question_paper_PDF_api_bp)
    app.register_blueprint(question_papers_dashboard_bp)
    app.register_blueprint(question_papers_editor_bp)
    app.register_blueprint(get_seat_chits_bp)


    app.register_blueprint(temp_page_bp)
    app.register_blueprint(fill_colums_api_bp)


    app.register_blueprint(RTE_students_bp)
