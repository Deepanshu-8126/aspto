"""
AI-INFLUENCER-OS — DaanKieft/ai-influencer Studio Adapter
Provides local-first REST/JSON API contract and studio data models
compatible with DaanKieft/ai-influencer (Vite + React web studio).
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("studio_adapter")


class AIInfluencerStudioAdapter:
    """
    Adapter for DaanKieft/ai-influencer local-first web app:
    - Persona profiles (name, bio, niches, aesthetic styles, LoRA weights)
    - Video reel asset catalog and metadata
    - Fast REST payload serializers for 60-sec Vercel/Vite deployment
    """

    def __init__(self, storage_path: str = "data/studio_profile.json"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            self._init_default_profile()

    def _init_default_profile(self):
        default_data = {
            "influencer": {
                "id": "inf_aisha_01",
                "name": "Aisha Verma",
                "handle": "@aisha.verma_ai",
                "niche": ["fashion", "luxury_lifestyle", "skincare", "dance"],
                "base_model": "SDXL-Juggernaut-v8",
                "lora_path": "models/lora/my_face.safetensors",
                "lora_weight": 0.92,
                "preferred_video_engine": "wan2.2_flf2v",
                "voice_engine": "qwen3_tts",
                "character_traits": {
                    "vibe": "warm, stylish, playful, hyper-aesthetic",
                    "slang": "Hinglish, chic, subtle Gen-Z emojis",
                },
                "stats": {
                    "followers_aggregate": 142500,
                    "engagement_rate": 8.4,
                    "active_brand_deals": 4,
                }
            },
            "recent_generations": [],
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)

    def get_profile(self) -> Dict[str, Any]:
        """Loads current influencer persona definition."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            self._init_default_profile()
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def update_profile(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Saves updated persona settings (e.g. new LoRA or preferred video engine)."""
        current = self.get_profile()
        current["influencer"].update(updates)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return current

    def record_generation(
        self,
        topic: str,
        video_url: str,
        engine: str = "wan2.2_flf2v",
        views: int = 0,
    ) -> Dict[str, Any]:
        """Appends generated asset into the studio gallery."""
        current = self.get_profile()
        item = {
            "id": f"gen_{int(datetime.now().timestamp())}",
            "topic": topic,
            "video_url": video_url,
            "engine": engine,
            "created_at": datetime.now().isoformat(),
            "views": views,
        }
        current["recent_generations"].insert(0, item)
        current["recent_generations"] = current["recent_generations"][:50]
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return item

    def export_vite_config(self) -> Dict[str, Any]:
        """Returns API config payload consumed by Vite/React frontend."""
        profile = self.get_profile()
        return {
            "appName": "AI-Influencer Studio",
            "version": "2026.4",
            "profile": profile["influencer"],
            "endpoints": {
                "generate": "/api/generate",
                "publish": "/api/publish",
                "analytics": "/api/analytics",
            },
        }


# Global singleton
studio_adapter = AIInfluencerStudioAdapter()
