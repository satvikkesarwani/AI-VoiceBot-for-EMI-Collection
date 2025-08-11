from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, ReminderSettings, Bill
from reminder_service import generate_reminder_message, send_whatsapp_reminder, send_voice_call_reminder
from elevenlabs_service import generate_voice_audio
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

reminders_bp = Blueprint('reminders', __name__)

@reminders_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_reminder_settings():
    user_id = get_jwt_identity()
    logger.info(f"[GET SETTINGS] Request from user_id: {user_id}")
    
    settings = ReminderSettings.query.filter_by(user_id=user_id).first()
    logger.debug(f"[GET SETTINGS] Query result for user {user_id}: {settings}")
    
    if not settings:
        logger.info(f"[GET SETTINGS] No settings found for user {user_id}, creating defaults")
        # Create default settings
        settings = ReminderSettings(user_id=user_id)
        db.session.add(settings)
        try:
            db.session.commit()
            logger.info(f"[GET SETTINGS] Default settings created successfully for user {user_id}")
        except Exception as e:
            logger.error(f"[GET SETTINGS ERROR] Failed to create default settings for user {user_id}: {str(e)}")
            db.session.rollback()
            raise
    
    response_data = {
        'local_notifications': settings.local_notifications,
        'whatsapp_enabled': settings.whatsapp_enabled,
        'call_enabled': settings.call_enabled,
        'sms_enabled': settings.sms_enabled,
        'days_before': settings.days_before,
        'preferred_time': settings.preferred_time
    }
    
    logger.debug(f"[GET SETTINGS] Returning settings for user {user_id}: {response_data}")
    return jsonify(response_data), 200

