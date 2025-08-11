import os
import tempfile
from elevenlabs import ElevenLabs
from elevenlabs import play, save, stream
from elevenlabs import VoiceSettings
from dotenv import load_dotenv
import logging


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from a .env file
logger.info("[ELEVENLABS INIT] Loading environment variables")
load_dotenv()

# Set your ElevenLabs API key
api_key = os.getenv("ELEVENLABS_API_KEY")
logger.info(f"[ELEVENLABS INIT] API key loaded: {'*' * 30 + api_key[-4:] if api_key else 'NOT SET'}")

try:
    # Initialize client with API key
    client = ElevenLabs(api_key=api_key)
    logger.info("[ELEVENLABS INIT] Client successfully initialized")
except Exception as e:
    logger.error(f"[ELEVENLABS INIT ERROR] Failed to initialize client: {str(e)}")

def generate_voice_audio(text: str, voice_id: str = None):
    """Generate voice audio using ElevenLabs API."""
    logger.info("[ELEVENLABS GENERATE] Starting audio generation")
    logger.debug(f"[ELEVENLABS GENERATE] Text length: {len(text)} characters")
    logger.debug(f"[ELEVENLABS GENERATE] Text preview: {text[:100]}...")
    logger.debug(f"[ELEVENLABS GENERATE] Voice ID provided: {voice_id}")
    
    try:
        # Use default voice ID if none is provided
        if not voice_id:
            default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            voice_id = default_voice_id
            logger.info(f"[ELEVENLABS GENERATE] Using default voice ID: {voice_id}")
        else:
            logger.info(f"[ELEVENLABS GENERATE] Using provided voice ID: {voice_id}")
        
        # Log voice settings
        voice_settings = VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.5,
            use_speaker_boost=True
        )
        logger.debug(f"[ELEVENLABS GENERATE] Voice settings - Stability: 0.5, Similarity: 0.75, Style: 0.5, Speaker boost: True")
        
        # Generate audio using new client method
        logger.info("[ELEVENLABS GENERATE] Calling ElevenLabs API to generate audio")
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            voice_settings=voice_settings
        )
        logger.info("[ELEVENLABS GENERATE] Audio generated successfully")
        
        # Save to temporary file
        logger.debug("[ELEVENLABS GENERATE] Creating temporary file for audio")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            temp_path = tmp_file.name
            logger.debug(f"[ELEVENLABS GENERATE] Temporary file path: {temp_path}")
            
            logger.info("[ELEVENLABS GENERATE] Saving audio to temporary file")
            save(audio, temp_path)
            
            # Verify file was created and get size
            if os.path.exists(temp_path):
                file_size = os.path.getsize(temp_path)
                logger.info(f"[ELEVENLABS GENERATE] Audio file saved successfully. Size: {file_size} bytes")
            else:
                logger.error(f"[ELEVENLABS GENERATE] Audio file not found after save: {temp_path}")
            
            return {"success": True, "audio_path": temp_path}
            
    except Exception as e:
        logger.error(f"[ELEVENLABS GENERATE ERROR] Failed to generate audio: {str(e)}", exc_info=True)
        logger.debug(f"[ELEVENLABS GENERATE ERROR] Error type: {type(e).__name__}")
        print(f"Error generating ElevenLabs audio: {e}")
        return {"success": False, "error": str(e)}

def get_available_voices():
    """Get list of available voices from ElevenLabs."""
    logger.info("[ELEVENLABS VOICES] Fetching available voices")
    
    try:
        logger.debug("[ELEVENLABS VOICES] Calling ElevenLabs API to get voices")
        # Use new client method to get voices
        voices_response = client.voices.search()
        available_voices = voices_response.voices
        
        logger.info(f"[ELEVENLABS VOICES] Retrieved {len(available_voices)} voices")
        
        voice_list = []
        for voice in available_voices:
            voice_data = {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "category": voice.category,
            }
            voice_list.append(voice_data)
            logger.debug(f"[ELEVENLABS VOICES] Voice: {voice.name} (ID: {voice.voice_id}, Category: {voice.category})")
        
        logger.info(f"[ELEVENLABS VOICES] Successfully processed {len(voice_list)} voices")
        
        # Log categories summary
        categories = {}
        for v in voice_list:
            cat = v.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        logger.debug(f"[ELEVENLABS VOICES] Voice categories: {categories}")
        
        return {"success": True, "voices": voice_list}
        
    except Exception as e:
        logger.error(f"[ELEVENLABS VOICES ERROR] Failed to get voices: {str(e)}", exc_info=True)
        logger.debug(f"[ELEVENLABS VOICES ERROR] Error type: {type(e).__name__}")
        print(f"Error getting ElevenLabs voices: {e}")
        return {"success": False, "error": str(e)}