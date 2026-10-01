#!/usr/bin/env python3
"""
DIYA WAKER — Telegram pe prompt aaye to Kaggle GPU kernel jaga do.

KYUN
----
GPU server 5 min idle hone pe khud band ho jaata hai (quota bachane ko).
Phir Telegram pe koi sunne wala nahi bachta. Ye script GitHub Actions pe
har 5 min chalti hai (CPU, free) aur zaroorat padne pe GPU jagati hai.

SABSE ZAROORI TRICK — "peek without consume"
--------------------------------------------
Telegram getUpdates tabhi messages ko "pada hua" maanta hai jab tum agli baar
`offset = last_id + 1` ke saath call karo. Hum offset bhejte hi NAHI, isliye
messages queue me pade rehte hain aur GPU server boot hote hi wahi backlog
padh ke process kar leta hai. Dono poller aapas me nahi takraate.

FLOW
----
  1. Telegram peek karo (consume nahi)
  2. Koi naya user message nahi -> chup-chaap exit
  3. Kaggle kernel pehle se RUNNING -> exit (server khud handle karega)
  4. Warna kernel push karke run trigger karo + Telegram pe batao

ENV (GitHub Secrets se aate hain)
---------------------------------
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, KAGGLE_USERNAME, KAGGLE_KEY
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KERNEL = "diya-rai-server"
IGNORE_PREFIXES = ("/status", "/queue", "/web", "/help", "/ping", "/stop", "/sleep")


def env(name, default=""):
    v = os.getenv(name, "").strip()
    if v:
        return v
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, val = line.split("=", 1)
                if k.strip() == name:
                    return val.strip().strip('"').strip("'")
    return default


BOT = env("TELEGRAM_BOT_TOKEN")
CHAT = env("TELEGRAM_CHAT_ID") or env("TELEGRAM_ADMIN_CHAT_ID")
USER = env("KAGGLE_USERNAME")
KEY = env("KAGGLE_KEY") or env("KAGGLE_API_TOKEN")
API = f"https://api.telegram.org/bot{BOT}"


def log(*a):
    print(*a, flush=True)


def need(**kw):
    missing = [k for k, v in kw.items() if not v]
    if missing:
        sys.exit(f"❌ missing env: {', '.join(missing)}")


def tg(text):
    import requests
    try:
        requests.post(f"{API}/sendMessage",
                      data={"chat_id": CHAT, "text": text[:4000]}, timeout=20)
    except Exception as e:
        log(f"tg send fail: {e}")


def peek_updates():
    """Pending updates dekho — par CONSUME mat karo (offset bhejo hi mat)."""
    import requests
    r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=30)
    data = r.json()
    if not data.get("ok"):
        log(f"getUpdates fail: {data}")
        return []
    out = []
    for u in data.get("result", []):
        m = u.get("message") or u.get("channel_post") or {}
        if str(m.get("chat", {}).get("id")) != str(CHAT):
            continue
        t = (m.get("text") or "").strip()
        if not t:
            continue
        if t.lower().startswith(IGNORE_PREFIXES):
            continue          # ye GPU ke bina bhi matlab nahi rakhte
        out.append(t)
    return out


def kaggle_env():
    d = Path.home() / ".kaggle"
    d.mkdir(exist_ok=True)
    if KEY.startswith("KGAT_"):
        f = d / "access_token"
        f.write_text(KEY)
        f.chmod(0o600)
        os.environ["KAGGLE_API_TOKEN"] = KEY
    else:
        f = d / "kaggle.json"
        f.write_text(json.dumps({"username": USER, "key": KEY}))
        f.chmod(0o600)
        os.environ["KAGGLE_USERNAME"], os.environ["KAGGLE_KEY"] = USER, KEY


def kernel_status():
    r = subprocess.run(["kaggle", "kernels", "status", f"{USER}/{KERNEL}"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr)
    for s in ("RUNNING", "QUEUED", "ERROR", "COMPLETE", "CANCEL"):
        if s in out.upper():
            return s
    return "UNKNOWN"


def main():
    need(TELEGRAM_BOT_TOKEN=BOT, TELEGRAM_CHAT_ID=CHAT,
         KAGGLE_USERNAME=USER, KAGGLE_KEY=KEY)

    pending = peek_updates()
    log(f"pending prompts: {len(pending)}")
    if not pending:
        log("kuch nahi — GPU soya rehne do")
        return

    for p in pending[:3]:
        log(f"   • {p[:70]}")

    kaggle_env()
    st = kernel_status()
    log(f"kernel status: {st}")

    if st in ("RUNNING", "QUEUED"):
        log("GPU pehle se chal raha hai — server khud padh lega")
        return

    log("GPU jaga raha hoon...")
    tg(f"{len(pending)} prompt mila — GPU jag raha hai, ~2 min me photo aayegi.")

    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "push_kaggle.py"),
                        "server", "--force"], capture_output=True, text=True)
    out = r.stdout + r.stderr
    log(out[-1500:])
    if "successfully pushed" in out:
        log("✅ GPU start ho gaya")
    else:
        tg("GPU start nahi ho paya. Kaggle quota ya session limit check karo.")
        sys.exit(1)


if __name__ == "__main__":
    main()
