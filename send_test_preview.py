import asyncio
import os
from dotenv import load_dotenv

load_dotenv("d:/ai_influencer/.env")
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def send_preview():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    bot = Bot(token=token)
    photo_path = r"d:\ai_influencer\output\images\diya_rai_cafe_bandra.jpg"

    caption = (
        "☕ <b>Diya Rai Feed Post Preview</b>\n\n"
        "<i>\"Coffee tastes 10x better when the cafe looks like a movie set ☕✨ "
        "What's your go-to coffee order? Tell me below! 🥐\"</i>\n\n"
        "📍 <b>Location:</b> Bandra, Mumbai\n"
        "🎯 <b>Target Account:</b> @diyarai_016\n"
        "🏷️ #mumbaicafe #bandradiaries #coffeelover #explorepage"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Post Direct to Instagram", callback_data="approve_post"),
            InlineKeyboardButton("🛑 Reject", callback_data="reject_post")
        ]
    ])

    with open(photo_path, "rb") as f:
        await bot.send_photo(
            chat_id=chat_id,
            photo=f,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    print("SUCCESS: Preview sent to Telegram!")

if __name__ == "__main__":
    asyncio.run(send_preview())
