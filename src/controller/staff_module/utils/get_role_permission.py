
from flask import Blueprint, jsonify, render_template_string, request
from src.model import Permissions, RolePermissions

from src import db
from src.controller.auth.login_required import login_required
from src.controller.permissions.permission_required import permission_required
from src.model.Roles import Roles


get_role_permissions_bp = Blueprint( 'get_role_permissions_bp',   __name__)
@get_role_permissions_bp.route('/api/get_role_permissions/<int:role_id>', methods=['GET'])
@permission_required('add_staff')
@login_required
def get_role_permissions(role_id):
    # Match the front-end parameter name

    print(role_id)

    if not role_id:
        return jsonify({'error': 'Missing role_id parameter'}), 400

    # Query permissions
    permissions = (
        db.session.query(
            Permissions.id,
        )
        .join(RolePermissions, RolePermissions.permission_id == Permissions.id)
        .filter(RolePermissions.role_id == role_id, Permissions.assignable.is_(True))
        .all()
    )

    print([p.id for p in permissions])


    return jsonify({
        'message': 'Permissions retrieved successfully',
        'permissions_list': [p.id for p in permissions]
    }), 200

