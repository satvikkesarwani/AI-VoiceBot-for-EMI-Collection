# loans.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, LoanDetails, Bill
import logging
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

loans_bp = Blueprint('loans', __name__)

@loans_bp.route('/loans', methods=['GET'])
@jwt_required()
def get_loans():
    """Get all active loan details for the authenticated user."""
    user_id = get_jwt_identity()
    logger.info(f"[LOANS GET] Request to get loans for user_id: {user_id}")

    try:
        loans = db.session.query(Bill, LoanDetails).join(
            LoanDetails, Bill.id == LoanDetails.bill_id
        ).filter(Bill.user_id == user_id, LoanDetails.is_active == True).all()

        loans_data = []
        for bill, loan in loans:
            loans_data.append({
                'bill_id': bill.id,
                'bill_name': bill.name,
                'total_amount': loan.total_amount,
                'monthly_payment': loan.monthly_payment,
                'total_installments': loan.total_installments,
                'installments_paid': loan.installments_paid,
                'interest_rate_percent': loan.interest_rate_percent,
                'amount_remaining': loan.amount_remaining,
                'is_active': loan.is_active
            })

        logger.info(f"[LOANS GET] Found {len(loans_data)} active loans for user {user_id}")
        return jsonify(loans_data), 200

    except Exception as e:
        logger.error(f"[LOANS GET ERROR] Failed to fetch loans for user {user_id}: {str(e)}", exc_info=True)
        return jsonify({'message': 'Failed to fetch loan data'}), 500


@loans_bp.route('/loans/<loan_id>/pay', methods=['POST'])
@jwt_required()
def pay_loan_installment(loan_id):
    """Increments the installments paid for a specific loan."""
    user_id = get_jwt_identity()
    logger.info(f"[LOANS PAY] Request to mark installment paid for loan: {loan_id} by user: {user_id}")

    loan = LoanDetails.query.get(loan_id)
    if not loan or loan.bill.user_id != user_id:
        return jsonify({'message': 'Loan not found or access denied'}), 404
    
    if loan.installments_paid >= loan.total_installments:
        return jsonify({'message': 'Loan is already fully paid'}), 400

    loan.installments_paid += 1
    
    try:
        db.session.commit()
        logger.info(f"[LOANS PAY] Installment marked as paid for loan {loan_id}. Paid: {loan.installments_paid}/{loan.total_installments}")

        return jsonify({
            'message': 'Installment marked as paid successfully',
            'installments_paid': loan.installments_paid,
            'amount_remaining': loan.amount_remaining
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"[LOANS PAY ERROR] Failed to mark installment paid for loan {loan_id}: {str(e)}", exc_info=True)
        return jsonify({'message': 'Failed to update loan status'}), 500
