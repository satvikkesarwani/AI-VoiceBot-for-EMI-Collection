
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User, ReminderSettings
import bcrypt
from datetime import datetime
import re
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validate email format"""
    logger.debug(f"[VALIDATE EMAIL] Checking email format: {email}")
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = re.match(pattern, email) is not None
    logger.debug(f"[VALIDATE EMAIL] Email valid: {is_valid}")
    return is_valid

def validate_phone(phone):
    """Validate phone number format"""
    logger.debug(f"[VALIDATE PHONE] Checking phone format: {phone}")
    # Remove all non-digit characters for validation
    digits_only = re.sub(r'\D', '', phone)
    logger.debug(f"[VALIDATE PHONE] Digits only: {digits_only}, Length: {len(digits_only)}")
    # Check if it has at least 10 digits
    is_valid = len(digits_only) >= 10
    logger.debug(f"[VALIDATE PHONE] Phone valid: {is_valid}")
    return is_valid

# auth.py

@auth_bp.route('/register', methods=['POST'])
def register():
    print("[DEBUG] === STARTING REGISTRATION PROCESS ===")
    try:
        data = request.get_json()
        print(f"[DEBUG] Received data: {data}")
        
        if not data:
            print("[DEBUG] No data provided, returning 400")
            return jsonify({'message': 'No data provided'}), 400
        
        required = ['email', 'password', 'name', 'phone_number']
        missing_fields = [field for field in required if field not in data or not data[field]]
        if missing_fields:
            print(f"[DEBUG] Missing required fields: {missing_fields}")
            return jsonify({'message': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        if not validate_email(data['email']):
            print(f"[DEBUG] Invalid email format: {data['email']}")
            return jsonify({'message': 'Invalid email format'}), 400
        
        password_length = len(data['password'])
        if password_length < 6:
            print(f"[DEBUG] Password too short: {password_length} characters")
            return jsonify({'message': 'Password must be at least 6 characters long'}), 400
        
        if not validate_phone(data['phone_number']):
            print(f"[DEBUG] Invalid phone number: {data['phone_number']}")
            return jsonify({'message': 'Invalid phone number format'}), 400
        
        email_lower = data['email'].lower()
        existing_user = User.query.filter_by(email=email_lower).first()
        if existing_user:
            print(f"[DEBUG] Email already registered: {email_lower}")
            return jsonify({'message': 'Email already registered'}), 409
        
        print("[DEBUG] All validation passed, creating new user.")
        password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        
        user = User(
            email=email_lower,
            password_hash=password_hash.decode('utf-8'),
            name=data['name'].strip(),
            phone_number=data['phone_number'].strip()
        )
        
        db.session.add(user)
        db.session.flush()
        
        reminder_settings = ReminderSettings(user_id=user.id)
        db.session.add(reminder_settings)
        
        db.session.commit()
        print("[DEBUG] User and settings committed to database successfully.")
        
        token = create_access_token(identity=user.id)
        print(f"[DEBUG] JWT token created for user: {user.id}")
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone_number': user.phone_number
            }
        }), 201
        
    except Exception as e:
        print(f"[DEBUG] An unexpected error occurred: {str(e)}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'message': 'An error occurred during registration'}), 500
    
    

@auth_bp.route('/login', methods=['POST'])
def login():
    logger.info("[LOGIN] Login request received")
    try:
        data = request.get_json()
        
        if not data or not data.get('email') or not data.get('password'):
            logger.warning("[LOGIN] Missing email or password")
            return jsonify({'message': 'Email and password required'}), 400
        
        email_lower = data['email'].lower()
        logger.debug(f"[LOGIN] Login attempt for email: {email_lower}")
        
        user = User.query.filter_by(email=email_lower).first()
        
        if not user:
            logger.warning(f"[LOGIN] User not found: {email_lower}")
            return jsonify({'message': 'Invalid credentials'}), 401
        
        logger.debug(f"[LOGIN] User found with ID: {user.id}")
        
        # --- NEW DETAILED DEBUGGING LOGS ---
        print("--- PASSWORD DEBUG START ---")
        # Strip whitespace from the password from the app (a robust defense)
        app_password_stripped = data['password'].strip()
        print(f"Password from app: '{app_password_stripped}'")
        print(f"Hashed password from DB: '{user.password_hash}'")
        
        # Check password using bcrypt
        password_valid = bcrypt.checkpw(app_password_stripped.encode('utf-8'), user.password_hash.encode('utf-8'))
        
        print(f"Password check result: {password_valid}")
        print("--- PASSWORD DEBUG END ---")
        # --- END OF DETAILED DEBUGGING LOGS ---

        if not password_valid:
            logger.warning(f"[LOGIN] Password check FAILED for user: {email_lower}")
            return jsonify({'message': 'Invalid credentials'}), 401
        
        logger.info(f"[LOGIN] Password check PASSED for user: {email_lower}")
        token = create_access_token(identity=user.id)
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone_number': user.phone_number
            }
        }), 200
        
    except Exception as e:
        logger.error(f"[LOGIN ERROR] Login failed: {str(e)}", exc_info=True)
        return jsonify({'message': 'An error occurred during login'}), 500

# ... (the rest of your auth.py file remains the same) ...

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    logger.info("[GET PROFILE] Profile request received")
    try:
        user_id = get_jwt_identity()
        logger.debug(f"[GET PROFILE] JWT identity: {user_id}")
        
        user = User.query.get(user_id)
        
        if not user:
            logger.warning(f"[GET PROFILE] User not found: {user_id}")
            return jsonify({'message': 'User not found'}), 404
        
        logger.info(f"[GET PROFILE] Profile retrieved for user: {user.email}")
        return jsonify({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'phone_number': user.phone_number,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"[GET PROFILE ERROR] Failed to get profile: {str(e)}", exc_info=True)
        print(f"Get profile error: {str(e)}")
        return jsonify({'message': 'An error occurred while fetching profile'}), 500

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    logger.info("[UPDATE PROFILE] Profile update request received")
    try:
        user_id = get_jwt_identity()
        logger.debug(f"[UPDATE PROFILE] JWT identity: {user_id}")
        
        user = User.query.get(user_id)
        
        if not user:
            logger.warning(f"[UPDATE PROFILE] User not found: {user_id}")
            return jsonify({'message': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            logger.warning("[UPDATE PROFILE] No data provided")
            return jsonify({'message': 'No data provided'}), 400
        
        logger.debug(f"[UPDATE PROFILE] Update data keys: {list(data.keys())}")
        updates = []
        
        if 'name' in data and data['name']:
            old_name = user.name
            user.name = data['name'].strip()
            updates.append(f"name: '{old_name}' -> '{user.name}'")
            logger.debug(f"[UPDATE PROFILE] Name updated: {old_name} -> {user.name}")
        
        if 'phone_number' in data and data['phone_number']:
            if not validate_phone(data['phone_number']):
                logger.warning(f"[UPDATE PROFILE] Invalid phone number: {data['phone_number']}")
                return jsonify({'message': 'Invalid phone number format'}), 400
            old_phone = user.phone_number
            user.phone_number = data['phone_number'].strip()
            updates.append(f"phone: '{old_phone}' -> '{user.phone_number}'")
            logger.debug(f"[UPDATE PROFILE] Phone updated: {old_phone} -> {user.phone_number}")
        
        if updates:
            logger.info(f"[UPDATE PROFILE] Updating user {user_id}: {', '.join(updates)}")
            db.session.commit()
            logger.info(f"[UPDATE PROFILE] Profile updated successfully for user: {user.email}")
        else:
            logger.info(f"[UPDATE PROFILE] No changes made for user: {user.email}")
        
        return jsonify({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'phone_number': user.phone_number
        }), 200
        
    except Exception as e:
        logger.error(f"[UPDATE PROFILE ERROR] Failed to update profile: {str(e)}", exc_info=True)
        db.session.rollback()
        print(f"Update profile error: {str(e)}")
        return jsonify({'message': 'An error occurred while updating profile'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    user_id = get_jwt_identity()
    logger.info(f"[LOGOUT] Logout request from user: {user_id}")
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/verify-token', methods=['GET'])
@jwt_required()
def verify_token():
    """Endpoint to verify if a token is still valid"""
    logger.info("[VERIFY TOKEN] Token verification request")
    try:
        user_id = get_jwt_identity()
        logger.debug(f"[VERIFY TOKEN] JWT identity: {user_id}")
        
        user = User.query.get(user_id)
        
        if not user:
            logger.warning(f"[VERIFY TOKEN] Invalid token - user not found: {user_id}")
            return jsonify({'message': 'Invalid token'}), 401
        
        logger.info(f"[VERIFY TOKEN] Token valid for user: {user.email}")
        return jsonify({
            'valid': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'phone_number': user.phone_number
            }
        }), 200
        
    except Exception as e:
        logger.error(f"[VERIFY TOKEN ERROR] Token verification failed: {str(e)}", exc_info=True)
        print(f"Token verification error: {str(e)}")
        return jsonify({'message': 'Invalid token'}), 401
