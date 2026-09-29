"""
AIInfluencerOS — WhatsApp Service (OpenWA wrapper)
Handles WhatsApp DM automation with AI personality.
"""

import os
import json
import random
import logging
import asyncio
from typing import Optional
from datetime import datetime, date

import httpx

logger = logging.getLogger("whatsapp")


class WhatsAppService:
    """Wrapper around OpenWA API for WhatsApp automation."""

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        session_id: str = "default",
        max_dms_per_day: int = 50,
        reply_delay_min: int = 3,
        reply_delay_max: int = 10,
        personality: dict = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.session_id = session_id
        self.max_dms_per_day = max_dms_per_day
        self.reply_delay_min = reply_delay_min
        self.reply_delay_max = reply_delay_max
        self.personality = personality or {}
        self._client = httpx.AsyncClient(timeout=30)
        self._dms_today = 0
        self._last_dm_date = None

        # Integrated Mem0 Brain Agent
        try:
            from brain.agent import BrainAgent
            self.brain = BrainAgent()
        except Exception:
            self.brain = None

    async def close(self):
        await self._client.aclose()

    def _check_rate_limit(self) -> bool:
        today = date.today()
        if self._last_dm_date != today:
            self._dms_today = 0
            self._last_dm_date = today
        return self._dms_today < self.max_dms_per_day

    async def _human_delay(self):
        delay = random.uniform(self.reply_delay_min, self.reply_delay_max)
        await asyncio.sleep(delay)

    async def _api_call(self, endpoint: str, method: str = "POST", data: dict = None) -> dict:
        """Make an API call to OpenWA."""
        url = f"{self.api_url}/{endpoint}"
        try:
            if method == "POST":
                resp = await self._client.post(url, json=data or {})
            else:
                resp = await self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"OpenWA API error [{endpoint}]: {e}")
            return {"error": str(e)}

    async def send_message(self, phone: str, message: str) -> bool:
        """
        Send a WhatsApp message.

        Args:
            phone: Phone number with country code (e.g., "919876543210@c.us")
            message: Text message to send

        Returns:
            True if sent successfully
        """
        if not self._check_rate_limit():
            logger.warning("WhatsApp daily DM limit reached")
            return False

        await self._human_delay()

        result = await self._api_call("sendText", data={
            "chatId": phone if "@" in phone else f"{phone}@c.us",
            "text": message,
        })

        if "error" not in result:
            self._dms_today += 1
            logger.info(f"WhatsApp message sent to {phone}")
            return True

        return False

    async def send_product_link(self, phone: str, product: dict) -> bool:
        """Send a product recommendation DM."""
        dm_greeting = self.personality.get("engagement", {}).get("dm_greeting", "Hey! 💕")

        message = (
            f"{dm_greeting}\n\n"
            f"You asked about {product.get('name', 'this')}! Here's the deets:\n\n"
            f"✨ {product.get('product', '')}\n"
            f"💰 {product.get('price', '')}\n"
            f"🔗 {product.get('link', '')}\n\n"
            f"Let me know if you have any questions! 🫶"
        )

        return await self.send_message(phone, message)

    async def auto_reply(self, phone: str, incoming_message: str, brands: list = None) -> bool:
        """
        Generate and send an AI-style auto-reply based on the incoming message.

        Uses keyword matching (no API needed — keeps it free).
        """
        reply = self._generate_reply(incoming_message, brands)
        return await self.send_message(phone, reply)

    def _generate_reply(self, message: str, brands: list = None, phone: str = "whatsapp_user") -> str:
        """Generate an authentic human reply using BrainAgent with fallback."""
        if self.brain:
            try:
                return self.brain.respond(user_id=phone, message=message, platform="whatsapp")
            except Exception as e:
                logger.warning(f"BrainAgent fallback triggered: {e}")

        msg_lower = message.lower()
        dm_style = self.personality.get("engagement", {}).get("dm_style", "friendly")
        greeting = self.personality.get("engagement", {}).get("dm_greeting", "Heyy! 💕")

        # Product inquiry detection
        if brands:
            for brand in brands:
                product_name = brand.get("product", "").lower()
                brand_name = brand.get("name", "").lower()
                if product_name in msg_lower or brand_name in msg_lower:
                    return (
                        f"{greeting}\n\n"
                        f"Yesss I love {brand.get('product', 'this')}! 😍\n\n"
                        f"{brand.get('pitch', '')}\n\n"
                        f"💰 {brand.get('price', '')}\n"
                        f"🔗 {brand.get('link', '')}\n\n"
                        f"Trust me, you'll love it! 💅✨"
                    )

        # Generic replies by intent
        if any(w in msg_lower for w in ["collab", "collaboration", "brand", "sponsorship", "partnership"]):
            return (
                f"{greeting}\n\n"
                "Omg yes I'd love to collab! 🫶\n\n"
                "Can you tell me more about your brand and what you have in mind?\n\n"
                "Looking forward to hearing from you! ✨"
            )

        if any(w in msg_lower for w in ["price", "cost", "rate", "charge", "fee"]):
            return (
                f"{greeting}\n\n"
                "Thanks for reaching out! 💕\n\n"
                "My rates depend on the type of content — Reels, Stories, or a combo.\n"
                "DM me the details and I'll send you my rate card! 📩\n\n"
                "Excited to work together! ✨"
            )

        if any(w in msg_lower for w in ["hi", "hello", "hey", "sup", "what's up"]):
            return f"{greeting} Thanks for reaching out! How can I help you? 😊✨"

        if any(w in msg_lower for w in ["routine", "skincare", "skin care", "products"]):
            return (
                f"{greeting}\n\n"
                "I literally get this question SO much 😂\n\n"
                "Check out my recent reels — I break down my full routine there!\n"
                "But if you want specific recs, just tell me your skin type 💕\n\n"
                "Happy to help! 🫶"
            )

        # Default friendly reply
        replies = [
            f"{greeting} Thanks for the message! 💕 What would you like to know?",
            f"{greeting} So sweet of you to DM! 🥰 How can I help?",
            f"{greeting} Love hearing from you guys! ✨ What's on your mind?",
        ]
        return random.choice(replies)

    async def get_unread_messages(self) -> list:
        """Get unread WhatsApp messages."""
        result = await self._api_call("getUnreadMessages", method="GET")
        if isinstance(result, list):
            return result
        return result.get("messages", [])

    async def health_check(self) -> bool:
        """Check if OpenWA server is running."""
        try:
            resp = await self._client.get(f"{self.api_url}/getConnectionState")
            return resp.status_code == 200
        except Exception:
            return False
