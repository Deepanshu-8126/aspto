"""
AI-INFLUENCER-OS — Instagram Auto-Poster for GitHub Actions
"""

import os
import logging
from pathlib import Path
from typing import Optional

try:
    from instagrapi import Client  # type: ignore
except ImportError:
    Client = None

logger = logging.getLogger("instagram_poster")


def post_to_instagram(
    video_path: str,
    caption: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[str]:
    """Upload Reel to Instagram."""
    user = username or os.environ.get("IG_USERNAME")
    pwd = password or os.environ.get("IG_PASSWORD")

    if not user or not pwd or user == "CHANGE_ME":
        logger.warning("Instagram credentials not provided in environment. Skipping upload.")
        return None

    if Client is None:
        logger.error("instagrapi not installed.")
        return None

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None

    client = Client()
    try:
        logger.info(f"Logging in to Instagram as @{user}...")
        client.login(user, pwd)

        logger.info("Uploading Reel...")
        media = client.clip_upload(
            path=Path(video_path),
            caption=caption,
        )

        ig_url = f"https://www.instagram.com/reel/{media.pk}/"
        logger.info(f"✅ Reel posted successfully: {ig_url}")
        return ig_url

    except Exception as e:
        logger.error(f"Failed to post to Instagram: {e}")
        return None
