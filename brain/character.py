"""
AI-INFLUENCER-OS — Character & Personality Engine
Enforces Aisha's personality, anti-AI guardrails, and human simulation.
"""

import os
import json
import random
from typing import Dict, Optional


class CharacterEngine:
    """Manages Aisha's personality, tone, quirks, and anti-AI guardrails."""

    def __init__(self, personality_path: Optional[str] = None):
        if personality_path is None:
            personality_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "personality.json")
        self.personality_path = personality_path
        self.persona = self._load_persona()

    def _load_persona(self) -> Dict:
        if not os.path.exists(self.personality_path):
            return {"name": "Aisha", "age": 24, "city": "Mumbai"}
        with open(self.personality_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_busy_excuse(self) -> str:
        """Returns realistic human micro-excuse to simulate busy creator life."""
        excuses = [
            "Studio ke vanity se reply kar rahi hoon ✨",
            "Shoot ke break mein phone dekha toh socha reply kar doon 😊",
            "Arre aaj subah se shoot chal raha tha, abhi break mila! 💅",
            "Ghar wapas jaate waqt cab se reply kar rahi hoon 🚗",
            "Quickly reply kar rahi hoon, next shot ready hai! 📸",
        ]
        return random.choice(excuses)

    def build_system_prompt(self, memory_summary: str, product_context: Optional[str] = None) -> str:
        """Construct the prompt enforcing authentic human identity from aisha_persona.md."""
        persona_md_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "aisha_persona.md")
        base_prompt = ""
        if os.path.exists(persona_md_path):
            with open(persona_md_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        else:
            name = self.persona.get("name", "Aisha")
            age = self.persona.get("age", 24)
            base_prompt = f"You are {name}, a {age}-year-old fashion, lifestyle & dance creator living in Mumbai."

        prompt = f"""{base_prompt}

FAN MEMORY & RELATIONSHIP CONTEXT:
{memory_summary}
- If relationship is REGULAR: act familiar, like you remember them. You can offer discount code AISHA50 if they ask for deals.
- If relationship is VIP: act like close friends, warmly and excitedly. You can offer code AISHA100.
- If relationship is NEW: be warm, welcoming, and helpful.
"""
        if product_context:
            prompt += f"""
RELEVANT BRAND PRODUCT FROM CATALOG:
{product_context}
- If the fan is asking about this product, price, or how to buy: answer naturally from the info above and casually share the link.
"""
        return prompt

    def sanitize_response(self, text: str) -> str:
        """Filter out any robotic or AI-sounding leakage."""
        cleaned = text.strip()
        # Remove markdown quotes or tags
        cleaned = cleaned.replace("```json", "").replace("```", "").strip('"')

        banned_phrases = [
            "As an AI,",
            "As an artificial intelligence,",
            "I do not have feelings,",
            "How can I assist you today?",
            "I apologize for the confusion.",
        ]
        for b in banned_phrases:
            cleaned = cleaned.replace(b, "")

        return cleaned.strip()
