"""
AI-INFLUENCER-OS — Script & Voice Generation (Gemini Free + edge-tts)
Generates viral hooks, captions, hashtags, and optional voiceover.
"""

import os
import json
import asyncio
from typing import Optional

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False


def generate_script_and_caption(
    topic: str,
    dress: str = "glamorous outfit",
    api_key: Optional[str] = None,
) -> dict:
    """Generate viral Reel script, hook, caption, and hashtags using Gemini Free API."""
    key = api_key or os.environ.get("GEMINI_API_KEY")

    if HAS_GENAI and key and key != "CHANGE_ME":
        try:
            client = genai.Client(api_key=key)
            prompt = (
                f"You are a top Instagram AI fashion & dance creator. Write content for a Reel.\n"
                f"Topic: {topic}\n"
                f"Outfit: {dress}\n\n"
                "Return STRICTLY a JSON object with keys:\n"
                "- 'hook': 3-second bold text for screen\n"
                "- 'narration': short spoken voice line (max 15 words)\n"
                "- 'caption': engaging caption with emoji\n"
                "- 'hashtags': list of 15 trending hashtags\n"
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            print(f"Gemini generation fallback: {e}")

    # High quality fallback
    return {
        "hook": f"Wait till the end! ✨",
        "narration": f"Feeling unstoppable in this {dress} today!",
        "caption": f"When the music takes over 💃✨ Loving this {dress} vibe! Drop a ❤️ if you're feeling this energy!",
        "hashtags": ["#reels", "#dance", "#trending", "#viral", "#ootd", "#fashion", "#explore", "#fyp"],
    }


async def generate_voiceover_edge(text: str, output_path: str, voice: str = "hi-IN-SwaraNeural") -> str:
    """Generate crystal-clear voiceover using Microsoft edge-tts (100% free)."""
    if not HAS_EDGE_TTS:
        print("edge-tts not installed, skipping voiceover.")
        return ""

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"✅ Voiceover saved via edge-tts: {output_path}")
        return output_path
    except Exception as e:
        print(f"edge-tts failed: {e}")
        return ""
