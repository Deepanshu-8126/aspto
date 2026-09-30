"""
AIInfluencerOS — Scheduler (APScheduler)
Handles automatic post scheduling with cron-based timing.
"""

import os
import json
import random
import logging
import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler")


class PostScheduler:
    """Manages automated content generation and posting schedule."""

    def __init__(
        self,
        cloud_client,
        instagram_service,
        database_module,
        config: dict,
    ):
        self.cloud = cloud_client
        self.instagram = instagram_service
        self.db = database_module
        self.config = config
        self.scheduler = BackgroundScheduler(
            timezone=config.get("scheduler", {}).get("timezone", "Asia/Kolkata")
        )
        self._running = False

    def _execute_async(self, coro_fn, *args, **kwargs):
        """Helper to run async jobs in BackgroundScheduler worker threads."""
        try:
            asyncio.run(coro_fn(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in scheduled task: {e}")

    def start(self):
        """Start the scheduler with configured post times."""
        if self._running:
            return

        post_times = self.config.get("scheduler", {}).get("post_times", [])
        topics = self.config.get("scheduler", {}).get("topics_rotation", [])

        for i, time_str in enumerate(post_times):
            hour, minute = map(int, time_str.split(":"))
            job_id = f"auto_post_{i}"

            self.scheduler.add_job(
                self._execute_async,
                CronTrigger(hour=hour, minute=minute),
                id=job_id,
                replace_existing=True,
                args=[self._auto_generate_and_post],
                kwargs={"topics": topics},
            )
            logger.info(f"Scheduled auto-post at {time_str}")

        self.scheduler.start()
        self._running = True
        logger.info(f"Scheduler started with {len(post_times)} daily slots")

    def stop(self):
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")

    def schedule_single_post(self, time_str: str, topic: str, brand_id: int = 0):
        """
        Schedule a single post at a specific time today.

        Args:
            time_str: Time in HH:MM format
            topic: Content topic
            brand_id: Optional brand ID
        """
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if run_time <= now:
            run_time += timedelta(days=1)

        job_id = f"single_post_{run_time.strftime('%H%M')}"

        self.scheduler.add_job(
            self._execute_async,
            "date",
            run_date=run_time,
            id=job_id,
            replace_existing=True,
            args=[self._auto_generate_and_post],
            kwargs={"topic": topic, "brand_id": brand_id},
        )

        logger.info(f"Single post scheduled at {run_time.strftime('%Y-%m-%d %H:%M')}")
        return run_time.strftime("%Y-%m-%d %H:%M")

    async def _auto_generate_and_post(
        self,
        topic: str = None,
        brand_id: int = 0,
        topics: list = None,
    ):
        """Auto-generate content and post it."""
        try:
            # Pick random topic if none specified
            if topic is None:
                if topics:
                    topic = random.choice(topics)
                else:
                    topic = "lifestyle tips"

            # Pick a random active brand
            if brand_id == 0:
                brands = self.db.list_brands(active_only=True)
                if brands:
                    brand = random.choice(brands)
                    brand_id = brand["id"]

            logger.info(f"Auto-generating: topic='{topic}', brand_id={brand_id}")

            # Create post record
            post_id = self.db.create_post(topic=topic, brand_id=brand_id)

            # Generate content via cloud
            video_path = await self.cloud.generate_and_wait(topic, brand_id)

            if video_path is None:
                self.db.update_post(post_id, status="failed")
                logger.error("Content generation failed")
                return

            self.db.update_post(post_id, video_path=video_path, status="generated")

            # Get caption from script data
            # (in real flow, the cloud returns this; here we generate locally)
            caption = f"✨ {topic} ✨\nDouble tap if this hits different! 💕"
            hashtags = [topic.replace(" ", ""), "reels", "viral", "trending", "explore"]

            self.db.update_post(post_id, caption=caption, hashtags=json.dumps(hashtags))

            # Post to Instagram using 8-Feature Anti-Detection Bridge
            from actions.instagram_bridge import InstagramAIAgentBridge
            bridge = InstagramAIAgentBridge(self.instagram)
            post_type = "photo" if video_path.lower().endswith((".png", ".jpg", ".jpeg")) else "reel"
            ig_url = bridge.publish_content_safely(video_path, caption, hashtags, post_type=post_type)

            if ig_url:
                self.db.update_post(post_id, ig_url=ig_url, status="posted")
                logger.info(f"✅ Auto-posted via anti-detection layer: {ig_url}")
            else:
                self.db.update_post(post_id, status="failed")
                logger.error("Instagram posting failed")

        except Exception as e:
            logger.error(f"Auto-post pipeline error: {e}")

    def get_scheduled_jobs(self) -> list:
        """Get all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M") if job.next_run_time else "N/A",
                "trigger": str(job.trigger),
            })
        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        return self._running
