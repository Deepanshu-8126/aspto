"""
================================================================================
 DIYA RAI — SDXL LoRA TRAINER (Kaggle T4 / P100, ~30-40 min)
================================================================================
Yeh script aapke 15 real Diya photos se ek asli LoRA train karta hai.
Iske baad face "almost swap" nahi, balki *exact* generate hoga.

KYUN YEH TEZ HAI
----------------
1. VAE latents ek baar pre-compute hote hain  -> har step pe VAE nahi chalta
2. Text embeddings ek baar pre-compute hote hain -> dono text encoders
   training se PEHLE RAM se delete ho jaate hain (~5 GB VRAM free)
3. Sirf UNet attention LoRA train hota hai (rank 32)
4. 8-bit Adam + gradient checkpointing -> T4 16GB me aaram se fit

KAGGLE SETUP
------------
  Accelerator : GPU T4 x2  (ya P100)
  Internet    : ON
  Dataset     : apna `10_diyarai woman` folder Kaggle Dataset me upload karo
                (naam: diya-lora-dataset)

CHALANA
-------
  !python kaggle_lora_train.py --data "/kaggle/input/diya-lora-dataset" --steps 1500

OUTPUT
------
  /kaggle/working/diyarai_sdxl_lora.safetensors   <- isko Kaggle Dataset
                                                     "diyarai-sdxl-lora" me upload karo
================================================================================
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

# ------------------------------------------------------------------ #
# 0. Dependencies (sirf jo missing hain — Kaggle me torch pehle se hai)
# ------------------------------------------------------------------ #
def _fix_torchao():
    """Kaggle image me torchao 0.10 preinstalled hai. peft usko dekh kar
    `ImportError: Found an incompatible version of torchao` phenk deta hai
    (peft/tuners/lora/torchao.py). Humein torchao chahiye hi nahi -> hata do.
    Ye peft/diffusers import se PEHLE chalna chahiye."""
    try:
        import torchao
        ver = getattr(torchao, "__version__", "0")
        major_minor = tuple(int(x) for x in ver.split(".")[:2] if x.isdigit())
        if major_minor and major_minor < (0, 16):
            print(f"[deps] torchao {ver} peft se clash karta hai — hata raha hoon")
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q",
                            "torchao"], check=False)
            for m in [m for m in sys.modules if m.startswith("torchao")]:
                del sys.modules[m]
    except ImportError:
        pass
    except Exception as e:
        print(f"[deps] torchao check skip: {e}")


def _ensure_deps():
    if "--help" in sys.argv or "-h" in sys.argv:
        return
    _fix_torchao()
    need = []
    for mod, pkg in [
        ("diffusers", "diffusers>=0.31.0"),
        ("peft", "peft>=0.13.0"),
        ("transformers", "transformers>=4.44.0"),
        ("accelerate", "accelerate>=0.33.0"),
        ("safetensors", "safetensors"),
        ("bitsandbytes", "bitsandbytes"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            need.append(pkg)
    if need:
        print(f"[deps] installing: {need}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", *need],
            check=True,
        )
    else:
        print("[deps] sab pehle se installed — 0 sec")


_ensure_deps()

import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from diffusers import AutoencoderKL, DDPMScheduler, StableDiffusionXLPipeline, UNet2DConditionModel
from diffusers.utils import convert_state_dict_to_diffusers
from peft import LoraConfig, get_peft_model_state_dict
from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPTokenizer

# ------------------------------------------------------------------ #
# 1. Args
# ------------------------------------------------------------------ #
p = argparse.ArgumentParser()
p.add_argument("--data", type=str, default="/kaggle/input/diya-lora-dataset",
               help="Folder jisme .png + .txt caption pairs hain (nested bhi chalega)")
p.add_argument("--base", type=str, default="stabilityai/stable-diffusion-xl-base-1.0")
p.add_argument("--out", type=str, default="/kaggle/working/diyarai_sdxl_lora.safetensors")
p.add_argument("--trigger", type=str, default="diyarai")
p.add_argument("--steps", type=int, default=900,
               help="12 saaf images ke liye 900 kaafi hai (pehle 15 gande pe 1500 the)")
p.add_argument("--rank", type=int, default=32)
p.add_argument("--alpha", type=int, default=16)
p.add_argument("--lr", type=float, default=1e-4)
p.add_argument("--batch", type=int, default=1)
p.add_argument("--accum", type=int, default=2, help="gradient accumulation = effective batch")
p.add_argument("--width", type=int, default=832)
p.add_argument("--height", type=int, default=1216)
p.add_argument("--seed", type=int, default=42)
p.add_argument("--save_every", type=int, default=150,
               help="Itne steps pe LoRA save — beech me ruke to kaam na ude")
p.add_argument("--preview_every", type=int, default=300,
               help="Itne steps pe sample image bana ke Telegram pe bhejo (0 = off)")
p.add_argument("--snr_gamma", type=float, default=5.0, help="Min-SNR weighting (0 = off)")
p.add_argument("--noise_offset", type=float, default=0.03)
args = p.parse_args()

# ---- Telegram progress (optional) ----
def _secret(name):
    for d in (Path.cwd(), Path(__file__).resolve().parent,
              Path(__file__).resolve().parent.parent):
        f = d / ".env"
        if f.exists():
            for line in f.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
    v = os.getenv(name)
    if v:
        return v
    try:
        from kaggle_secrets import UserSecretsClient
        return UserSecretsClient().get_secret(name)
    except Exception:
        return ""


_BT, _CI = _secret("TELEGRAM_BOT_TOKEN"), _secret("TELEGRAM_CHAT_ID")


def tg(text, photo=None):
    if not (_BT and _CI):
        return
    try:
        import requests
        if photo and os.path.exists(photo):
            with open(photo, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{_BT}/sendPhoto",
                              data={"chat_id": _CI, "caption": text[:1024]},
                              files={"photo": f}, timeout=90)
        else:
            requests.post(f"https://api.telegram.org/bot{_BT}/sendMessage",
                          data={"chat_id": _CI, "text": text[:4000]}, timeout=20)
    except Exception:
        pass

torch.manual_seed(args.seed)
random.seed(args.seed)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16

print("=" * 72)
print("  DIYA RAI SDXL LoRA TRAINER")
print("=" * 72)
if DEVICE == "cpu":
    sys.exit("[FATAL] GPU nahi mila. Kaggle Settings -> Accelerator -> GPU T4 x2 karo.")
print(f"  GPU        : {torch.cuda.get_device_name(0)}")
print(f"  Resolution : {args.width}x{args.height}")
print(f"  Steps      : {args.steps} | rank {args.rank} | lr {args.lr}")
print("=" * 72)

# ------------------------------------------------------------------ #
# 2. Dataset discovery
# ------------------------------------------------------------------ #
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
root = Path(args.data)
if not root.exists():
    sys.exit(f"[FATAL] Data folder nahi mila: {root}")

pairs = []
for img in sorted(root.rglob("*")):
    if img.suffix.lower() not in IMG_EXT:
        continue
    txt = img.with_suffix(".txt")
    if txt.exists():
        caption = txt.read_text(encoding="utf-8").strip()
    else:
        caption = f"{args.trigger}, a young Indian woman, photorealistic portrait"
    # Trigger word hamesha aage ho — identity isi token pe bandhti hai
    if args.trigger.lower() not in caption.lower():
        caption = f"{args.trigger}, {caption}"
    pairs.append((img, caption))

if not pairs:
    sys.exit(f"[FATAL] {root} me koi image nahi mili.")
print(f"[data] {len(pairs)} image/caption pairs mile")
for i, (im, c) in enumerate(pairs[:3]):
    print(f"       {im.name}: {c[:70]}...")

# ------------------------------------------------------------------ #
# 3. VAE latents pre-compute (ek baar) -> phir VAE delete
# ------------------------------------------------------------------ #
print("\n[1/4] VAE latents cache kar raha hoon...")
t0 = time.time()

vae = AutoencoderKL.from_pretrained(
    "madebyollin/sdxl-vae-fp16-fix", torch_dtype=DTYPE
).to(DEVICE).eval()

to_tensor = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5]),
])


def load_and_crop(path):
    """Resize short side, center crop -> SDXL crop-coords bhi return karo."""
    im = Image.open(path).convert("RGB")
    ow, oh = im.size
    scale = max(args.width / ow, args.height / oh)
    nw, nh = math.ceil(ow * scale), math.ceil(oh * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    top = max(0, (nh - args.height) // 2)
    left = max(0, (nw - args.width) // 2)
    im = im.crop((left, top, left + args.width, top + args.height))
    return im, (oh, ow), (top, left)


cache = []
with torch.no_grad():
    for img_path, caption in pairs:
        im, orig_hw, crop_tl = load_and_crop(img_path)
        px = to_tensor(im).unsqueeze(0).to(DEVICE, dtype=DTYPE)
        lat = vae.encode(px).latent_dist.sample() * vae.config.scaling_factor
        cache.append({
            "latent": lat.squeeze(0).cpu(),
            "caption": caption,
            "orig_hw": orig_hw,
            "crop_tl": crop_tl,
        })

del vae
torch.cuda.empty_cache()
print(f"      done in {time.time() - t0:.1f}s — VAE unloaded")

# ------------------------------------------------------------------ #
# 4. Text embeddings pre-compute -> phir dono text encoders delete
# ------------------------------------------------------------------ #
print("\n[2/4] Text embeddings cache kar raha hoon...")
t0 = time.time()

tok1 = CLIPTokenizer.from_pretrained(args.base, subfolder="tokenizer")
tok2 = CLIPTokenizer.from_pretrained(args.base, subfolder="tokenizer_2")
te1 = CLIPTextModel.from_pretrained(
    args.base, subfolder="text_encoder", torch_dtype=DTYPE).to(DEVICE).eval()
te2 = CLIPTextModelWithProjection.from_pretrained(
    args.base, subfolder="text_encoder_2", torch_dtype=DTYPE).to(DEVICE).eval()


@torch.no_grad()
def encode_prompt(text):
    ids1 = tok1(text, padding="max_length", max_length=tok1.model_max_length,
                truncation=True, return_tensors="pt").input_ids.to(DEVICE)
    ids2 = tok2(text, padding="max_length", max_length=tok2.model_max_length,
                truncation=True, return_tensors="pt").input_ids.to(DEVICE)
    o1 = te1(ids1, output_hidden_states=True)
    o2 = te2(ids2, output_hidden_states=True)
    prompt_embeds = torch.cat([o1.hidden_states[-2], o2.hidden_states[-2]], dim=-1)
    pooled = o2[0]
    return prompt_embeds.squeeze(0).cpu(), pooled.squeeze(0).cpu()


for item in cache:
    pe, pl = encode_prompt(item["caption"])
    item["prompt_embeds"] = pe
    item["pooled"] = pl

# Validation prompt bhi abhi encode kar lo — baad me text encoders delete ho jaayenge
VAL_PROMPT = (f"{args.trigger}, a 23yo Indian woman, candid photo in a sunlit cafe, "
              f"beige top, natural skin texture, sharp eyes, 85mm photograph")
VAL_NEG = "blurry, plastic skin, 3d render, cartoon, deformed face, watermark, lowres"
VAL = {}
VAL["pe"], VAL["pl"] = encode_prompt(VAL_PROMPT)
VAL["npe"], VAL["npl"] = encode_prompt(VAL_NEG)

del te1, te2, tok1, tok2
torch.cuda.empty_cache()
print(f"      done in {time.time() - t0:.1f}s — text encoders unloaded "
      f"({torch.cuda.memory_allocated() / 1e9:.2f} GB in use)")


class CachedSet(Dataset):
    def __len__(self):
        return len(cache)

    def __getitem__(self, i):
        return cache[i]


def collate(batch):
    return {
        "latents": torch.stack([b["latent"] for b in batch]),
        "prompt_embeds": torch.stack([b["prompt_embeds"] for b in batch]),
        "pooled": torch.stack([b["pooled"] for b in batch]),
        "orig_hw": [b["orig_hw"] for b in batch],
        "crop_tl": [b["crop_tl"] for b in batch],
    }


loader = DataLoader(CachedSet(), batch_size=args.batch, shuffle=True,
                    collate_fn=collate, num_workers=0, drop_last=True)

# ------------------------------------------------------------------ #
# 5. UNet + LoRA
# ------------------------------------------------------------------ #
print("\n[3/4] UNet load + LoRA attach...")
unet = UNet2DConditionModel.from_pretrained(
    args.base, subfolder="unet", torch_dtype=DTYPE).to(DEVICE)
unet.requires_grad_(False)
unet.enable_gradient_checkpointing()
try:
    unet.enable_xformers_memory_efficient_attention()
    print("      xformers attention ON")
except Exception:
    pass

lora_cfg = LoraConfig(
    r=args.rank,
    lora_alpha=args.alpha,
    init_lora_weights="gaussian",
    target_modules=["to_k", "to_q", "to_v", "to_out.0"],
)
unet.add_adapter(lora_cfg)

# LoRA params fp32 me rakho warna fp16 me gradients underflow karte hain
lora_params = []
for n, prm in unet.named_parameters():
    if "lora" in n:
        prm.data = prm.data.float()
        prm.requires_grad_(True)
        lora_params.append(prm)
print(f"      trainable LoRA params: {sum(p.numel() for p in lora_params):,}")

try:
    import bitsandbytes as bnb
    optim = bnb.optim.AdamW8bit(lora_params, lr=args.lr, weight_decay=1e-2)
    print("      optimizer: AdamW8bit")
except Exception:
    optim = torch.optim.AdamW(lora_params, lr=args.lr, weight_decay=1e-2)
    print("      optimizer: AdamW (fp32)")

sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=args.steps, eta_min=args.lr * 0.05)
noise_sched = DDPMScheduler.from_pretrained(args.base, subfolder="scheduler")
scaler = torch.cuda.amp.GradScaler()

alphas_cumprod = noise_sched.alphas_cumprod.to(DEVICE)


def snr_weights(timesteps):
    a = alphas_cumprod[timesteps]
    snr = a / (1 - a)
    return (torch.stack([snr, args.snr_gamma * torch.ones_like(snr)], dim=1).min(dim=1)[0] / snr)


# ------------------------------------------------------------------ #
# 5b. Live preview — training ke beech me likeness check karne ke liye
# ------------------------------------------------------------------ #
from diffusers import DPMSolverMultistepScheduler  # noqa: E402


@torch.no_grad()
def make_preview(step_no, n_steps=25, cfg=5.0):
    """Mini sampler: cached embeds + temporary VAE. Telegram pe bhej deta hai."""
    unet.eval()
    try:
        sch = DPMSolverMultistepScheduler.from_pretrained(
            args.base, subfolder="scheduler", use_karras_sigmas=True,
            algorithm_type="dpmsolver++")
        sch.set_timesteps(n_steps, device=DEVICE)

        lat = torch.randn(1, 4, args.height // 8, args.width // 8,
                          device=DEVICE, dtype=DTYPE,
                          generator=torch.Generator(DEVICE).manual_seed(args.seed))
        lat = lat * sch.init_noise_sigma

        pe = torch.cat([VAL["npe"][None], VAL["pe"][None]]).to(DEVICE, DTYPE)
        pl = torch.cat([VAL["npl"][None], VAL["pl"][None]]).to(DEVICE, DTYPE)
        tid = torch.tensor([[args.height, args.width, 0, 0, args.height, args.width]] * 2,
                           device=DEVICE, dtype=DTYPE)

        for t in sch.timesteps:
            inp = sch.scale_model_input(torch.cat([lat] * 2), t)
            with torch.cuda.amp.autocast(dtype=DTYPE):
                out = unet(inp, t, encoder_hidden_states=pe,
                           added_cond_kwargs={"text_embeds": pl, "time_ids": tid}).sample
            u, c = out.chunk(2)
            lat = sch.step(u + cfg * (c - u), t, lat).prev_sample

        vae_p = AutoencoderKL.from_pretrained(
            "madebyollin/sdxl-vae-fp16-fix", torch_dtype=DTYPE).to(DEVICE).eval()
        img = vae_p.decode(lat / vae_p.config.scaling_factor).sample
        del vae_p
        torch.cuda.empty_cache()

        img = ((img.float() / 2 + 0.5).clamp(0, 1)[0].permute(1, 2, 0).cpu().numpy() * 255)
        path = f"/kaggle/working/preview_step{step_no}.jpg"
        Image.fromarray(img.astype("uint8")).save(path, quality=92)
        print(f"  >> preview: {path}")
        tg(f"Training preview — step {step_no}/{args.steps}\n"
           f"Chehra kitna match kar raha hai dekho.", path)
    except Exception as e:
        print(f"  !! preview fail: {e}")
    finally:
        unet.train()
        torch.cuda.empty_cache()


# ------------------------------------------------------------------ #
# 6. Training loop
# ------------------------------------------------------------------ #
print("\n[4/4] Training shuru...\n")
unet.train()
step = 0
t_start = time.time()
running = 0.0
data_iter = iter(loader)

while step < args.steps:
    optim.zero_grad(set_to_none=True)

    for _ in range(args.accum):
        try:
            batch = next(data_iter)
        except StopIteration:
            data_iter = iter(loader)
            batch = next(data_iter)

        latents = batch["latents"].to(DEVICE, dtype=DTYPE)
        bsz = latents.shape[0]

        noise = torch.randn_like(latents)
        if args.noise_offset > 0:
            noise += args.noise_offset * torch.randn(
                (bsz, latents.shape[1], 1, 1), device=DEVICE, dtype=DTYPE)

        t = torch.randint(0, noise_sched.config.num_train_timesteps, (bsz,), device=DEVICE).long()
        noisy = noise_sched.add_noise(latents, noise, t)

        add_time_ids = torch.tensor(
            [[*batch["orig_hw"][i], *batch["crop_tl"][i], args.height, args.width]
             for i in range(bsz)], device=DEVICE, dtype=DTYPE)

        with torch.cuda.amp.autocast(dtype=DTYPE):
            pred = unet(
                noisy, t,
                encoder_hidden_states=batch["prompt_embeds"].to(DEVICE, dtype=DTYPE),
                added_cond_kwargs={
                    "text_embeds": batch["pooled"].to(DEVICE, dtype=DTYPE),
                    "time_ids": add_time_ids,
                },
            ).sample

            if args.snr_gamma > 0:
                per = F.mse_loss(pred.float(), noise.float(), reduction="none").mean([1, 2, 3])
                loss = (per * snr_weights(t)).mean()
            else:
                loss = F.mse_loss(pred.float(), noise.float())
            loss = loss / args.accum

        scaler.scale(loss).backward()
        running += loss.item()

    scaler.unscale_(optim)
    torch.nn.utils.clip_grad_norm_(lora_params, 1.0)
    scaler.step(optim)
    scaler.update()
    sched.step()
    step += 1

    if step % 25 == 0:
        el = time.time() - t_start
        eta = el / step * (args.steps - step)
        print(f"  step {step:>5}/{args.steps} | loss {running / 25:.4f} "
              f"| lr {sched.get_last_lr()[0]:.2e} | {el / step:.2f}s/it "
              f"| ETA {eta / 60:.1f} min | VRAM {torch.cuda.max_memory_allocated() / 1e9:.1f}GB")
        if step % 250 == 0:
            tg(f"Training {step}/{args.steps} ({100 * step / args.steps:.0f}%) "
               f"| loss {running / 25:.4f} | ETA {eta / 60:.0f} min")
        running = 0.0

    if args.preview_every and step % args.preview_every == 0 and step < args.steps:
        make_preview(step)

    if step % args.save_every == 0 or step == args.steps:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        sd = convert_state_dict_to_diffusers(get_peft_model_state_dict(unet))
        StableDiffusionXLPipeline.save_lora_weights(
            save_directory=str(out.parent),
            unet_lora_layers=sd,
            weight_name=out.name,
            safe_serialization=True,
        )
        print(f"  >> saved {out}  (step {step})")

if args.preview_every:
    make_preview(args.steps)

print("\n" + "=" * 72)
print(f"  TRAINING COMPLETE in {(time.time() - t_start) / 60:.1f} min")
tg(f"LoRA TRAINING COMPLETE\n{args.steps} steps in {(time.time() - t_start) / 60:.0f} min\n\n"
   f"Ab {args.out} download karke Kaggle Dataset 'diyarai-sdxl-lora' banao,\n"
   f"phir diya_server.py chalao.")
print(f"  LoRA: {args.out}")
print(f"  Trigger word: '{args.trigger}'  (prompt me hamesha lagana)")
print("=" * 72)
print("""
AGLA STEP:
  1. /kaggle/working/diyarai_sdxl_lora.safetensors download karo
  2. Kaggle -> Datasets -> New Dataset -> naam: diyarai-sdxl-lora
  3. diya_live_worker.py wala kernel chalao — wo LoRA auto-detect kar lega
""")
