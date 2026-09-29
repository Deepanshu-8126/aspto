"""
AI-INFLUENCER-OS — Advanced Telegram Preview & Inline Keyboard Approval Flow
Sends 4K video preview with interactive inline buttons [✅ APPROVE & POST] and [❌ REJECT].
"""

import os
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger("telegram_approval")


class TelegramApproval:
    """Handles Telegram video preview with interactive inline buttons & text replies."""

    def __init__(self, bot_token: Optional[str] = None, admin_chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = admin_chat_id or os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and self.bot_token != "CHANGE_ME")

    def send_preview(self, video_path: str, caption: str, reel_url: str) -> Optional[int]:
        """Send video preview with interactive inline buttons."""
        if not self.is_configured():
            logger.warning("Telegram not configured. Skipping preview.")
            return None

        text = (
            "👑 **AI Influencer — Review Ready!** 🎬\n\n"
            f"📝 **Caption:**\n_{caption[:250]}..._\n\n"
            f"🔗 **Reference Reel:** {reel_url}\n\n"
            "Tap a button below or reply **APPROVE** to post to Instagram:"
        )

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚀 APPROVE & POST REEL", "callback_data": "approve_post"},
                    {"text": "🛑 CANCEL", "callback_data": "reject_post"},
                ]
            ]
        }

        try:
            # 1. Send video preview if available (< 50MB)
            if os.path.exists(video_path) and os.path.getsize(video_path) <= 49 * 1024 * 1024:
                logger.info("Sending video preview to Telegram...")
                with open(video_path, "rb") as f:
                    requests.post(
                        f"{self.base_url}/sendVideo",
                        data={"chat_id": self.chat_id, "caption": "🎬 4K Video Preview (AI-Generated)"},
                        files={"video": f},
                        timeout=60,
                    )

            # 2. Send action card with inline buttons
            msg_resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": inline_keyboard,
                },
                timeout=15,
            )
            msg_resp.raise_for_status()

            # Record latest update ID to avoid processing past events
            updates = requests.get(f"{self.base_url}/getUpdates", timeout=10).json()
            latest_id = updates["result"][-1]["update_id"] if updates.get("result") else 0
            return latest_id

        except Exception as e:
            logger.error(f"Failed to send Telegram preview: {e}")
            return None

    def wait_for_approval(self, last_update_id: int, timeout_minutes: int = 15) -> bool:
        """
        Polls Telegram updates for inline button clicks or text replies.
        If AUTO_POST is set to 'true', approves automatically.
        """
        if os.environ.get("AUTO_POST", "true").lower() == "true":
            logger.info("AUTO_POST=true is enabled. Auto-approving post.")
            return True

        logger.info(f"Waiting for Telegram approval (timeout {timeout_minutes} mins)...")
        start_time = time.time()
        timeout_sec = timeout_minutes * 60

        while time.time() - start_time < timeout_sec:
            try:
                resp = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": last_update_id + 1, "timeout": 10},
                    timeout=15,
                )
                data = resp.json()
                for item in data.get("result", []):
                    last_update_id = item["update_id"]

                    # Check 1: Button click (callback query)
                    cb = item.get("callback_query")
                    if cb:
                        cb_data = cb.get("data", "")
                        cb_id = cb.get("id")
                        requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": cb_id})

                        if cb_data == "approve_post":
                            logger.info("✅ Post APPROVED via Telegram Button!")
                            requests.post(f"{self.base_url}/sendMessage", json={"chat_id": self.chat_id, "text": "🚀 Button tapped: Posting to Instagram now!"})
                            return True
                        elif cb_data == "reject_post":
                            logger.info("❌ Post REJECTED via Telegram Button.")
                            requests.post(f"{self.base_url}/sendMessage", json={"chat_id": self.chat_id, "text": "🛑 Post cancelled."})
                            return False

                    # Check 2: Text message reply
                    msg = item.get("message", {}).get("text", "").strip().upper()
                    sender = str(item.get("message", {}).get("chat", {}).get("id"))
                    if sender == str(self.chat_id):
                        if any(w in msg for w in ["APPROVE", "POST", "YES", "OK", "HAAN"]):
                            logger.info("✅ Post APPROVED via text reply!")
                            requests.post(f"{self.base_url}/sendMessage", json={"chat_id": self.chat_id, "text": "🚀 Posting to Instagram now!"})
                            return True
                        elif any(w in msg for w in ["REJECT", "NO", "CANCEL", "MAT KAR"]):
                            logger.info("❌ Post REJECTED via text reply.")
                            requests.post(f"{self.base_url}/sendMessage", json={"chat_id": self.chat_id, "text": "🛑 Post cancelled."})
                            return False

            except Exception as e:
                logger.warning(f"Error checking Telegram updates: {e}")

            time.sleep(5)

        logger.warning("Approval timed out. Skipping post.")
        return False
