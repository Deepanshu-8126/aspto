"""
================================================================================
 DIYA RAI — UNIFIED GPU SERVER  (Kaggle T4)
================================================================================
EK process, teen cheezein ek saath:

   [ Web Dashboard ]  ─┐
                       ├─>  JOB QUEUE  ─>  GPU WORKER THREAD  ─>  outputs
   [ Telegram Bot  ]  ─┘       (background)        (SDXL + Diya LoRA)

FAST RESPONSE KAISE
-------------------
 * API turant job_id return karta hai (<50 ms). GPU alag thread me chalta hai,
   isliye dashboard ya Telegram kabhi freeze nahi hota.
 * Dashboard pe card foran dikh jaata hai with live stopwatch, image aate hi
   fill ho jaata hai.
 * Telegram pe foran "queued #12" aata hai, phir photo.
 * Startup pe ek warm-up pass chalta hai -> pehli asli image slow nahi hoti.
 * Model ek hi baar load hota hai; har image ~15-20 s (T4, 28 steps).

KAGGLE SETUP
------------
  Accelerator : GPU T4 x2      Internet : ON
  Dataset     : diyarai-sdxl-lora   (training se bani .safetensors)
  Secrets     : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

CHALANA
-------
  !python diya_server.py
  -> console me public dashboard URL print hoga (https://xxx.trycloudflare.com)
  -> wahi URL Telegram pe bhi aa jaayega
================================================================================
"""

import os

# Kaggle logs ko progress-bar spam se bachao (ye imports se PEHLE set hona chahiye)
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("DIFFUSERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TQDM_DISABLE", "1")

# Neeche wali marker line ko `scripts/push_kaggle.py` push ke waqt .env ki
# values se replace karta hai — SIRF private Kaggle kernel wali copy me.
# Repo me token kabhi nahi jaata. Kaggle Secrets use karo to ye zaroori hi nahi.
# === SECRETS_INJECT_MARKER ===

import argparse
import copy
import glob
import json
import queue
import random
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from pathlib import Path

# ------------------------------------------------------------------ #
# 0. Args + fast deps
# ------------------------------------------------------------------ #
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="SG161222/RealVisXL_V4.0")
ap.add_argument("--lora", default=None, help="LoRA path (auto-detect agar na do)")
ap.add_argument("--port", type=int, default=7860)
ap.add_argument("--no-tunnel", action="store_true", help="public URL mat banao")
ap.add_argument("--no-telegram", action="store_true")
ap.add_argument("--swap", action="store_true", help="face polish default ON")
ap.add_argument("--idle-minutes", type=float, default=5.0,
                help="Itne minute koi kaam na mile to GPU band (0 = kabhi nahi). "
                     "Kaggle quota bachane ke liye.")
ARGS = ap.parse_args()


def _fix_torchao():
    """Kaggle image me torchao 0.10 preinstalled hai. peft usko dekh kar
    `ImportError: Found an incompatible version of torchao` phenk deta hai,
    jisse LoRA load FAIL ho jaati hai aur base model chalta hai (chehra exact
    nahi aata). Humein torchao chahiye hi nahi -> hata do.
    Ye peft/diffusers import se PEHLE chalna chahiye."""
    try:
        import torchao
        ver = getattr(torchao, "__version__", "0")
        mm = tuple(int(x) for x in ver.split(".")[:2] if x.isdigit())
        if mm and mm < (0, 16):
            print(f"[deps] torchao {ver} peft se clash karta hai — hata raha hoon",
                  flush=True)
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q",
                            "torchao"], check=False)
            for m in [m for m in sys.modules if m.startswith("torchao")]:
                del sys.modules[m]
    except ImportError:
        pass
    except Exception as e:
        print(f"[deps] torchao check skip: {e}", flush=True)


def ensure(mods):
    _fix_torchao()
    missing = [pkg for mod, pkg in mods if not _has(mod)]
    if missing:
        print(f"[deps] installing {missing}", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "--no-cache-dir", *missing], check=False)


