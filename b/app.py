# Updated app.py - Add chatbot blueprint registration
import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from models import db
from auth import auth_bp
from bills import bills_bp
from reminders import reminders_bp
from receipts import receipts_bp
from loans import loans_bp
from scheduler import start_scheduler
from local_storage_service import init_storage
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    logger.info("=" * 80)
    logger.info("[APP INIT] Starting Flask application creation")
    logger.info(f"[APP INIT] Current time: {datetime.now()}")
    logger.info("=" * 80)
    
    app = Flask(__name__)
    logger.info(f"[APP INIT] Flask app created: {app.name}")
    
    logger.info("[APP CONFIG] Loading configuration from Config object")
    app.config.from_object(Config)
    
    # Add encryption key for API keys (generate a secure key in production)
    app.config['ENCRYPTION_KEY'] = os.getenv('ENCRYPTION_KEY', 'kAaC4slEgkDJsyEE-81UWU2QHy4lKnRqB1_uEXpCtuQ=')
    
    # Log key configuration values (be careful not to log sensitive data)
    logger.debug(f"[APP CONFIG] Debug mode: {app.config.get('DEBUG')}")
    logger.debug(f"[APP CONFIG] Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')}")
    logger.debug(f"[APP CONFIG] JWT Algorithm: {app.config.get('JWT_ALGORITHM', 'NOT SET')}")
    
    # Set max file size for uploads
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
    logger.info(f"[APP CONFIG] Max content length set to: {Config.MAX_CONTENT_LENGTH} bytes ({Config.MAX_CONTENT_LENGTH / 1024 / 1024}MB)")
    
    # Initialize extensions
    logger.info("[APP INIT] Initializing extensions")
    
    logger.debug("[APP INIT] Initializing database")
    db.init_app(app)
    
    logger.debug("[APP INIT] Initializing CORS")
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    logger.debug("[APP INIT] Initializing JWT Manager")
    JWTManager(app)
    
    # Initialize local storage
    logger.info("[APP INIT] Initializing local storage")
    init_storage()
    
    # Initialize the AI Service and attach it to the app object
    logger.info("[APP INIT] AI Service instance created and attached to app.")
    
    # Register blueprints
    logger.info("[APP INIT] Registering blueprints")
    
    blueprints = [
        (auth_bp, '/api/auth', 'auth'),
        (bills_bp, '/api/bills', 'bills'),
        (reminders_bp, '/api/reminders', 'reminders'),
        (receipts_bp, '/api/receipts', 'receipts'),
        (loans_bp, '/api', 'loans'),
    ]
    
    for blueprint, prefix, name in blueprints:
        app.register_blueprint(blueprint, url_prefix=prefix)
        logger.debug(f"[APP INIT] Registered blueprint '{name}' with prefix '{prefix}'")
    
    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        logger.debug("[HEALTH CHECK] Health check endpoint called")
        return jsonify({'status': 'healthy', 'message': 'Bills Reminder API is running'}), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        logger.warning(f"[ERROR 404] Not found: {request.url}")
        logger.debug(f"[ERROR 404] Method: {request.method}, Path: {request.path}")
        return jsonify({'message': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"[ERROR 500] Internal server error: {str(error)}")
        logger.error(f"[ERROR 500] Request URL: {request.url}")
        logger.error(f"[ERROR 500] Request method: {request.method}")
        return jsonify({'message': 'Internal server error'}), 500
    
    @app.errorhandler(413)
    def file_too_large(error):
        logger.warning(f"[ERROR 413] File too large from {request.remote_addr}")
        logger.debug(f"[ERROR 413] Content length: {request.content_length if request.content_length else 'Unknown'}")
        return jsonify({'message': 'File too large. Maximum size is 16MB'}), 413
    
    # Log all registered routes
    logger.info("[APP INIT] All registered routes:")
    for rule in app.url_map.iter_rules():
        methods = ', '.join(rule.methods - {'HEAD', 'OPTIONS'})
        logger.debug(f"[APP INIT] Route: {rule.rule} [{methods}] -> {rule.endpoint}")
    
    logger.info("[APP INIT] Flask application creation completed successfully")
    return app

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("[MAIN] Starting application in main block")
    logger.info("=" * 80)
    
    app = create_app()
    
    # Create tables including new chatbot tables
    logger.info("[MAIN] Creating database tables")
    with app.app_context():
        try:
            
            db.create_all()
            logger.info("[MAIN] Database tables created successfully")
            
            # Log table information
            tables = db.metadata.tables.keys()
            logger.debug(f"[MAIN] Created tables: {', '.join(tables)}")
        except Exception as e:
            logger.error(f"[MAIN ERROR] Failed to create database tables: {str(e)}", exc_info=True)
            raise
    
    # Start the scheduler
    logger.info("[MAIN] Starting scheduler")
    try:
        start_scheduler(app)
        logger.info("[MAIN] Scheduler started successfully")
    except Exception as e:
        logger.error(f"[MAIN ERROR] Failed to start scheduler: {str(e)}", exc_info=True)
        raise
    
    logger.info("[MAIN] Starting Flask development server")
    logger.info(f"[MAIN] Server configuration - Debug: True, Port: 5000, Reloader: False")
    logger.info("[MAIN] Application ready to receive requests")
    logger.info("=" * 80)
    
    app.run(debug=True, port=5000, use_reloader=False)