from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from local_storage_service import (
    upload_receipt_to_local, 
    get_receipt_path, 
    get_receipt_url,
    delete_receipt_from_local
)
from models import db, Bill
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

receipts_bp = Blueprint('receipts', __name__)

@receipts_bp.route('/scan-receipt', methods=['POST'])
@jwt_required()
def scan_receipt():
    """Upload and process receipt using local storage"""
    user_id = get_jwt_identity()
    logger.info(f"[SCAN RECEIPT] Request from user_id: {user_id}")
    
    if 'receipt' not in request.files:
        logger.warning(f"[SCAN RECEIPT] No receipt file in request from user {user_id}")
        return jsonify({'message': 'No receipt file provided'}), 400
    
    file = request.files['receipt']
    logger.debug(f"[SCAN RECEIPT] File received: {file.filename}")
    logger.debug(f"[SCAN RECEIPT] File content type: {file.content_type}")
    
    if file.filename == '':
        logger.warning(f"[SCAN RECEIPT] Empty filename from user {user_id}")
        return jsonify({'message': 'No file selected'}), 400
    
    # Upload to local storage
    logger.info(f"[SCAN RECEIPT] Uploading file '{file.filename}' to local storage")
    result = upload_receipt_to_local(file, user_id)
    logger.debug(f"[SCAN RECEIPT] Upload result: {result}")
    
    if not result['success']:
        logger.error(f"[SCAN RECEIPT] Failed to upload receipt: {result.get('error')}")
        return jsonify({'message': 'Failed to upload receipt', 'error': result.get('error')}), 500
    
    logger.info(f"[SCAN RECEIPT] Successfully uploaded as: {result['filename']}")
    logger.debug(f"[SCAN RECEIPT] File URL: {result['url']}")
    
    # Mock OCR processing (in real app, you'd use Tesseract OCR or similar)
    # For now, return a sample bill structure
    mock_bill_data = {
        'id': None,
        'name': 'Scanned Bill',
        'amount': 0.0,
        'due_date': None,
        'category': 'other',
        'frequency': 'once',
        'is_paid': False,
        'notes': f"Receipt uploaded: {result['filename']}",
        'receipt_url': result['url']
    }
    
    logger.info(f"[SCAN RECEIPT] Returning mock bill data for user {user_id}")
    logger.debug(f"[SCAN RECEIPT] Mock bill data: {mock_bill_data}")
    
    return jsonify(mock_bill_data), 200

