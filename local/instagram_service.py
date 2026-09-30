"""
AIInfluencerOS — Instagram Service (instagrapi wrapper)
Handles posting Reels, Stories, and DM automation with session recovery,
URL-to-PK resolution, and rate limiting.
"""

import os
import time
import random
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path

from instagrapi import Client  # type: ignore

logger = logging.getLogger("instagram")


class InstagramService:
    """Wrapper around instagrapi for Instagram automation."""

    def __init__(
        self,
        username: str,
        password: str,
        session_id: str = "",
        max_posts_per_day: int = 5,
        delay_min: int = 60,
        delay_max: int = 300,
    ):
        self.username = username
        self.password = password
        self.session_id = session_id
        self.max_posts_per_day = max_posts_per_day
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.client = Client()
        self._logged_in = False
        self._posts_today = 0
        self._last_post_date = None

    def login(self, session_path: str = "data/ig_session.json") -> bool:
        """Login to Instagram with session caching and auto-recovery."""
        # 1. Direct login by session_id cookie (immune to out-of-date checks)
        if self.session_id and self.session_id != "CHANGE_ME":
            try:
                self.client.login_by_sessionid(self.session_id)
                os.makedirs(os.path.dirname(session_path), exist_ok=True)
                self.client.dump_settings(session_path)
                logger.info("Instagram: Logged in successfully via session_id")
                self._logged_in = True
                return True
            except Exception as e:
                logger.warning(f"session_id login notice: {e}")

        if not self.username or self.username == "CHANGE_ME" or not self.password or self.password == "CHANGE_ME":
            logger.warning("Instagram credentials not configured ('CHANGE_ME') — skipping login")
            self._logged_in = False
            return False

        # Attempt login using saved session
        if os.path.exists(session_path):
            try:
                self.client.load_settings(session_path)
                self.client.login(self.username, self.password)
                logger.info("Instagram: Logged in from saved session")
                self._logged_in = True
                return True
            except Exception as se:
                logger.warning(f"Saved session expired/invalid ({se}), attempting fresh login...")
                try:
                    os.remove(session_path)
                except OSError:
                    pass

        # Fresh login
        try:
            self.client.login(self.username, self.password)
            os.makedirs(os.path.dirname(session_path), exist_ok=True)
            self.client.dump_settings(session_path)
            logger.info("Instagram: Fresh login successful")
            self._logged_in = True
            return True
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            self._logged_in = False
            return False

    def _check_rate_limit(self) -> bool:
        """Check if we're within daily post limits."""
        today = datetime.now().date()
        if self._last_post_date != today:
            self._posts_today = 0
            self._last_post_date = today
        return self._posts_today < self.max_posts_per_day

    def _human_delay(self, min_s: int = None, max_s: int = None):
        """Add random delay to mimic human behavior."""
        low = self.delay_min if min_s is None else min_s
        high = self.delay_max if max_s is None else max_s
        if high <= 0 or low < 0 or high < low:
            return
        delay = random.uniform(low, high)
        logger.info(f"Human delay: {delay:.0f}s")
        time.sleep(delay)

    def _resolve_media_pk(self, media_id: str) -> str:
        """Resolve a media ID, URL, or shortcode to numeric media PK."""
        if not media_id:
            return ""
        media_id_str = str(media_id).strip()
        if "instagram.com" in media_id_str:
            try:
                return str(self.client.media_pk_from_url(media_id_str))
            except Exception:
                pass
        return media_id_str

    def post_reel(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
        thumbnail_path: str = None,
    ) -> Optional[str]:
        """
        Post a Reel to Instagram.

        Args:
            video_path: Path to the MP4 file
            caption: Post caption text
            hashtags: List of hashtags (auto-appended to caption)
            thumbnail_path: Custom thumbnail image (optional)

        Returns:
            Instagram URL of the posted reel, or None on failure
        """
        if not self._logged_in:
            logger.error("Not logged in to Instagram")
            return None

        if not self._check_rate_limit():
            logger.warning(f"Rate limit reached ({self.max_posts_per_day} posts/day)")
            return None

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None

        # Build caption with hashtags
        full_caption = caption or ""
        if hashtags:
            clean_tags = [f"#{h.strip('#')}" for h in hashtags if h.strip('#')]
            if clean_tags:
                full_caption = f"{full_caption}\n\n{' '.join(clean_tags[:20])}".strip()

        try:
            self._human_delay()

            v_path = Path(video_path)
            t_path = Path(thumbnail_path) if thumbnail_path and os.path.exists(thumbnail_path) else None

            media = self.client.clip_upload(
                path=v_path,
                caption=full_caption,
                thumbnail=t_path,
            )

            self._posts_today += 1
            ig_url = f"https://www.instagram.com/reel/{media.pk}/"
            logger.info(f"Reel posted: {ig_url}")
            return ig_url

        except Exception as e:
            logger.error(f"Failed to post reel: {e}")
            return None

    def post_story(
        self,
        media_path: str,
        is_video: bool = True,
    ) -> Optional[str]:
        """
        Post a Story to Instagram.

        Returns:
            Story media ID, or None on failure
        """
        if not self._logged_in:
            logger.error("Not logged in to Instagram")
            return None

        if not os.path.exists(media_path):
            logger.error(f"Story media file not found: {media_path}")
            return None

        try:
            self._human_delay(min_s=5, max_s=15)

            p = Path(media_path)
            if is_video:
                media = self.client.video_upload_to_story(p)
            else:
                media = self.client.photo_upload_to_story(p)

            logger.info(f"Story posted: {media.pk}")
            return str(media.pk)

        except Exception as e:
            logger.error(f"Failed to post story: {e}")
            return None

    def send_dm(self, username: str, message: str) -> bool:
        """Send a DM to a user."""
        if not self._logged_in:
            logger.error("Not logged in to Instagram")
            return False

        try:
            user_id = self.client.user_id_from_username(username.lstrip("@"))
            self.client.direct_send(message, user_ids=[user_id])
            logger.info(f"DM sent to @{username}")
            return True
        except Exception as e:
            logger.error(f"Failed to send DM to @{username}: {e}")
            return False

    def reply_to_comment(self, media_id: str, comment_id: str, reply_text: str) -> bool:
        """Reply to a comment on a post."""
        if not self._logged_in:
            logger.error("Not logged in to Instagram")
            return False

        try:
            pk = self._resolve_media_pk(media_id)
            c_id = int(comment_id) if str(comment_id).isdigit() else None
            self.client.media_comment(pk, reply_text, replied_to_comment_id=c_id)
            return True
        except Exception as e:
            logger.error(f"Failed to reply to comment: {e}")
            return False

    def get_recent_comments(self, media_id: str, limit: int = 20) -> list:
        """Get recent comments on a post."""
        if not self._logged_in:
            logger.error("Not logged in to Instagram")
            return []

        try:
            pk = self._resolve_media_pk(media_id)
            comments = self.client.media_comments(pk, amount=limit)
            return [
                {
                    "id": str(c.pk),
                    "username": getattr(c.user, "username", "anonymous"),
                    "text": c.text,
                    "timestamp": c.created_at_utc.isoformat() if getattr(c, "created_at_utc", None) else "",
                }
                for c in comments
            ]
        except Exception as e:
            logger.error(f"Failed to get comments: {e}")
            return []

    def get_account_insights(self) -> dict:
        """Get basic account metrics."""
        if not self._logged_in:
            return {}

        try:
            info = self.client.account_info()
            return {
                "username": info.username,
                "followers": info.follower_count,
                "following": info.following_count,
                "posts": info.media_count,
            }
        except Exception as e:
            logger.error(f"Failed to get insights: {e}")
            return {}

    def get_media_insights(self, media_id: str) -> dict:
        """Get metrics for a specific post."""
        if not self._logged_in:
            return {}

        try:
            pk = self._resolve_media_pk(media_id)
            info = self.client.media_info(pk)
            return {
                "likes": getattr(info, "like_count", 0) or 0,
                "comments": getattr(info, "comment_count", 0) or 0,
                "views": getattr(info, "view_count", 0) or 0,
            }
        except Exception as e:
            logger.error(f"Failed to get media insights: {e}")
            return {}
