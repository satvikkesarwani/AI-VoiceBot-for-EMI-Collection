import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import send_file, current_app
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = 'uploads/receipts'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

logger.info(f"[STORAGE CONFIG] Upload folder: {UPLOAD_FOLDER}")
logger.info(f"[STORAGE CONFIG] Allowed extensions: {ALLOWED_EXTENSIONS}")

def init_storage():
    """Initialize local storage directories"""
    logger.info(f"[INIT STORAGE] Initializing storage directory: {UPLOAD_FOLDER}")
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        logger.debug(f"[INIT STORAGE] Directory created/verified: {os.path.abspath(UPLOAD_FOLDER)}")
        logger.debug(f"[INIT STORAGE] Directory exists: {os.path.exists(UPLOAD_FOLDER)}")
        logger.debug(f"[INIT STORAGE] Directory permissions: {oct(os.stat(UPLOAD_FOLDER).st_mode)[-3:]}")
    except Exception as e:
        logger.error(f"[INIT STORAGE ERROR] Failed to create directory: {str(e)}", exc_info=True)
        raise

def allowed_file(filename):
    """Check if file extension is allowed"""
    logger.debug(f"[FILE CHECK] Checking file: {filename}")
    
    has_extension = '.' in filename
    if not has_extension:
        logger.warning(f"[FILE CHECK] File has no extension: {filename}")
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    is_allowed = extension in ALLOWED_EXTENSIONS
    
    logger.debug(f"[FILE CHECK] Extension: {extension}, Allowed: {is_allowed}")
    return has_extension and is_allowed

