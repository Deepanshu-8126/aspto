"""
AIInfluencerOS — Main Entry Point
Wires together: Telegram Bot + Scheduler + Cloud Client + Instagram + WhatsApp
Runs on your i5 laptop 24/7 (low CPU, low RAM).
"""

import os
import sys
import json
import asyncio
import logging

import yaml
from dotenv import load_dotenv

# Load master .env
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from local.cloud_client import CloudClient
from local.instagram_service import InstagramService
from local.whatsapp_service import WhatsAppService
from local.telegram_bot import TelegramBot
from local.scheduler import PostScheduler
from local import database as db

# ── Logging ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/aiinfluencer.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ── Config Loader ────────────────────────────────────────

def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_personality() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "personality.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Service Initialization ───────────────────────────────

def init_services(config: dict, personality: dict):
    """Initialize all services."""

    # Database
    db.init_db()
    brands_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "brands.json")
    db.seed_brands_from_json(brands_json)
    logger.info("✅ Database initialized")

    # Cloud Client
    cloud_client = CloudClient(
        gradio_url=config["cloud"]["gradio_url"],
        timeout=config["cloud"]["timeout"],
        retry_attempts=config["cloud"]["retry_attempts"],
        retry_delay=config["cloud"]["retry_delay"],
    )
    logger.info("✅ Cloud client initialized")

    # Instagram Service
    ig_conf = config.get("instagram", {})
    instagram = InstagramService(
        username=ig_conf.get("username", os.environ.get("IG_USERNAME", "")),
        password=ig_conf.get("password", os.environ.get("IG_PASSWORD", "")),
        session_id=ig_conf.get("session_id", os.environ.get("IG_SESSION_ID", "")),
        max_posts_per_day=ig_conf.get("max_posts_per_day", 5),
        delay_min=ig_conf.get("human_delay_min", 60),
        delay_max=ig_conf.get("human_delay_max", 300),
    )
    ig_logged_in = instagram.login()
    if ig_logged_in:
        logger.info("✅ Instagram logged in")
    else:
        logger.warning("⚠️ Instagram login failed — posting will be disabled")

    # WhatsApp Service
    whatsapp = WhatsAppService(
        api_url=config["whatsapp"]["api_url"],
        session_id=config["whatsapp"]["session_id"],
        max_dms_per_day=config["whatsapp"]["max_dms_per_day"],
        reply_delay_min=config["whatsapp"]["reply_delay_min"],
        reply_delay_max=config["whatsapp"]["reply_delay_max"],
        personality=personality,
    )
    logger.info("✅ WhatsApp service initialized")

    # Scheduler
    scheduler = PostScheduler(
        cloud_client=cloud_client,
        instagram_service=instagram,
        database_module=db,
        config=config,
    )
    logger.info("✅ Scheduler initialized")

    # Telegram Bot
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("telegram", {}).get("bot_token", "")
    tg_admin = os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or config.get("telegram", {}).get("admin_chat_id", "")
    telegram = TelegramBot(
        bot_token=tg_token,
        admin_chat_id=tg_admin,
        cloud_client=cloud_client,
        instagram_service=instagram,
        whatsapp_service=whatsapp,
        scheduler=scheduler,
        database_module=db,
    )
    logger.info("✅ Telegram bot initialized")

    return {
        "cloud": cloud_client,
        "instagram": instagram,
        "whatsapp": whatsapp,
        "scheduler": scheduler,
        "telegram": telegram,
    }


# ── Main ─────────────────────────────────────────────────

def main():
    """Start all services."""
    logger.info("=" * 60)
    logger.info("🚀 AIInfluencerOS Starting...")
    logger.info("=" * 60)

    config = load_config()
    personality = load_personality()

    services = init_services(config, personality)

    # Start scheduler
    services["scheduler"].start()
    logger.info("⏰ Auto-post scheduler running")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("telegram", {}).get("bot_token", "")
    if not bot_token or bot_token == "CHANGE_ME":
        logger.warning("=" * 60)
        logger.warning("⚠️ TELEGRAM BOT TOKEN IS NOT CONFIGURED ('CHANGE_ME')")
        logger.warning("   To use Telegram commands, get a token from @BotFather and update config/config.yaml")
        logger.warning("   Scheduler is active. Press Ctrl+C to exit.")
        logger.warning("=" * 60)
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            services["scheduler"].stop()
            asyncio.run(services["cloud"].close())
            asyncio.run(services["whatsapp"].close())
        return

    # Build Telegram bot
    bot_app = services["telegram"].build()

    # Register post-shutdown hook for clean teardown
    async def post_shutdown(application):
        logger.info("Cleaning up services...")
        services["scheduler"].stop()
        await services["cloud"].close()
        await services["whatsapp"].close()

    bot_app.post_shutdown = post_shutdown

    logger.info("=" * 60)
    logger.info("✅ AIInfluencerOS is LIVE!")
    logger.info("   • Telegram bot: Ready")
    logger.info("   • Scheduler: Running")
    logger.info("   • Instagram: " + ("Connected" if services["instagram"]._logged_in else "Disconnected"))
    logger.info("=" * 60)

    # Run the bot (this blocks and handles event loop + signal handling)
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 AIInfluencerOS shutting down...")