@reminders_bp.route('/settings', methods=['PUT'])
@jwt_required()
def update_reminder_settings():
    user_id = get_jwt_identity()
    logger.info(f"[UPDATE SETTINGS] Request from user_id: {user_id}")
    
    settings = ReminderSettings.query.filter_by(user_id=user_id).first()
    logger.debug(f"[UPDATE SETTINGS] Current settings found: {settings is not None}")
    
    if not settings:
        logger.info(f"[UPDATE SETTINGS] Creating new settings for user {user_id}")
        settings = ReminderSettings(user_id=user_id)
        db.session.add(settings)
    
    data = request.get_json()
    logger.debug(f"[UPDATE SETTINGS] Received data: {data}")
    
    # Track what's being updated
    updates = []
    
    if 'local_notifications' in data:
        old_value = settings.local_notifications
        settings.local_notifications = data['local_notifications']
        updates.append(f"local_notifications: {old_value} -> {data['local_notifications']}")
        
    if 'whatsapp_enabled' in data:
        old_value = settings.whatsapp_enabled
        settings.whatsapp_enabled = data['whatsapp_enabled']
        updates.append(f"whatsapp_enabled: {old_value} -> {data['whatsapp_enabled']}")
        
    if 'call_enabled' in data:
        old_value = settings.call_enabled
        settings.call_enabled = data['call_enabled']
        updates.append(f"call_enabled: {old_value} -> {data['call_enabled']}")
        
    if 'sms_enabled' in data:
        old_value = settings.sms_enabled
        settings.sms_enabled = data['sms_enabled']
        updates.append(f"sms_enabled: {old_value} -> {data['sms_enabled']}")
        
    if 'days_before' in data:
        old_value = settings.days_before
        settings.days_before = data['days_before']
        updates.append(f"days_before: {old_value} -> {data['days_before']}")
        
    if 'preferred_time' in data:
        old_value = settings.preferred_time
        settings.preferred_time = data['preferred_time']
        updates.append(f"preferred_time: {old_value} -> {data['preferred_time']}")
    
    logger.info(f"[UPDATE SETTINGS] Updates for user {user_id}: {', '.join(updates) if updates else 'No changes'}")
    
    try:
        db.session.commit()
        logger.info(f"[UPDATE SETTINGS] Successfully updated settings for user {user_id}")
    except Exception as e:
        logger.error(f"[UPDATE SETTINGS ERROR] Failed to update settings for user {user_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'message': 'Failed to update settings', 'error': str(e)}), 500
    
    return jsonify({'message': 'Settings updated successfully'}), 200

@reminders_bp.route('/test', methods=['POST'])
@jwt_required()
def test_reminder():
    user_id = get_jwt_identity()
    logger.info(f"[TEST REMINDER] Request from user_id: {user_id}")
    
    user = User.query.get(user_id)
    logger.debug(f"[TEST REMINDER] User found: {user is not None}")
    
    if not user:
        logger.warning(f"[TEST REMINDER] User {user_id} not found")
        return jsonify({'message': 'User not found'}), 404
    
    logger.debug(f"[TEST REMINDER] User phone: {user.phone_number}")
    
    if not user.phone_number:
        logger.warning(f"[TEST REMINDER] User {user_id} has no phone number")
        return jsonify({'message': 'Phone number required for reminders'}), 400
    
    data = request.get_json()
    reminder_type = data.get('type')
    logger.info(f"[TEST REMINDER] Type requested: {reminder_type}")
    
    if reminder_type not in ['whatsapp', 'call', 'elevenlabs']:
        logger.warning(f"[TEST REMINDER] Invalid reminder type: {reminder_type}")
        return jsonify({'message': 'Invalid reminder type'}), 400
    
    # Create test bill data
    test_bill_data = {
        'name': 'Test Bill',
        'amount': 1000,
        'due_date': datetime.now().strftime('%Y-%m-%d')
    }
    logger.debug(f"[TEST REMINDER] Test bill data: {test_bill_data}")
    
    # Generate message
    logger.debug(f"[TEST REMINDER] Generating message for user: {user.name}")
    message = generate_reminder_message(user.name, test_bill_data)
    logger.debug(f"[TEST REMINDER] Generated message: {message[:100]}...")
    
    # Send reminder based on type
    result = None
    try:
        if reminder_type == 'whatsapp':
            # --- THIS IS THE FIX ---
            # Using a static, pre-saved message for the fastest and correct response.
            message = "Whatsapp Test successfully done! Your number is ready for future reminders :)"
            logger.info(f"[TEST REMINDER] Sending WhatsApp test to {user.phone_number}")
            result = send_whatsapp_reminder(user.phone_number, message)
            
        elif reminder_type == 'call':
            # Using a static message for the call test as well.
            message = f"Hello {user.name}. This is a test call from your bills reminder application. Your reminders are set up correctly. Goodbye."
            logger.info(f"[TEST REMINDER] Sending voice call test to {user.phone_number}")
            result = send_voice_call_reminder(user.phone_number, message)
            
        elif reminder_type == 'elevenlabs':
            logger.info(f"[TEST REMINDER] Generating ElevenLabs audio")
            # Generate audio file using ElevenLabs
            audio_result = generate_voice_audio(message)
            logger.debug(f"[TEST REMINDER] ElevenLabs result: {audio_result}")
            
            if audio_result['success']:
                result = {'success': True, 'message': 'Audio generated', 'audio_path': audio_result['audio_path']}
                logger.info(f"[TEST REMINDER] Audio generated at: {audio_result.get('audio_path')}")
            else:
                result = audio_result
                logger.warning(f"[TEST REMINDER] Audio generation failed: {audio_result}")
    except Exception as e:
        logger.error(f"[TEST REMINDER ERROR] Exception during {reminder_type} test: {str(e)}", exc_info=True)
        result = {'success': False, 'error': str(e)}
    
    if result.get('success'):
        logger.info(f"[TEST REMINDER] Test reminder sent successfully via {reminder_type}")
        return jsonify({
            'status': 'success',
            'message': f'Test reminder sent via {reminder_type}',
            'details': result
        }), 200
    else:
        logger.error(f"[TEST REMINDER] Failed to send test reminder via {reminder_type}: {result}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to send reminder via {reminder_type}',
            'details': result
        }), 500

