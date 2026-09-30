import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from local.instagram_service import InstagramService

def main():
    image_path = "data/story_diya.jpg"
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found at {image_path}")
        return

    username = os.environ.get("IG_USERNAME", "diyarai_016")
    password = os.environ.get("IG_PASSWORD", "")
    session_id = os.environ.get("IG_SESSIONID") or os.environ.get("IG_SESSION_ID", "")

    print("==================================================")
    print(f"[ACTION] Publishing Diya Rai Story to @{username}")
    print(f"[MEDIA] Media: {image_path}")
    print("[AUDIO] Recommended Track: 'O Rangrez' (Slowed + Reverb) / 'Husn'")
    print("==================================================")

    svc = InstagramService(username=username, password=password, session_id=session_id)
    if not svc.login():
        print("[ERROR] Login failed.")
        return

    print("Uploading photo to Instagram Story...")
    media_id = svc.post_story(image_path, is_video=False)
    if media_id:
        print(f"[SUCCESS] Story successfully posted! Media PK: {media_id}")
    else:
        print("[FAILED] Could not post story. Check logs.")

if __name__ == "__main__":
    main()