@receipts_bp.route('/<bill_id>/receipt', methods=['POST'])
@jwt_required()
def upload_bill_receipt(bill_id):
    """Upload receipt for existing bill"""
    user_id = get_jwt_identity()
    logger.info(f"[UPLOAD RECEIPT] Request from user_id: {user_id} for bill_id: {bill_id}")
    
    # Verify bill ownership
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    logger.debug(f"[UPLOAD RECEIPT] Bill found: {bill is not None}")
    
    if not bill:
        logger.warning(f"[UPLOAD RECEIPT] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    logger.debug(f"[UPLOAD RECEIPT] Bill details - Name: {bill.name}, Amount: {bill.amount}")
    
    if 'receipt' not in request.files:
        logger.warning(f"[UPLOAD RECEIPT] No receipt file in request")
        return jsonify({'message': 'No receipt file provided'}), 400
    
    file = request.files['receipt']
    logger.debug(f"[UPLOAD RECEIPT] File received: {file.filename}")
    logger.debug(f"[UPLOAD RECEIPT] File content type: {file.content_type}")
    
    if file.filename == '':
        logger.warning(f"[UPLOAD RECEIPT] Empty filename")
        return jsonify({'message': 'No file selected'}), 400
    
    # Upload to local storage
    logger.info(f"[UPLOAD RECEIPT] Uploading file '{file.filename}' for bill {bill_id}")
    result = upload_receipt_to_local(file, user_id)
    logger.debug(f"[UPLOAD RECEIPT] Upload result: {result}")
    
    if not result['success']:
        logger.error(f"[UPLOAD RECEIPT] Failed to upload receipt: {result.get('error')}")
        return jsonify({'message': 'Failed to upload receipt'}), 500
    
    logger.info(f"[UPLOAD RECEIPT] Successfully uploaded as: {result['filename']}")
    
    # Update bill notes with receipt info
    notes_data = {}
    if bill.notes:
        logger.debug(f"[UPLOAD RECEIPT] Existing notes: {bill.notes}")
        try:
            notes_data = json.loads(bill.notes)
            logger.debug(f"[UPLOAD RECEIPT] Parsed notes data: {notes_data}")
        except Exception as e:
            logger.warning(f"[UPLOAD RECEIPT] Failed to parse notes as JSON: {str(e)}")
            notes_data = {'original_notes': bill.notes}
    
    # Delete old receipt if exists
    old_receipt = notes_data.get('receipt_filename')
    if old_receipt:
        logger.info(f"[UPLOAD RECEIPT] Deleting old receipt: {old_receipt}")
        delete_result = delete_receipt_from_local(old_receipt)
        logger.debug(f"[UPLOAD RECEIPT] Old receipt deletion result: {delete_result}")
    
    notes_data['receipt_filename'] = result['filename']
    bill.notes = json.dumps(notes_data)
    logger.debug(f"[UPLOAD RECEIPT] Updated notes: {bill.notes}")
    
    try:
        db.session.commit()
        logger.info(f"[UPLOAD RECEIPT] Successfully updated bill {bill_id} with receipt")
    except Exception as e:
        logger.error(f"[UPLOAD RECEIPT ERROR] Failed to commit changes: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'message': 'Failed to update bill'}), 500
    
    return jsonify({
        'message': 'Receipt uploaded successfully',
        'receipt_url': result['url']
    }), 200

@receipts_bp.route('/<bill_id>/receipt', methods=['GET'])
@jwt_required()
def get_bill_receipt(bill_id):
    """Get receipt URL for a bill"""
    user_id = get_jwt_identity()
    logger.info(f"[GET RECEIPT] Request from user_id: {user_id} for bill_id: {bill_id}")
    
    # Verify bill ownership
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    logger.debug(f"[GET RECEIPT] Bill found: {bill is not None}")
    
    if not bill:
        logger.warning(f"[GET RECEIPT] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    # Get receipt filename from notes
    try:
        logger.debug(f"[GET RECEIPT] Bill notes: {bill.notes}")
        notes_data = json.loads(bill.notes or '{}')
        receipt_filename = notes_data.get('receipt_filename')
        logger.debug(f"[GET RECEIPT] Receipt filename from notes: {receipt_filename}")
        
        if not receipt_filename:
            logger.info(f"[GET RECEIPT] No receipt filename in notes for bill {bill_id}")
            return jsonify({'message': 'No receipt found for this bill'}), 404
        
        # Get URL
        logger.info(f"[GET RECEIPT] Getting URL for receipt: {receipt_filename}")
        result = get_receipt_url(receipt_filename)
        logger.debug(f"[GET RECEIPT] URL result: {result}")
        
        if result['success']:
            logger.info(f"[GET RECEIPT] Successfully retrieved receipt URL for bill {bill_id}")
            return jsonify({'receipt_url': result['url']}), 200
        else:
            logger.error(f"[GET RECEIPT] Failed to get receipt URL: {result.get('error')}")
            return jsonify({'message': 'Failed to get receipt URL'}), 500
            
    except Exception as e:
        logger.error(f"[GET RECEIPT ERROR] Error processing receipt: {str(e)}", exc_info=True)
        return jsonify({'message': 'No receipt found for this bill'}), 404

@receipts_bp.route('/<bill_id>/receipt', methods=['DELETE'])
@jwt_required()
def delete_bill_receipt(bill_id):
    """Delete receipt for a bill"""
    user_id = get_jwt_identity()
    logger.info(f"[DELETE RECEIPT] Request from user_id: {user_id} for bill_id: {bill_id}")
    
    # Verify bill ownership
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    logger.debug(f"[DELETE RECEIPT] Bill found: {bill is not None}")
    
    if not bill:
        logger.warning(f"[DELETE RECEIPT] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    # Get receipt filename from notes
    try:
        logger.debug(f"[DELETE RECEIPT] Bill notes: {bill.notes}")
        notes_data = json.loads(bill.notes or '{}')
        receipt_filename = notes_data.get('receipt_filename')
        logger.debug(f"[DELETE RECEIPT] Receipt filename from notes: {receipt_filename}")
        
        if not receipt_filename:
            logger.info(f"[DELETE RECEIPT] No receipt filename in notes for bill {bill_id}")
            return jsonify({'message': 'No receipt found for this bill'}), 404
        
        # Delete file
        logger.info(f"[DELETE RECEIPT] Deleting receipt file: {receipt_filename}")
        result = delete_receipt_from_local(receipt_filename)
        logger.debug(f"[DELETE RECEIPT] Deletion result: {result}")
        
        if result['success']:
            # Update bill notes
            del notes_data['receipt_filename']
            bill.notes = json.dumps(notes_data) if notes_data else None
            logger.debug(f"[DELETE RECEIPT] Updated notes after deletion: {bill.notes}")
            
            try:
                db.session.commit()
                logger.info(f"[DELETE RECEIPT] Successfully deleted receipt for bill {bill_id}")
            except Exception as e:
                logger.error(f"[DELETE RECEIPT ERROR] Failed to commit changes: {str(e)}", exc_info=True)
                db.session.rollback()
                return jsonify({'message': 'Failed to update bill'}), 500
            
            return jsonify({'message': 'Receipt deleted successfully'}), 200
        else:
            logger.error(f"[DELETE RECEIPT] Failed to delete receipt file: {result.get('error')}")
            return jsonify({'message': 'Failed to delete receipt'}), 500
            
    except Exception as e:
        logger.error(f"[DELETE RECEIPT ERROR] Error processing request: {str(e)}", exc_info=True)
        return jsonify({'message': 'Error processing request'}), 500

@receipts_bp.route('/view/<user_id>/<filename>', methods=['GET'])
@jwt_required()
def view_receipt(user_id, filename):
    """Serve receipt file"""
    current_user_id = get_jwt_identity()
    logger.info(f"[VIEW RECEIPT] Request from user_id: {current_user_id} to view {user_id}/{filename}")
    
    # Security check - users can only view their own receipts
    if current_user_id != user_id:
        logger.warning(f"[VIEW RECEIPT] Unauthorized access attempt - user {current_user_id} trying to access {user_id}'s receipt")
        return jsonify({'message': 'Unauthorized'}), 403
    
    # Get file path
    full_filename = f"{user_id}/{filename}"
    logger.info(f"[VIEW RECEIPT] Getting path for file: {full_filename}")
    result = get_receipt_path(full_filename)
    logger.debug(f"[VIEW RECEIPT] Path result: {result}")
    
    if result['success']:
        file_path = result['path']
        logger.info(f"[VIEW RECEIPT] File found at: {file_path}")
        
        # Determine file type
        file_extension = filename.rsplit('.', 1)[1].lower()
        logger.debug(f"[VIEW RECEIPT] File extension: {file_extension}")
        
        if file_extension in ['jpg', 'jpeg']:
            mimetype = 'image/jpeg'
        elif file_extension == 'png':
            mimetype = 'image/png'
        elif file_extension == 'pdf':
            mimetype = 'application/pdf'
        else:
            mimetype = 'application/octet-stream'
        
        logger.info(f"[VIEW RECEIPT] Serving file with mimetype: {mimetype}")
        
        try:
            return send_file(file_path, mimetype=mimetype)
        except Exception as e:
            logger.error(f"[VIEW RECEIPT ERROR] Failed to send file: {str(e)}", exc_info=True)
            return jsonify({'message': 'Error serving file'}), 500
    else:
        logger.warning(f"[VIEW RECEIPT] File not found: {full_filename}")
        return jsonify({'message': 'File not found'}), 404