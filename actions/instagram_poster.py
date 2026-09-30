"""
AI-INFLUENCER-OS — Instagram Auto-Poster
Supports: Photo posts + Video Reels with auto-detection
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

try:
    from instagrapi import Client  # type: ignore
except ImportError:
    Client = None

logger = logging.getLogger("instagram_poster")

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi"}


def _get_client() -> Optional["Client"]:
    session_id  = os.environ.get("IG_SESSION_ID", "")
    user        = os.environ.get("IG_USERNAME", "")
    pwd         = os.environ.get("IG_PASSWORD", "")
    session_file = "data/ig_session.json"

    if Client is None:
        logger.error("instagrapi not installed.")
        return None

    client = Client()
    try:
        if session_id:
            client.login_by_sessionid(session_id)
            logger.info("Logged in via SESSION_ID")
        elif os.path.exists(session_file):
            client.load_settings(session_file)
            client.login(user, pwd)
            logger.info("Logged in via session_file")
        elif user and pwd:
            client.login(user, pwd)
            os.makedirs("data", exist_ok=True)
            client.dump_settings(session_file)
            logger.info(f"Fresh login as @{user}")
        else:
            logger.error("No Instagram credentials found!")
            return None
        return client
    except Exception as e:
        logger.error(f"Instagram login failed: {e}")
        return None


def post_to_instagram(
    video_path: str,
    caption: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    media_type: Optional[str] = None,   # "photo" | "video" | None (auto-detect)
) -> Optional[str]:
    """Upload Photo or Reel to Instagram — auto-detects media type."""

    if not os.path.exists(video_path):
        logger.error(f"Media file not found: {video_path}")
        return None

    client = _get_client()
    if not client:
        return None

    ext = Path(video_path).suffix.lower()

    # Auto-detect: force media_type if passed, else detect from extension
    is_photo = (media_type == "photo") or (media_type is None and ext in PHOTO_EXTS)
    is_video = (media_type == "video") or (media_type is None and ext in VIDEO_EXTS)

    try:
        if is_photo:
            logger.info(f"Uploading Photo to Instagram: {video_path}")
            media = client.photo_upload(
                path=Path(video_path),
                caption=caption,
            )
            ig_url = f"https://www.instagram.com/p/{media.pk}/"
            logger.info(f"✅ Photo posted: {ig_url}")
            return ig_url

        elif is_video:
            logger.info(f"Uploading Reel to Instagram: {video_path}")
            # Retry once on media_needs_reupload
            for attempt in range(2):
                try:
                    media = client.clip_upload(
                        path=Path(video_path),
                        caption=caption,
                    )
                    ig_url = f"https://www.instagram.com/reel/{media.pk}/"
                    logger.info(f"✅ Reel posted: {ig_url}")
                    return ig_url
                except Exception as e:
                    if "media_needs_reupload" in str(e) and attempt == 0:
                        logger.warning("media_needs_reupload — retrying in 3s...")
                        time.sleep(3)
                        continue
                    raise
        else:
            logger.error(f"Unknown media type for extension: {ext}")
            return None

    except Exception as e:
        logger.error(f"Failed to post to Instagram: {e}")
        return None

