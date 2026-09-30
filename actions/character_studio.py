"""
AI-INFLUENCER-OS — Aisha Character Studio & Reference Face Picker
Inspired by Open-Generative-AI "AI Influencer Studio".
Maintains consistent character identity, multi-angle reference portraits,
and Open-Generative-AI compatible JSON export.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("character_studio")

CHARACTER_DIR = Path("models/character/aisha")
CHARACTER_PROFILE_FILE = CHARACTER_DIR / "profile.json"


class AishaCharacterStudio:
    """
    Manages Aisha's permanent identity, reference face picker, and multi-angle catalog.
    """

    DEFAULT_TRAITS = {
        "character_id": "diya_rai_01",
        "name": "Diya Rai",
        "age": 23,
        "location": "Mumbai, India",
        "appearance": {
            "skin_tone": "Warm golden Indian radiant undertone",
            "hair": "Long glossy dark brown wavy hair with subtle highlights",
            "eyes": "Expressive captivating almond deep brown eyes",
            "body": "Slim athletic, 5'6\" height",
            "distinctive_features": "Charming smile, elegant collarbone, sharp defined jawline",
        },
        "style_vibe": "Chic Mumbai street fashion + luxury evening glam",
        "active_reference_angle": "smiling",
        "angles": {
            "front_face": "Frontal portrait, direct eye contact with camera, neutral chic look",
            "side_profile": "90-degree side profile, showing jawline and wavy hair texture",
            "three_quarter": "3/4 angle portrait, dynamic three-quarter view, natural posture",
            "smiling": "Warm confident smile showing teeth, joyful influencer energy",
            "serious": "High-fashion editorial high-glam serious gaze",
            "looking_away": "Candid side look, looking off-camera towards sunset golden hour",
        },
        "voice_profile": {
            "engine": "qwen3_tts",
            "emotion": "happy",
            "language": "hi-en (Hinglish)",
            "sample_rate": 48000,
        },
    }

    def __init__(self):
        CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
        if not CHARACTER_PROFILE_FILE.exists():
            self._save_profile(self.DEFAULT_TRAITS)
            self._ensure_reference_images()

    def get_profile(self) -> Dict[str, Any]:
        """Loads Aisha's character profile."""
        try:
            with open(CHARACTER_PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return self.DEFAULT_TRAITS

    def _save_profile(self, profile: Dict[str, Any]):
        with open(CHARACTER_PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

    def _ensure_reference_images(self):
        """Creates initial multi-angle placeholder reference images if they don't exist yet."""
        colors = {
            "front_face": (34, 34, 46),
            "side_profile": (42, 38, 52),
            "three_quarter": (38, 44, 56),
            "smiling": (48, 36, 48),
            "serious": (32, 40, 44),
            "looking_away": (44, 40, 36),
        }
        for angle, color in colors.items():
            img_path = CHARACTER_DIR / f"{angle}.png"
            if not img_path.exists():
                img = Image.new("RGB", (704, 1408), color=color)
                draw = ImageDraw.Draw(img)
                # Draw minimal face silhouette and text
                draw.ellipse([(200, 350), (504, 750)], outline=(212, 175, 55), width=4)
                draw.text((220, 800), f"Aisha - {angle.title()}", fill=(255, 255, 255))
                img.save(img_path)

    def set_active_angle(self, angle: str) -> str:
        """Sets which reference face angle to use for content generation."""
        profile = self.get_profile()
        if angle in profile.get("angles", {}):
            profile["active_reference_angle"] = angle
            self._save_profile(profile)
            logger.info(f"Active face reference set to: {angle}")
            return f"✅ Active reference face set to: {angle.replace('_', ' ').title()}"
        return f"❌ Invalid angle. Choose from: {list(profile.get('angles', {}).keys())}"

    def get_active_reference_image(self) -> str:
        """Returns file path of the currently selected reference face."""
        profile = self.get_profile()
        angle = profile.get("active_reference_angle", "smiling")
        img_path = CHARACTER_DIR / f"{angle}.png"
        if img_path.exists():
            return str(img_path)
        # Fallback to general avatar
        return "output/avatar.png"

    def export_open_generative_ai_format(self, output_path: str = "data/aisha_open_gen_ai.json") -> str:
        """
        Exports character in Open-Generative-AI (Anil-matcha/Open-Generative-AI)
        JSON format for direct desktop app import.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        profile = self.get_profile()
        open_gen_data = {
            "app": "Open-Generative-AI",
            "version": "1.0.9",
            "studio_tab": "AI Influencer Studio",
            "character": {
                "name": profile["name"],
                "gender": "female",
                "age": profile["age"],
                "ethnicity": "Indian",
                "hair": profile["appearance"]["hair"],
                "eyes": profile["appearance"]["eyes"],
                "bodyType": profile["appearance"]["body"],
                "clothingStyle": profile["style_vibe"],
                "referenceImages": [
                    str(CHARACTER_DIR / f"{angle}.png") for angle in profile.get("angles", {})
                ],
                "activeReference": self.get_active_reference_image(),
                "promptModifier": (
                    f"ultra realistic Indian young woman {profile['name']}, 24yo, "
                    f"{profile['appearance']['hair']}, {profile['appearance']['eyes']}, "
                    f"flawless skin, natural warm lighting, 8k uhd, dslr portrait"
                ),
            },
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(open_gen_data, f, indent=2)
        logger.info(f"Exported Open-Generative-AI character profile to {output_path}")
        return output_path


# Global singleton
character_studio = AishaCharacterStudio()
