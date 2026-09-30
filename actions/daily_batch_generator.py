"""
AI-INFLUENCER-OS — 5 Posts/Day Automated Batch Generator
Orchestrates Diya Rai's daily lifecycle content pipeline (08:00, 12:00, 16:00, 20:00, 22:00).
Integrates:
- Diya Rai Character Studio (multi-angle face consistency)
- Qwen3-TTS (emotional voice cloning)
- Wan2.2 MoE (photorealistic 9:16 video generation)
- Local SQLite Database (pipeline & scheduling tracking)
- Open-Generative-AI compatibility
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from actions.character_studio import character_studio
from cloud.voice_engine import voice_engine
from cloud.video_engine import video_engine
from local import database as db

logger = logging.getLogger("daily_batch_generator")

DAILY_SCHEDULE_SLOTS = [
    {
        "slot_id": "slot_1_story_morning",
        "time": "08:00",
        "title": "Good Morning Story",
        "post_type": "story",
        "preferred_angle": "smiling",
        "theme": "Morning Sunlight & Chai",
        "scene_prompt": (
            "candid vertical story shot of diyarai woman in Bandra apartment balcony holding ceramic cutting chai mug, "
            "warm morning sun rays, cozy oversized white tee, candid natural smile, shot on iphone 15 pro, realistic film grain"
        ),
        "voice_script": "Sunny day in Mumbai! ☀️ Aaj boutique pe fittings hain, GRWM video later! Have a lovely day guys! ✨",
        "emotion": "happy",
        "hashtags": ["#MorningVibes", "#MumbaiSun", "#AishaDiaries"],
    },
    {
        "slot_id": "slot_2_reel_ootd",
        "time": "08:30",
        "title": "Outfit of the Day (OOTD)",
        "post_type": "reel",
        "preferred_angle": "front_face",
        "theme": "Fashion Inspo & Street Style",
        "scene_prompt": (
            "photorealistic medium wide shot of diyarai woman in chic tailored beige linen blazer and vintage denim, "
            "walking down leafy Bandra street, holding iced coffee, confident natural walk, 8k vertical 9:16"
        ),
        "voice_script": "Aaj ka outfit check! 🔥 Linen blazer is literally my summer lifesaver. Comment mein batao kal kya pehnu?",
        "emotion": "excited",
        "hashtags": ["#OOTD", "#StreetStyleMumbai", "#BandraDiaries", "#StyleInspo", "#ReelsIndia"],
    },
    {
        "slot_id": "slot_3_story_lunch",
        "time": "12:30",
        "title": "Lunch Break Chai & Vada Pav Story",
        "post_type": "story",
        "preferred_angle": "three_quarter",
        "theme": "BTS Studio & Lunch Break",
        "scene_prompt": (
            "candid phone perspective shot of diyarai woman in studio styling room holding plate with hot vada pav, "
            "clothes racks in soft blurred background, playful happy expression, natural room light, raw 8k"
        ),
        "voice_script": "Lunch break scene! 🫓 Bandra ka best vada pav, honestly nothing beats this. Kal wahi jaungi!",
        "emotion": "chill",
        "hashtags": ["#LunchBreak", "#MumbaiFoodie", "#VadaPavLove", "#BTS"],
    },
    {
        "slot_id": "slot_4_reel_bts",
        "time": "16:30",
        "title": "Boutique Fittings & Shoot BTS Reel",
        "post_type": "reel",
        "preferred_angle": "three_quarter",
        "theme": "BTS Creator Chaos",
        "scene_prompt": (
            "candid behind the scenes footage of diyarai woman adjusting pastel evening dresses on mannequin, "
            "measuring tape around neck, focused creative expressions then laughing at camera, natural studio lighting, 9:16"
        ),
        "voice_script": "Fittings ke beech mein! 💅 Costume change number 4 and honestly thak gayi hoon, but the dresses are so worth it! 💪",
        "emotion": "sultry",
        "hashtags": ["#StylistDiaries", "#BoutiqueLife", "#ShootBTS", "#FashionDesigner"],
    },
    {
        "slot_id": "slot_5_reel_personal",
        "time": "20:00",
        "title": "Relatable Story / Mom Conversation Reel",
        "post_type": "reel",
        "preferred_angle": "serious",
        "theme": "Relatable Indian Family Life",
        "scene_prompt": (
            "candid portrait of diyarai woman sitting on cozy sofa at home holding phone to ear laughing, "
            "warm ambient lamp lighting, cozy pastel pajama set, natural skin texture, laughing candidly, 8k uhd"
        ),
        "voice_script": "Mummy ne phone kiya aur pehla question: 'Beta shaadi kab kar rahi ho?' 😂 Indian moms will literally never change! Can you relate?",
        "emotion": "happy",
        "hashtags": ["#DesiRelatable", "#IndianMoms", "#FamilyMoments", "#FunnyReels", "#JustGirlThings"],
    },
    {
        "slot_id": "slot_6_story_night",
        "time": "22:00",
        "title": "Good Night & Cat Mochi Story",
        "post_type": "story",
        "preferred_angle": "looking_away",
        "theme": "Bedtime Routine & Cat Mochi",
        "scene_prompt": (
            "cozy dark bedroom illuminated by soft fairy lights, diyarai woman in oversized hoodie petting orange tabby cat Mochi on bed, "
            "sleepy gentle smile, serene aesthetic, raw photorealistic film grain"
        ),
        "voice_script": "Mochi ke saath cuddling in bed 🐱💤 Wrapping up for the night. Good night everyone, sweet dreams! 🌙",
        "emotion": "whisper",
        "hashtags": ["#GoodNightFam", "#CatMom", "#MochiVibes", "#SleepyHours"],
    },
]


class DailyBatchGenerator:
    """
    Automated generation and batch orchestration of Diya Rai's 5 daily scheduled posts.
    """

    def __init__(self):
        db.init_db()
        self.output_dir = Path("output/daily_batches")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_schedule_slots(self) -> List[Dict[str, Any]]:
        """Returns the 5 daily slot configurations."""
        return DAILY_SCHEDULE_SLOTS

    def generate_slot(
        self,
        slot_index: int,
        date_str: Optional[str] = None,
        force_angle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates content for a single daily slot.
        - Obtains reference face
        - Generates Qwen3-TTS audio
        - Generates Wan2.2 MoE video
        - Records in SQLite database
        """
        if slot_index < 0 or slot_index >= len(DAILY_SCHEDULE_SLOTS):
            raise ValueError(f"Invalid slot index {slot_index}. Must be 0 to 4.")

        slot = DAILY_SCHEDULE_SLOTS[slot_index]
        today = date_str or datetime.now().strftime("%Y-%m-%d")
        slot_name = slot["slot_id"]

        # 1. Resolve reference face image
        angle = force_angle or slot.get("preferred_angle", "smiling")
        char_dir = Path("models/character/aisha")
        angle_img = char_dir / f"{angle}.png"
        ref_image = str(angle_img) if angle_img.exists() else character_studio.get_active_reference_image()

        # 2. Generate voiceover via Qwen3-TTS
        audio_output = f"output/audio/{today}_{slot_name}.wav"
        voice_path = voice_engine.generate_voice(
            text=slot["voice_script"],
            ref_audio_path="models/voice/reference_aisha.wav",
            output_path=audio_output,
            emotion=slot["emotion"],
        )

        # 3. Generate video via Wan2.2
        video_output = f"output/video/{today}_{slot_name}.mp4"
        vid_res = video_engine.generate(
            prompt=slot["scene_prompt"],
            image_path=ref_image,
            audio_path=voice_path,
            duration=5,
            engine="wan2.2",
            output_path=video_output,
        )
        final_video_path = vid_res.get("output_path", video_output)

        # 4. Create and record post in SQLite DB
        caption = f"{slot['title']}\n\n{slot['voice_script']}"
        hashtags_str = " ".join(slot["hashtags"])
        full_caption = f"{caption}\n\n{hashtags_str}"

        post_id = db.create_post(
            topic=slot["title"],
            script=slot["voice_script"],
            caption=full_caption,
            hashtags=json.dumps(slot["hashtags"]),
            video_path=final_video_path,
            platform="instagram",
            post_type=slot["post_type"],
            resolution="1080x1920",
        )

        db.update_post(
            post_id,
            status="generated",
            video_path=final_video_path,
        )

        db.log_audit_event(
            "DAILY_SLOT_GENERATED",
            f"Generated Slot {slot['time']} - {slot['title']} (Post ID: {post_id})",
            source="daily_batch_generator",
        )

        logger.info(f"✅ Slot {slot['time']} generated successfully: Post ID {post_id}")

        return {
            "post_id": post_id,
            "slot_id": slot["slot_id"],
            "time": slot["time"],
            "title": slot["title"],
            "theme": slot["theme"],
            "angle": angle,
            "reference_image": ref_image,
            "voice_path": voice_path,
            "video_path": final_video_path,
            "caption": full_caption,
            "status": "generated",
        }

    def generate_daily_batch(
        self,
        date_str: Optional[str] = None,
        force_angle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes full daily batch: generates all 5 scheduled posts for Diya Rai.
        """
        today = date_str or datetime.now().strftime("%Y-%m-%d")
        results = []
        logger.info(f"🚀 Starting Diya Rai 5-Post Daily Batch for date: {today}")

        for idx, _ in enumerate(DAILY_SCHEDULE_SLOTS):
            slot_res = self.generate_slot(idx, date_str=today, force_angle=force_angle)
            results.append(slot_res)

        summary_file = self.output_dir / f"batch_{today}.json"
        batch_summary = {
            "batch_date": today,
            "character": "Diya Rai",
            "total_posts": len(results),
            "generated_at": datetime.now().isoformat(),
            "posts": results,
        }

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(batch_summary, f, indent=2)

        logger.info(f"🎉 5-Post Daily Batch complete! Summary saved to {summary_file}")
        return batch_summary

    def export_open_generative_ai_batch(
        self,
        output_path: str = "data/daily_batch_open_gen_ai.json",
    ) -> str:
        """
        Exports the 5 daily posts in an Open-Generative-AI compatible schedule format.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        schedule_data = {
            "format": "Open-Generative-AI Workflow Schedule",
            "version": "1.0.9",
            "character_id": "aisha_mumbai_01",
            "name": "Diya Rai",
            "slots": [
                {
                    "time": s["time"],
                    "title": s["title"],
                    "angle": s["preferred_angle"],
                    "prompt": s["scene_prompt"],
                    "script": s["voice_script"],
                    "emotion": s["emotion"],
                    "type": s["post_type"],
                    "tags": s["hashtags"],
                }
                for s in DAILY_SCHEDULE_SLOTS
            ],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schedule_data, f, indent=2)
        return output_path

    def plan_dynamic_lifestyle_carousel(
        self,
        topic_or_location: Optional[str] = None,
        outfit_style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Uses the LLM Lifestyle Director to generate a 4-slide Instagram Carousel & Reel plan
        with natural poses, real Gen-Z caption, and viral audio.
        """
        from brain.lifestyle_director import lifestyle_director
        return lifestyle_director.plan_lifestyle_post(
            topic_or_location=topic_or_location,
            outfit_style=outfit_style
        )


# Global singleton
daily_batch_generator = DailyBatchGenerator()