def _has(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


ensure([("diffusers", "diffusers>=0.31.0"),
        ("peft", "peft>=0.13.0"),
        ("transformers", "transformers>=4.44.0"),
        ("safetensors", "safetensors"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("requests", "requests")])

import requests                                            # noqa: E402
from PIL import Image, ImageDraw, ImageFilter              # noqa: E402
import torch                                               # noqa: E402
import uvicorn                                             # noqa: E402

# baaki shor band karo
try:
    import logging as _lg
    import warnings
    warnings.filterwarnings("ignore")
    from huggingface_hub.utils import disable_progress_bars
    disable_progress_bars()
    import diffusers.utils.logging as _dl
    _dl.set_verbosity_error()
    import transformers.utils.logging as _tl
    _tl.set_verbosity_error()
    for _n in ("huggingface_hub", "diffusers", "transformers", "accelerate"):
        _lg.getLogger(_n).setLevel(_lg.ERROR)
except Exception:
    pass

from fastapi import FastAPI, HTTPException                 # noqa: E402
from fastapi.middleware.cors import CORSMiddleware         # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse   # noqa: E402
from pydantic import BaseModel                             # noqa: E402

# ------------------------------------------------------------------ #
# 1. Config
# ------------------------------------------------------------------ #
OUT = Path("/kaggle/working/outputs") if Path("/kaggle/working").exists() else Path("./outputs")
OUT.mkdir(parents=True, exist_ok=True)
MODELS = OUT.parent / "models"
MODELS.mkdir(parents=True, exist_ok=True)

TRIGGER = "diyarai"
# Realism negatives. "studio/professional/8k" jaisi cheezein NEGATIVE me daalni
# hoti hain — positive me daalne se hi AI-look aata hai.
NEG = (
    # --- HAATH sabse pehle aur sabse bhaari (SDXL me order matter karta hai) ---
    "(extra fingers:1.6), (fused fingers:1.6), (missing fingers:1.5), "
    "(six fingers:1.6), (deformed hands:1.6), (malformed hands:1.5), "
    "(mutated hands:1.5), (bad hands:1.5), (long fingers:1.3), "
    "(extra limbs:1.4), (deformed fingers:1.5), claw hand, melted fingers, "
    # --- skin / plastic look ---
    "airbrushed, smooth plastic skin, waxy skin, poreless, retouched, beauty filter, "
    "doll face, mannequin, overprocessed, hdr, oversaturated, oversharpened, "
    "glossy, shiny skin, studio lighting, professional photoshoot, glamour shot, "
    # --- colour cast (minimax jaisa neutral chahiye) ---
    "orange skin, heavy teal and orange grade, instagram filter, color cast, "
    "3d render, cgi, octane render, unreal engine, digital art, illustration, "
    "painting, cartoon, anime, airbrush, "
    # --- aankhein ---
    "(dead eyes:1.4), (glassy eyes:1.4), lifeless eyes, asymmetric eyes, cross eyed, "
    # --- SDXL ka beauty-bias: chehra patla+lamba, muh chhota kar deta hai.
    #     Landmark se naapa: jaw -4.5%, mouth -4.6%, face length +5.2%
    "(narrow jaw:1.3), (slim face:1.3), (long face:1.3), (pointed chin:1.2), "
    "(small mouth:1.2), (thin lips:1.2), (long philtrum:1.2), model face, "
    "deformed face, bad anatomy, "
    "watermark, text, logo, signature, jpeg artifacts, duplicate, mutated, lowres")

# Camera/realism ke alag flavours — har image pe thoda rotate hota hai taaki
# sab ek jaisi "AI stock photo" na lagein.
REAL_LOOKS = [
    "amateur iphone 15 pro photo, slight motion blur, natural indoor lighting",
    "candid snapshot taken by a friend, phone camera, slightly off-center framing",
    "casual photo, available light, mild sensor noise, no flash",
    "photo dump style picture, natural window light, imperfect framing",
    "everyday phone photo, soft overcast daylight, unedited",
]

# ------------------------------------------------------------------ #
# SCENE LIBRARY — asli ladki ki asli zindagi.
# Har scene me 4 cheezein hai: JAGAH + KAPDE + ROSHNI + KYA KAR RAHI HAI.
# Jitna specific, utna kam "AI stock photo" jaisa.
# ------------------------------------------------------------------ #
SCENES = {
 # ---------------- DIN / DAYLIGHT ----------------
 "day": [
  "sitting on her bed in a pale yellow cotton kurta, late morning sunlight through a grilled window making stripes on the wall, hair still messy from sleep, holding a steel tumbler of chai",
  "standing on the balcony in a grey oversized tshirt and shorts, drying her hair with a towel, harsh 11am sun, clothes drying on the line behind her",
  "in an auto rickshaw, mustard kurti with dupatta, one hand holding the rail, afternoon sun through the open side, dusty road behind",
  "walking through a crowded local market, light blue cotton suit, carrying a jute bag with vegetables, midday overhead light, fruit stalls blurred behind",
  "sitting on a park bench in a white tee and blue jeans, dappled shade from a neem tree, scrolling her phone, slight squint from the brightness",
  "at a rooftop in a sage green kurta, golden 5pm light from the side, laundry lines and water tanks around, wind pushing her hair across her face",
  "in a college corridor, kurti and tote bag, flat fluorescent plus window light, leaning against a pillar mid conversation",
  "on a metro train in a beige co-ord set, seated by the window, overexposed daylight from outside, earphones in",
 ],
 # ---------------- RAAT / NIGHT ----------------
 "night": [
  "on a terrace at night in a black cotton kurta, lit only by warm yellow string lights, city darkness behind, holding a cup with both hands",
  "in her bedroom at 1am, oversized tshirt, only the phone screen lighting her face from below, duvet around her, tired eyes",
  "walking a street at night in a denim jacket, lit by an orange sodium vapour streetlight, closed shop shutters behind, shallow puddle reflections",
  "sitting at a dhaba at night in a maroon kurti, lit by a single bare tube light overhead, steel plates on the table, moths around the bulb",
  "in a car at night, passenger seat, soft red and green light from the dashboard and passing streetlights sliding across her face",
  "at a wedding function at night, pastel pink lehenga with silver jhumkas, warm marigold fairy lights and a single camera flash catching her",
  "leaning out a window at night in a sleeveless top, blue moonlight on one side of her face and warm room light on the other",
  "night terrace, cotton pyjama set, sitting cross-legged on a mat, lit by a mobile torch kept face up, stars barely visible",
 ],
 # ---------------- MONSOON / BAARISH ----------------
 "monsoon": [
  "standing under a shop awning during heavy rain, soaked white kurta, grey flat overcast light, water sheeting off the edge of the awning",
  "in an auto during monsoon, plastic side curtains down, raindrops crawling across the clear plastic, dim green-grey light on her face",
  "on a balcony in a light cotton kurti, holding her hand out into the drizzle, wet railing, petrichor grey sky, hair frizzy from humidity",
  "walking a flooded street in a yellow kurti holding sandals in one hand and an umbrella in the other, ankle deep brown water, dull rainy daylight",
  "sitting by a rain streaked window with chai and pakoras, cold blue daylight filtering through the water on the glass, condensation at the edges",
  "caught in sudden rain in a light blue salwar, hair stuck to her forehead, laughing, wet road reflecting a dull sky",
  "night monsoon, standing in a doorway, rain lit from behind by a streetlight so each drop glows, her face in soft shadow",
 ],
 # ---------------- KHANA PEENA / FOOD ----------------
 "food": [
  "eating street pani puri, standing at a thela, mid bite with one hand cupped under her chin, evening market light, bowl of water in the vendor's hand",
  "sitting on the kitchen floor eating roti sabzi from a steel thali, warm tube light overhead, pressure cooker on the stove behind",
  "drinking cutting chai at a tapri, holding the small glass with fingertips because it is hot, morning light, newspaper on the counter",
  "eating a plate of momos with red chutney at a street stall, steam rising, winter evening, wearing a hoodie",
  "making maggi at 2am in the kitchen, lit only by the stove flame and a dim bulb, stirring the pot in an oversized tshirt",
  "at a cafe with a filter coffee and an unfinished croissant, window light from the left, menu card and crumbs on the marble table",
  "cutting mangoes at the dining table in summer, juice on her fingers, hot afternoon light through a curtain",
  "eating golgappa with friends, candid, mouth full, hand raised, evening street light, slightly out of focus friends around",
 ],
 # ---------------- ROZ KA DIN / DAILY LIFE ----------------
 "daily": [
  "brushing her teeth in front of a bathroom mirror, hair tied in a loose bun, cold white morning light from a frosted window",
  "folding dried clothes on the bed, pile of laundry around, flat afternoon light, slight slouch in her posture",
  "hanging clothes on the terrace line in a cotton nighty, bending to pick from the bucket, strong direct sun, clothes pins in her mouth",
  "watering plants on the balcony early morning, mug in hand, soft 7am light, bare feet on wet tiles",
  "sitting on the floor against the bed, laptop on a cushion, working late, screen glow on her face, cold tea beside her",
  "getting ready at a dressing table, putting on a silver jhumka, looking into a small mirror, warm bulb light from the side",
  "lying on her stomach on the bed reading, legs up, afternoon window light across the sheets",
  "on a crowded local bus, holding the overhead bar, tired face, harsh light from the window, bag in front of her",
  "sweeping the floor in the morning in an old salwar, hair tied back, dusty light beams from the window",
  "oiling her hair sitting on the floor in front of a mirror, bottle of coconut oil beside her, soft indoor light",
 ],
}

# Purane chhote presets bhi chalte rahein
PRESETS = {
    "cafe": "sitting in an aesthetic Mumbai cafe, beige linen co-ord, iced latte, soft window light, candid",
    "saree": "wearing an elegant red chiffon saree, terrace at golden hour sunset, wind in hair",
    "street": "street style in Bandra, oversized denim jacket and baggy jeans, city bokeh, walking candid",
    "gym": "in matching activewear set at a modern gym, mirror selfie, natural morning light",
    "traditional": "wearing a pastel chikankari kurta with jhumkas, festive home decor, warm lamps",
}
for _cat, _lst in SCENES.items():
    PRESETS[_cat] = _lst[0]


STATE = {
    "n": 1, "scale": 1.0, "steps": 30, "cfg": 3.5,
    "real": True,      # hires fix + face detail pass
    "cam": 1.0,        # camera simulation 0-1.5 (0 = off)
    "look": "minimax", # colour profile: minimax | phone | raw
    "match": 0.68,     # asli photo <-> asli photo ka min 0.690 hai,
                       # isliye 0.68 = "utna hi match jitna do asli photos me"
    "retry": 2,        # itni baar tak dobara try karega
    "hands": True,     # haath ko safe framing + extra negative
    "width": 832, "height": 1216, "swap": ARGS.swap,
    "made": 0, "failed": 0, "start": time.time(),
    "current": None, "gpu": "", "lora": None, "url": "",
    "last_img": None, "last_prompt": "",
    "caption": "", "capstyle": "soft",
    "model_ready": False,
    "last_activity": time.time(),   # idle shutdown isi se naapa jaata hai
    "idle_min": ARGS.idle_minutes,
}


def touch(why=""):
    """Koi bhi activity hui -> idle timer reset."""
    STATE["last_activity"] = time.time()
    if why:
        print(f"[idle] timer reset ({why})", flush=True)

JOBS = OrderedDict()           # job_id -> dict
JOBQ = queue.Queue()
LOCK = threading.Lock()


def _load_dotenv():
    """Local run ke liye .env padho (Kaggle pe Secrets use hote hain)."""
    for d in (Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
        f = d / ".env"
        if f.exists():
            for line in f.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


_load_dotenv()


def _secret(name, default=""):
    """Priority: env var / .env  ->  Kaggle Secrets  ->  default.
    Secrets kabhi code me hardcode nahi hote."""
    v = os.getenv(name)
    if v:
        return v
    try:
        from kaggle_secrets import UserSecretsClient
        return UserSecretsClient().get_secret(name)
    except Exception:
        return default


BOT_TOKEN = _secret("TELEGRAM_BOT_TOKEN")
CHAT_ID = _secret("TELEGRAM_CHAT_ID") or _secret("TELEGRAM_ADMIN_CHAT_ID")
TG_OK = bool(BOT_TOKEN and CHAT_ID) and not ARGS.no_telegram
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# HF token ho to downloads tez + rate limit zyada
_hf = _secret("HF_TOKEN")
if _hf:
    os.environ.setdefault("HF_TOKEN", _hf)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", _hf)


def tg(text, photo=None):
    if not TG_OK:
        return
    try:
        if photo and os.path.exists(photo):
            with open(photo, "rb") as f:
                requests.post(f"{API}/sendPhoto",
                              data={"chat_id": CHAT_ID, "caption": text[:1024]},
                              files={"photo": f}, timeout=120)
        else:
            requests.post(f"{API}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text[:4000]}, timeout=20)
    except Exception as e:
        print(f"[tg] {e}", flush=True)


print("=" * 72)
print("  DIYA RAI UNIFIED GPU SERVER")
print("=" * 72, flush=True)
if not torch.cuda.is_available():
    sys.exit("[FATAL] GPU off. Kaggle Settings -> Accelerator -> GPU T4 x2")
STATE["gpu"] = torch.cuda.get_device_name(0)
print(f"  GPU      : {STATE['gpu']}")
if TG_OK:
    try:
        _me = requests.get(f"{API}/getMe", timeout=15).json()
        print(f"  Telegram : ON  (@{_me['result']['username']} -> chat {CHAT_ID})")
    except Exception:
        print("  Telegram : ON  (getMe check fail — token galat ho sakta hai)")
else:
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", BOT_TOKEN),
                              ("TELEGRAM_CHAT_ID", CHAT_ID)) if not v]
    print("  Telegram : OFF")
    print("  " + "!" * 66)
    print(f"  !! Missing Kaggle Secret(s): {', '.join(missing)}")
    print("  !! Kaggle notebook -> right panel -> Add-ons -> Secrets")
    print("  !!   TELEGRAM_BOT_TOKEN = <BotFather token>")
    print("  !!   TELEGRAM_CHAT_ID   = <tumhara chat id>")
    print("  !! Secret add karke notebook dobara run karo.")
    print("  !! Tab tak sirf web dashboard chalega (wo theek kaam karega).")
    print("  " + "!" * 66, flush=True)

# ------------------------------------------------------------------ #
# 2. Job helpers
# ------------------------------------------------------------------ #
def new_job(prompt, source, n=None, scale=None, steps=None, swap=None):
    touch(f"naya job from {source}")
    jid = uuid.uuid4().hex[:8]
    with LOCK:
        JOBS[jid] = {
            "id": jid, "prompt": prompt, "source": source,
            "status": "queued", "created": time.time(), "started": None,
            "finished": None, "images": [], "error": None,
            "n": n or STATE["n"], "scale": scale or STATE["scale"],
            "steps": steps or STATE["steps"],
            "swap": STATE["swap"] if swap is None else swap,
            "pos": JOBQ.qsize() + 1,
        }
        while len(JOBS) > 200:
            JOBS.popitem(last=False)
    JOBQ.put(jid)
    return JOBS[jid]


def build_prompt(text, seed=None):
    """Realism-first prompt.

    JO HATAYA (ye hi AI-look dete hain):
      "8k", "highly detailed", "photorealistic", "masterpiece",
      "Sony A7R V 85mm f/1.4", "shallow depth of field", "professional"
    Ye sab model ko commercial/CGI render ki taraf dhakelte hain.

    JO DAALA: amateur phone-photo language + skin/eye imperfections.
    """
    body = (text or "").strip()
    body = PRESETS.get(body.lower(), body) or PRESETS["cafe"]
    if TRIGGER not in body.lower():
        body = f"{TRIGGER} woman, {body}"
    look = REAL_LOOKS[(seed or int(time.time())) % len(REAL_LOOKS)]
    # Haath = AI ka sabse bada tell. Agar user ne khud haath nahi maanga to
    # model ko aisi framing di jaati hai jahan haath simple/relaxed rehte hain.
    hands = ""
    if STATE.get("hands", True):
        asked = any(w in body.lower() for w in
                    ("hand", "finger", "holding", "peace sign", "wave", "haath"))
        hands = (", both hands clearly visible with exactly five natural fingers, "
                 "relaxed natural hand pose"
                 if asked else
                 ", hands relaxed and resting naturally, arms down, "
                 "hands away from face, simple uncluttered hand pose")
    return (f"{look}, {body}{hands}, 23 year old Indian woman, "
            f"real skin texture with visible pores, faint blemishes and fine vellus hair, "
            f"natural under-eye shadow, subtle skin redness around nose and cheeks, "
            f"detailed iris with catchlights and visible sclera veins, slightly moist eyes, "
            f"rounded softly square jawline, full cheeks, wide natural smile, "
            f"short philtrum, full lower lip, "
            f"natural uneven lighting, neutral white balance, true to life colors, "
            f"unretouched, film grain")


# ------------------------------------------------------------------ #
# 3. GPU worker thread  (model load + queue consumer)
# ------------------------------------------------------------------ #
PIPE = None
_FACE = {"ready": False, "app": None, "swapper": None, "gfp": None, "emb": None}

INSWAPPER_URL = "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/inswapper_128.onnx"
GFPGAN_URL = ("https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/"
              "models/facerestore_models/GFPGANv1.4.onnx")


def _download(url, dest, min_mb=10):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > min_mb * 1024 * 1024:
        return True
    print(f"[dl] {dest.name}", flush=True)
    # NOTE: wget me -nc aur -O saath nahi chalte (purane code ka bug). Sirf -O.
    r = subprocess.run(["wget", "-q", "-L", url, "-O", str(dest)])
    ok = r.returncode == 0 and dest.exists() and dest.stat().st_size > min_mb * 1024 * 1024
    if not ok:
        dest.unlink(missing_ok=True)
        print(f"[dl] FAILED {url}", flush=True)
    return ok


def find_lora():
    if ARGS.lora and os.path.exists(ARGS.lora):
        return ARGS.lora
    for pat in ("/kaggle/input/**/diyarai*.safetensors",
                "/kaggle/input/**/*lora*.safetensors",
                "/kaggle/working/*.safetensors",
                "./*.safetensors"):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    return None


def load_pipeline():
    global PIPE
    from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler

    t0 = time.time()
    print(f"[load] {ARGS.base}", flush=True)
    PIPE = AutoPipelineForText2Image.from_pretrained(
        ARGS.base, torch_dtype=torch.float16, variant="fp16",
        use_safetensors=True, add_watermarker=False).to("cuda")
    # Full SDXL ke liye DPM++ 2M Karras (turbo ke saath yeh MAT lagana)
    PIPE.scheduler = DPMSolverMultistepScheduler.from_config(
        PIPE.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++")
    PIPE.set_progress_bar_config(disable=True)
    try:
        PIPE.enable_xformers_memory_efficient_attention()
    except Exception:
        pass
    PIPE.enable_vae_slicing()

    lora = find_lora()
    if lora:
        try:
            PIPE.load_lora_weights(lora, adapter_name="diya")
            PIPE.set_adapters(["diya"], adapter_weights=[STATE["scale"]])
            STATE["lora"] = Path(lora).name
            sz = os.path.getsize(lora) / 1e6
            print(f"[load] ✅ LoRA ATTACHED: {lora} ({sz:.0f} MB, scale {STATE['scale']})",
                  flush=True)
        except Exception as e:
            STATE["lora"] = None
            print(f"[load] ❌ LoRA load FAIL: {e}", flush=True)
            tg(f"LoRA load fail hui:\n{e}\n\nBase model se chalega (chehra exact nahi aayega).")
    else:
        STATE["lora"] = None
        print("[load] " + "!" * 60, flush=True)
        print("[load] !! LoRA NAHI MILI — chehra exact nahi aayega.", flush=True)
        print("[load] !! Kaggle notebook -> Add-ons/Input -> Add Dataset ->", flush=True)
        print("[load] !!   ukboy7u787/diyarai-sdxl-lora", flush=True)
        print("[load] " + "!" * 60, flush=True)

    # Warm-up: CUDA kernels compile ho jaate hain -> pehli asli image fast
    print("[load] warm-up...", flush=True)
    PIPE(prompt="warmup", num_inference_steps=2, guidance_scale=1.0,
         width=512, height=512)
    torch.cuda.empty_cache()
    STATE["model_ready"] = True
    print(f"[load] READY in {time.time() - t0:.1f}s", flush=True)


def init_face():
    if _FACE["ready"]:
        return True
    ensure([("insightface", "insightface==0.7.3"),
            ("onnxruntime", "onnxruntime-gpu"),
            ("cv2", "opencv-python-headless")])
    try:
        import cv2, numpy as np, onnxruntime as ort, insightface
        from insightface.app import FaceAnalysis
        if not _download(INSWAPPER_URL, MODELS / "inswapper_128.onnx", 100):
            return False
        prov = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        app = FaceAnalysis(name="buffalo_l", providers=prov)
        app.prepare(ctx_id=0, det_size=(640, 640))
        swapper = insightface.model_zoo.get_model(
            str(MODELS / "inswapper_128.onnx"), providers=prov)
        gfp = None
        if _download(GFPGAN_URL, MODELS / "GFPGANv1.4.onnx", 100):
            gfp = ort.InferenceSession(str(MODELS / "GFPGANv1.4.onnx"), providers=prov)
        embs = []
        anchors = glob.glob("/kaggle/input/**/*.png", recursive=True) + \
                  glob.glob("/kaggle/input/**/*.jpg", recursive=True)
        for a in anchors[:12]:
            img = cv2.imread(a)
            if img is None:
                continue
            fs = app.get(img)
            if fs:
                f = max(fs, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
                embs.append(f.embedding / np.linalg.norm(f.embedding))
        if not embs:
            return False
        fused = np.mean(embs, axis=0)
        _FACE.update(ready=True, app=app, swapper=swapper, gfp=gfp,
                     emb=fused / np.linalg.norm(fused))
        print(f"[face] {len(embs)} anchors fused", flush=True)
        return True
    except Exception:
        traceback.print_exc()
        return False


def polish(path):
    if not init_face():
        return path
    import cv2, numpy as np
    img = cv2.imread(path)
    faces = _FACE["app"].get(img)
    if not faces:
        return path
    tgt = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))
    src = copy.deepcopy(tgt)
    src.embedding = _FACE["emb"]
    out = _FACE["swapper"].get(img, tgt, src, paste_back=True)
    if _FACE["gfp"] is not None:
        try:
            from insightface.utils import face_align
            aimg, M = face_align.warp_and_crop_face(out, tgt.kps, crop_size=(512, 512),
                                                    mode="arcface")
            x = (aimg.astype(np.float32)/127.5 - 1.0)[:, :, ::-1].transpose(2, 0, 1)[None]
            s = _FACE["gfp"]
            y = s.run([s.get_outputs()[0].name], {s.get_inputs()[0].name: x})[0][0]
            y = np.clip((y.transpose(1, 2, 0)[:, :, ::-1] + 1.0)*127.5, 0, 255).astype(np.uint8)
            IM = cv2.invertAffineTransform(M)
            h, w = out.shape[:2]
            wr = cv2.warpAffine(y, IM, (w, h), borderMode=cv2.BORDER_REPLICATE)
            m = np.zeros((512, 512), np.float32)
            cv2.ellipse(m, (256, 260), (195, 235), 0, 0, 360, 1.0, -1)
            m = cv2.GaussianBlur(m, (31, 31), 11)
            wm = cv2.warpAffine(m, IM, (w, h), borderMode=cv2.BORDER_CONSTANT)[..., None]
            out = (wr*wm + out*(1-wm)).astype(np.uint8)
        except Exception as e:
            print(f"[face] gfpgan skip: {e}", flush=True)
    # NOTE: pehle yahan unsharp mask tha (addWeighted 1.18/-0.18).
    # Wo over-sharpening hi "AI jaisa" look deta tha — hata diya.
    p2 = path.replace(".jpg", "_hd.jpg")
    cv2.imwrite(p2, out, [int(cv2.IMWRITE_JPEG_QUALITY), 97])
    return p2



# ------------------------------------------------------------------ #
# 3b. REALISM PIPELINE — hires fix + face detail + grain
# ------------------------------------------------------------------ #
# "AI jaisa lagta hai" ke teen asli karan aur unka ilaaj:
#   1. Prompt me "8k/photorealistic/professional"  -> build_prompt me hataya
#   2. Aankhein base resolution pe sirf ~60px hoti hain -> FACE DETAIL PASS
#   3. Sab kuch ek saman sharp + clean  -> HIRES FIX + FILM GRAIN
I2I = None          # img2img pipeline (same weights, extra VRAM nahi)
_DET = {"app": None, "tried": False}


def get_i2i():
    global I2I
    if I2I is None:
        from diffusers import StableDiffusionXLImg2ImgPipeline
        I2I = StableDiffusionXLImg2ImgPipeline.from_pipe(PIPE)
        I2I.set_progress_bar_config(disable=True)
    return I2I


def get_detector():
    """Face detection + recognition (identity score ke liye)."""
    if _DET["tried"]:
        return _DET["app"]
    _DET["tried"] = True
    try:
        ensure([("insightface", "insightface==0.7.3"),
                ("onnxruntime", "onnxruntime-gpu"),
                ("cv2", "opencv-python-headless")])
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"],
                           providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        _DET["app"] = app
        print("[real] face detector ready", flush=True)
    except Exception as e:
        print(f"[real] detector load fail: {e}", flush=True)
    return _DET["app"]


def hires_fix(img, prompt, scale=1.4, strength=0.32, steps=16):
    """Image ko bada karke halka sa dobara render — detail aur texture aati hai,
    aur 'flat AI render' wala look toot-ta hai."""
    try:
        w, h = img.size
        nw, nh = (int(w * scale) // 8) * 8, (int(h * scale) // 8) * 8
        big = img.resize((nw, nh), Image.LANCZOS)
        out = get_i2i()(prompt=prompt, negative_prompt=NEG, image=big,
                        strength=strength, num_inference_steps=steps,
                        guidance_scale=STATE["cfg"]).images[0]
        return out
    except Exception as e:
        print(f"[real] hires skip: {e}", flush=True)
        torch.cuda.empty_cache()
        return img


def face_detail(img, prompt, strength=0.30, steps=16):
    """ADetailer-style: chehre ko crop karke 1024 pe alag se render karo.
    Isi se aankhein, iris, eyelashes aur lips asli lagte hain —
    base image me face sirf ~15% area hota hai to detail hi nahi banti."""
    app = get_detector()
    if app is None:
        return img
    try:
        import cv2
        import numpy as np
        arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        faces = app.get(arr)
        if not faces:
            return img
        f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        W, H = img.size
        # bbox ko 1.7x phailao (baal/jaw/gardan include ho)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        half = int(max(x2 - x1, y2 - y1) * 0.85)
        X1, Y1 = max(0, cx - half), max(0, cy - half)
        X2, Y2 = min(W, cx + half), min(H, cy + half)
        if X2 - X1 < 64 or Y2 - Y1 < 64:
            return img

        crop = img.crop((X1, Y1, X2, Y2)).resize((1024, 1024), Image.LANCZOS)
        face_prompt = (f"{TRIGGER} woman, close up face, real skin with pores and "
                       f"fine texture, detailed iris with catchlights, individual "
                       f"eyelashes, natural lips with fine lines, "
                       f"rounded jawline, full cheeks, wide mouth, short philtrum, "
                       f"large almond eyes with heavy upper lid, unretouched, film grain")
        fixed = get_i2i()(prompt=face_prompt, negative_prompt=NEG, image=crop,
                          strength=strength, num_inference_steps=steps,
                          guidance_scale=STATE["cfg"]).images[0]
        fixed = fixed.resize((X2 - X1, Y2 - Y1), Image.LANCZOS)

        # feathered mask se blend karo warna kinare dikhte hain
        mask = Image.new("L", (X2 - X1, Y2 - Y1), 0)
        ImageDraw.Draw(mask).ellipse(
            [int((X2 - X1) * 0.04), int((Y2 - Y1) * 0.04),
             int((X2 - X1) * 0.96), int((Y2 - Y1) * 0.96)], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(max(6, (X2 - X1) // 18)))
        out = img.copy()
        out.paste(fixed, (X1, Y1), mask)
        return out
    except Exception as e:
        print(f"[real] face detail skip: {e}", flush=True)
        torch.cuda.empty_cache()
        return img


_REF_EMB = {"v": None, "tried": False, "n": 0}


def ref_embedding():
    """Asli Diya photos ka average face embedding — identity ka 'ground truth'.
    Isi se naapa jaata hai ki generated chehra kitna match kar raha hai."""
    if _REF_EMB["tried"]:
        return _REF_EMB["v"]
    _REF_EMB["tried"] = True
    app = get_detector()
    if app is None:
        return None
    try:
        import numpy as np, cv2, glob as _g
        files = sorted(set(_g.glob("/kaggle/input/**/*.jpg", recursive=True) +
                           _g.glob("/kaggle/input/**/*.png", recursive=True) +
                           _g.glob("/kaggle/input/**/*.jpeg", recursive=True)))[:40]
        embs = []
        for f in files:
            a = cv2.imread(f)
            if a is None:
                continue
            fc = app.get(a)
            if not fc:
                continue
            e = max(fc, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1])).normed_embedding
            embs.append(e)
        if len(embs) < 2:
            print(f"[id] reference faces kam mile ({len(embs)}) — score off", flush=True)
            return None
        v = np.mean(embs, 0)
        _REF_EMB["v"] = v / (np.linalg.norm(v) + 1e-9)
        _REF_EMB["n"] = len(embs)
        print(f"[id] reference embedding ready ({len(embs)} faces)", flush=True)
    except Exception as e:
        print(f"[id] ref embedding fail: {e}", flush=True)
    return _REF_EMB["v"]


# m1-m6 landmarks se naapa hua asli dhaancha (inter-pupil distance = 1.0)
GEO_REF = {"face_ratio": (1.244, 0.049), "eye_w": (0.413, 0.018),
           "eye_open": (0.404, 0.022), "eye_to_mouth": (1.060, 0.012),
           "nose_to_mouth": (0.520, 0.046), "mouth_w": (0.849, 0.018),
           "jaw_w": (2.256, 0.028), "chin_len": (0.752, 0.024)}


def geo_score(face):
    """Chehre ka DHAANCHA kitna milta hai (0-1). Embedding identity dekhti hai,
    ye haddi ka structure dekhta hai — jaw, muh, aankh ka size, chin."""
    try:
        import numpy as np
        L, k = face.landmark_2d_106, face.kps
        ipd = np.linalg.norm(k[0] - k[1])
        if ipd < 1:
            return None
        x1, y1, x2, y2 = face.bbox
        eyec, mc = (k[0] + k[1]) / 2, (k[3] + k[4]) / 2
        le, re = L[[33,34,35,36,37,38,39,40,41,42]], L[[87,88,89,90,91,92,93,94,95,96]]
        ew = ((le[:,0].ptp() + re[:,0].ptp()) / 2)
        eh = ((le[:,1].ptp() + re[:,1].ptp()) / 2)
        jaw = L[0:33]
        cur = {"face_ratio": (y2-y1)/(x2-x1), "eye_w": ew/ipd, "eye_open": eh/max(ew,1e-6),
               "eye_to_mouth": np.linalg.norm(mc-eyec)/ipd,
               "nose_to_mouth": np.linalg.norm(mc-k[2])/ipd,
               "mouth_w": np.linalg.norm(k[3]-k[4])/ipd,
               "jaw_w": jaw[:,0].ptp()/ipd, "chin_len": (jaw[:,1].max()-mc[1])/ipd}
        # har metric ko asli photos ke spread (sigma) me naapo
        z = [abs(cur[m] - GEO_REF[m][0]) / max(GEO_REF[m][1], 1e-6) for m in GEO_REF]
        return float(max(0.0, 1.0 - sum(z) / len(z) / 3.0))   # 3 sigma = 0
    except Exception:
        return None


def face_score(img):
    """0-1 cosine similarity vs asli Diya.
    Naapa hua baseline: asli photo <-> asli photo = 0.690 min / 0.793 avg.
    To 0.69+ ka matlab hai "utna hi match jitna uski do asli photos me"."""
    ref = ref_embedding()
    if ref is None:
        return None
    try:
        import numpy as np, cv2
        fc = get_detector().get(cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR))
        if not fc:
            return None
        f = max(fc, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        idv = float(np.dot(ref, f.normed_embedding))
        g = geo_score(f)
        if g is None:
            return idv
        # 75% identity + 25% dhaancha
        return 0.75 * idv + 0.25 * g
    except Exception:
        return None


_HANDS = None


def get_hands():
    """mediapipe hand detector (lazy). Na mile to None -> pass skip ho jaata hai."""
    global _HANDS
    if _HANDS is None:
        try:
            import mediapipe as mp
        except Exception:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                            "mediapipe"], check=False)
            try:
                import mediapipe as mp
            except Exception as e:
                print(f"[real] mediapipe nahi mila: {e}", flush=True)
                _HANDS = False
                return None
        _HANDS = mp.solutions.hands.Hands(
            static_image_mode=True, max_num_hands=2, min_detection_confidence=0.3)
        print("[real] hand detector ready", flush=True)
    return _HANDS or None


def hand_detail(img, strength=0.38, steps=14):
    """Haath ko crop karke 768 pe dobara render — ungliyan sharp aur sahi.
    Base image me haath ~8% area hota hai, isliye wahan detail banti hi nahi
    aur wo blurry/bigda hua dikhta hai."""
    det = get_hands()
    if det is None:
        return img
    try:
        import numpy as np
        W, H = img.size
        res = det.process(np.array(img.convert("RGB")))
        if not res.multi_hand_landmarks:
            return img
        out = img
        for lm in res.multi_hand_landmarks[:2]:
            xs = [p.x * W for p in lm.landmark]
            ys = [p.y * H for p in lm.landmark]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            half = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.85
            if half < 24:
                continue
            X1, Y1 = int(max(0, cx - half)), int(max(0, cy - half))
            X2, Y2 = int(min(W, cx + half)), int(min(H, cy + half))
            if X2 - X1 < 64 or Y2 - Y1 < 64:
                continue
            crop = out.crop((X1, Y1, X2, Y2)).resize((768, 768), Image.LANCZOS)
            fixed = get_i2i()(
                prompt=("close up of a human hand, five natural fingers, "
                        "correct anatomy, realistic skin texture on knuckles, "
                        "visible fingernails, sharp focus, natural light"),
                negative_prompt=NEG, image=crop, strength=strength,
                num_inference_steps=steps, guidance_scale=STATE["cfg"]).images[0]
            fixed = fixed.resize((X2 - X1, Y2 - Y1), Image.LANCZOS)
            mask = Image.new("L", (X2 - X1, Y2 - Y1), 0)
            ImageDraw.Draw(mask).ellipse(
                [int((X2 - X1) * .05), int((Y2 - Y1) * .05),
                 int((X2 - X1) * .95), int((Y2 - Y1) * .95)], fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(max(5, (X2 - X1) // 16)))
            tmp = out.copy()
            tmp.paste(fixed, (X1, Y1), mask)
            out = tmp
        return out
    except Exception as e:
        print(f"[real] hand detail skip: {e}", flush=True)
        torch.cuda.empty_cache()
        return img


# Asli Diya photos se naape gaye numbers (training dataset ka fingerprint).
# AI output in sab pe fail hota hai -> isi se "AI jaisa" lagta hai.
REF = {"black": 5.4, "white": 205.0, "sat": 0.387, "noise": 2.4}

# Colour "look" profiles. minimax = neutral white balance, gentle contrast,
# natural (kam) saturation, saaf lekin sterile nahi — yahi MiniMax ka signature hai.
LOOKS = {
    "minimax": dict(black=6.0,  white=212.0, sat=0.360, noise=1.3,
                    ca=0.0005, soft=0.28, softmix=0.40, vig=0.05, wb=0.60),
    "phone":   dict(black=5.4,  white=205.0, sat=0.387, noise=2.4,
                    ca=0.0012, soft=0.40, softmix=0.55, vig=0.10, wb=0.25),
    "raw":     dict(black=2.0,  white=235.0, sat=0.430, noise=0.6,
                    ca=0.0002, soft=0.15, softmix=0.25, vig=0.03, wb=0.15),
}


def camera_sim(img, amount=1.0, look=None):
    """Asli camera ki khaamiyan wapas daalo.

    Naapa hua farq (reference photos vs AI output):
      whites : asli 205  |  AI 255   <- sabse bada "digital" tell
      blacks : asli   5  |  AI   0
      sat    : asli 0.39 |  AI 0.50+
      noise  : asli 2.4  |  AI ~0 (perfectly clean)
    Lens aberration, softness aur vignette bhi AI output me bilkul nahi hote.
    """
    try:
        import numpy as np
        P = LOOKS.get(look or STATE.get("look", "minimax"), LOOKS["minimax"])
        a = np.asarray(img.convert("RGB")).astype(np.float32)
        h, w = a.shape[:2]

        # 0) WHITE BALANCE — AI output me aksar orange/magenta cast hota hai.
        #    Grey-world correction se colour "natural" ho jaata hai (minimax look).
        if P["wb"] > 0:
            m = a.reshape(-1, 3).mean(0)
            g = m.mean()
            a *= (1.0 + ((g / np.maximum(m, 1e-3)) - 1.0) * P["wb"] * amount)[None, None, :]

        # 1) Chromatic aberration — har asli lens me, AI me kabhi nahi
        ca = P["ca"] * amount
        for ch, sc in ((0, 1 + ca), (2, 1 - ca)):
            im = Image.fromarray(a[:, :, ch].clip(0, 255).astype(np.uint8))
            nw, nh = max(w + 2, int(w * sc)), max(h + 2, int(h * sc))
            im = im.resize((nw, nh), Image.BICUBIC)
            l, t = (nw - w) // 2, (nh - h) // 2
            a[:, :, ch] = np.asarray(im.crop((l, t, l + w, t + h))).astype(np.float32)

        # 2) Lens softness — RADIAL, poori image pe nahi.
        #    Asli lens center pe sharp hoti hai aur corners pe soft.
        #    Pehle ye uniform blur tha -> isi se haath/kapde blur lag rahe the.
        yy, xx = np.mgrid[0:h, 0:w]
        rad = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        rad = np.clip(rad / 1.414, 0, 1)
        soft = np.asarray(Image.fromarray(a.clip(0, 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(P["soft"] * amount))).astype(np.float32)
        mix = (P["softmix"] * amount * (0.12 + 0.88 * rad ** 2))[..., None]
        a = a * (1 - mix) + soft * mix

        # 3) TONE RANGE — sabse bada fix
        lum = a.mean(2)
        p1, p99 = np.percentile(lum, 1), np.percentile(lum, 99)
        if p99 - p1 > 1:
            lo = P["black"] + (p1 - P["black"]) * (1 - amount)
            hi = P["white"] + (p99 - P["white"]) * (1 - amount)
            a = (a - p1) * ((hi - lo) / (p99 - p1)) + lo

        # 4) Saturation reference ke paas
        mx, mn = a.max(2), a.min(2)
        cur = ((mx - mn) / (mx + 1e-6)).mean()
        if cur > 0.01:
            f = 1.0 + (P["sat"] / cur - 1.0) * 0.7 * amount
            g = a.mean(2, keepdims=True)
            a = g + (a - g) * f

        # 5) Vignette
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        a *= (1 - P["vig"] * amount * np.clip(r - 0.35, 0, None) ** 2)[..., None]

        # 6) Grain — shadows me zyada
        l2 = a.mean(2, keepdims=True) / 255.0
        a += (np.random.normal(0, 1, a.shape).astype(np.float32)
              * (P["noise"] * amount * (1.5 - 0.7 * l2)))
        return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
    except Exception as e:
        print(f"[real] camera_sim skip: {e}", flush=True)
        return img


# ------------------------------------------------------------------ #
# 3c. INSTAGRAM BACKEND  (@diyarai_016)
# ------------------------------------------------------------------ #
_IG = {"cl": None, "tried": False, "err": ""}
IG_SESSION = "/kaggle/working/ig_session.json"


def ig_client():
    """instagrapi client. Session file reuse hota hai taaki baar baar
    login na ho (Instagram repeated login ko block karta hai)."""
    if _IG["cl"] or _IG["tried"]:
        return _IG["cl"]
    _IG["tried"] = True
    user = os.getenv("IG_USERNAME", "")
    pwd = os.getenv("IG_PASSWORD", "")
    sid = os.getenv("IG_SESSION_ID", "")
    if not (user and (pwd or sid)):
        _IG["err"] = "IG_USERNAME + IG_PASSWORD (ya IG_SESSION_ID) Kaggle Secrets me daalo"
        return None
    try:
        ensure([("instagrapi", "instagrapi")])
        from instagrapi import Client
        cl = Client()
        cl.delay_range = [2, 6]          # anti-ban: har request ke beech gap
        if os.path.exists(IG_SESSION):
            try:
                cl.load_settings(IG_SESSION)
                cl.login(user, pwd) if pwd else cl.login_by_sessionid(sid)
                cl.get_timeline_feed()    # session zinda hai ya nahi
                _IG["cl"] = cl
                print("[ig] session se login", flush=True)
                return cl
            except Exception:
                pass
        if sid:
            cl.login_by_sessionid(sid)
        else:
            cl.login(user, pwd)
        cl.dump_settings(IG_SESSION)
        _IG["cl"] = cl
        print(f"[ig] fresh login @{user}", flush=True)
    except Exception as e:
        _IG["err"] = str(e)[:200]
        print(f"[ig] login fail: {e}", flush=True)
    return _IG["cl"]


CAP_STYLES = {
 "soft":   ["{x} 🤍", "bas yahi mood tha ✨", "{x}, aur kuch nahi 🌸",
            "slow din, soft light 🤍"],
 "desi":   ["{x} 🌼", "ghar wali feeling ✨", "chai + {x} ☕",
            "apna sa din 🧡"],
 "sassy":  ["{x}, deal with it 😌", "no filter, no apology ✨",
            "main hoon na 💅", "{x} 🔥"],
 "short":  ["{x}", "✨", "🤍", "mood"],
 "hindi":  ["{x} — aaj ka din aisa hi tha 🤍", "thoda sa sukoon ✨",
            "yaad rakhne wala pal 🌸", "bas chalta raha din ☁️"],
}

IG_TAGS = ("#indiangirl #desigirl #ootd #indianfashion #delhigirl #mumbai "
           "#sareelove #kurti #indianstyle #explore #instadaily #photooftheday")


def ig_caption(scene_text, style=None, tags=True):
    """Scene se natural caption. Style STATE['capstyle'] se aata hai."""
    if STATE.get("caption"):            # user ne khud likha hai
        c = STATE["caption"]
        return f"{c}\n\n.\n.\n{IG_TAGS}" if tags else c
    base = (scene_text or "").split(",")[0].strip()
    base = (base[0].upper() + base[1:]) if base else "Aaj ka din"
    st = style or STATE.get("capstyle", "soft")
    c = random.choice(CAP_STYLES.get(st, CAP_STYLES["soft"])).format(x=base)
    return f"{c}\n\n.\n.\n{IG_TAGS}" if tags else c


def _ig_fit(path, tw, th, suffix):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    sc = max(tw / w, th / h)
    im = im.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
    l, t = (im.width - tw) // 2, (im.height - th) // 2
    out = str(Path(path).with_suffix("")) + suffix
    im.crop((l, t, l + tw, t + th)).save(out, quality=94, subsampling=1)
    return out


def ig_story(path):
    """Story = 9:16 (1080x1920)."""
    cl = ig_client()
    if cl is None:
        return False, _IG["err"] or "login nahi hua"
    try:
        m = cl.photo_upload_to_story(_ig_fit(path, 1080, 1920, "_story.jpg"))
        return True, f"Story live (24h) — id {m.pk}"
    except Exception as e:
        return False, str(e)[:250]


def ig_post(path, caption):
    cl = ig_client()
    if cl is None:
        return False, _IG["err"] or "login nahi hua"
    try:
        # IG feed ko 4:5 (1080x1350) pasand hai
        m = cl.photo_upload(_ig_fit(path, 1080, 1350, "_ig.jpg"), caption)
        return True, f"https://instagram.com/p/{m.code}"
    except Exception as e:
        return False, str(e)[:250]


def reload_base(model_id):
    """Base checkpoint runtime pe badlo (LoRA dobara attach hoti hai)."""
    global PIPE, I2I
    from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler
    old, I2I = PIPE, None
    PIPE = None
    del old
    torch.cuda.empty_cache()
    pipe = AutoPipelineForText2Image.from_pretrained(
        model_id, torch_dtype=torch.float16, variant="fp16",
        use_safetensors=True, add_watermarker=False).to("cuda")
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++")
    pipe.set_progress_bar_config(disable=True)
    try:
        pipe.enable_xformers_memory_efficient_attention()
    except Exception:
        pass
    pipe.enable_vae_slicing()
    lora = find_lora()
    if lora:
        pipe.load_lora_weights(lora, adapter_name="diya")
        pipe.set_adapters(["diya"], adapter_weights=[STATE["scale"]])
    PIPE = pipe
    ARGS.base = model_id
    print(f"[load] base switched -> {model_id}", flush=True)


def gpu_worker():
    load_pipeline()
    tg(f"Diya GPU server ONLINE\nGPU: {STATE['gpu']}\n"
       f"LoRA: {STATE['lora'] or 'NONE'}\nDashboard: {STATE['url'] or 'starting...'}")
    while True:
        jid = JOBQ.get()
        job = JOBS.get(jid)
        if not job or job["status"] == "cancelled":
            continue
        job.update(status="running", started=time.time())
        STATE["current"] = jid
        if job["source"] == "telegram":
            tg(f"Banana shuru #{jid}\n{job['prompt'][:120]}")
        try:
            if STATE["lora"]:
                PIPE.set_adapters(["diya"], adapter_weights=[job["scale"]])
            full = build_prompt(job["prompt"])
            for i in range(job["n"]):
                t = time.time()
                best, best_sc, tries = None, -1.0, 0
                want = STATE.get("match", 0.0)
                maxtry = STATE.get("retry", 2) if want > 0 else 1
                while tries < maxtry:
                    tries += 1
                    full = build_prompt(job["prompt"], seed=int(t) + i * 97 + tries * 311)
                    # retry pe LoRA thodi strong — identity kam padi thi
                    if tries > 1 and STATE["lora"]:
                        PIPE.set_adapters(["diya"],
                                          adapter_weights=[min(1.2, job["scale"] + 0.12 * (tries - 1))])
                    cand = PIPE(prompt=full, negative_prompt=NEG,
                                num_inference_steps=job["steps"],
                                guidance_scale=STATE["cfg"],
                                width=STATE["width"], height=STATE["height"]).images[0]
                    sc = face_score(cand) if want > 0 else None
                    if sc is None:
                        best, best_sc = cand, -1.0
                        break
                    if sc > best_sc:
                        best, best_sc = cand, sc
                    print(f"[id] try {tries}: face match {sc:.3f}", flush=True)
                    if sc >= want:
                        break
                img = best
                if STATE["lora"]:
                    PIPE.set_adapters(["diya"], adapter_weights=[job["scale"]])
                stage = "base"
                if STATE["real"]:
                    img = hires_fix(img, full);   stage = "hires"
                    img = face_detail(img, full); stage = "face"
                    if STATE.get("hands", True):
                        img = hand_detail(img);   stage = "hands"
                    torch.cuda.empty_cache()
                final_sc = face_score(img) if want > 0 else None
                if STATE["cam"]:
                    img = camera_sim(img, STATE["cam"])
                name = f"diya_{int(time.time())}_{i}.jpg"
                p = str(OUT / name)
                img.save(p, quality=95, subsampling=1)
                if job["swap"]:
                    p = polish(p)
                    name = Path(p).name
                dt = time.time() - t
                job["images"].append({"file": name, "secs": round(dt, 1)})
                STATE["made"] += 1
                STATE["last_img"], STATE["last_prompt"] = p, job["prompt"]
                if job["source"] == "telegram":
                    mtxt = ""
                    if final_sc is not None:
                        tick = "✅" if final_sc >= 0.69 else ("🟡" if final_sc >= 0.60 else "❌")
                        mtxt = f" | face {final_sc*100:.0f}% {tick}"
                        if tries > 1:
                            mtxt += f" ({tries} try)"
                    tg(f"Diya #{STATE['made']} | {dt:.0f}s | LoRA {job['scale']}"
                       f"{mtxt}\n{job['prompt'][:140]}", p)
                print(f"[gen] {name} {dt:.1f}s", flush=True)
            job.update(status="done", finished=time.time())
            touch("job done")
        except Exception as e:
            traceback.print_exc()
            job.update(status="error", error=str(e), finished=time.time())
            STATE["failed"] += 1
            if job["source"] == "telegram":
                tg(f"Error #{jid}: {e}")
        finally:
            STATE["current"] = None
            JOBQ.task_done()


# ------------------------------------------------------------------ #
# 4. Telegram poller thread
# ------------------------------------------------------------------ #
HELP = ("Diya Rai Studio\n"
        "---------------------\n"
        "Bas prompt likh do. Command ki zaroorat nahi.\n"
        "   mirror selfie in pink pajamas, bedroom\n\n"
        "/n 2       ek saath kitni photo (1-4)\n"
        "/best      sabse real (dheema ~45s)\n"
        "/fast      jaldi (~15s)\n"
        "/sleep     GPU band karo (quota bachao)\n\n"
        "/day /night /monsoon /food /daily\n"
        "           asli zindagi ke scenes (HD filter on)\n"
        "/scenes    poori list\n"
        "/post      Instagram feed pe\n"
        "/story     Instagram story pe (24h)\n"
        "/caption   apna caption likho\n"
        "/presets   ready-made prompts\n"
        "/more      baaki saare controls")

MORE = ("Advanced\n"
        "---------------------\n"
        "Inhe chhedne ki zaroorat nahi — /best aur /fast\n"
        "already sahi values set kar dete hain.\n\n"
        "LOOK\n"
        "/look minimax|phone|raw   colour profile\n"
        "/cam 1.0                  camera realism (0-1.5)\n"
        "/cfg 3.5                  3.5 real | 6+ plastic\n"
        "/hands on|off             ungli fix\n\n"
        "IDENTITY\n"
        "/scale 1.0                LoRA strength (0.1-1.2)\n"
        "/match 0.68               face match target (0 = off)\n"
        "/swap on|off              face polish (plastic kar sakta hai)\n"
        "/base realvis|realvis5|sdxl|jugg\n\n"
        "SPEED\n"
        "/steps 30                 15-40\n"
        "/real on|off              hires + face detail\n\n"
        "INSTAGRAM\n"
        "/ig                       account status\n"
        "/post                     feed post (4:5)\n"
        "/story                    story (9:16, 24h)\n"
        "/caption <text>           apna caption | auto\n"
        "/style soft|desi|sassy|short|hindi\n\n"
        "SERVER\n"
        "/status  /queue  /web  /stay 20  /stop")


def telegram_loop():
    offset = None
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"timeout": 50, "offset": offset}, timeout=60)
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
                    continue
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                low = text.lower()
                touch("telegram message")
                print(f"[tg] {text}", flush=True)

                if low in ("/start", "/help"):
                    tg(HELP + f"\n\nDashboard: {STATE['url']}")
                elif low.startswith("/web"):
                    tg(f"Dashboard: {STATE['url'] or 'tunnel abhi ban raha hai...'}")
                elif low.startswith("/presets"):
                    tg("Seedha naam likh do:\n" + "\n".join(f"- {k}" for k in PRESETS))
                elif low.startswith("/status"):
                    tg(status_text())
                elif low.startswith("/queue"):
                    pend = [j for j in JOBS.values() if j["status"] in ("queued", "running")]
                    tg(f"Queue: {len(pend)}\n" + "\n".join(
                        f"#{j['id']} {j['status']} — {j['prompt'][:40]}" for j in pend[:10])
                       if pend else "Queue khaali — ready")
                elif low.startswith("/stop") or low.startswith("/sleep"):
                    shutdown("tumne bola", tell=False)
                    tg("GPU band. Agla prompt bhejo to waker jaga dega.")
                elif low.startswith("/stay"):
                    try:
                        STATE["idle_min"] = float(text.split()[1])
                    except Exception:
                        STATE["idle_min"] = 0
                    tg(f"Idle shutdown = {STATE['idle_min'] or 'OFF (quota jalega!)'}"
                       + (" min" if STATE["idle_min"] else ""))
                elif low.startswith("/n"):
                    try:
                        STATE["n"] = max(1, min(4, int(text.split()[1])))
                        tg(f"n = {STATE['n']}")
                    except Exception:
                        tg("Use: /n 2")
                elif low.startswith("/scale"):
                    try:
                        STATE["scale"] = max(0.1, min(1.2, float(text.split()[1])))
                        tg(f"LoRA scale = {STATE['scale']}  (1.0 = max likeness)")
                    except Exception:
                        tg("Use: /scale 0.95")
                elif low.startswith("/steps"):
                    try:
                        STATE["steps"] = max(15, min(40, int(text.split()[1])))
                        tg(f"steps = {STATE['steps']}")
                    except Exception:
                        tg("Use: /steps 30")
                elif low.startswith("/real"):
                    STATE["real"] = "off" not in low
                    tg(f"Realism pass (hires + face detail) = "
                       f"{'ON' if STATE['real'] else 'OFF'}\n"
                       + ("Aankhein/skin asli lagengi, ~25s extra lagega."
                          if STATE["real"] else "Tez hoga par AI jaisa lagega."))
                elif low.startswith("/cfg"):
                    try:
                        STATE["cfg"] = max(1.5, min(9.0, float(text.split()[1])))
                        tg(f"cfg = {STATE['cfg']}\n"
                           f"3.5-4.5 = sabse real. 6+ = plastic/AI look.")
                    except Exception:
                        tg("Use: /cfg 4")
                elif low.split()[0].lstrip("/") in SCENES:
                    cat = low.split()[0].lstrip("/")
                    extra = text.split(" ", 1)[1].strip() if " " in text else ""
                    sc = random.choice(SCENES[cat])
                    if extra:
                        sc = f"{sc}, {extra}"
                    # HD filter hamesha ON — command se aaya matlab best quality
                    STATE.update(real=True, cam=max(STATE["cam"], 1.0),
                                 look="minimax", hands=True)
                    new_job(sc, "telegram")
                    tg(f"🎬 {cat} scene\n{sc[:200]}\n\nHD filter on. Bana raha hoon...")
                elif low.startswith("/scenes"):
                    tg("Scene commands — har baar naya scene milta hai:\n\n"
                       + "\n".join(f"/{k}  ({len(v)} scenes)" for k, v in SCENES.items())
                       + "\n\nSaath me apna detail bhi likh sakte ho:\n"
                         "   /night red saree\n   /food with friends\n\n"
                         "Inme HD filter hamesha on rehta hai.")
                elif low.startswith("/caption"):
                    arg = text.split(" ", 1)[1].strip() if " " in text else ""
                    if arg.lower() in ("off", "clear", "auto", "-"):
                        STATE["caption"] = ""
                        tg("Caption auto mode on.\nAbhi banega: \n\n"
                           + ig_caption(STATE.get("last_prompt", ""), tags=False))
                    elif arg:
                        STATE["caption"] = arg
                        tg(f"Caption set:\n\n{arg}\n\n"
                           "Ab /post ya /story bhejo.\n/caption auto = wapas automatic")
                    else:
                        tg("Abhi ka caption:\n\n"
                           + ig_caption(STATE.get("last_prompt", ""), tags=False)
                           + "\n\nApna likhne ke liye:\n/caption aaj ka mood 🤍\n"
                             "Automatic ke liye: /caption auto")
                elif low.startswith("/capstyle") or low.startswith("/style"):
                    w = text.split()[1].lower() if len(text.split()) > 1 else ""
                    if w in CAP_STYLES:
                        STATE["capstyle"] = w
                        STATE["caption"] = ""
                        tg(f"Caption style = {w}\n\nSample:\n"
                           + ig_caption(STATE.get("last_prompt", ""), w, tags=False))
                    else:
                        tg("Caption styles:\n\n"
                           + "\n".join(
                               f"/style {k}\n   {ig_caption(STATE.get('last_prompt',''), k, tags=False)}"
                               for k in CAP_STYLES)
                           + f"\n\nAbhi: {STATE['capstyle']}")
                elif low.startswith("/post") or low.startswith("/story"):
                    story = low.startswith("/story")
                    last = STATE.get("last_img")
                    if not last or not os.path.exists(last):
                        tg("Pehle koi photo banao, phir /post ya /story")
                    elif low.strip() in ("/post", "/story"):
                        cap = ig_caption(STATE.get("last_prompt", ""), tags=False)
                        kind = "STORY (24h)" if story else "FEED POST"
                        tg(f"📤 {kind} — confirm karo\n"
                           f"{'─'*22}\n"
                           + ("" if story else f"Caption:\n{cap}\n\n")
                           + f"Size: {'1080x1920 (9:16)' if story else '1080x1350 (4:5)'}\n"
                             f"{'─'*22}\n"
                             f"Haan -> {low.strip()} yes\n"
                             "Caption badlo -> /caption <apna text>\n"
                             "Style badlo -> /style")
                    else:
                        tg("Instagram pe daal raha hoon...")
                        if story:
                            ok, res = ig_story(last)
                        else:
                            ok, res = ig_post(last, ig_caption(STATE.get("last_prompt", "")))
                        tg(f"✅ {'Story' if story else 'Post'} live\n{res}"
                           if ok else f"❌ Fail: {res}")
                elif low.startswith("/ig"):
                    cl = ig_client()
                    if cl is None:
                        tg(f"Instagram connected nahi.\n{_IG['err']}\n\n"
                           "Kaggle -> Add-ons -> Secrets me daalo:\n"
                           "IG_USERNAME, IG_PASSWORD")
                    else:
                        try:
                            u = cl.account_info()
                            tg(f"✅ @{u.username}\n{u.follower_count} followers\n\n"
                               "/post = last photo Instagram pe daalo")
                        except Exception as e:
                            tg(f"Connected, par info nahi mili: {e}")
                elif low.startswith("/match"):
                    try:
                        STATE["match"] = max(0.0, min(0.85, float(text.split()[1])))
                    except Exception:
                        STATE["match"] = 0.0 if STATE["match"] else 0.68
                    tg(f"face match target = {STATE['match'] or 'OFF'}\n"
                       "Jo photo match na kare, dobara banti hai (max "
                       f"{STATE['retry']} try).\n0.55+ = pakka wahi chehra")
                elif low.startswith("/more"):
                    tg(MORE)
                elif low.startswith("/best"):
                    STATE.update(scale=1.0, steps=24, cfg=3.5, real=True, cam=1.0,
                                 look="minimax", hands=True, swap=False,
                                 match=0.68, retry=3)
                    tg("BEST mode\n"
                       "hires + face detail + hand repair + camera sim\n"
                       "face match check ON (68% se kam ho to dobara banata hai)\n"
                       "~40s per photo. Ab prompt bhejo.")
                elif low.startswith("/fast"):
                    STATE.update(scale=1.0, steps=18, cfg=3.5, real=True, cam=1.0,
                                 look="minimax", hands=False, swap=False,
                                 match=0.0, retry=1)
                    tg("FAST mode\n"
                       "face detail on, hires/hand pass off, no retry\n"
                       "~15s per photo. Wapas: /best")
                elif low.startswith("/look"):
                    want = (text.split()[1].lower() if len(text.split()) > 1 else "")
                    if want in LOOKS:
                        STATE["look"] = want
                        tg(f"colour look = {want}")
                    else:
                        tg("/look minimax  natural colour, neutral WB (default)\n"
                           "/look phone    thoda zyada grainy phone look\n"
                           "/look raw      model ka apna colour\n"
                           f"\nAbhi: {STATE['look']}")
                elif low.startswith("/hands"):
                    STATE["hands"] = not (len(text.split()) > 1 and
                                          text.split()[1].lower() in ("off", "0", "no"))
                    tg(f"hand guard = {'ON' if STATE['hands'] else 'OFF'}\n"
                       "ON = haath relaxed/neeche rakhe jaate hain, ungliyan kam bigadti hain")
                elif low.startswith("/cam"):
                    try:
                        STATE["cam"] = max(0.0, min(1.5, float(text.split()[1])))
                    except Exception:
                        STATE["cam"] = 0.0 if STATE["cam"] else 1.0
                    tg(f"camera sim = {STATE['cam'] or 'OFF'}\n"
                       f"0 = raw AI look | 1.0 = asli phone photo | 1.5 = zyada")
                elif low.startswith("/base"):
                    want = text.split(" ", 1)[1].strip() if " " in text else ""
                    opts = {"realvis": "SG161222/RealVisXL_V4.0",
                            "realvis5": "SG161222/RealVisXL_V5.0",
                            "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
                            "jugg": "RunDiffusion/Juggernaut-XL-v9"}
                    if want.lower() in opts:
                        want = opts[want.lower()]
                    if not want:
                        tg("Base model badlo (reload ~90s):\n"
                           + "\n".join(f"/base {k}  -> {v}" for k, v in opts.items())
                           + f"\n\nAbhi: {ARGS.base}")
                    else:
                        tg(f"{want} load kar raha hoon... ~90s")
                        try:
                            reload_base(want)
                            tg(f"Base model badal gaya: {want}\nAb prompt bhejo.")
                        except Exception as e:
                            tg(f"Fail: {e}")
                elif low.startswith("/swap"):
                    STATE["swap"] = "on" in low
                    tg(f"face polish = {'ON' if STATE['swap'] else 'OFF'}")
                elif low.startswith("/photo"):
                    pr = text.split(" ", 1)[1] if " " in text else ""
                    if not pr:
                        tg("Prompt likho:\n/photo red saree, terrace sunset")
                    else:
                        j = new_job(pr, "telegram")
                        tg(f"Queued #{j['id']} (position {JOBQ.qsize()})")
                elif not low.startswith("/"):
                    j = new_job(text, "telegram")
                    tg(f"Queued #{j['id']} (position {JOBQ.qsize()})")
                else:
                    tg(HELP)
        except Exception as e:
            print(f"[tg] poll {e}", flush=True)
            time.sleep(5)



def shutdown(reason, tell=True):
    """GPU session band karo — Kaggle quota bachane ke liye."""
    print(f"\n[idle] SHUTDOWN: {reason}", flush=True)
    if tell:
        tg(f"GPU band kar raha hoon ({reason}).\n"
           f"Quota bacha: ab khaali nahi jalega.\n\n"
           f"Agla prompt bhejo — GitHub waker 5 min ke andar GPU wapas jaga dega "
           f"(ya Kaggle pe khud Run daba do).")
    time.sleep(2)          # Telegram ko bhejne ka time do
    os._exit(0)


def idle_watchdog():
    """Har 15 sec check: koi kaam nahi + queue khaali => band."""
    if not STATE["idle_min"]:
        print("[idle] auto-shutdown OFF (--idle-minutes 0)", flush=True)
        return
    limit = STATE["idle_min"] * 60
    warned = False
    print(f"[idle] auto-shutdown ON — {STATE['idle_min']:.0f} min", flush=True)
    while True:
        time.sleep(15)
        # kaam chal raha hai ya queue me pada hai -> timer reset
        if JOBQ.qsize() or STATE["current"]:
            touch()
            warned = False
            continue
        idle = time.time() - STATE["last_activity"]
        if idle > limit:
            shutdown(f"{STATE['idle_min']:.0f} min se koi kaam nahi")
        elif idle > limit - 60 and not warned:
            warned = True
            left = int(limit - idle)
            tg(f"1 minute me GPU band ho jayega (quota bachane ke liye).\n"
               f"Kuch banana hai to abhi prompt bhejo — timer reset ho jayega.")
            print(f"[idle] {left}s bache", flush=True)


def _idle_str():
    if not STATE["idle_min"]:
        return "auto-shutdown off"
    left = STATE["idle_min"] * 60 - (time.time() - STATE["last_activity"])
    return f"{max(0, left) / 60:.1f} min baad band"


def status_text():
    return (f"DIYA SERVER\n"
            f"GPU     : {STATE['gpu']}\n"
            f"VRAM    : {torch.cuda.memory_allocated()/1e9:.1f} GB\n"
            f"Model   : {'ready' if STATE['model_ready'] else 'loading...'}\n"
            f"LoRA    : {STATE['lora'] or 'NONE (base model)'}\n"
            f"Uptime  : {(time.time()-STATE['start'])/60:.0f} min\n"
            f"Banayi  : {STATE['made']}  |  Fail: {STATE['failed']}\n"
            f"Queue   : {JOBQ.qsize()}\n"
            f"Idle    : {_idle_str()}\n"
            f"real={'on' if STATE['real'] else 'off'} cfg={STATE['cfg']} "
            f"cam={STATE['cam']} look={STATE['look']} hands={STATE['hands']}\n"
                        f"face match target={STATE['match']}\n"
            f"n={STATE['n']} scale={STATE['scale']} steps={STATE['steps']} "
            f"swap={'on' if STATE['swap'] else 'off'}\n"
            f"Web     : {STATE['url']}")


# ------------------------------------------------------------------ #
# 5. FastAPI + dashboard
# ------------------------------------------------------------------ #
app = FastAPI(title="Diya Rai Studio")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


class GenReq(BaseModel):
    prompt: str
    n: int | None = None
    scale: float | None = None
    steps: int | None = None
    swap: bool | None = None


@app.post("/api/generate")
def api_generate(req: GenReq):
    """Turant job_id lautata hai — GPU background me chalta hai."""
    if not req.prompt.strip():
        raise HTTPException(400, "prompt khaali hai")
    j = new_job(req.prompt.strip(), "web", req.n, req.scale, req.steps, req.swap)
    return {"job_id": j["id"], "status": "queued", "queue": JOBQ.qsize()}


@app.get("/api/state")
def api_state():
    with LOCK:
        jobs = list(JOBS.values())[-40:][::-1]
    return {
        "gpu": STATE["gpu"],
        "vram": round(torch.cuda.memory_allocated() / 1e9, 2),
        "model_ready": STATE["model_ready"],
        "lora": STATE["lora"],
        "uptime": int(time.time() - STATE["start"]),
        "made": STATE["made"], "failed": STATE["failed"],
        "queue": JOBQ.qsize(), "current": STATE["current"],
        "idle_min": STATE["idle_min"],
        "idle_left": max(0, STATE["idle_min"] * 60 - (time.time() - STATE["last_activity"])) if STATE["idle_min"] else None,
        "defaults": {k: STATE[k] for k in ("n", "scale", "steps", "swap", "real", "cfg", "cam", "look", "hands", "match")},
        "presets": PRESETS,
        "url": STATE["url"],
        "jobs": jobs,
        "now": time.time(),
    }


@app.post("/api/settings")
def api_settings(body: dict):
    for k in ("n", "scale", "steps", "swap", "cfg", "real", "cam", "look", "hands", "match"):
        if k in body:
            STATE[k] = body[k]
    return {"ok": True, "state": {k: STATE[k] for k in ("n", "scale", "steps", "swap")}}


@app.post("/api/cancel/{jid}")
def api_cancel(jid: str):
    j = JOBS.get(jid)
    if j and j["status"] == "queued":
        j["status"] = "cancelled"
        return {"ok": True}
    return {"ok": False}


@app.get("/img/{name}")
def api_img(name: str):
    p = OUT / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(str(p), media_type="image/jpeg")


@app.get("/health")
def health():
    return {"ok": True, "ready": STATE["model_ready"]}


DASHBOARD = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diya Rai Studio</title><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0f;color:#e8e8f0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:18px}
a{color:#c084fc}
.wrap{max-width:1250px;margin:0 auto}
h1{font-size:21px;font-weight:700;letter-spacing:-.4px}
h1 span{background:linear-gradient(90deg,#f472b6,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:16px}
.pill{font-size:11px;padding:4px 11px;border-radius:99px;background:#1a1a26;border:1px solid #2a2a3a;color:#9ca3af;white-space:nowrap}
.pill b{color:#e8e8f0;font-weight:600}
.ok{color:#4ade80}.warn{color:#fbbf24}.bad{color:#f87171}
.card{background:#12121a;border:1px solid #23233a;border-radius:14px;padding:16px;margin-bottom:16px}
textarea{width:100%;background:#0a0a12;border:1px solid #2a2a3a;border-radius:10px;color:#e8e8f0;
 padding:12px;font:inherit;resize:vertical;min-height:76px;outline:none}
textarea:focus{border-color:#a78bfa}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin:11px 0}
.chip{font-size:12px;padding:5px 12px;border-radius:99px;background:#1a1a2a;border:1px solid #2e2e44;
 cursor:pointer;transition:.15s;text-transform:capitalize}
.chip:hover{background:#2a2a44;border-color:#a78bfa}
.ctrls{display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin:13px 0}
.ctrl{display:flex;flex-direction:column;gap:3px;min-width:140px}
.ctrl label{font-size:11px;color:#8b8ba7;text-transform:uppercase;letter-spacing:.5px}
.ctrl label b{color:#c084fc}
input[type=range]{accent-color:#a78bfa;width:100%}
.sw{display:flex;align-items:center;gap:7px;font-size:13px;cursor:pointer;color:#9ca3af}
button{background:linear-gradient(135deg,#a78bfa,#f472b6);border:0;color:#0a0a0f;font-weight:700;
 padding:12px 30px;border-radius:10px;cursor:pointer;font-size:15px;transition:.15s}
button:hover{filter:brightness(1.12)}
button:disabled{opacity:.45;cursor:not-allowed;filter:none}
.sec{font-size:12px;color:#8b8ba7;text-transform:uppercase;letter-spacing:.8px;margin:0 0 11px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:13px}
.tile{background:#0d0d16;border:1px solid #23233a;border-radius:11px;overflow:hidden;position:relative;aspect-ratio:832/1216}
.tile img{width:100%;height:100%;object-fit:cover;display:block;cursor:zoom-in}
.tile .meta{position:absolute;left:0;right:0;bottom:0;padding:18px 9px 7px;font-size:10px;color:#cbd5e1;
 background:linear-gradient(transparent,rgba(0,0,0,.9));pointer-events:none}
.load{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px;
 background:repeating-linear-gradient(45deg,#12121c,#12121c 11px,#15151f 11px,#15151f 22px)}
.spin{width:28px;height:28px;border:3px solid #2a2a3a;border-top-color:#a78bfa;border-radius:50%;animation:s .8s linear infinite}
@keyframes s{to{transform:rotate(360deg)}}
.t{font-variant-numeric:tabular-nums;font-size:12px;color:#a78bfa;font-weight:600}
.lbl{font-size:10px;color:#6b7280;text-align:center;padding:0 9px;line-height:1.35}
.err{color:#f87171;font-size:11px;padding:9px;text-align:center}
.empty{color:#4b5563;font-size:13px;padding:26px;text-align:center}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.93);display:none;align-items:center;justify-content:center;z-index:99;cursor:zoom-out}
#lb img{max-width:94vw;max-height:94vh;border-radius:8px}
</style></head><body><div class="wrap">

<div class="top">
  <h1>👑 <span>Diya Rai Studio</span></h1>
  <div class="pill" id="p-model">booting…</div>
  <div class="pill" id="p-lora">LoRA —</div>
  <div class="pill" id="p-q">queue 0</div>
  <div class="pill" id="p-made">0 made</div>
  <div class="pill" id="p-gpu">—</div>
  <div class="pill" id="p-idle"></div>
</div>

<div class="card">
  <textarea id="prompt" placeholder="Prompt likho… jaise: red chiffon saree, terrace sunset, candid smile, wind in hair"></textarea>
  <div class="chips" id="chips"></div>
  <div class="ctrls">
    <div class="ctrl"><label>Images <b id="v-n">1</b></label>
      <input type="range" id="n" min="1" max="4" step="1" value="1"></div>
    <div class="ctrl"><label>Identity (LoRA) <b id="v-scale">0.85</b></label>
      <input type="range" id="scale" min="0.3" max="1.2" step="0.05" value="0.85"></div>
    <div class="ctrl"><label>Steps <b id="v-steps">28</b></label>
      <input type="range" id="steps" min="15" max="40" step="1" value="28"></div>
    <label class="sw"><input type="checkbox" id="swap"> Face polish (GFPGAN)</label>
    <button id="go">Generate</button>
  </div>
</div>

<div class="card">
  <p class="sec">Processing & Output</p>
  <div class="grid" id="grid"><div class="empty">Abhi kuch nahi banaya. Upar prompt daalo.</div></div>
</div>

</div><div id="lb"><img id="lbi"></div><script>
let NOW_SKEW=0, PRESETS={};
const $=id=>document.getElementById(id);
['n','scale','steps'].forEach(k=>$(k).oninput=e=>{$('v-'+k).textContent=e.target.value});

async function go(){
  const p=$('prompt').value.trim(); if(!p)return;
  $('go').disabled=true; $('go').textContent='Queued…';
  try{
    await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt:p,n:+$('n').value,scale:+$('scale').value,
                           steps:+$('steps').value,swap:$('swap').checked})});
    await tick();
  }catch(e){alert(e)}
  setTimeout(()=>{$('go').disabled=false;$('go').textContent='Generate'},400);
}
$('go').onclick=go;
$('prompt').onkeydown=e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))go()};
$('lb').onclick=()=>$('lb').style.display='none';

function fmt(s){s=Math.max(0,s);const m=Math.floor(s/60);
  return m?`${m}m ${String(Math.floor(s%60)).padStart(2,'0')}s`:`${s.toFixed(1)}s`}

function render(d){
  NOW_SKEW = d.now - Date.now()/1000;
  $('p-model').innerHTML = d.model_ready
    ? '<b class="ok">● model ready</b>' : '<b class="warn">● loading model…</b>';
  $('p-lora').innerHTML = d.lora
    ? 'LoRA <b class="ok">'+d.lora+'</b>' : '<b class="bad">no LoRA — train karo</b>';
  $('p-q').innerHTML='queue <b>'+d.queue+'</b>';
  $('p-made').innerHTML='<b>'+d.made+'</b> made'+(d.failed?' · <b class="bad">'+d.failed+' fail</b>':'');
  $('p-gpu').innerHTML=d.gpu+' · <b>'+d.vram+' GB</b>';
  const ip=$('p-idle');
  if(d.idle_left==null){ip.innerHTML='idle-off';ip.style.display='';}
  else{const m=d.idle_left/60;
    ip.innerHTML='GPU band in <b class="'+(m<1?'bad':m<2?'warn':'ok')+'">'+m.toFixed(1)+'m</b>';
    ip.style.display='';}

  if(!Object.keys(PRESETS).length && d.presets){
    PRESETS=d.presets;
    $('chips').innerHTML=Object.keys(PRESETS).map(k=>`<div class="chip" data-k="${k}">${k}</div>`).join('');
    $('chips').querySelectorAll('.chip').forEach(c=>c.onclick=()=>{$('prompt').value=PRESETS[c.dataset.k]});
  }

  const tiles=[];
  for(const j of d.jobs){
    if(j.status==='done'){
      for(const im of j.images) tiles.push(
        `<div class="tile"><img src="/img/${im.file}" loading="lazy" onclick="zoom(this.src)">
         <div class="meta">${im.secs}s · ${j.source} · scale ${j.scale}<br>${esc(j.prompt).slice(0,60)}</div></div>`);
    }else if(j.status==='running'){
      const el=(Date.now()/1000+NOW_SKEW)-j.started;
      tiles.push(`<div class="tile"><div class="load"><div class="spin"></div>
         <div class="t" data-st="${j.started}">${fmt(el)}</div>
         <div class="lbl">${esc(j.prompt).slice(0,60)}</div>
         <div class="lbl" style="color:#a78bfa">generating ${j.images.length}/${j.n}</div></div></div>`);
    }else if(j.status==='queued'){
      tiles.push(`<div class="tile"><div class="load">
         <div class="t" style="color:#6b7280">⏳ queued</div>
         <div class="lbl">${esc(j.prompt).slice(0,60)}</div></div></div>`);
    }else if(j.status==='error'){
      tiles.push(`<div class="tile"><div class="load"><div class="err">⚠ ${esc(j.error||'error')}</div>
         <div class="lbl">${esc(j.prompt).slice(0,60)}</div></div></div>`);
    }
  }
  $('grid').innerHTML = tiles.length?tiles.join(''):'<div class="empty">Abhi kuch nahi banaya. Upar prompt daalo.</div>';
}
function esc(s){return (s||'').replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]))}
function zoom(src){$('lbi').src=src;$('lb').style.display='flex'}
async function tick(){try{render(await (await fetch('/api/state')).json())}catch(e){}}
setInterval(tick,1600);
setInterval(()=>document.querySelectorAll('.t[data-st]').forEach(e=>{
  e.textContent=fmt((Date.now()/1000+NOW_SKEW)-+e.dataset.st)}),100);
tick();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD


# ------------------------------------------------------------------ #
# 6. Public tunnel (cloudflared — free, no signup)
# ------------------------------------------------------------------ #
def start_tunnel(port):
    try:
        cf = MODELS / "cloudflared"
        if not cf.exists():
            if not _download(
                "https://github.com/cloudflare/cloudflared/releases/latest/download/"
                "cloudflared-linux-amd64", cf, 5):
                return None
            cf.chmod(0o755)
        proc = subprocess.Popen(
            [str(cf), "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        t0 = time.time()
        for line in proc.stdout:
            m = re.search(r"https://[-\w]+\.trycloudflare\.com", line)
            if m:
                return m.group(0)
            if time.time() - t0 > 60:
                break
    except Exception as e:
        print(f"[tunnel] {e}", flush=True)
    return None


def tunnel_thread(port):
    url = start_tunnel(port)
    if url:
        STATE["url"] = url
        print("\n" + "=" * 72)
        print(f"  DASHBOARD LIVE:  {url}")
        print("=" * 72 + "\n", flush=True)
        tg(f"Dashboard live:\n{url}\n\nTelegram se bhi bana sakte ho — seedha prompt likho.")
    else:
        STATE["url"] = f"http://127.0.0.1:{port}"
        print("[tunnel] nahi bana — local only", flush=True)


# ------------------------------------------------------------------ #
# 7. Boot
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    threading.Thread(target=gpu_worker, daemon=True).start()
    threading.Thread(target=idle_watchdog, daemon=True).start()
    if not ARGS.no_tunnel:
        threading.Thread(target=tunnel_thread, args=(ARGS.port,), daemon=True).start()
    if TG_OK:
        threading.Thread(target=telegram_loop, daemon=True).start()
        print("[tg] poller started", flush=True)
    else:
        print("[tg] secrets missing — sirf web dashboard chalega", flush=True)

    print(f"[web] http://0.0.0.0:{ARGS.port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=ARGS.port, log_level="warning")
