"""
AI-INFLUENCER-OS — Autonomous Lifestyle, Travel & Aesthetic Director
Empowers Diya Rai with an LLM Brain that autonomously plans:
- Real human influencer travel itineraries (Himachal waterfalls, Goa beaches, Bandra cafes)
- Candid, anti-pose photography directions (looking away, touching hair, sitting on rocks)
- Multi-photo Instagram carousel plans (4-5 cohesive slides)
- Natural Gen-Z captions (zero robotic AI words)
- Trending audio & SEO tags tailored to current viral algorithms
"""

import os
import json
import random
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("lifestyle_director")

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class LifestyleDirector:
    """
    Autonomous Creative Director for Diya Rai:
    Plans photorealistic lifestyle, travel, and brand campaigns that look 100% human.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._gemini_client = None
        if HAS_GENAI and self.api_key and self.api_key != "CHANGE_ME":
            try:
                self._gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def plan_lifestyle_post(
        self,
        topic_or_location: Optional[str] = None,
        outfit_style: Optional[str] = None,
        is_brand_collab: bool = False,
        brand_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete, photorealistic Instagram Carousel & Reel plan.
        If topic_or_location is None, the AI autonomously invents a trending travel/lifestyle moment.
        """
        if self._gemini_client:
            try:
                return self._generate_with_gemini(topic_or_location, outfit_style, is_brand_collab, brand_name)
            except Exception as e:
                logger.error(f"Gemini generation failed: {e}. Falling back to curated director engine.")

        return self._generate_curated_fallback(topic_or_location, outfit_style, is_brand_collab, brand_name)

    def _generate_with_gemini(
        self,
        topic_or_location: Optional[str],
        outfit_style: Optional[str],
        is_brand_collab: bool,
        brand_name: Optional[str]
    ) -> Dict[str, Any]:
        """Uses Gemini 2.0 Flash to synthesize creative direction for Diya Rai."""
        theme_hint = topic_or_location or "trending aesthetic weekend trip or city lifestyle"
        collab_hint = f"Sponsorship with {brand_name}" if is_brand_collab and brand_name else "Organic lifestyle/travel post"

        system_instruction = """You are the Lead Creative Director & Social Media Strategist for Diya Rai (@diyarai_official), 
a popular 23-year-old Mumbai/Delhi fashion, travel & lifestyle influencer.

CRITICAL RULES:
1. Diya Rai must look 100% REAL human. NEVER suggest stiff or robotic poses.
2. Every scene must feel like an authentic candid photo taken by a friend on an iPhone 15 Pro, with natural sunlight and depth.
3. LoRA trigger token: 'diyarai woman' MUST be in every SDXL prompt.
4. The caption MUST sound like a genuine Gen-Z Indian female influencer: casual Hinglish, cute relatable questions, natural emojis, ZERO AI buzzwords (never #AI, #Virtual, #Digital).
5. Output ONLY valid JSON."""

        prompt = f"""Plan a viral Instagram Carousel Post (4 slides) and Reel concept for Diya Rai.
Context:
- Theme / Location: {theme_hint}
- Outfit Style: {outfit_style or "Trending stylish casual"}
- Type: {collab_hint}

Return a JSON object with this exact structure:
{{
  "title": "Short internal title",
  "location_name": "e.g., Jibhi Waterfall, Tirthan Valley, Himachal Pradesh",
  "vibe": "e.g., monsoon wanderlust & peace",
  "trending_audio": "e.g., Pritam & KK - Labon Ko (Lofi Remix)",
  "caption": "Natural Hinglish caption with engagement question for comments",
  "hashtags": ["#himachaldiaries", "#waterfallvibes", "#ootd", "#travelindia", "#reelsindia"],
  "slides": [
    {{
      "slide_number": 1,
      "shot_type": "Full body wide candid",
      "pose_description": "Standing near waterfall looking away, hair gently in mist breeze",
      "sdxl_prompt": "photorealistic medium wide shot of diyarai woman in casual loose red flannel shirt over white crop top and baggy jeans, standing in green mountain meadow admiring majestic rushing waterfall, mist in air, sunny overcast, photorealistic 8k, raw candid photography, shot on 35mm lens",
      "negative_prompt": "blurry, low quality, oversaturated, plastic skin, stiff pose, doll face, 3d render"
    }},
    {{
      "slide_number": 2,
      "shot_type": "Medium seated candid",
      "pose_description": "Sitting comfortably on a mossy rock looking sideways, candid laughter",
      "sdxl_prompt": "candid photography of diyarai woman sitting casually on large grey rock near flowing mountain stream, holding stainless steel travel mug, natural warm smile, soft afternoon daylight, raw texture, 8k",
      "negative_prompt": "blurry, low quality, cartoon, smooth plastic skin"
    }},
    {{
      "slide_number": 3,
      "shot_type": "Scenic environmental b-roll",
      "pose_description": "Breathtaking vertical landscape of the waterfall crashing into crystal pool with pine trees",
      "sdxl_prompt": "majestic mountain waterfall crashing between granite cliffs in himachal forest, lush green pine trees, sun rays piercing through water mist, vertical 9:16 composition, national geographic quality",
      "negative_prompt": "blurry, oversaturated, artificial"
    }},
    {{
      "slide_number": 4,
      "shot_type": "Close-up portrait",
      "pose_description": "Close up face candid, smiling softly at camera with natural wind-blown hair",
      "sdxl_prompt": "close up portrait of diyarai woman, authentic skin pores and fine details, natural eye sparkle, soft smile, sunlight glistening on dewy skin, outdoor nature backdrop, 8k uhd",
      "negative_prompt": "airbrushed, plastic face, unnatural eyes, cartoon"
    }}
  ]
}}"""

        response = self._gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        data = json.loads(response.text)
        return data

    def _generate_curated_fallback(
        self,
        topic_or_location: Optional[str],
        outfit_style: Optional[str],
        is_brand_collab: bool,
        brand_name: Optional[str]
    ) -> Dict[str, Any]:
        """High-craft curated fallback ensuring flawless execution even offline."""
        destinations = [
            {
                "location": "Jibhi Waterfalls, Himachal Pradesh",
                "outfit": "loose red flannel open shirt, white rib tank top, relaxed light-wash denim",
                "vibe": "mountain wanderlust & rainy peace",
                "audio": "Pritam, KK - Labon Ko (Chill Lofi Edit)",
                "caption": "Chasing waterfalls and missing no alarms 🌲🌧️ Honestly didn't want to leave this spot... Rate the view 1-10? 👇🤍",
                "tags": ["#himachaldiaries", "#chasingwaterfalls", "#ootd", "#travelindia", "#aestheticvibes", "#reelsinstagram"],
                "bg_element": "gushing mountain waterfall crashing between rocky cliffs with pine trees",
            },
            {
                "location": "Aesthetic South Bombay Heritage Cafe",
                "outfit": "oversized beige linen blazer, white tee, minimal gold hoop earrings",
                "vibe": "old money vintage city aesthetic",
                "audio": "Aditya A - Chaand Baaliyan (Acoustic)",
                "caption": "Coffee tastes 10x better when the cafe looks like a movie set ☕✨ What's your go-to coffee order? Tell me below! 🥐",
                "tags": ["#mumbaicafe", "#oldmoneyoutfit", "#bandradiaries", "#coffeelover", "#minimalistfashion", "#explorepage"],
                "bg_element": "sunlit vintage cafe table with iced latte and french croissant, high ceilings and green plants",
            },
            {
                "location": "Vagator Cliff Sunset, North Goa",
                "outfit": "terracotta boho maxi skirt, crochet cream halter top, messy beach waves",
                "vibe": "golden hour ocean glow",
                "audio": "King, Nick Jonas - Maan Meri Jaan (Sunset Mix)",
                "caption": "Golden hour in Goa hits completely different 🌅✨ Not answering emails for the next 48 hours bye 🐚🌴 Which slide is your favorite?",
                "tags": ["#goadiaries", "#goldenhourglow", "#beachvibes", "#sunsetlovers", "#bohostyle", "#reelsindia"],
                "bg_element": "golden sunset over arabian sea with gentle waves and rocky shoreline",
            }
        ]

        # Select matching or random destination
        selected = destinations[0]
        if topic_or_location:
            t_lower = topic_or_location.lower()
            for d in destinations:
                if any(k in t_lower for k in ["cafe", "mumbai", "coffee"]):
                    selected = destinations[1]
                    break
                elif any(k in t_lower for k in ["beach", "goa", "sunset"]):
                    selected = destinations[2]
                    break
        else:
            selected = random.choice(destinations)

        outfit = outfit_style or selected["outfit"]
        loc = selected["location"]
        bg = selected["bg_element"]

        return {
            "title": f"Diya Rai at {loc}",
            "location_name": loc,
            "vibe": selected["vibe"],
            "trending_audio": selected["audio"],
            "caption": selected["caption"],
            "hashtags": selected["tags"],
            "slides": [
                {
                    "slide_number": 1,
                    "shot_type": "Full body wide candid",
                    "pose_description": "Standing looking at scenery with wind gently moving hair",
                    "sdxl_prompt": f"photorealistic wide angle photo of diyarai woman wearing {outfit}, admiring {bg}, natural mountain lighting, authentic skin texture, shot on 35mm lens, candid street style",
                    "negative_prompt": "blurry, low quality, smooth plastic skin, 3d render, oversaturated"
                },
                {
                    "slide_number": 2,
                    "shot_type": "Medium seated candid",
                    "pose_description": "Sitting relaxed looking sideways, natural laughter",
                    "sdxl_prompt": f"candid photograph of diyarai woman sitting on rock, dressed in {outfit}, natural laugh, beautiful background of {bg}, soft natural bokeh, 8k uhd",
                    "negative_prompt": "plastic doll face, airbrushed, cartoon, extra limbs"
                },
                {
                    "slide_number": 3,
                    "shot_type": "Scenic environmental shot",
                    "pose_description": "Atmospheric vertical shot of the landscape with zero people",
                    "sdxl_prompt": f"vertical 9:16 cinematography of {bg}, morning mist and golden sun rays, national geographic aesthetic, hyper-detailed",
                    "negative_prompt": "low resolution, oversaturated, artificial"
                },
                {
                    "slide_number": 4,
                    "shot_type": "Warm close-up portrait",
                    "pose_description": "Candid close up smile looking toward camera",
                    "sdxl_prompt": f"close up portrait of diyarai woman, wearing {outfit}, genuine warm smile, natural skin pores and realistic eyes, {bg} in soft blurred background, 8k",
                    "negative_prompt": "plastic skin, mannequin, artificial, blurry"
                }
            ]
        }


# Global singleton
lifestyle_director = LifestyleDirector()
