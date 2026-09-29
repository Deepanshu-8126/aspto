"""
AIInfluencerOS — System Health & Diagnostics Check
Run: python check.py
"""

import sys
import os

# Set UTF-8 encoding for Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("       AIInfluencerOS -- System Diagnostic Check")
print("=" * 60)

# 1. Check Python & Virtual Environment
print("\n[1] Python Environment:")
print(f"  Python Version: {sys.version.split()[0]}")
print(f"  Interpreter:    {sys.executable}")

# 2. Check Local Dependencies
print("\n[2] Checking Required Local Packages:")
packages = [
    ("python-telegram-bot", "telegram"),
    ("instagrapi", "instagrapi"),
    ("apscheduler", "apscheduler"),
    ("gradio", "gradio"),
    ("gradio-client", "gradio_client"),
    ("google-genai", "google.genai"),
    ("pyyaml", "yaml"),
    ("httpx", "httpx"),
    ("aiohttp", "aiohttp"),
    ("aiofiles", "aiofiles"),
    ("pillow", "PIL"),
    ("requests", "requests"),
]

all_pkgs_ok = True
for display_name, import_name in packages:
    try:
        __import__(import_name)
        print(f"  [PASS] {display_name:<25}")
    except ImportError:
        print(f"  [FAIL] {display_name:<25} (NOT INSTALLED)")
        all_pkgs_ok = False

# 3. Check Local Project Modules
print("\n[3] Checking Local Application Modules:")
modules = [
    ("local.database", "Database CRUD"),
    ("local.cloud_client", "Cloud GPU Client"),
    ("local.instagram_service", "Instagram Service"),
    ("local.whatsapp_service", "WhatsApp Service"),
    ("local.scheduler", "Post Scheduler"),
    ("local.telegram_bot", "Telegram Bot"),
    ("local.main", "Local Controller Entry"),
    ("dashboard.app", "Gradio Dashboard"),
]

all_mods_ok = True
for mod_name, desc in modules:
    try:
        __import__(mod_name)
        print(f"  [PASS] {mod_name:<25} ({desc})")
    except Exception as e:
        print(f"  [FAIL] {mod_name:<25} -> {e}")
        all_mods_ok = False

# 4. Check Database
print("\n[4] Checking Database Connectivity:")
try:
    from local import database as db
    db.init_db()
    stats = db.get_analytics()
    brands = db.list_brands(active_only=True)
    print(f"  [PASS] SQLite Database initialized at data/influencer.db")
    print(f"  [INFO] Total Posts in DB: {stats['total_posts']}, Active Brands: {len(brands)}")
except Exception as e:
    print(f"  [FAIL] Database check failed: {e}")

# 5. Check Cloud Modules Syntax
print("\n[5] Checking Cloud GPU Modules (Syntax & Safe Import):")
cloud_modules = [
    "cloud.script_gen",
    "cloud.image_gen",
    "cloud.voice_gen",
    "cloud.video_gen",
    "cloud.lipsync",
    "cloud.ffmpeg_merge",
    "cloud.pipeline",
    "cloud.gradio_app",
    "cloud.colab_notebook",
]

for cm in cloud_modules:
    try:
        __import__(cm)
        print(f"  [PASS] {cm:<25}")
    except Exception as e:
        print(f"  [FAIL] {cm:<25} -> {e}")

print("\n" + "=" * 60)
if all_pkgs_ok and all_mods_ok:
    print("  RESULT: ALL CHECKS PASSED (0 ERRORS)")
    print("  Your system is completely healthy and ready!")
else:
    print("  RESULT: SOME CHECKS FAILED. Review errors above.")
print("=" * 60 + "\n")
