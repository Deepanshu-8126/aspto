"""
AI-INFLUENCER-OS — Telegram Notifier for GitHub Actions
Sends 'Done Boss' update and video preview directly to user's Telegram.
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger("telegram_notifier")


def send_telegram_update(
    message: str,
    video_path: Optional[str] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """Send message and optional video preview to Telegram admin."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    admin_id = chat_id or os.environ.get("TELEGRAM_ADMIN_CHAT_ID")

    if not token or not admin_id or token == "CHANGE_ME":
        logger.warning("Telegram credentials not configured. Skipping notification.")
        return False

    base_url = f"https://api.telegram.org/bot{token}"

    try:
        # Send text message
        payload = {
            "chat_id": admin_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        resp = requests.post(f"{base_url}/sendMessage", json=payload, timeout=20)
        resp.raise_for_status()

        # Send video preview if available and < 50MB
        if video_path and os.path.exists(video_path):
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            if file_size_mb <= 48:
                logger.info(f"Sending video preview ({file_size_mb:.1f} MB)...")
                with open(video_path, "rb") as f:
                    files = {"video": f}
                    data = {"chat_id": admin_id, "caption": "🎬 Video Preview (4K / 1080p)"}
                    requests.post(f"{base_url}/sendVideo", data=data, files=files, timeout=60)
            else:
                logger.info(f"Video file is {file_size_mb:.1f} MB (>50MB Telegram limit). Sent notification without video attachment.")

        return True

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False
