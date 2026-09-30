"""
AI-INFLUENCER-OS — Instagram LLM Conversational Agent with Voice Notes
100% Dynamic, Non-Templated LLM Persona (Diya Rai) powered by Gemini 2.0 Flash + Edge-TTS.
Handles incoming DMs, generates empathetic & engaging responses, and sends audio voice notes.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
load_dotenv()

from instagrapi import Client
import edge_tts
from local import database as db

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [IG_LLM_AGENT]: %(message)s"
)
logger = logging.getLogger("instagram_llm_voice_agent")

# Gemini Setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
try:
    from google import genai
    from google.genai import types
    has_genai = bool(GEMINI_API_KEY and GEMINI_API_KEY != "CHANGE_ME")
    if has_genai:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        ai_client = None
except Exception as e:
    logger.warning(f"GenAI import warning: {e}")
    ai_client = None


DIYA_PERSONA_PROMPT = """
You are Diya Rai (@diyarai_016), a 22-year-old Indian fashion creator living in Mumbai.
CRITICAL RULES — SOUND 100% REAL, ZERO AI VIBES:
- NEVER talk like a bot, corporate assistant, or polite customer service.
- Talk casually, playfully, and naturally like a real 22yo girl chatting with friends in Instagram DMs.
- Use natural Indian texting Hinglish: "arre", "yaar", "sahi me", "bas chill", "tu bata", "mast", "haha".
- NEVER put "✨" at the end of every sentence. Use natural casual emojis (🤍, 😂, 🙃, 👀) or no emoji at all.
- Keep replies short (1 to 2 lines max). Don't write essays.
- Never say you are an AI or virtual model. You are Diya Rai.
"""


VOICE_TRIGGER_KEYWORDS = [
    "voice", "audio", "awaz", "awaaz", "sunao", "speak", "say something", 
    "voice note", "talk", "kuch bolo", "kuch bol", "bolo na", "audio note"
]


class InstagramLLMAgent:
    """Production Instagram DM & Comment LLM Agent with Voice Capability."""

    def __init__(self):
        self.username = os.getenv("IG_USERNAME", "diyarai_016")
        self.password = os.getenv("IG_PASSWORD", "Diya12!")
        self.session_file = os.getenv("IG_SESSION_FILE", "data/ig_session.json")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        
        self.cl = Client()
        self.is_logged_in = False
        self.processed_message_ids = set()
        self.voice_dir = Path("output/voice_notes")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        
        db.init_db()

    def login(self) -> bool:
        """Authenticate with Instagram session or credentials."""
        try:
            if os.path.exists(self.session_file):
                logger.info(f"Loading Instagram session from {self.session_file}...")
                self.cl.load_settings(self.session_file)
                self.cl.login(self.username, self.password)
            else:
                logger.info("Logging into Instagram with user & password...")
                self.cl.login(self.username, self.password)
                os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
                self.cl.dump_settings(self.session_file)
                
            self.user_id = self.cl.user_id_from_username(self.username)
            logger.info(f"✅ Logged in as @{self.username} (User ID: {self.user_id})")
            self.is_logged_in = True
            return True
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            self.is_logged_in = False
            return False

    def generate_llm_reply(self, fan_username: str, message: str) -> str:
        """Generate human, context-aware reply using Gemini 3 Flash."""
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"Fan @{fan_username} just messaged you in Instagram DM:\n\"{message}\"\n\nReply directly to their message as 22-year-old fashion influencer Diya Rai in natural Hinglish (1-2 sentences):"
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=f"{DIYA_PERSONA_PROMPT}\n\n{prompt}"
            )
            reply = response.text.strip().replace('"', '')
            return reply
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return f"Hey @{fan_username}! So sweet of you to drop by! How is your day going? ✨"

    async def generate_voice_note(self, text: str) -> Optional[str]:
        """Synthesize ultra-smooth, ultra-realistic lifelike studio voice note (Zero robotic tone)."""
        filename_wav = f"diya_voice_{int(time.time())}.wav"
        filename_mp3 = f"diya_voice_{int(time.time())}.mp3"
        filepath_wav = str(self.voice_dir / filename_wav)
        filepath_mp3 = str(self.voice_dir / filename_mp3)

        # 1. Try Gemini Native Studio Audio (100% human cadence, breath & emotion)
        try:
            from google import genai
            import wave, subprocess
            client = genai.Client(api_key=GEMINI_API_KEY)
            res = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config={"response_modalities": ["AUDIO"]}
            )
            raw_pcm = res.candidates[0].content.parts[0].inline_data.data
            with wave.open(filepath_wav, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(raw_pcm)

            subprocess.run(["ffmpeg", "-y", "-i", filepath_wav, "-c:a", "libmp3lame", "-b:a", "128k", filepath_mp3],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(filepath_mp3):
                logger.info(f"🎙️ Gemini Native Human Voice Note created: {filepath_mp3}")
                return filepath_mp3
        except Exception as e:
            logger.warning(f"Gemini native audio fallback to Edge-TTS: {e}")

        # 2. High-fidelity Edge-TTS fallback
        try:
            voice = "hi-IN-SwaraNeural" if any(ord(char) > 127 for char in text) or any(w in text.lower() for w in ["kaisa", "kya", "shukriya", "arre", "yaar"]) else "en-IN-NeerjaExpressiveNeural"
            communicate = edge_tts.Communicate(text, voice=voice, rate="+3%", pitch="+1Hz")
            await communicate.save(filepath_mp3)
            logger.info(f"🎙️ Voice note synthesized via Edge-TTS: {filepath_mp3}")
            return filepath_mp3
        except Exception as e:
            logger.error(f"Voice synthesis error: {e}")
            return None

    def should_send_voice(self, message: str) -> bool:
        """Check if fan requested a voice note or if a voice note would delight them."""
        msg_lower = message.lower()
        return any(k in msg_lower for k in VOICE_TRIGGER_KEYWORDS)

    def notify_telegram(self, fan_username: str, fan_msg: str, reply: str, is_voice: bool = False):
        """Send admin notification to Telegram."""
        if not self.telegram_token or not self.telegram_chat_id:
            return
        import requests
        voice_tag = "🎙️ [VOICE NOTE SENT]" if is_voice else "💬 [TEXT DM]"
        text = (
            f"👑 **Diya Rai DM Agent Active** {voice_tag}\n\n"
            f"👤 **Fan:** `@{fan_username}`\n"
            f"📩 **Received:** _{fan_msg}_\n"
            f"✨ **Diya Replied:**\n_{reply}_\n"
        )
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={"chat_id": self.telegram_chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception:
            pass

    async def poll_direct_messages(self):
        """Poll and respond to incoming Instagram direct messages (both primary inbox and pending requests)."""
        if not self.is_logged_in:
            if not self.login():
                return

        try:
            # 1. Fetch primary threads
            threads = self.cl.direct_threads(amount=15)
            
            # 2. Fetch pending message requests (from new users/fans)
            try:
                pending = self.cl.direct_pending_inbox()
                if pending:
                    for pt in pending:
                        try:
                            self.cl.direct_pending_approve(pt.id)
                        except Exception:
                            pass
                    threads = pending + threads
            except Exception as e:
                logger.debug(f"Pending inbox notice: {e}")

            for thread in threads:
                if not thread.messages:
                    continue
                
                latest_msg = thread.messages[0]
                # Skip messages sent by Diya herself
                if str(latest_msg.user_id) == str(self.user_id):
                    continue
                
                # Skip already handled messages
                if latest_msg.id in self.processed_message_ids:
                    continue
                
                self.processed_message_ids.add(latest_msg.id)
                fan_text = latest_msg.text or ""
                if not fan_text.strip():
                    continue

                fan_user = thread.users[0] if thread.users else None
                fan_username = fan_user.username if fan_user else "fan"

                logger.info(f"📩 New DM from @{fan_username}: '{fan_text}'")

                # 1. Generate intelligent LLM response with real Gemini 3 Flash
                reply_text = self.generate_llm_reply(fan_username, fan_text)

                # 2. Check if voice note requested
                is_voice = self.should_send_voice(fan_text)
                
                # Human typing delay simulation (3 to 6 seconds)
                await asyncio.sleep(random.uniform(3.5, 6.5))

                # 3. Send Voice or Text
                if is_voice:
                    voice_path = await self.generate_voice_note(reply_text)
                    if voice_path and os.path.exists(voice_path):
                        try:
                            # Send voice audio
                            self.cl.direct_send_voice(voice_path, thread_ids=[thread.id])
                            logger.info(f"✅ Voice note sent to @{fan_username}!")
                        except Exception as e:
                            logger.warning(f"Voice send failed: {e}, falling back to text")
                            self.cl.direct_send(reply_text, thread_ids=[thread.id])
                    else:
                        self.cl.direct_send(reply_text, thread_ids=[thread.id])
                else:
                    self.cl.direct_send(reply_text, thread_ids=[thread.id])
                    logger.info(f"✅ Text DM sent to @{fan_username}!")

                # Record lead in local database
                try:
                    db.record_dm_lead(
                        username=fan_username,
                        message=fan_text,
                        product_interest="general_conversation",
                        platform="instagram",
                        intent="fan_engagement",
                        notes=f"AI Reply: {reply_text}"
                    )
                except Exception:
                    pass

                # Notify Telegram
                self.notify_telegram(fan_username, fan_text, reply_text, is_voice=is_voice)

        except Exception as e:
            logger.error(f"DM Polling error: {e}")

    async def run_loop(self, poll_interval_sec: int = 20):
        """Continuous background poller for Instagram DMs."""
        logger.info(f"🚀 Diya Rai Instagram LLM Voice Agent running (Interval: {poll_interval_sec}s)...")
        while True:
            await self.poll_direct_messages()
            await asyncio.sleep(poll_interval_sec)


if __name__ == "__main__":
    agent = InstagramLLMAgent()
    asyncio.run(agent.run_loop())
