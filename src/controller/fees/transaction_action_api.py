# src/controller/fees/transaction_action_api.py

from flask import session, request, jsonify, Blueprint
from sqlalchemy import and_

from src.model import FeeTransaction, FeeData
from src import db

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

transaction_action_api_bp = Blueprint('transaction_action_api_bp', __name__)


@transaction_action_api_bp.route('/api/delete_fee_transaction', methods=["POST"])
@login_required
@permission_required('pay_fees')
def delete_fee_transaction():
    """
    Soft delete a fee transaction (mark as deleted without removing from DB)
    Sets is_deleted = True to hide transaction from user view
    
    Expected JSON body:
        - transaction_id: ID of the transaction to delete
    
    Returns:
        JSON with success message and updated transaction data
    """
    data = request.get_json()
    
    if not data or not data.get("transaction_id"):
        return jsonify({"message": "transaction_id is required"}), 400
    
    try:
        school_id = session["school_id"]
        transaction_id = data.get("transaction_id")
        
        # Verify transaction exists and belongs to this school
        transaction = db.session.query(FeeTransaction).filter(
            and_(
                FeeTransaction.id == transaction_id,
                FeeTransaction.school_id == school_id
            )
        ).first()
        
        if not transaction:
            return jsonify({"message": "Transaction not found"}), 404
        
        # Check if already deleted
        if transaction.is_deleted is True:
            return jsonify({
                "message": "Transaction is already deleted",
                "transaction_id": transaction_id
            }), 400
        
        # Soft delete: Set is_deleted flag to True
        transaction.is_deleted = True
        db.session.commit()
        
        return jsonify({
            "message": "Transaction deleted successfully",
            "transaction_id": transaction_id,
            "is_deleted": True
        }), 200
        
    except Exception as e:
        print(f"Error deleting transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"message": f"Error deleting transaction: {str(e)}"}), 500


@transaction_action_api_bp.route('/api/restore_fee_transaction', methods=["POST"])
@login_required
@permission_required('pay_fees')
def restore_fee_transaction():
    """
    Restore a soft-deleted fee transaction
    Sets is_deleted = False to show transaction to user again
    
    Expected JSON body:
        - transaction_id: ID of the transaction to restore
    
    Returns:
        JSON with success message and updated transaction data
    """
    data = request.get_json()
    
    if not data or not data.get("transaction_id"):
        return jsonify({"error": "transaction_id is required"}), 400
    
    try:
        school_id = session["school_id"]
        transaction_id = data.get("transaction_id")
        
        # Verify transaction exists and belongs to this school
        transaction = db.session.query(FeeTransaction).filter(
            and_(
                FeeTransaction.id == transaction_id,
                FeeTransaction.school_id == school_id
            )
        ).first()
        
        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404
        
        # Check if not deleted
        if transaction.is_deleted is not True:
            return jsonify({
                "error": "Transaction is not deleted",
                "transaction_id": transaction_id
            }), 400
        
        # Soft restore: Set is_deleted flag to False
        transaction.is_deleted = False
        db.session.commit()
        
        return jsonify({
            "message": "Transaction restored successfully",
            "transaction_id": transaction_id,
            "is_deleted": False
        }), 200
        
    except Exception as e:
        print(f"Error restoring transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"Error restoring transaction: {str(e)}"}), 500
