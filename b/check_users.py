import sqlite3
import os
import logging

# --- Configuration ---
# This is the corrected path to the database inside the Flask instance folder.
DB_FILE = os.path.join('instance', 'bills_reminder.db')

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# -------------------

def view_registered_users():
    """Connects to the database and prints all registered users with logging."""
    logging.info("Starting the process to view registered users.")
    
    if not os.path.exists(DB_FILE):
        logging.error(f"Database file '{DB_FILE}' not found.")
        logging.warning("Please run the main backend application (app.py) first to create the database.")
        return

    conn = None
    try:
        logging.info(f"Connecting to database: {DB_FILE}")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        logging.info("Executing query to fetch all users from the 'user' table.")
        cursor.execute("SELECT id, name, email, phone_number, created_at FROM user")
        
        users = cursor.fetchall()
        logging.info(f"Query finished. Found {len(users)} user(s).")

        if not users:
            logging.info("The 'user' table is empty. No users have been registered yet.")
        else:
            print("\n--- Registered User Details ---")
            for user in users:
                user_id, name, email, phone, created_at = user
                logging.info(f"Processing user: Name='{name}', Email='{email}'")
                print(f"\n  Name: {name}")
                print(f"  Email: {email}")
                print(f"  Phone: {phone}")
                print(f"  Registered On: {created_at}")
                print("  " + "-" * 20)

    except sqlite3.Error as e:
        logging.error(f"A database error occurred: {e}")
    finally:
        if conn:
            logging.info("Closing database connection.")
            conn.close()

if __name__ == '__main__':
    view_registered_users()