@reminders_bp.route('/send', methods=['POST'])
@jwt_required()
def send_reminder():
    """Send reminder for a specific bill"""
    user_id = get_jwt_identity()
    logger.info(f"[SEND REMINDER] Request from user_id: {user_id}")
    
    data = request.get_json()
    logger.debug(f"[SEND REMINDER] Request data: {data}")
    
    bill_id = data.get('bill_id')
    reminder_type = data.get('type')
    
    logger.debug(f"[SEND REMINDER] Bill ID: {bill_id}, Type: {reminder_type}")
    
    if not bill_id or not reminder_type:
        logger.warning(f"[SEND REMINDER] Missing required fields - bill_id: {bill_id}, type: {reminder_type}")
        return jsonify({'message': 'Missing bill_id or type'}), 400
    
    # Get bill and user
    bill = Bill.query.filter_by(id=bill_id, user_id=user_id).first()
    logger.debug(f"[SEND REMINDER] Bill found: {bill is not None}")
    
    if not bill:
        logger.warning(f"[SEND REMINDER] Bill {bill_id} not found for user {user_id}")
        return jsonify({'message': 'Bill not found'}), 404
    
    logger.debug(f"[SEND REMINDER] Bill details - Name: {bill.name}, Amount: {bill.amount}, Due: {bill.due_date}")
    logger.debug(f"[SEND REMINDER] Bill settings - WhatsApp: {bill.enable_whatsapp}, Call: {bill.enable_call}")
    
    user = User.query.get(user_id)
    if not user.phone_number:
        logger.warning(f"[SEND REMINDER] User {user_id} has no phone number")
        return jsonify({'message': 'Phone number required'}), 400
    
    logger.debug(f"[SEND REMINDER] User phone: {user.phone_number}")
    
    # Prepare bill data
    bill_data = {
        'name': bill.name,
        'amount': bill.amount,
        'due_date': bill.due_date.strftime('%Y-%m-%d')
    }
    logger.debug(f"[SEND REMINDER] Prepared bill data: {bill_data}")
    
    # Generate and send reminder
    logger.debug(f"[SEND REMINDER] Generating message for user: {user.name}")
    message = generate_reminder_message(user.name, bill_data)
    logger.debug(f"[SEND REMINDER] Generated message: {message[:100]}...")
    
    result = None
    try:
        if reminder_type == 'whatsapp' and bill.enable_whatsapp:
            logger.info(f"[SEND REMINDER] Sending WhatsApp reminder to {user.phone_number} for bill {bill_id}")
            result = send_whatsapp_reminder(user.phone_number, message)
            logger.debug(f"[SEND REMINDER] WhatsApp result: {result}")
            
        elif reminder_type == 'call' and bill.enable_call:
            logger.info(f"[SEND REMINDER] Sending voice reminder to {user.phone_number} for bill {bill_id}")
            result = send_voice_call_reminder(user.phone_number, message)
            logger.debug(f"[SEND REMINDER] Voice call result: {result}")
            
        else:
            logger.warning(f"[SEND REMINDER] Reminder type {reminder_type} not enabled for bill {bill_id}")
            logger.debug(f"[SEND REMINDER] Bill settings - WhatsApp: {bill.enable_whatsapp}, Call: {bill.enable_call}")
            return jsonify({'message': 'Reminder type not enabled for this bill'}), 400
            
    except Exception as e:
        logger.error(f"[SEND REMINDER ERROR] Exception during {reminder_type} send: {str(e)}", exc_info=True)
        result = {'success': False, 'error': str(e)}
    
    if result.get('success'):
        logger.info(f"[SEND REMINDER] Successfully sent {reminder_type} reminder for bill {bill_id}")
        return jsonify({
            'status': 'success',
            'message': f'Reminder sent via {reminder_type}'
        }), 200
    else:
        logger.error(f"[SEND REMINDER] Failed to send {reminder_type} reminder for bill {bill_id}: {result}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to send reminder',
            'details': result
        }), 500