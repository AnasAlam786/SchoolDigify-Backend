# src/controller/pay_fee.py

from flask import render_template, session, url_for, redirect, request, jsonify, Blueprint


from src.model import StudentsDB, StudentSessions, ClassData, TeachersLogin
from src.model.ClassAccess import ClassAccess
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

pay_fee_bp = Blueprint( 'pay_fee_bp',   __name__)


@pay_fee_bp.route('/pay_fee', methods=["GET"])
@login_required
def pay_fee():
    return render_template('fees.html')