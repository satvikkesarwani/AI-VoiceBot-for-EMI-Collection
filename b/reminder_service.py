# Place this at the very top of the file
from dotenv import load_dotenv
load_dotenv()
import os
import requests
from datetime import datetime
from twilio.rest import Client
import google.generativeai as genai
from config import Config
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure Gemini
logger.info("[GEMINI CONFIG] Configuring Gemini AI")
genai.configure(api_key=Config.GOOGLE_API_KEY)
logger.debug(f"[GEMINI CONFIG] API key configured: {'*' * 10 + Config.GOOGLE_API_KEY[-4:] if Config.GOOGLE_API_KEY else 'NOT SET'}")

def generate_reminder_message(name, bill_data):
    """Generate reminder message using Gemini AI"""
    logger.info(f"[MESSAGE GEN] Starting message generation for user: {name}")
    logger.debug(f"[MESSAGE GEN] Bill data received: {bill_data}")

    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')

    current_hour = datetime.now().hour
    logger.debug(f"[MESSAGE GEN] Current hour: {current_hour}")

    if 5 <= current_hour < 12:
        greeting = "Good morning"
    elif 12 <= current_hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    logger.debug(f"[MESSAGE GEN] Selected greeting: {greeting}")

    prompt = f"""
    You are a friendly financial assistant creating a reminder message.

    Create a natural, friendly reminder with this structure:
    1. Start with: "Hey {name}, {greeting}."
    2. Remind about the bill payment:
       - Bill: {bill_data.get('name')}
       - Amount: ₹{bill_data.get('amount')}
       - Due Date: {bill_data.get('due_date')}
    3. End with: "Hope you have a nice day."

    Keep it brief and friendly.
    """

    logger.debug(f"[MESSAGE GEN] Generated prompt for Gemini: {prompt[:200]}...")

    try:
        logger.info("[MESSAGE GEN] Calling Gemini AI to generate message")
        response = gemini_model.generate_content(prompt)
        generated_message = response.text.strip()
        logger.info(f"[MESSAGE GEN] Successfully generated message via Gemini")
        logger.debug(f"[MESSAGE GEN] Generated message: {generated_message}")
        return generated_message
    except Exception as e:
        logger.error(f"[MESSAGE GEN ERROR] Gemini generation failed: {str(e)}", exc_info=True)
        # Fallback message
        fallback_message = (
            f"Hi {name}, this is a reminder that your payment for '{bill_data.get('name')}' "
            f"is due on {bill_data.get('due_date')}. Amount due: ₹{bill_data.get('amount')}."
        )
        logger.info("[MESSAGE GEN] Using fallback message due to Gemini error")
        logger.debug(f"[MESSAGE GEN] Fallback message: {fallback_message}")
        return fallback_message

def send_whatsapp_reminder(phone_number, message_body):
    """Send WhatsApp reminder using Twilio"""
    logger.info(f"[WHATSAPP] Starting WhatsApp reminder to: {phone_number}")
    logger.debug(f"[WHATSAPP] Message length: {len(message_body)} characters")
    logger.debug(f"[WHATSAPP] Message preview: {message_body[:100]}...")

    # FIX: Correct the phone number format by prepending +91 if not present
    if not phone_number.startswith('+91'):
        phone_number = '+91' + phone_number.replace(' ', '')

    try:
        # --- NEW DEBUG CODE ---
        print("--- DEBUG: CHECKING TWILIO KEYS ---")
        print(f"Account SID from Config: {Config.TWILIO_ACCOUNT_SID}")
        print(f"Auth Token from Config: {Config.TWILIO_AUTH_TOKEN}")
        print("-----------------------------------")
        # --- END OF NEW DEBUG CODE ---

        logger.debug(f"[WHATSAPP] Twilio Account SID: {'*' * 30 + Config.TWILIO_ACCOUNT_SID[-4:] if Config.TWILIO_ACCOUNT_SID else 'NOT SET'}")
        logger.debug(f"[WHATSAPP] Twilio Auth Token: {'*' * 30 + Config.TWILIO_AUTH_TOKEN[-4:] if Config.TWILIO_AUTH_TOKEN else 'NOT SET'}")
        logger.debug(f"[WHATSAPP] WhatsApp From Number: {Config.TWILIO_WHATSAPP_FROM}")

        logger.info("[WHATSAPP] Creating Twilio client")
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)

        formatted_to = f'whatsapp:{phone_number}'
        logger.debug(f"[WHATSAPP] Formatted recipient: {formatted_to}")

        logger.info("[WHATSAPP] Sending message via Twilio")
        message = client.messages.create(
            body=message_body,
            from_=Config.TWILIO_WHATSAPP_FROM,
            to=formatted_to
        )

        logger.info(f"[WHATSAPP] Message sent successfully with SID: {message.sid}")
        logger.debug(f"[WHATSAPP] Message status: {message.status}")

        return {"success": True, "sid": message.sid}
    except Exception as e:
        logger.error(f"[WHATSAPP ERROR] Failed to send WhatsApp message: {str(e)}", exc_info=True)
        logger.debug(f"[WHATSAPP ERROR] Error type: {type(e).__name__}")
        return {"success": False, "error": str(e)}

def send_voice_call_reminder(phone_number, message_body):
    """Sends a voice call reminder using Bland AI"""
    logger.info(f"[BLAND AI] Starting voice call reminder to: {phone_number}")

    # FIX: Correct the phone number format by prepending +91 if not present
    if not phone_number.startswith('+91'):
        phone_number = '+91' + phone_number.replace(' ', '')

    # Bland AI API Endpoint
    url = "https://api.bland.ai/call"

    # FIX 1: The authorization header requires the "Bearer" prefix.
    headers = {
        "authorization": Config.BLAND_AI_API_KEY
    }

    # FIX 2: Using the stable 'voice_id' instead of the name 'voice'.
    data = {
        "phone_number": phone_number,
        "task": message_body,
        "voice_id": "e1289219-0ea2-4f22-a994-c542c2a48a0f"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        logger.info(f"[BLAND AI] Successfully triggered voice call: {response.json()}")
        return {"success": True, "details": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"[BLAND AI ERROR] Request failed: {str(e)}", exc_info=True)
        if hasattr(e, 'response') and e.response is not None:
            return {"success": False, "error": f"HTTP Error: {e.response.text}"}
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"[BLAND AI ERROR] An unexpected error occurred: {e}", exc_info=True)
        return {"success": False, "error": str(e)}