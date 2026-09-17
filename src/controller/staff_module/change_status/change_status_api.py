from flask import Blueprint, jsonify, request, session

from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model import Roles
from src.model.TeachersLogin import TeachersLogin
from src import db, r


change_status_api_bp = Blueprint( 'change_status_api_bp', __name__ )

@change_status_api_bp.route('/api/delete_staff_api', methods=['POST'])
@login_required
@permission_required('delete_staff')
def delete_staff_api():
    data = request.form
    staff_id = data.get('staff_id')

    school_id = session.get('school_id')

    if not staff_id:
        return jsonify({'error': 'Staff ID is required'}), 400

    try:
        staff_id = int(staff_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid Staff ID'}), 400

    staff_data = (
        db.session.query(TeachersLogin, Roles.role_name, Roles.is_deletable)
        .join(Roles, TeachersLogin.role_id == Roles.id)
        .filter(
            TeachersLogin.id == staff_id,
            TeachersLogin.school_id == school_id
        )
        .first()
    )
    staff, role_name, is_deletable = staff_data

    if not staff:
        return jsonify({'error': 'Staff not found'}), 404

    if is_deletable is False:
        return jsonify({
            'error': f'Unable to delete staff with the role "{role_name}".'
        }), 400

    try:
        staff.status = 'deleted'

        # Remove Redis data
        r.delete(staff.id)

        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Error occurred while deleting staff! Please contact support.'
        }), 500

    return jsonify({
        'message': 'Staff deleted successfully',
        'staff_id': staff.id
    }), 200




@change_status_api_bp.route('/api/revoke_deleted_staff_api', methods=['POST'])
@login_required
@permission_required('delete_staff')
def revoke_deleted_staff_api():
    data = request.form
    staff_id = data.get('staff_id')

    school_id = session.get('school_id')

    if not staff_id:
        return jsonify({'error': 'Staff ID is required'}), 400

    try:
        staff_id = int(staff_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid Staff ID'}), 400

    staff = TeachersLogin.query.filter_by(
        id=staff_id, school_id=school_id
    ).first()

    if not staff:
        return jsonify({'error': 'Staff not found'}), 404

    if staff.status != 'deleted':
        return jsonify({'error': 'Staff is not deleted, unable to restore!'}), 400

    try:
        staff.status = 'active'
        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Error occurred while restoring staff! Please contact support.'
        }), 500

    return jsonify({
        'message': 'Staff restored successfully',
        'staff_id': staff.id
    }), 200

