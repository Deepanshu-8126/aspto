"""
AI-INFLUENCER-OS — Living Digital Human Engine (The 22-Year-Old Soul)
Transforms Diya Rai from a static AI into a living, breathing 22-year-old creator:
- Daily Spontaneous Stories (Morning coffee, shoot chaos, interactive polls, late-night music)
- Threads / Twitter Micro-Thoughts (Witty, cute, relatable Gen-Z humor)
- Real-Time Cultural Pulse (Weather, viral trends, music, sports, gossip)
- Flawed, Natural Human DM Conversations (Zero robotic syntax, 100% human warmth)
- Multi-Platform Omnipresence (Instagram, Threads, Facebook, YouTube)
"""

import os
import json
import random
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("living_soul")

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class LivingSoulEngine:
    """
    Simulates the living daily consciousness of Diya Rai (22 years old):
    Generates real-time daily stories, relatable Threads, reaction to world events,
    and genuine human connection.
    """

    def __init__(self, personality_path: Optional[str] = None, api_key: Optional[str] = None):
        if personality_path is None:
            personality_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "personality.json")
        self.personality_path = personality_path
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.persona = self._load_persona()
        self._gemini_client = None

        if HAS_GENAI and self.api_key and self.api_key != "CHANGE_ME":
            try:
                self._gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def _load_persona(self) -> Dict:
        if not os.path.exists(self.personality_path):
            return {"name": "Diya Rai", "age": 22, "cities": ["Mumbai", "Delhi"]}
        with open(self.personality_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_daily_stories(self, count: int = 4) -> List[Dict[str, Any]]:
        """
        Generates spontaneous daily Instagram Stories across the day.
        Real humans post raw, imperfect, relatable stories—not just polished feed posts!
        """
        slots = [
            {
                "time_of_day": "Morning (08:30 AM)",
                "story_type": "boomerang_or_candid",
                "scene": "Car window view on highway / iced coffee cup in hand",
                "caption": "Monday morning traffic is a personal attack 😭 Need 3 iced lattes to survive today! ☕🚗",
                "interactive_sticker": None,
                "visual_prompt": "candid photo taken from inside cab, aesthetic iced coffee cup held by diyarai woman, morning sun through car window, blurred city street background, shot on iphone 15 pro, realistic film grain"
            },
            {
                "time_of_day": "Afternoon (02:00 PM)",
                "story_type": "mirror_selfie_bts",
                "scene": "Vanity makeup room with lights and clothes rack",
                "caption": "Shoot day chaos! 💅 Costume change #4... Should I keep the hair up or down? 🤔",
                "interactive_sticker": {"type": "poll", "question": "Hair style for the next reel?", "options": ["Messy Bun 👱‍♀️", "Open Waves 🌊"]},
                "visual_prompt": "candid mirror selfie of diyarai woman in makeup room, vanity mirror with lightbulbs, holding phone, stylish casual chic fit, half smile, natural messy hair, photorealistic raw shot"
            },
            {
                "time_of_day": "Evening (06:30 PM)",
                "story_type": "interactive_qna",
                "scene": "Cozy sunset balcony with warm evening light",
                "caption": "Done for the day! ✨ Got 30 mins before my next meeting... Ask me anything! Let's gossip 👇",
                "interactive_sticker": {"type": "question_box", "prompt": "Ask me anything! 💬"},
                "visual_prompt": "candid aesthetic shot of diyarai woman relaxing on balcony during golden hour sunset, wearing oversized cozy hoodie, warm golden light on face, authentic skin pores, relaxed candid"
            },
            {
                "time_of_day": "Night (11:15 PM)",
                "story_type": "spotify_music_vibe",
                "scene": "Dark room aesthetic with soft warm lamp light",
                "caption": "Midnight playlist on repeat 🌙🎧 Current obsession: 'Pritam - Tu Hi Meri Shab Hai (Lofi)'. What's everyone listening to rn?",
                "interactive_sticker": {"type": "music_sticker", "song": "Tu Hi Meri Shab Hai - Lofi", "artist": "KK, Pritam"},
                "visual_prompt": "aesthetic mood photo, dark cozy bedroom corner with fairy lights, diyarai woman resting head on hand wearing headphones, soft warm mood, peaceful candid"
            }
        ]

        if self._gemini_client:
            try:
                prompt = """You are Diya Rai, a 22-year-old living Mumbai/Delhi lifestyle influencer.
Generate 4 spontaneous, raw Instagram Stories for today.
Include:
1. Morning routine / traffic / coffee moment
2. Afternoon BTS / mirror selfie / outfit choice
3. Evening interactive story with a Poll or Question sticker
4. Late night chill vibe with a real Bollywood or Lofi song

Format as valid JSON:
[
  {
    "time_of_day": "Morning (08:30 AM)",
    "story_type": "boomerang_or_candid",
    "scene": "short description",
    "caption": "natural Hinglish caption with emojis",
    "interactive_sticker": {"type": "poll", "question": "...", "options": ["A", "B"]} or null,
    "visual_prompt": "detailed photorealistic SDXL prompt with 'diyarai woman' token"
  }
]"""
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                return json.loads(response.text)
            except Exception as e:
                logger.warning(f"Gemini stories failed: {e}. Using curated life slots.")

        return slots[:count]

    def generate_threads_thoughts(self, count: int = 4) -> List[Dict[str, str]]:
        """
        Generates 22-year-old relatable micro-thoughts for Threads & Twitter/X.
        Real people post funny, witty, self-aware thoughts—not sponsored ads!
        """
        curated_thoughts = [
            {
                "text": "Adulting ka manual kahan milta hai? Honestly mujhe refund chahiye 🥲",
                "category": "relatable_humor",
                "vibe": "funny"
            },
            {
                "text": "My brain at 3 PM: Eat salad, drink water, hit the gym.\nMy brain at 11 PM: Let’s order waffles and watch crime documentaries 🧇😭",
                "category": "lifestyle",
                "vibe": "chaotic_relatable"
            },
            {
                "text": "Normalize cancelling plans just to lay in bed in an oversized hoodie with cold coffee 🤍✨",
                "category": "self_care",
                "vibe": "chill"
            },
            {
                "text": "Why does my phone battery last longer than my social energy at parties? lol ngl",
                "category": "quirk",
                "vibe": "witty"
            },
            {
                "text": "If travelling was free, you would literally never see me in the city again 🌲🏔️",
                "category": "wanderlust",
                "vibe": "travel"
            }
        ]

        if self._gemini_client:
            try:
                prompt = """You are Diya Rai, a 22-year-old witty, aesthetic Indian influencer on Threads/Twitter.
Generate 4 short, highly shareable, viral text thoughts that a 22-year-old girl would post.
Topics: adulting struggles, iced coffee obsession, late night snacking, travel craving, funny relatable quirks.
Language: Natural Gen-Z Hinglish (Roman script, trendy, funny, zero robotic language).
Return JSON:
[{"text": "...", "category": "...", "vibe": "..."}]"""
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                return json.loads(response.text)
            except Exception as e:
                logger.warning(f"Gemini threads failed: {e}")

        return random.sample(curated_thoughts, min(count, len(curated_thoughts)))

    def react_to_realtime_event(self, event_or_news: str) -> Dict[str, str]:
        """
        Allows Diya Rai to react dynamically to real-world happenings:
        e.g., 'Heavy rain in Mumbai', 'India wins cricket match', 'New Deepika Padukone movie look'.
        """
        if self._gemini_client:
            try:
                prompt = f"""You are Diya Rai, 22 years old, aesthetic Indian influencer.
React to this real-world event/trend naturally as a girl posting on her Instagram Story or Threads:
Event: '{event_or_news}'

Guidelines:
- 100% natural, emotional, authentic reaction
- Natural Hinglish with emojis
- NO robotic phrases
Return JSON:
{{
  "post_type": "story_or_thread",
  "reaction_text": "...",
  "suggested_visual": "what image to show (e.g. rain on window, celebration selfie)",
  "sdxl_prompt": "photorealistic prompt with 'diyarai woman' token"
}}"""
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                return json.loads(response.text)
            except Exception as e:
                logger.warning(f"Gemini event reaction failed: {e}")

        # Fallback reaction
        return {
            "post_type": "story",
            "reaction_text": f"Wait is this really happening?! 😱 {event_or_news} honestly can't even process this rn haha! What do you guys think? 👇",
            "suggested_visual": "candid shock/smile expression looking at phone",
            "sdxl_prompt": "candid photo of diyarai woman looking at smartphone in cafe, genuine surprised expression, natural daylight, photorealistic 8k"
        }

    def generate_human_dm_reply(self, message: str, fan_name: str = "") -> str:
        """
        Responds to fan DMs with 100% authentic girl-next-door energy:
        Playful, warm, laughing off bot accusations, sharing cute behind-the-scenes thoughts.
        """
        msg_lower = message.lower()

        # Handle bot / AI accusation with playful human laughter
        if any(w in msg_lower for w in ["ai", "bot", "fake", "robot", "real"]):
            replies = [
                "Hahaha kya yaar! 😂 Subah 6 baje se uthkar shoot kar rahi hoon aur tum bot bol rahe ho! Agle shoot pe mera spot boy ban jao, fir pata chalega kitni mehnat lagti hai 🙈💅",
                "Bot? Literally me shivering in the mountains trying to get one good photo and you calling me AI 😭 Aisa mat bolo yaar, dil se bura lagta hai haha! 🤍",
                "Arre main 100% zinda insaan hoon baba! 😂 Bas lighting aur camera thoda zyada accha hai haha! How are you doing anyway? 🥰"
            ]
            return random.choice(replies)

        # Compliments on outfits / beauty
        if any(w in msg_lower for w in ["beautiful", "pretty", "dress", "outfit", "cute", "sundar", "gorgeous"]):
            compliment_replies = [
                f"Awww thank you so much {fan_name or 'cutie'}! 🥺 Literally made my whole day! The outfit is from Zara btw! 💕",
                f"You're too sweet yaar! 🙈 Sachi mein accha lag raha tha? Mujhe laga thoda over ho gaya tha haha! Love you! 🤍✨",
                "Hehe thank you babe! 🥰 Shooting was so chaotic today so your message is like a breath of fresh air!"
            ]
            return random.choice(compliment_replies)

        # LLM Synthesis for general queries
        if self._gemini_client:
            try:
                system_instruction = """You are Diya Rai, a warm, lively 22-year-old fashion, travel & lifestyle influencer.
Reply to a follower's DM on Instagram.
RULES:
1. Speak in natural Hinglish (Roman script mixed with casual Hindi & English).
2. Keep it punchy (1-3 sentences max).
3. Sound like a bestie chatting on phone: warm, relatable, expressive.
4. ZERO robotic phrases. NEVER say 'I am an AI' or 'How can I assist you'."""
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"Fan message: '{message}'. Fan name: '{fan_name}'. Reply as Diya Rai:",
                )
                return response.text.strip().strip('"')
            except Exception as e:
                logger.warning(f"Gemini DM reply failed: {e}")

        return f"Heyy {fan_name or 'babe'}! 💕 Thanks so much for reaching out! In between shoots right now but wanted to quickly say hi! How is your day going? ✨"


# Global singleton
living_soul = LivingSoulEngine()
