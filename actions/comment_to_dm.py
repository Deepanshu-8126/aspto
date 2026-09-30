"""
AI-INFLUENCER-OS — Comment to DM Automation Engine (Xeven777/openinstadm)
Automatically scans comments on published Reels/Posts for trigger keywords
(e.g., 'LINK', 'STYLE', 'PRICE', 'OUTFIT', 'BUY') and sends personalized DMs
with affiliate product links and promo codes, recording leads into SQLite.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from local import database as db

logger = logging.getLogger("comment_to_dm")

DEFAULT_TRIGGERS = {
    "link": "Hey {username}! Here is the direct link to the outfit you asked about: {link} ✨ Use code {promo_code} for discount!",
    "style": "Hey {username}! So happy you liked the style! Here are the styling details: {link} (Code: {promo_code})",
    "price": "Hey {username}! The product is priced at {price}. Direct link: {link} (Use code {promo_code}!)",
    "outfit": "Hey gorgeous! Here is where I got this outfit: {link} ✨ Promo code: {promo_code}",
    "skincare": "Hey {username}! My daily skincare secret is here: {link} ✨ Enjoy {promo_code} at checkout!",
}


class OpenInstaDMAgent:
    """
    Automated Comment-to-DM conversion agent based on Xeven777/openinstadm.
    """

    def __init__(self, brand_id: Optional[int] = None):
        self.brand_id = brand_id
        db.init_db()

    def detect_trigger(self, comment_text: str) -> Optional[str]:
        """Checks if a user's comment contains any conversion keywords."""
        text_lower = comment_text.lower()
        for keyword in DEFAULT_TRIGGERS:
            if re.search(rf"\b{keyword}\b", text_lower):
                return keyword
        return None

    def process_comment(
        self,
        username: str,
        comment_text: str,
        post_id: Optional[int] = None,
        brand_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Parses a fan comment, selects an active affiliate offer, generates the personalized DM,
        and logs the lead into the database.
        """
        trigger = self.detect_trigger(comment_text)
        if not trigger:
            return {"status": "ignored", "reason": "No conversion trigger keyword detected"}

        # Fetch active brand product
        active_brands = db.list_brands(active_only=True)
        brand = active_brands[0] if active_brands else {
            "name": "Aisha Boutique",
            "product": "Signature Collection",
            "price": "₹499",
            "link": "https://aishafashion.in/vip",
            "promo_code": "AISHA50",
        }

        template = DEFAULT_TRIGGERS.get(trigger, DEFAULT_TRIGGERS["link"])
        dm_text = template.format(
            username=username,
            link=brand.get("link", "https://aishafashion.in/vip"),
            promo_code=brand.get("promo_code", "AISHA50"),
            price=brand.get("price", "exclusive"),
        )

        # Record lead into SQLite dm_leads
        lead_id = db.record_dm_lead(
            username=username,
            message=comment_text,
            product_interest=brand.get("product", "general"),
            platform="instagram",
            intent=f"trigger_{trigger}",
            notes=f"Auto-generated DM sent via openinstadm trigger '{trigger}'",
        )

        db.log_audit_event(
            "COMMENT_TO_DM_SENT",
            f"Auto DM queued to @{username} for trigger '{trigger}' (Lead ID: {lead_id})",
            source="openinstadm",
        )

        logger.info(f"✅ openinstadm: Auto DM queued for @{username} (Trigger: '{trigger}')")

        return {
            "status": "success",
            "lead_id": lead_id,
            "username": username,
            "trigger": trigger,
            "dm_text": dm_text,
            "brand": brand.get("name"),
            "product": brand.get("product"),
            "promo_code": brand.get("promo_code"),
        }

    def batch_process_comments(self, comments: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Processes a list of recent post comments in batch."""
        results = []
        for c in comments:
            username = c.get("username", "fan")
            text = c.get("text", "")
            res = self.process_comment(username=username, comment_text=text)
            results.append(res)
        return results


# Global singleton
openinstadm_agent = OpenInstaDMAgent()
