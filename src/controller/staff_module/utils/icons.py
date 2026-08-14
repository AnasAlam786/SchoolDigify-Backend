permission_icons = {
    # --- Student Management ---
    "student_list": "fas fa-users",  # 👥 list of students
    "student_details": "fas fa-info-circle",  # ℹ️ detailed info
    "admission": "fas fa-user-plus",  # ➕ add student
    "update_student": "fas fa-user-edit",  # ✏️ edit student info
    "delete_student": "fas fa-user-minus",  # ❌ delete student record
    "promote_student": "fas fa-user-graduate",  # 🎓 academic promotion
    "export_student_data": "fas fa-file-excel",  # 📊 export data / reports
    "students_stats": "fas fa-chart-pie",  # 📈 analytics & stats
    "tc": "fas fa-file-export",  # 📤 transfer certificate
    "idcard": "fas fa-id-card",  # 🪪 identity cards
    
    # --- Staff Management ---
    "show_staff": "fas fa-users-cog",  # 👥 list/view staff members
    "add_staff": "fas fa-user-plus",  # ➕ add new staff
    "edit_staff": "fas fa-user-edit",  # ✏️ edit staff record
    "update_staff": "fas fa-user-tie",  # 👔 update staff details
    "delete_staff": "fas fa-user-slash",  # 🚫 remove/deactivate staff
    
    # --- Examination & Marks ---
    "show_marks": "fas fa-eye",  # 👁️ view-only marks
    "fill_marks": "fas fa-pen",  # 🖋️ input/edit marks
    "lock_marks": "fas fa-lock",  # 🔒 finalize / lock marks entry
    "override_marks_lock": "fas fa-unlock-alt",  # 🔓 override locked marks
    "create_paper": "fas fa-file-alt",  # 📄 paper creation
    "view_all_papers": "fas fa-folder-open",  # 📁 view test/exam papers
    "get_result": "fas fa-file-signature",  # 🧾 report cards / results
    "admit_card": "fas fa-file-invoice",  # 📘 admit cards & exam scheme
    
    # --- Attendance & Calendar ---
    "attendance": "fas fa-clipboard-user",  # 📋 mark/view attendance
    "overall_attendance": "fas fa-chart-bar",  # 📊 overall attendance reports
    "mark_any_day_attendance": "fas fa-calendar-check",  # 📅 backdated attendance
    "view_holidays": "fas fa-umbrella-beach",  # 🏖️ view holiday list
    "mark_holiday": "fas fa-calendar-minus",  # 🗓️ declare/mark holiday
    "change_session": "fas fa-calendar-alt",  # 📅 change academic session
    
    # --- Finance & Fees ---
    "pay_fees": "fas fa-rupee-sign",  # 💰 fee payments
    "view_fee_data": "fas fa-wallet",  # 👛 view fee structures & reports
    
    # --- System & Access Control ---
    "control_access": "fas fa-user-shield",  # 🛡️ manage roles & permissions
}

ROLE_ICONS = {
    "Manager":        {"icon": "fa-solid fa-crown",               "color": "text-yellow-500"},
    "Principal":      {"icon": "fa-solid fa-user-tie",            "color": "text-blue-600"},
    "Vice Principal": {"icon": "fa-solid fa-user-graduate",       "color": "text-violet-600"},
    "Admin":          {"icon": "fa-solid fa-user-shield",         "color": "text-purple-600"},
    "Teacher":        {"icon": "fa-solid fa-chalkboard-teacher",  "color": "text-green-600"},
    "Support Staff":  {"icon": "fa-solid fa-people-carry-box",    "color": "text-orange-500"},
    "Clerk":          {"icon": "fa-solid fa-file-pen",            "color": "text-sky-500"},
    "Reception":      {"icon": "fa-solid fa-phone-volume",        "color": "text-pink-500"},
    "Accountant":     {"icon": "fa-solid fa-file-invoice-dollar", "color": "text-amber-500"}
}
