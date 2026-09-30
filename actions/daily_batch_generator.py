"""
AI-INFLUENCER-OS — 5 Posts/Day Automated Batch Generator
Orchestrates Aisha's daily lifecycle content pipeline (08:00, 12:00, 16:00, 20:00, 22:00).
Integrates:
- Aisha Character Studio (multi-angle face consistency)
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
        "slot_id": "slot_1_morning",
        "time": "08:00",
        "title": "Morning OOTD & Job Tip",
        "preferred_angle": "smiling",
        "theme": "Career & Daily Motivation",
        "scene_prompt": (
            "Aisha in smart casual beige blazer and white silk top, holding black coffee cup, "
            "modern Mumbai high-rise office balcony, bright warm morning sunlight, confident radiant smile, "
            "photorealistic 8k, vertical 9:16"
        ),
        "voice_script": (
            "Good morning fam! Starting my day with fresh energy. Aaj ka quick tip: never wait "
            "for the perfect moment, create it! What is your main goal today? Tell me in the comments!"
        ),
        "emotion": "happy",
        "post_type": "reel",
        "hashtags": ["#AishaVerma", "#MorningVibes", "#OOTD", "#CareerTips", "#MumbaiInfluencer", "#DailyMotivation"],
    },
    {
        "slot_id": "slot_2_lunch",
        "time": "12:00",
        "title": "Lunch Break Chai & Mumbai Cafe",
        "preferred_angle": "three_quarter",
        "theme": "Mumbai Lifestyle & Food",
        "scene_prompt": (
            "Aisha in pastel floral summer dress, outdoor seating at aesthetic Bandra cafe, "
            "holding traditional cutting chai glass, soft natural sunlight, relaxed friendly vibe, "
            "photorealistic 8k, vertical 9:16"
        ),
        "voice_script": (
            "Lunch break scene! Honestly, Mumbai ki cutting chai ke bina din adhoora hai. "
            "Tum sabka lunch break kaisa ja raha hai? Are you team chai or team coffee?"
        ),
        "emotion": "chill",
        "post_type": "reel",
        "hashtags": ["#MumbaiCafe", "#ChaiLover", "#LifestyleBlogger", "#MidDayVibes", "#BandraDiaries", "#AishaDiaries"],
    },
    {
        "slot_id": "slot_3_fitness",
        "time": "16:00",
        "title": "3 Exercises for Flat Tummy & Gym Fit",
        "preferred_angle": "front_face",
        "theme": "Fitness & Core Routine",
        "scene_prompt": (
            "Aisha in sleek mauve gym activewear, holding water bottle, aesthetic fitness studio "
            "with ambient neon rim light, fit athletic physique, determined energetic expression, "
            "photorealistic 8k, vertical 9:16"
        ),
        "voice_script": (
            "Post-workout glow! 3 simple core exercises you can do anywhere, even during busy work days. "
            "Remember guys, consistency beats perfection every single time! Let's get active!"
        ),
        "emotion": "excited",
        "post_type": "reel",
        "hashtags": ["#FitnessMotivation", "#WorkoutRoutine", "#FlatTummyTips", "#HealthyLiving", "#AishaFit"],
    },
    {
        "slot_id": "slot_4_evening",
        "time": "20:00",
        "title": "Summer Evening Dress Haul & Glam",
        "preferred_angle": "serious",
        "theme": "Fashion Inspo & Evening Glam",
        "scene_prompt": (
            "Aisha in emerald satin evening dress, luxury Mumbai rooftop restaurant overlooking "
            "city lights at golden hour dusk, elegant posture, high-fashion editorial look, "
            "photorealistic 8k, vertical 9:16"
        ),
        "voice_script": (
            "Evening glam look unlocked! Obsessed with this satin silhouette for dinner nights. "
            "How would you style this look? Drop a comment if you want the outfit link!"
        ),
        "emotion": "sultry",
        "post_type": "reel",
        "hashtags": ["#EveningGlam", "#FashionHaul", "#DinnerOutfit", "#LuxuryLifestyle", "#MumbaiNights", "#StyleInspo"],
    },
    {
        "slot_id": "slot_5_night",
        "time": "22:00",
        "title": "Night Routine & Sign-off",
        "preferred_angle": "looking_away",
        "theme": "Self-care & Night Story",
        "scene_prompt": (
            "Aisha in cozy cream silk loungewear at home, soft warm fairy lights, serene peaceful expression, "
            "candid look towards window, peaceful evening aesthetic, photorealistic 8k, vertical 9:16"
        ),
        "voice_script": (
            "Wrapping up a beautiful day. Truly grateful for all your love on today's posts. "
            "Time to unplug, rest, and recharge. Kal subah milte hain, good night everyone!"
        ),
        "emotion": "whisper",
        "post_type": "story",
        "hashtags": ["#NightRoutine", "#GoodNightFam", "#SelfCare", "#PeacefulMindset", "#AishaDiaries"],
    },
]


class DailyBatchGenerator:
    """
    Automated generation and batch orchestration of Aisha's 5 daily scheduled posts.
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
        Executes full daily batch: generates all 5 scheduled posts for Aisha.
        """
        today = date_str or datetime.now().strftime("%Y-%m-%d")
        results = []
        logger.info(f"🚀 Starting Aisha 5-Post Daily Batch for date: {today}")

        for idx, _ in enumerate(DAILY_SCHEDULE_SLOTS):
            slot_res = self.generate_slot(idx, date_str=today, force_angle=force_angle)
            results.append(slot_res)

        summary_file = self.output_dir / f"batch_{today}.json"
        batch_summary = {
            "batch_date": today,
            "character": "Aisha Verma",
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
            "name": "Aisha Verma",
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


# Global singleton
daily_batch_generator = DailyBatchGenerator()