def upload_receipt_to_local(file, user_id):
    """Upload receipt image to local storage"""
    logger.info(f"[UPLOAD] Starting upload for user: {user_id}")
    logger.debug(f"[UPLOAD] Original filename: {file.filename}")
    
    try:
        # Initialize storage
        init_storage()
        
        # Check if file is allowed
        if not allowed_file(file.filename):
            logger.warning(f"[UPLOAD] File type not allowed: {file.filename}")
            return {
                "success": False, 
                "error": "File type not allowed. Allowed types: " + ", ".join(ALLOWED_EXTENSIONS)
            }
        
        # Create user directory if it doesn't exist
        user_folder = os.path.join(UPLOAD_FOLDER, str(user_id))
        logger.info(f"[UPLOAD] Creating user folder: {user_folder}")
        
        try:
            os.makedirs(user_folder, exist_ok=True)
            logger.debug(f"[UPLOAD] User folder created/verified: {os.path.abspath(user_folder)}")
        except Exception as e:
            logger.error(f"[UPLOAD ERROR] Failed to create user folder: {str(e)}")
            raise
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_id = str(uuid.uuid4())
        filename = f"{timestamp}_{unique_id}.{file_extension}"
        
        logger.debug(f"[UPLOAD] Generated filename: {filename}")
        logger.debug(f"[UPLOAD] Timestamp: {timestamp}, UUID: {unique_id}, Extension: {file_extension}")
        
        # Full path for the file
        file_path = os.path.join(user_folder, filename)
        logger.info(f"[UPLOAD] Saving file to: {file_path}")
        
        # Save file
        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            logger.info(f"[UPLOAD] File saved successfully. Size: {file_size} bytes")
            logger.debug(f"[UPLOAD] File exists: {os.path.exists(file_path)}")
        except Exception as e:
            logger.error(f"[UPLOAD ERROR] Failed to save file: {str(e)}", exc_info=True)
            raise
        
        # Generate URL path (relative path that will be used to retrieve the file)
        url_path = f"/api/receipts/view/{user_id}/{filename}"
        stored_filename = f"{user_id}/{filename}"
        
        logger.info(f"[UPLOAD] Upload successful - Stored as: {stored_filename}")
        logger.debug(f"[UPLOAD] URL path: {url_path}")
        
        return {
            "success": True,
            "filename": stored_filename,
            "url": url_path,
            "full_path": file_path
        }
        
    except Exception as e:
        logger.error(f"[UPLOAD ERROR] Upload failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

def delete_receipt_from_local(filename):
    """Delete receipt from local storage"""
    logger.info(f"[DELETE] Attempting to delete file: {filename}")
    
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        logger.debug(f"[DELETE] Full path: {file_path}")
        
        if os.path.exists(file_path):
            logger.info(f"[DELETE] File found, deleting: {file_path}")
            file_size = os.path.getsize(file_path)
            os.remove(file_path)
            logger.info(f"[DELETE] File deleted successfully. Size was: {file_size} bytes")
            
            # Check if parent directory is empty and clean up
            parent_dir = os.path.dirname(file_path)
            if parent_dir != UPLOAD_FOLDER:
                try:
                    if not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        logger.info(f"[DELETE] Removed empty directory: {parent_dir}")
                except Exception as e:
                    logger.debug(f"[DELETE] Could not remove directory {parent_dir}: {str(e)}")
            
            return {"success": True}
        else:
            logger.warning(f"[DELETE] File not found: {file_path}")
            return {"success": False, "error": "File not found"}
            
    except Exception as e:
        logger.error(f"[DELETE ERROR] Failed to delete file: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

def get_receipt_path(filename):
    """Get full path for a receipt file"""
    logger.debug(f"[GET PATH] Getting path for: {filename}")
    
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        logger.debug(f"[GET PATH] Full path: {file_path}")
        
        if os.path.exists(file_path):
            logger.info(f"[GET PATH] File found: {file_path}")
            file_stats = os.stat(file_path)
            logger.debug(f"[GET PATH] File size: {file_stats.st_size} bytes")
            logger.debug(f"[GET PATH] Last modified: {datetime.fromtimestamp(file_stats.st_mtime)}")
            return {"success": True, "path": file_path}
        else:
            logger.warning(f"[GET PATH] File not found: {file_path}")
            return {"success": False, "error": "File not found"}
            
    except Exception as e:
        logger.error(f"[GET PATH ERROR] Failed to get path: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

def get_receipt_url(filename):
    """Get URL for receipt (for local storage, returns the view endpoint)"""
    logger.debug(f"[GET URL] Getting URL for: {filename}")
    
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        logger.debug(f"[GET URL] Checking existence of: {file_path}")
        
        if os.path.exists(file_path):
            # Extract user_id and filename from the path
            parts = filename.split('/')
            logger.debug(f"[GET URL] Filename parts: {parts}")
            
            if len(parts) == 2:
                user_id, file_name = parts
                url = f"/api/receipts/view/{user_id}/{file_name}"
                logger.debug(f"[GET URL] Generated URL with user_id: {url}")
            else:
                url = f"/api/receipts/view/{filename}"
                logger.debug(f"[GET URL] Generated URL without user_id: {url}")
            
            logger.info(f"[GET URL] URL generated successfully: {url}")
            return {"success": True, "url": url}
        else:
            logger.warning(f"[GET URL] File not found: {file_path}")
            return {"success": False, "error": "File not found"}
            
    except Exception as e:
        logger.error(f"[GET URL ERROR] Failed to get URL: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

def cleanup_user_receipts(user_id):
    """Clean up all receipts for a user (useful when deleting user account)"""
    logger.info(f"[CLEANUP] Starting cleanup for user: {user_id}")
    
    try:
        user_folder = os.path.join(UPLOAD_FOLDER, str(user_id))
        logger.debug(f"[CLEANUP] User folder path: {user_folder}")
        
        if os.path.exists(user_folder):
            # Count files before deletion
            file_count = 0
            total_size = 0
            for root, dirs, files in os.walk(user_folder):
                file_count += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            logger.info(f"[CLEANUP] Found {file_count} files, total size: {total_size} bytes")
            
            # Delete the folder
            shutil.rmtree(user_folder)
            logger.info(f"[CLEANUP] Successfully deleted user folder: {user_folder}")
            logger.debug(f"[CLEANUP] Freed {total_size} bytes of storage")
        else:
            logger.warning(f"[CLEANUP] User folder not found: {user_folder}")
            
        return {"success": True}
    except Exception as e:
        logger.error(f"[CLEANUP ERROR] Failed to cleanup user receipts: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}