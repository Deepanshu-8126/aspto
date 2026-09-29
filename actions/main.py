"""
AI-INFLUENCER-OS — GitHub Actions Daily Pipeline Orchestrator
Zero Laptop Load — runs on GitHub runners + Hugging Face Spaces.
"""

import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("actions_main")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from actions.motion_extractor import get_next_target
from actions.hf_client import MultiAccountHFClient
from actions.instagram_poster import post_to_instagram
from actions.telegram_notifier import send_telegram_update


def run():
    logger.info("=" * 60)
    logger.info("🚀 AI-INFLUENCER-OS — Daily Pipeline Starting")
    logger.info(f"   Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # 1. Config & Spaces
    video_space = os.environ.get("HF_VIDEO_SPACE", "").strip()
    upscaler_space = os.environ.get("HF_UPSCALER_SPACE", "").strip()

    if not video_space:
        logger.error("HF_VIDEO_SPACE environment variable is missing! e.g., 'your-username/video-gen'")
        send_telegram_update("❌ **Pipeline Error:** HF_VIDEO_SPACE secret is missing in GitHub repository settings.")
        sys.exit(1)

    # 2. Extract next target from links.txt or manual input
    target = None
    manual_url = os.environ.get("MANUAL_REEL_URL")
    if manual_url:
        target = {
            "url": manual_url,
            "dress": os.environ.get("MANUAL_DRESS", "chic modern aesthetic outfit"),
            "bg": os.environ.get("MANUAL_BG", "luxury penthouse balcony"),
            "topic": os.environ.get("MANUAL_TOPIC", "viral trending dance"),
        }
        logger.info(f"Using manual target input: {target['url']}")
    else:
        target = get_next_target("links.txt")

    if not target or not target.get("url"):
        logger.warning("No target reel found in links.txt. Nothing to process.")
        send_telegram_update("⚠️ **Notice:** No active target reel found in `links.txt` queue.")
        return

    logger.info(f"🎯 Target Reel: {target['url']}")
    logger.info(f"👗 Outfit: {target['dress']}")
    logger.info(f"🌆 Scene: {target['bg']}")

    # 3. Call Hugging Face Spaces (Wan2.1 Motion Transfer + SD1.5 + LoRA + Llama 3.1)
    hf_client = MultiAccountHFClient(video_space=video_space, upscaler_space=upscaler_space)

    try:
        video_1080p, caption = hf_client.generate_video(
            instagram_url=target["url"],
            dress=target["dress"],
            bg=target["bg"],
            topic=target.get("topic", "trending dance"),
        )
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        send_telegram_update(f"❌ **Generation Failed:** {e}")
        sys.exit(1)

    # 4. Optional 4K Upscale via Real-ESRGAN Space
    final_video = video_1080p
    if upscaler_space:
        logger.info("✨ Upscaling to 4K via Real-ESRGAN Space...")
        final_video = hf_client.upscale_to_4k(video_1080p)

    # 5. Auto-Post to Instagram
    ig_url = post_to_instagram(video_path=final_video, caption=caption)

    # 6. Telegram "Done Boss" Notification
    status_msg = (
        "👑 **Done Boss! Aaj ki Reel Ban Gayi!** 🎬\n\n"
        f"📝 **Caption:**\n_{caption[:200]}..._\n\n"
        f"👗 **Dress:** `{target['dress']}`\n"
        f"🌆 **Scene:** `{target['bg']}`\n\n"
        f"🔗 **Original Ref:** {target['url']}\n"
    )

    if ig_url:
        status_msg += f"✅ **Instagram Post:** [Watch Reel]({ig_url})\n"
    else:
        status_msg += "⚠️ *Instagram Auto-Post skipped/unconfigured — video saved in GitHub artifacts.*\n"

    status_msg += "\n🔥 *Generated 100% on Hugging Face ZeroGPU (Zero Laptop Load)*"

    send_telegram_update(
        message=status_msg,
        video_path=final_video,
    )

    logger.info("=" * 60)
    logger.info("🎉 Daily Pipeline Finished Successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
