"""
AIInfluencerOS — Telegram Bot
Command handler for /generate, /post, /schedule, /status, /brand, /analytics, /voice.
"""

import os
import json
import logging
import asyncio
from functools import wraps

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger("telegram_bot")


class TelegramBot:
    """Telegram bot controller for AIInfluencerOS."""

    def __init__(
        self,
        bot_token: str,
        admin_chat_id: str,
        cloud_client,
        instagram_service,
        whatsapp_service,
        scheduler,
        database_module,
    ):
        self.bot_token = bot_token
        self.admin_chat_id = str(admin_chat_id)
        self.cloud = cloud_client
        self.instagram = instagram_service
        self.whatsapp = whatsapp_service
        self.scheduler = scheduler
        self.db = database_module
        self.app = None
        self._last_generated_video = None

    def _admin_only(self, func):
        """Decorator to restrict commands to admin only."""
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if str(update.effective_chat.id) != self.admin_chat_id:
                await update.message.reply_text("⛔ Unauthorized. Admin only.")
                return
            return await func(update, context)
        return wrapper

    async def _setup_commands(self, app: Application):
        """Register bot commands for the menu."""
        commands = [
            BotCommand("generate", "Generate a reel — /generate <topic> --brand <id>"),
            BotCommand("post", "Post last generated reel to Instagram"),
            BotCommand("schedule", "Schedule a post — /schedule <HH:MM> [topic]"),
            BotCommand("status", "Pipeline status + today's posts"),
            BotCommand("brand", "Brand management — add/list/remove"),
            BotCommand("analytics", "Account analytics"),
            BotCommand("voice", "Update voice sample"),
            BotCommand("help", "Show all commands"),
        ]
        await app.bot.set_my_commands(commands)

    def build(self) -> Application:
        """Build the Telegram bot application."""
        self.app = Application.builder().token(self.bot_token).build()

        # Register handlers (all admin-restricted)
        handlers = {
            "generate": self._cmd_generate,
            "post": self._cmd_post,
            "schedule": self._cmd_schedule,
            "status": self._cmd_status,
            "brand": self._cmd_brand,
            "analytics": self._cmd_analytics,
            "voice": self._cmd_voice,
            "help": self._cmd_help,
            "start": self._cmd_help,
        }

        for cmd, handler in handlers.items():
            self.app.add_handler(CommandHandler(cmd, self._admin_only(handler)))

        # Post-init hook for command menu
        self.app.post_init = self._setup_commands

        return self.app

    # ── Command Handlers ─────────────────────────────────

    async def _cmd_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /generate <topic> --brand <id>
        Triggers full content generation pipeline.
        """
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ Usage: `/generate <topic> --brand <id>`\n"
                "Example: `/generate summer skincare --brand 1`",
                parse_mode="Markdown",
            )
            return

        # Parse topic and brand
        full_text = " ".join(args)
        brand_id = 0
        topic = full_text

        if "--brand" in full_text:
            parts = full_text.split("--brand")
            topic = parts[0].strip()
            try:
                brand_id = int(parts[1].strip())
            except (ValueError, IndexError):
                brand_id = 0

        await update.message.reply_text(
            f"🎬 **Generating Reel**\n\n"
            f"📝 Topic: `{topic}`\n"
            f"🏷️ Brand ID: `{brand_id}`\n\n"
            f"⏳ This takes ~10-15 min. I'll notify you when done!",
            parse_mode="Markdown",
        )

        # Create DB record
        post_id = self.db.create_post(topic=topic, brand_id=brand_id if brand_id > 0 else None)

        # Trigger cloud generation
        try:
            is_healthy = await self.cloud.health_check()
            if not is_healthy:
                await update.message.reply_text("⚠️ Cloud GPU is offline. Check Colab session.")
                self.db.update_post(post_id, status="failed")
                return

            result = await self.cloud.generate(topic, brand_id)
            task_id = result.get("task_id", "unknown") if isinstance(result, dict) else str(result)

            await update.message.reply_text(f"✅ Queued! Task ID: `{task_id}`", parse_mode="Markdown")

            # Wait for completion in background
            asyncio.create_task(
                self._wait_and_notify(update.effective_chat.id, task_id, post_id, context)
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")
            self.db.update_post(post_id, status="failed")

    async def _wait_and_notify(self, chat_id, task_id, post_id, context):
        """Background task: wait for generation, then notify."""
        try:
            # Wait for the specific task to finish
            status = await self.cloud.wait_for_completion(task_id)
            video_path = await self.cloud.download_output(task_id)

            if video_path:
                self._last_generated_video = video_path
                self.db.update_post(post_id, video_path=video_path, status="generated")

                await context.bot.send_message(
                    chat_id,
                    f"✅ **Reel Generated!**\n\n"
                    f"📁 `{os.path.basename(video_path)}`\n\n"
                    f"Use /post to publish to Instagram.",
                    parse_mode="Markdown",
                )

                # Send video preview
                try:
                    with open(video_path, "rb") as f:
                        await context.bot.send_video(chat_id, f, caption="Preview 🎬")
                except Exception:
                    pass
            else:
                self.db.update_post(post_id, status="failed")
                await context.bot.send_message(chat_id, "❌ Generation failed. Check cloud logs.")

        except Exception as e:
            self.db.update_post(post_id, status="failed")
            await context.bot.send_message(chat_id, f"❌ Pipeline error: `{e}`", parse_mode="Markdown")

    async def _cmd_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/post — Post last generated reel to Instagram."""
        if not self._last_generated_video:
            # Check DB for latest generated post
            posts = self.db.get_posts_by_status("generated")
            if posts:
                self._last_generated_video = posts[0].get("video_path")
            else:
                await update.message.reply_text("❌ No generated reel found. Use /generate first.")
                return

        await update.message.reply_text("📤 Posting to Instagram...")

        post = self.db.get_posts_by_status("generated")
        caption = post[0].get("caption", "✨") if post else "✨ New Reel ✨"
        hashtags = json.loads(post[0].get("hashtags", "[]")) if post else []

        ig_url = self.instagram.post_reel(
            self._last_generated_video,
            caption=caption,
            hashtags=hashtags,
        )

        if ig_url:
            if post:
                self.db.update_post(post[0]["id"], ig_url=ig_url, status="posted")
            await update.message.reply_text(
                f"✅ **Posted!**\n\n🔗 {ig_url}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("❌ Failed to post. Check Instagram login.")

    async def _cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/schedule <HH:MM> [topic] — Schedule a post."""
        args = context.args
        if not args:
            jobs = self.scheduler.get_scheduled_jobs()
            if jobs:
                lines = ["📅 **Scheduled Posts:**\n"]
                for j in jobs:
                    lines.append(f"• `{j['id']}` → {j['next_run']}")
                await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "❌ Usage: `/schedule 18:00 skincare tips`\n"
                    "Or just `/schedule` to see scheduled posts.",
                    parse_mode="Markdown",
                )
            return

        time_str = args[0]
        topic = " ".join(args[1:]) if len(args) > 1 else "lifestyle tips"

        try:
            scheduled_time = self.scheduler.schedule_single_post(time_str, topic)
            await update.message.reply_text(
                f"✅ **Scheduled!**\n\n"
                f"⏰ {scheduled_time}\n"
                f"📝 {topic}",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/status — Show pipeline status and today's posts."""
        today_posts = self.db.get_today_posts()
        analytics = self.db.get_analytics()

        cloud_healthy = await self.cloud.health_check()
        cloud_status = "🟢 Online" if cloud_healthy else "🔴 Offline"

        scheduler_status = "🟢 Running" if self.scheduler.is_running else "🔴 Stopped"

        lines = [
            "📊 **AIInfluencerOS Status**\n",
            f"☁️ Cloud GPU: {cloud_status}",
            f"⏰ Scheduler: {scheduler_status}",
            f"📱 Posts Today: {analytics['today_posts']}",
            f"📈 Total Posts: {analytics['total_posts']}",
            f"👀 Total Views: {analytics['total_views']}",
            f"❤️ Total Likes: {analytics['total_likes']}",
            f"💬 Total Comments: {analytics['total_comments']}",
            f"📩 DM Leads: {analytics['total_leads']}",
        ]

        if today_posts:
            lines.append("\n**Today's Posts:**")
            for p in today_posts[:5]:
                status_icon = {"posted": "✅", "generated": "🎬", "pending": "⏳", "failed": "❌"}.get(p["status"], "❓")
                lines.append(f"{status_icon} {p['topic'][:30]} — {p['status']}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_brand(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/brand add|list|remove — Brand management."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "🏷️ **Brand Commands:**\n\n"
                "`/brand list` — Show all brands\n"
                "`/brand add <name> <product> <price>` — Add brand\n"
                "`/brand remove <id>` — Remove brand",
                parse_mode="Markdown",
            )
            return

        action = args[0].lower()

        if action == "list":
            brands = self.db.list_brands(active_only=False)
            if not brands:
                await update.message.reply_text("No brands yet. Use `/brand add`.", parse_mode="Markdown")
                return

            lines = ["🏷️ **Brands:**\n"]
            for b in brands:
                status = "✅" if b["active"] else "❌"
                lines.append(f"{status} **{b['id']}**: {b['name']} — {b['product']} ({b['price']})")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        elif action == "add" and len(args) >= 3:
            name = args[1]
            product = args[2]
            price = args[3] if len(args) > 3 else ""
            brand_id = self.db.add_brand(name, product, price)
            await update.message.reply_text(
                f"✅ Brand added! ID: `{brand_id}`\n"
                f"Name: {name}\nProduct: {product}\nPrice: {price}",
                parse_mode="Markdown",
            )

        elif action == "remove" and len(args) >= 2:
            try:
                brand_id = int(args[1])
                self.db.delete_brand(brand_id)
                await update.message.reply_text(f"✅ Brand {brand_id} deactivated.")
            except ValueError:
                await update.message.reply_text("❌ Invalid brand ID.")

        else:
            await update.message.reply_text("❌ Invalid usage. Try `/brand list`.", parse_mode="Markdown")

    async def _cmd_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/analytics — Show account analytics."""
        db_analytics = self.db.get_analytics()
        ig_insights = self.instagram.get_account_insights()

        lines = [
            "📊 **Analytics Dashboard**\n",
            "**Instagram:**",
            f"👤 Followers: {ig_insights.get('followers', 'N/A')}",
            f"📱 Posts: {ig_insights.get('posts', 'N/A')}",
            f"➡️ Following: {ig_insights.get('following', 'N/A')}",
            "",
            "**AIInfluencerOS:**",
            f"🎬 Total Reels: {db_analytics['total_posts']}",
            f"👀 Total Views: {db_analytics['total_views']}",
            f"❤️ Total Likes: {db_analytics['total_likes']}",
            f"💬 Total Comments: {db_analytics['total_comments']}",
            f"📩 DM Leads: {db_analytics['total_leads']}",
        ]

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/voice update — Upload new voice sample."""
        await update.message.reply_text(
            "🎤 **Voice Update**\n\n"
            "Send a 5-second WAV audio file as a reply to this message.\n"
            "This will update your AI voice clone.",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/help — Show all commands."""
        help_text = """
🤖 **AIInfluencerOS Commands**

🎬 **Content:**
`/generate <topic> --brand <id>` — Generate reel
`/post` — Post last reel to Instagram
`/schedule <HH:MM> [topic]` — Schedule post

📊 **Monitoring:**
`/status` — Pipeline + posts status
`/analytics` — Views, likes, followers

🏷️ **Brands:**
`/brand list` — Show all brands
`/brand add <name> <product> <price>`
`/brand remove <id>`

🎤 **Settings:**
`/voice update` — Update voice sample
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def send_notification(self, message: str):
        """Send a notification to the admin."""
        if self.app and self.app.bot:
            await self.app.bot.send_message(self.admin_chat_id, message, parse_mode="Markdown")
