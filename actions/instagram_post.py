"""
AI-INFLUENCER-OS — Instagram Post Module
Posts 4K Reels to Instagram via instagrapi.
"""

import os
import logging
from pathlib import Path
from typing import Optional

try:
    from instagrapi import Client  # type: ignore
except ImportError:
    Client = None

logger = logging.getLogger("instagram_post")


def upload_reel(
    video_path: str,
    caption: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[str]:
    """Uploads a Reel to Instagram and returns the public post URL."""
    user = username or os.environ.get("IG_USERNAME")
    pwd = password or os.environ.get("IG_PASSWORD")

    if not user or not pwd or user == "CHANGE_ME":
        logger.warning("Instagram credentials not set in secrets. Skipping upload.")
        return None

    if Client is None:
        logger.error("instagrapi is not installed.")
        return None

    if not os.path.exists(video_path):
        logger.error(f"Video file missing: {video_path}")
        return None

    client = Client()
    try:
        logger.info(f"Logging in to Instagram as @{user}...")
        client.login(user, pwd)

        logger.info(f"Uploading Reel: {video_path}...")
        media = client.clip_upload(
            path=Path(video_path),
            caption=caption,
        )

        post_url = f"https://www.instagram.com/reel/{media.pk}/"
        logger.info(f"🎉 Reel live on Instagram: {post_url}")
        return post_url

    except Exception as e:
        logger.error(f"Instagram upload failed: {e}")
        return None


# Backward-compatible alias
post_reel = upload_reel

