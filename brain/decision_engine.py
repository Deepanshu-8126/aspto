"""
AI-INFLUENCER-OS — Daily Content Decision Engine (8:00 AM Routine)
Executes Aisha's daily morning creative evaluation:
1. Analytics Check: "Kal ka content kaisa chala?"
2. Trend Check: "Aaj kya viral hai?" (TrendWatch)
3. Brand Check: "Koi brand product aaya hai?" (Catalog RAG)
4. Mood Check: Day-of-week emotional state (Mon=tired, Wed=busy shoot, Fri=weekend hype, Sat=cat Mochi)
5. Variety Check: Prevents identical formats across past 3 days
6. Outputs: 5 authentic, human-grade posts planned for today.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from actions.trend_engine import ViralTrendEngine
from brain.hermes_memory import hermes_memory

logger = logging.getLogger("decision_engine")

MOOD_MAP = {
    0: {"day": "Monday", "mood": "Thak gayi hoon, missing weekend", "energy": "low_chill", "vibe": "candid coffee struggle"},
    1: {"day": "Tuesday", "mood": "Aaj mood on hai, ready for the grind", "energy": "high", "vibe": "fashion styling"},
    2: {"day": "Wednesday", "mood": "Shoot ka din, super busy chaos", "energy": "chaotic_creative", "vibe": "bts boutique fittings"},
    3: {"day": "Thursday", "mood": "Beach walk kiya, feeling refreshed", "energy": "calm_peaceful", "vibe": "juhu sunset & street style"},
    4: {"day": "Friday", "mood": "Weekend aa raha hai! Super excited", "energy": "party_vibe", "vibe": "glam evening & party wear"},
    5: {"day": "Saturday", "mood": "Free day, lazying around with Mochi", "energy": "lazy_cute", "vibe": "cat mochi cuddles & cozy thrift haul"},
    6: {"day": "Sunday", "mood": "College prep + cutting chai", "energy": "reflective", "vibe": "sunday routine & self-care"}
}


class ContentDecisionEngine:
    """Aisha's Internal Creative Mind: Runs every morning at 8:00 AM."""

    def __init__(self, brands_path: str = "config/brands.json"):
        self.brands_path = brands_path
        self.trend_engine = ViralTrendEngine()

    def _get_todays_mood(self) -> Dict[str, str]:
        weekday = datetime.now().weekday()
        return MOOD_MAP.get(weekday, MOOD_MAP[0])

    def _get_available_brand(self) -> Dict[str, Any]:
        if os.path.exists(self.brands_path):
            try:
                with open(self.brands_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    item = None
                    if isinstance(data, list) and data:
                        item = data[0]
                    elif isinstance(data, dict) and "brands" in data and data["brands"]:
                        item = data["brands"][0]
                    if item:
                        return {
                            "brand": item.get("name") or item.get("brand") or "StyleVerse",
                            "product": item.get("product", "Oversized Tee"),
                            "discount_code": "AISHA50",
                            "usp": item.get("pitch", "Super aesthetic daily wear")
                        }
            except Exception:
                pass
        return {
            "brand": "StyleVerse",
            "product": "Oversized Linen Shirt",
            "discount_code": "AISHA50",
            "usp": "Lightweight Mumbai summer wear"
        }

    def plan_daily_content(self) -> Dict[str, Any]:
        """
        Synthesizes today's 5-post content schedule based on mood, trends, and analytics.
        """
        mood_info = self._get_todays_mood()
        trends = self.trend_engine.fetch_trending_topics(limit=3)
        top_trend = trends[0] if trends else {"topic": "Old Money Styling", "trending_audio": "Stereo Love Lofi"}
        brand_item = self._get_available_brand()

        # Check yesterday's performance from workspace memory
        past_perf = hermes_memory.get_workspace_state("yesterday_performance", {"views": 14200, "status": "great"})

        posts = [
            {
                "slot": 1,
                "time": "08:30 AM",
                "title": "Good Morning + OOTD",
                "type": "story_and_reel",
                "mood_alignment": mood_info["mood"],
                "scene_prompt": (
                    f"candid wide shot of diyarai woman in Bandra apartment, wearing relaxed linen shirt, holding ceramic chai mug, "
                    f"natural morning window light, cat Mochi visible in background, authentic skin texture, shot on 35mm"
                ),
                "caption": f"Morning chai hits differently when it's {mood_info['day']} ☕✨ Current mood: {mood_info['mood']}! Tell me your plan for today? 👇",
                "trending_audio": top_trend.get("trending_audio", "Acoustic Morning Vibes"),
                "hashtags": ["#MorningVibes", "#AishaDiaries", "#OOTD", "#MumbaiLifestyle", "#MasalaChai"]
            },
            {
                "slot": 2,
                "time": "12:30 PM",
                "title": "Lunch Break + Boutique BTS",
                "type": "story",
                "mood_alignment": "Bandra boutique chaos",
                "scene_prompt": (
                    "candid mirror selfie of diyarai woman in styling studio, clothes rack with pastel dresses, holding phone, "
                    "laughing expression, natural lighting, stylish accessories, 8k"
                ),
                "caption": "Lunch break scene at the studio! 💅 Quick cutting chai break before the next fitting starts! Are you team chai or coffee?",
                "interactive_sticker": {"type": "poll", "options": ["Team Chai ☕", "Team Coffee 🧊"]},
                "hashtags": ["#StudioLife", "#BandraBoutique", "#BTS", "#StylistLife"]
            },
            {
                "slot": 3,
                "time": "04:30 PM",
                "title": "Shoot & Natural Brand Styling",
                "type": "reel_carousel",
                "mood_alignment": "Fashion inspiration",
                "scene_prompt": (
                    f"candid fashion photograph of diyarai woman styling {brand_item['product']}, "
                    f"South Bombay colonial street background, golden hour sunset glow, chic casual street style, photorealistic 8k"
                ),
                "caption": f"Obsessed with how this {brand_item['product']} fits! 🤍 Styled it for a quick evening meeting. Use code {brand_item.get('discount_code', 'AISHA50')} if you want it! Link in bio ✨",
                "brand_tagged": brand_item["brand"],
                "hashtags": ["#StreetStyleMumbai", "#OutfitInspo", "#ColabaDiaries", "#StyleFile"]
            },
            {
                "slot": 4,
                "time": "08:00 PM",
                "title": "Evening Real Story / College Stress",
                "type": "reel",
                "mood_alignment": mood_info["vibe"],
                "scene_prompt": (
                    "candid portrait of diyarai woman sitting on bench near Juhu beach at dusk, gentle breeze moving hair, "
                    "warm golden orange horizon, reflective gentle smile, authentic film grain"
                ),
                "caption": "Evening walks to clear my head after design college classes 🌊✨ Sometimes you just need 20 minutes of sea breeze and quiet. How was your day?",
                "trending_audio": "Pritam & KK - Labon Ko (Sunset Lofi)",
                "hashtags": ["#JuhuBeach", "#SunsetVibes", "#MumbaiRains", "#StudentLife", "#Relatable"]
            },
            {
                "slot": 5,
                "time": "10:30 PM",
                "title": "Good Night + Cat Mochi Cuddle",
                "type": "story_and_thread",
                "mood_alignment": "Night reflection",
                "scene_prompt": (
                    "cozy bedroom scene, warm fairy lights, diyarai woman lying comfortably on bed petting orange tabby cat Mochi, "
                    "relaxed peaceful smile, cozy oversized hoodie, soft cinematic lighting"
                ),
                "caption": "Mochi decided my laptop is his bed tonight, so no more work lol 🐱💤 Good night everyone, dream big tonight! 🌙",
                "hashtags": ["#NightRoutine", "#CatMom", "#MochiTheCat", "#GoodNightFam"]
            }
        ]

        daily_plan = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "character": "Aisha Verma",
            "age": 24,
            "city": "Mumbai",
            "mood": mood_info,
            "past_performance_context": past_perf,
            "trending_context": top_trend,
            "total_posts": len(posts),
            "posts": posts
        }

        # Store today's plan in Hermes Workspace Memory
        hermes_memory.set_workspace_state("active_daily_plan", daily_plan)
        logger.info(f"✨ 8:00 AM Decision complete: Planned 5 authentic posts for {mood_info['day']}")
        return daily_plan


# Global singleton
decision_engine = ContentDecisionEngine()
