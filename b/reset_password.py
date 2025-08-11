import sqlite3
import os
import sys
import bcrypt
import logging

# --- Configuration ---
DB_FILE = os.path.join('instance', 'bills_reminder.db')

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# -------------------

def reset_user_password(email, new_password):
    """Finds a user by email and resets their password."""
    logging.info(f"Attempting to reset password for email: {email}")

    if not os.path.exists(DB_FILE):
        logging.error(f"Database file '{DB_FILE}' not found. Is the main app running?")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM user WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            logging.error(f"No user found with the email: {email}")
            return

        user_id = user[0]
        logging.info(f"User found with ID: {user_id}. Proceeding with password reset.")

        # Hash the new password using bcrypt
        hashed_password_bytes = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # --- THIS IS THE FIX ---
        # Decode the bytes into a string before saving, to match the registration format.
        hashed_password_str = hashed_password_bytes.decode('utf-8')
        
        logging.info(f"Updating password hash for user ID: {user_id}")
        cursor.execute("UPDATE user SET password_hash = ? WHERE id = ?", (hashed_password_str, user_id))
        
        conn.commit()
        
        logging.info(f"Successfully reset password for {email}.")
        print(f"\nPassword for '{email}' has been updated successfully!")

    except sqlite3.Error as e:
        logging.error(f"A database error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            logging.info("Closing database connection.")
            conn.close()

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("\nUsage: python reset_password.py <email_address> <new_password>")
        print("Example: python reset_password.py user@example.com MyNewSecurePassword123")
        sys.exit(1)
    
    email_to_reset = sys.argv[1]
    new_password_to_set = sys.argv[2]
    
    reset_user_password(email_to_reset, new_password_to_set)