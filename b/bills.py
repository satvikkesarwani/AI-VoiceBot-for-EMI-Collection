from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Bill, Payment
from datetime import datetime
from models import db, Bill, Payment, LoanDetails
import logging



# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bills_bp = Blueprint('bills', __name__)

@bills_bp.route('', methods=['GET'])
@jwt_required()
def get_bills():
    user_id = get_jwt_identity()
    logger.info(f"[GET BILLS] Request from user_id: {user_id}")
    
    bills = Bill.query.filter_by(user_id=user_id).all()
    logger.debug(f"[GET BILLS] Found {len(bills)} bills for user {user_id}")
    
    bills_data = []
    for bill in bills:
        logger.debug(f"[GET BILLS] Processing bill: {bill.id} - {bill.name}")
        logger.debug(f"[GET BILLS] Bill details - Amount: {bill.amount}, Due: {bill.due_date}, Paid: {bill.is_paid}")
        
        bill_dict = {
            'id': bill.id,
            'name': bill.name,
            'account_name': bill.account_name, 
            'amount': bill.amount,
            'due_date': bill.due_date.isoformat(),
            'category': bill.category,
            'frequency': bill.frequency,
            'is_paid': bill.is_paid,
            'notes': bill.notes,
            'created_at': bill.created_at.isoformat(),
            'reminder_preferences': {
                'enable_whatsapp': bill.enable_whatsapp,
                'enable_call': bill.enable_call,
                'enable_sms': bill.enable_sms,
                'enable_local_notification': bill.enable_local_notification
            }
        }
        bills_data.append(bill_dict)
        
        logger.debug(f"[GET BILLS] Bill {bill.id} reminder prefs - WhatsApp: {bill.enable_whatsapp}, Call: {bill.enable_call}")
    
    logger.info(f"[GET BILLS] Returning {len(bills_data)} bills for user {user_id}")
    return jsonify(bills_data), 200

@bills_bp.route('', methods=['POST'])
@jwt_required()
def create_bill():
    user_id = get_jwt_identity()
    data = request.get_json()

    # --- Unified Validation ---
    required = ['name', 'amount', 'due_date', 'account_name', 'loan_details']
    if any(field not in data for field in required):
        return jsonify({'message': 'Missing required bill or loan fields'}), 400

    loan_details_data = data['loan_details']
    required_loan = ['total_amount', 'monthly_payment', 'total_installments']
    if any(field not in loan_details_data for field in required_loan):
        return jsonify({'message': 'Missing required loan detail fields'}), 400

    try:
        # --- Atomic Database Transaction ---
        # 1. Create the Bill object
        new_bill = Bill(
            user_id=user_id,
            account_name=data['account_name'],
            name=data['name'],
            amount=data['amount'],
            due_date=datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')),
            category='loan', # Always a loan
            frequency=data.get('frequency', 'monthly'),
            notes=data.get('notes')
        )
        db.session.add(new_bill)
        db.session.flush() # Flush to assign an ID to new_bill

        # 2. Create the LoanDetails object, linking it to the new bill
        new_loan_details = LoanDetails(
            bill_id=new_bill.id,
            total_amount=loan_details_data['total_amount'],
            monthly_payment=loan_details_data['monthly_payment'],
            total_installments=loan_details_data['total_installments'],
            installments_paid=loan_details_data.get('installments_paid', 0),
            interest_rate_percent=loan_details_data.get('interest_rate_percent', 0)
        )
        db.session.add(new_loan_details)

        # 3. Commit both objects to the database together
        db.session.commit()

        logger.info(f"Successfully created bill {new_bill.id} and loan details {new_loan_details.id}")

        return jsonify({'id': new_bill.id, 'message': 'Bill and loan details created successfully'}), 201

    except Exception as e:
        db.session.rollback() # Important: Roll back transaction on error
        logger.error(f"[CREATE BILL/LOAN ERROR] Failed to save: {str(e)}", exc_info=True)
        return jsonify({'message': 'Failed to create bill and loan details'}), 500

