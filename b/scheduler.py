# scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from models import db, Bill, User, ReminderSettings
from reminder_service import generate_reminder_message, send_whatsapp_reminder, send_voice_call_reminder
from models import db, Bill, User, ReminderSettings, LoanDetails
import pytz
import logging
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def start_scheduler(app):
    """
    Initializes and starts the background scheduler.
    The job functions are defined inside so they have access to the 'app' context
    without causing circular import errors.
    """
    logger.info("=== SCHEDULER START: Initializing scheduler ===")

    def check_and_send_reminders():
        """This job runs every minute to check for upcoming reminders."""
        with app.app_context():
            current_time = datetime.now().strftime('%H:%M')
            logger.info(f"[REMINDER CHECK] Starting reminder check at {current_time}")
            print("Scheduler: Checking for due bills...")
            
            users = User.query.filter(User.phone_number.isnot(None)).all()
            logger.info(f"[REMINDER CHECK] Found {len(users)} users with phone numbers")
            
            for user in users:
                logger.debug(f"[USER CHECK] Processing user: {user.id} - {user.name}")
                
                settings = ReminderSettings.query.filter_by(user_id=user.id).first()
                if not settings:
                    logger.warning(f"[USER CHECK] No reminder settings found for user {user.id}")
                    continue

                logger.debug(f"[USER CHECK] User {user.id} preferred time: {settings.preferred_time}")
                logger.debug(f"[USER CHECK] WhatsApp enabled: {settings.whatsapp_enabled}, Call enabled: {settings.call_enabled}")

                if not settings.preferred_time:
                    settings.preferred_time = '09:00'
                    logger.warning(f"[TIME FIX] preferred_time was empty for user {user.id}, setting to default '09:00'")

                # MODIFIED LOGIC: Check if current time exactly matches the user's preferred time.
                if settings.preferred_time == current_time:
                    logger.info(f"[TIME MATCH] Exact match found - Current: {current_time}, Preferred: {settings.preferred_time} for user {user.id}")
                    
                    bills_due = Bill.query.filter(
                        Bill.user_id == user.id,
                        Bill.is_paid == False
                    ).all()
                    
                    logger.info(f"[BILLS CHECK] Found {len(bills_due)} unpaid bills for user {user.id}")
                    
                    for bill in bills_due:
                        logger.debug(f"[BILL PROCESS] Processing bill: {bill.id} - {bill.name}")
                        logger.debug(f"[BILL PROCESS] Bill frequency: {bill.frequency}")
                        logger.debug(f"[BILL PROCESS] Bill due date: {bill.due_date}, Amount: {bill.amount}")
                        
                        # Check if reminder should be sent based on new unified schedule
                        if check_reminder_schedule(bill):
                            logger.info(f"[REMINDER TRIGGER] Bill {bill.id} qualifies for reminder")
                            
                            bill_data = {
                                'name': bill.name,
                                'amount': bill.amount,
                                'due_date': bill.due_date.strftime('%Y-%m-%d')
                            }
                            
                            logger.debug(f"[MESSAGE GEN] Generating message for bill: {bill_data}")
                            message = generate_reminder_message(user.name, bill_data)
                            logger.debug(f"[MESSAGE GEN] Generated message: {message[:50]}...")
                            
                            if settings.whatsapp_enabled and bill.enable_whatsapp:
                                logger.info(f"[WHATSAPP] Sending WhatsApp reminder to {user.phone_number} for bill {bill.id}")
                                try:
                                    send_whatsapp_reminder(user.phone_number, message)
                                    logger.info(f"[WHATSAPP] Successfully sent WhatsApp reminder for bill {bill.id}")
                                    update_last_reminder_sent(bill)
                                except Exception as e:
                                    logger.error(f"[WHATSAPP ERROR] Failed to send WhatsApp reminder for bill {bill.id}: {str(e)}")
                            else:
                                logger.debug(f"[WHATSAPP] Skipped - WhatsApp disabled (settings: {settings.whatsapp_enabled}, bill: {bill.enable_whatsapp})")
                            
                            if settings.call_enabled and bill.enable_call:
                                logger.info(f"[VOICE CALL] Sending voice reminder to {user.phone_number} for bill {bill.id}")
                                try:
                                    result = send_voice_call_reminder(user.phone_number, message)
                                    if result and result.get('success'):
                                        logger.info(f"[VOICE CALL] Successfully sent voice reminder for bill {bill.id}")
                                        update_last_reminder_sent(bill)
                                    else:
                                        logger.error(f"[VOICE CALL ERROR] Failed to send voice reminder for bill {bill.id}: {result.get('error', 'Unknown error')}")
                                except Exception as e:
                                    logger.error(f"[VOICE CALL ERROR] Failed to send voice reminder for bill {bill.id}: {str(e)}")
                            else:
                                logger.debug(f"[VOICE CALL] Skipped - Voice call disabled (settings: {settings.call_enabled}, bill: {bill.enable_call})")
                        else:
                            logger.debug(f"[BILL SKIP] Bill {bill.id} not due for reminder based on frequency")
                else:
                    logger.debug(f"[TIME SKIP] Current time {current_time} does not match user {user.id} preferred time {settings.preferred_time}")
            
            logger.info(f"[REMINDER CHECK] Completed reminder check at {datetime.now().strftime('%H:%M:%S')}")

    # NEW FUNCTION: Simplified reminder schedule check
    def check_reminder_schedule(bill):
        """
        Check if a reminder should be sent based on the due date.
        This simplified logic applies to all recurring bills.
        """
        current_date = datetime.now().date()
        bill_due_date = bill.due_date.date()
        
        days_left = (bill_due_date - current_date).days
        
        logger.debug(f"[SCHEDULE CHECK] Bill {bill.id} - Days left: {days_left}")
        
        # Unified logic: send reminder on the 3rd, 2nd, and 1st day before the due date, and on the due date itself.
        reminder_days = [3, 2, 1, 0]
        
        if days_left in reminder_days and days_left >= 0:
            logger.debug(f"[SCHEDULE CHECK] Bill {bill.id} - Sending reminder (days_left: {days_left})")
            return True

        return False

    def get_last_reminder_date(bill):
        """
        Get the date when the last reminder was sent for this bill.
        Stored in bill notes as JSON.
        """
        try:
            if bill.notes:
                notes_data = json.loads(bill.notes)
                if isinstance(notes_data, dict) and 'last_reminder_date' in notes_data:
                    return datetime.strptime(notes_data['last_reminder_date'], '%Y-%m-%d').date()
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"[REMINDER DATE] Could not parse last reminder date for bill {bill.id}: {str(e)}")
        return None

    def update_last_reminder_sent(bill):
        """
        Update the last reminder sent date for the bill.
        """
        try:
            notes_data = {}
            if bill.notes:
                try:
                    notes_data = json.loads(bill.notes)
                    if not isinstance(notes_data, dict):
                        notes_data = {'original_notes': bill.notes}
                except json.JSONDecodeError:
                    notes_data = {'original_notes': bill.notes}
            
            notes_data['last_reminder_date'] = datetime.now().strftime('%Y-%m-%d')
            bill.notes = json.dumps(notes_data)
            db.session.commit()
            logger.debug(f"[REMINDER DATE] Updated last reminder date for bill {bill.id}")
        except Exception as e:
            logger.error(f"[REMINDER DATE ERROR] Failed to update last reminder date for bill {bill.id}: {str(e)}")

    def handle_recurring_bills():
        """
        Check and create new bill instances for recurring bills.
        This runs daily to handle recurring bill generation.
        """
        with app.app_context():
            logger.info("[RECURRING CHECK] Starting recurring bills check")
            current_date = datetime.now().date()
            
            # Get all paid bills that have recurring frequencies
            recurring_bills = Bill.query.filter(
                Bill.is_paid == True,
                Bill.frequency.in_(['weekly', 'monthly', 'quarterly', 'yearly'])
            ).all()
            
            logger.info(f"[RECURRING CHECK] Found {len(recurring_bills)} paid recurring bills")
            
            for bill in recurring_bills:
                next_due_date = calculate_next_due_date(bill)
                
                if next_due_date:
                    # Check if a bill already exists for this next due date
                    existing_bill = Bill.query.filter(
                        Bill.user_id == bill.user_id,
                        Bill.name == bill.name,
                        Bill.due_date == next_due_date,
                        Bill.is_paid == False
                    ).first()
                    
                    if not existing_bill and next_due_date >= current_date:
                        # Create new bill instance for the next period
                        new_bill = Bill(
                            user_id=bill.user_id,
                            name=bill.name,
                            amount=bill.amount,
                            due_date=datetime.combine(next_due_date, datetime.min.time()),
                            category=bill.category,
                            frequency=bill.frequency,
                            is_paid=False,
                            notes=f"Auto-generated from recurring bill",
                            enable_whatsapp=bill.enable_whatsapp,
                            enable_call=bill.enable_call,
                            enable_sms=bill.enable_sms,
                            enable_local_notification=bill.enable_local_notification
                        )
                        
                        db.session.add(new_bill)
                        logger.info(f"[RECURRING CHECK] Created new recurring bill for {bill.name} due on {next_due_date}")
            
            try:
                db.session.commit()
                logger.info("[RECURRING CHECK] Completed recurring bills check")
            except Exception as e:
                logger.error(f"[RECURRING CHECK ERROR] Failed to save recurring bills: {str(e)}")
                db.session.rollback()

    def calculate_next_due_date(bill):
        """
        Calculate the next due date based on bill frequency.
        """
        if not bill.due_date:
            return None
            
        bill_due_date = bill.due_date.date() if hasattr(bill.due_date, 'date') else bill.due_date
        current_date = datetime.now().date()
        
        if bill.frequency == 'weekly':
            next_date = bill_due_date + timedelta(weeks=1)
        elif bill.frequency == 'monthly':
            next_date = bill_due_date + relativedelta(months=1)
        elif bill.frequency == 'quarterly':
            next_date = bill_due_date + relativedelta(months=3)
        elif bill.frequency == 'yearly':
            next_date = bill_due_date + relativedelta(years=1)
        else:
            return None
        
        # Only return if the next date is in the future
        if next_date > current_date:
            logger.debug(f"[NEXT DUE] Calculated next due date for {bill.name}: {next_date}")
            return next_date
        
        return None

    def check_overdue_bills():
        """This job runs daily to check for overdue bills."""
        with app.app_context():
            logger.info("[OVERDUE CHECK] Starting overdue bills check")
            print("Scheduler: Checking for overdue bills...")
            
            current_datetime = datetime.now()
            overdue_bills = Bill.query.filter(
                Bill.is_paid == False,
                Bill.due_date < current_datetime
            ).all()
            
            logger.info(f"[OVERDUE CHECK] Found {len(overdue_bills)} overdue bills")
            
            for bill in overdue_bills:
                logger.debug(f"[OVERDUE PROCESS] Processing overdue bill: {bill.id} - {bill.name}")
                
                user = User.query.get(bill.user_id)
                if not user:
                    logger.warning(f"[OVERDUE PROCESS] User not found for bill {bill.id} (user_id: {bill.user_id})")
                    continue
                
                if not user.phone_number:
                    logger.warning(f"[OVERDUE PROCESS] No phone number for user {user.id}")
                    continue
                
                days_overdue = (current_datetime - bill.due_date).days
                logger.debug(f"[OVERDUE PROCESS] Bill {bill.id} is {days_overdue} days overdue")
                
                # Only send overdue reminders for bills that were due recently
                if days_overdue <= 7:
                    message = f"URGENT: Your {bill.name} payment of ₹{bill.amount} is {days_overdue} days overdue. Please pay immediately to avoid late fees."
                    logger.info(f"[OVERDUE ALERT] Sending overdue alert for bill {bill.id} ({days_overdue} days overdue)")
                    
                    if bill.enable_whatsapp:
                        logger.info(f"[OVERDUE WHATSAPP] Sending WhatsApp overdue reminder to {user.phone_number}")
                        try:
                            send_whatsapp_reminder(user.phone_number, message)
                            logger.info(f"[OVERDUE WHATSAPP] Successfully sent overdue reminder for bill {bill.id}")
                        except Exception as e:
                            logger.error(f"[OVERDUE WHATSAPP ERROR] Failed to send overdue reminder for bill {bill.id}: {str(e)}")
                    else:
                        logger.debug(f"[OVERDUE WHATSAPP] WhatsApp disabled for bill {bill.id}")
                else:
                    logger.debug(f"[OVERDUE SKIP] Bill {bill.id} is {days_overdue} days overdue (>7 days, skipping)")
            
            logger.info(f"[OVERDUE CHECK] Completed overdue bills check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Add the jobs to the scheduler
    logger.info("[SCHEDULER CONFIG] Adding reminder_checker job (runs every minute)")
    scheduler.add_job(
        func=check_and_send_reminders,
        trigger="cron",
        minute="*",
        id='reminder_checker',
        replace_existing=True
    )
    
    logger.info("[SCHEDULER CONFIG] Adding recurring_bills_handler job (runs daily at 00:00)")
    scheduler.add_job(
        func=handle_recurring_bills,
        trigger="cron",
        hour=0,
        minute=0,
        id='recurring_bills_handler',
        replace_existing=True
    )
    
    logger.info("[SCHEDULER CONFIG] Adding overdue_checker job (runs daily at 10:00)")
    scheduler.add_job(
        func=check_overdue_bills,
        trigger="cron",
        hour=10,
        minute=0,
        id='overdue_checker',
        replace_existing=True
    )
    
    # Start the scheduler if it's not already running
    if not scheduler.running:
        logger.info("[SCHEDULER START] Starting the scheduler")
        scheduler.start()
        logger.info("[SCHEDULER START] Scheduler started successfully")
    else:
        logger.info("[SCHEDULER START] Scheduler already running")