@bills_bp.route('/<bill_id>', methods=['PUT'])
@jwt_required()
def update_bill(bill_id):
    user_id = get_jwt_identity()
    logger.info(f"[UPDATE BILL] Request from user_id: {user_id} for bill_id: {bill_id}")
    
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    
    if not bill:
        logger.warning(f"[UPDATE BILL] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    logger.debug(f"[UPDATE BILL] Found bill: {bill.name}")
    
    data = request.get_json()
    logger.debug(f"[UPDATE BILL] Update data keys: {list(data.keys()) if data else 'No data'}")
    
    # Track updates
    updates = []
    
    # Update fields
    if 'name' in data:
        old_name = bill.name
        bill.name = data['name']
        updates.append(f"name: '{old_name}' -> '{bill.name}'")
    # Add this block to handle updates
    if 'account_name' in data:
        old_account_name = bill.account_name
        bill.account_name = data['account_name']
        updates.append(f"account_name: '{old_account_name}' -> '{bill.account_name}'")
        
    if 'amount' in data:
        old_amount = bill.amount
        bill.amount = data['amount']
        updates.append(f"amount: {old_amount} -> {bill.amount}")
        
    if 'due_date' in data:
        try:
            old_due_date = bill.due_date
            bill.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            updates.append(f"due_date: {old_due_date} -> {bill.due_date}")
        except Exception as e:
            logger.error(f"[UPDATE BILL ERROR] Failed to parse due date: {str(e)}")
            return jsonify({'message': 'Invalid due date format'}), 400
            
    if 'category' in data:
        old_category = bill.category
        bill.category = data['category']
        updates.append(f"category: '{old_category}' -> '{bill.category}'")
        
    if 'frequency' in data:
        old_frequency = bill.frequency
        bill.frequency = data['frequency']
        updates.append(f"frequency: '{old_frequency}' -> '{bill.frequency}'")
        
    if 'notes' in data:
        bill.notes = data['notes']
        updates.append("notes: updated")
    
    # Update reminder preferences
    if 'reminder_preferences' in data:
        prefs = data['reminder_preferences']
        logger.debug(f"[UPDATE BILL] Updating reminder preferences: {prefs}")
        
        reminder_updates = []
        
        if 'enable_whatsapp' in prefs:
            old_value = bill.enable_whatsapp
            bill.enable_whatsapp = prefs['enable_whatsapp']
            if old_value != bill.enable_whatsapp:
                reminder_updates.append(f"whatsapp: {old_value} -> {bill.enable_whatsapp}")
                
        if 'enable_call' in prefs:
            old_value = bill.enable_call
            bill.enable_call = prefs['enable_call']
            if old_value != bill.enable_call:
                reminder_updates.append(f"call: {old_value} -> {bill.enable_call}")
                
        if 'enable_sms' in prefs:
            old_value = bill.enable_sms
            bill.enable_sms = prefs['enable_sms']
            if old_value != bill.enable_sms:
                reminder_updates.append(f"sms: {old_value} -> {bill.enable_sms}")
                
        if 'enable_local_notification' in prefs:
            old_value = bill.enable_local_notification
            bill.enable_local_notification = prefs['enable_local_notification']
            if old_value != bill.enable_local_notification:
                reminder_updates.append(f"local: {old_value} -> {bill.enable_local_notification}")
        
        if reminder_updates:
            updates.append(f"reminders: {{{', '.join(reminder_updates)}}}")
    
    if updates:
        logger.info(f"[UPDATE BILL] Updating bill {bill_id}: {'; '.join(updates)}")
    else:
        logger.info(f"[UPDATE BILL] No changes for bill {bill_id}")
    
    try:
        db.session.commit()
        logger.info(f"[UPDATE BILL] Bill {bill_id} updated successfully")
    except Exception as e:
        logger.error(f"[UPDATE BILL ERROR] Failed to update bill {bill_id}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'message': 'Failed to update bill'}), 500
    
    response_data = {
        'id': bill.id,
        'name': bill.name,
        'amount': bill.amount,
        'due_date': bill.due_date.isoformat(),
        'category': bill.category,
        'frequency': bill.frequency,
        'is_paid': bill.is_paid,
        'notes': bill.notes,
        'created_at': bill.created_at.isoformat()
    }
    
    logger.debug(f"[UPDATE BILL] Returning updated bill data for {bill_id}")
    return jsonify(response_data), 200

@bills_bp.route('/<bill_id>', methods=['DELETE'])
@jwt_required()
def delete_bill(bill_id):
    user_id = get_jwt_identity()
    logger.info(f"[DELETE BILL] Request from user_id: {user_id} for bill_id: {bill_id}")
    
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    
    if not bill:
        logger.warning(f"[DELETE BILL] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    bill_name = bill.name
    bill_amount = bill.amount
    
    logger.info(f"[DELETE BILL] Deleting bill: {bill_name} (Amount: {bill_amount})")
    
    try:
        db.session.delete(bill)
        db.session.commit()
        logger.info(f"[DELETE BILL] Bill {bill_id} deleted successfully")
    except Exception as e:
        logger.error(f"[DELETE BILL ERROR] Failed to delete bill {bill_id}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'message': 'Failed to delete bill'}), 500
    
    return '', 204

@bills_bp.route('/<bill_id>/pay', methods=['POST'])
@jwt_required()
def mark_bill_paid(bill_id):
    user_id = get_jwt_identity()
    logger.info(f"[MARK PAID] Request from user_id: {user_id} for bill_id: {bill_id}")
    
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    
    if not bill:
        logger.warning(f"[MARK PAID] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    logger.debug(f"[MARK PAID] Bill details - Name: {bill.name}, Amount: {bill.amount}, Was paid: {bill.is_paid}")
    
    if bill.is_paid:
        logger.info(f"[MARK PAID] Bill {bill_id} is already marked as paid")
    
    bill.is_paid = True
    
    # Create payment record
    logger.debug(f"[MARK PAID] Creating payment record for bill {bill_id}")
    payment = Payment(
        bill_id=bill.id,
        amount=bill.amount,
        payment_method='manual'
    )
    
    try:
        db.session.add(payment)
        db.session.commit()
        logger.info(f"[MARK PAID] Bill {bill_id} marked as paid with payment ID: {payment.id}")
        logger.debug(f"[MARK PAID] Payment details - Amount: {payment.amount}, Method: {payment.payment_method}")
    except Exception as e:
        logger.error(f"[MARK PAID ERROR] Failed to mark bill {bill_id} as paid: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'message': 'Failed to mark bill as paid'}), 500
    
    return jsonify({'message': 'Bill marked as paid'}), 200