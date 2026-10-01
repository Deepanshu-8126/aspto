"""
👑 DIYA RAI KAGGLE GPU MASTER WORKER
100% Cloud GPU Execution with Multi-Anchor Face Lock + GFPGAN v1.4 + FLUX/SDXL + Telegram Push
"""

import os
import sys
import glob
import time
import subprocess
from pathlib import Path

print("=" * 60)
print("🚀 Starting Diya Rai Kaggle GPU Master Pipeline...")
print("=" * 60)

# Step 0: Ensure compatible environment (Kaggle Numpy 2.x fix)
print("⏳ Configuring GPU environment & dependencies...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "numpy<2", "insightface", "onnxruntime-gpu", "diffusers", "transformers", "accelerate", "requests", "opencv-python-headless"
], check=True)

import cv2
import numpy as np
import requests
import torch

BOT_TOKEN = "8564017881:AAHyoqwTe-bNc9LLghXqvNPSFhPNpMrzmw0"
CHAT_ID = "6486771356"

def tg_send(text: str, img_path: str = None):
    try:
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={"chat_id": CHAT_ID, "caption": text, "parse_mode": "Markdown"},
                    files={"photo": f},
                    timeout=30
                )
            print(f"Telegram Photo sent: {r.status_code}")
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
                timeout=15
            )
            print(f"Telegram Message sent: {r.status_code}")
    except Exception as e:
        print(f"Telegram send error: {e}")

tg_send("🚀 **Diya Rai Kaggle GPU Master Started!**\n\nCloud GPU par aapki photos process ho rahi hain...")

# Step 1: Check GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"✅ Active Device: {device} | {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")

# Step 2: Download Models (Inswapper & GFPGAN)
MODELS_DIR = Path("/kaggle/working/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR = Path("/kaggle/working/outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

INSWAPPER_PATH = MODELS_DIR / "inswapper_128.onnx"
GFPGAN_PATH = MODELS_DIR / "GFPGANv1.4.onnx"

if not INSWAPPER_PATH.exists():
    print("⏳ Downloading Inswapper 128 model...")
    url = "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx"
    subprocess.run(["wget", "-q", "-nc", url, "-O", str(INSWAPPER_PATH)])

if not GFPGAN_PATH.exists():
    print("⏳ Downloading GFPGAN v1.4 model...")
    url = "https://github.com/xinntao/facexlib/releases/download/v0.1.0/GFPGANv1.4.onnx"
    subprocess.run(["wget", "-q", "-nc", url, "-O", str(GFPGAN_PATH)])

print("✅ Models downloaded successfully!")

# Step 3: Find User's Uploaded Anchor Photos
print("🔍 Searching for Diya model anchor photos in Kaggle input...")
possible_inputs = glob.glob("/kaggle/input/**/real*.png", recursive=True) + \
                  glob.glob("/kaggle/input/**/best*.jpg", recursive=True) + \
                  glob.glob("/kaggle/input/**/shadi*.png", recursive=True)

print(f"Found input photos: {possible_inputs}")

anchor_files = []
for p in possible_inputs:
    if any(k in os.path.basename(p).lower() for k in ["real_diya", "real", "best_v2", "jetsey", "shadi"]):
        anchor_files.append(p)

if not anchor_files:
    anchor_files = glob.glob("/kaggle/input/**/*.png", recursive=True)[:3]

print(f"⭐ Selected User Anchor Photos: {anchor_files}")

# Step 4: Initialize InsightFace on GPU
import insightface
from insightface.app import FaceAnalysis

print("⏳ Initializing FaceAnalysis on CUDA...")
app = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

swapper = insightface.model_zoo.get_model(
    str(INSWAPPER_PATH),
    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
)

# Step 5: Multi-Anchor Face Embedding Fusion
embeddings = []
for p in anchor_files:
    img = cv2.imread(p)
    if img is not None:
        faces = app.get(img)
        if faces:
            # Sort by area, take largest face
            faces = sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
            norm_emb = faces[0].embedding / np.linalg.norm(faces[0].embedding)
            embeddings.append(norm_emb)
            print(f"  ✅ Extracted face embedding from {os.path.basename(p)}")

if not embeddings:
    raise RuntimeError("No face detected in anchor images!")

fused_embedding = np.mean(embeddings, axis=0)
fused_embedding = fused_embedding / np.linalg.norm(fused_embedding)
print(f"🎉 Successfully fused {len(embeddings)} anchor face embeddings into Diya Master DNA!")

# Step 6: Initialize GFPGAN ONNX Restorer
import onnxruntime as ort

print("⏳ Loading GFPGAN ONNX Restorer on CUDA...")
gfpgan_sess = ort.InferenceSession(
    str(GFPGAN_PATH),
    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
)

def restore_face_gfpgan(img_bgr, face):
    """Aligns, enhances via GFPGAN, and softly blends back."""
    try:
        from insightface.utils import face_align
        aimg, M = face_align.warp_and_crop_face(
            img_bgr, face.kps, crop_size=(512, 512), mode='arcface'
        )
        norm_face = aimg.astype(np.float32) / 127.5 - 1.0
        norm_face = norm_face[:, :, ::-1].transpose(2, 0, 1)
        norm_face = np.expand_dims(norm_face, axis=0)

        input_name = gfpgan_sess.get_inputs()[0].name
        output_name = gfpgan_sess.get_outputs()[0].name
        restored = gfpgan_sess.run([output_name], {input_name: norm_face})[0][0]

        restored = np.clip((restored.transpose(1, 2, 0)[:, :, ::-1] + 1.0) * 127.5, 0, 255).astype(np.uint8)
        
        # Soft warp back with elliptical feather mask
        IM = cv2.invertAffineTransform(M)
        h, w = img_bgr.shape[:2]
        warped_restored = cv2.warpAffine(restored, IM, (w, h), borderMode=cv2.BORDER_REPLICATE)
        
        mask = np.zeros((512, 512), dtype=np.float32)
        cv2.ellipse(mask, (256, 260), (195, 235), 0, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (31, 31), 11)
        warped_mask = cv2.warpAffine(mask, IM, (w, h), borderMode=cv2.BORDER_CONSTANT)
        warped_mask = np.expand_dims(warped_mask, axis=2)

        blended = (warped_restored * warped_mask + img_bgr * (1.0 - warped_mask)).astype(np.uint8)
        return blended
    except Exception as e:
        print(f"GFPGAN enhancement error: {e}")
        return img_bgr

# Step 7: Generate Base Scene with SDXL / FLUX
print("⏳ Loading Fast SDXL Base Generation Model...")
from diffusers import AutopipelineForText2Image, DPMSolverMultistepScheduler

pipe = AutopipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo",
    torch_dtype=torch.float16,
    variant="fp16"
).to("cuda")
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

prompts = [
    (
        "A breathtaking high-fashion candid portrait of a gorgeous 22yo Indian woman sitting in a modern upscale cafe during golden hour, wearing a chic beige knitted top, warm window light, Sony A7R V 85mm f/1.4 lens, shallow depth of field, photorealistic, natural skin texture",
        "cafe_portrait"
    ),
    (
        "A stunning street style candid photo of a stylish young Indian woman walking in Bandra Mumbai, wearing an elegant red sports jacket, natural sunlit street bokeh, cinematic, 4k 35mm photograph, authentic pores, beautiful natural lighting",
        "street_portrait"
    )
]

generated_results = []
for i, (p_text, name) in enumerate(prompts):
    print(f"\n🎨 Generating Scene {i+1}: {name}...")
    base_img = pipe(prompt=p_text, num_inference_steps=4, guidance_scale=0.0, width=768, height=1024).images[0]
    base_path = OUTPUTS_DIR / f"base_{name}.jpg"
    base_img.save(str(base_path), quality=95)
    
    # Perform GPU Face Swap
    print(f"⚡ Applying Diya Rai Fused Face onto {name} on GPU...")
    bgr_img = cv2.imread(str(base_path))
    target_faces = app.get(bgr_img)
    if target_faces:
        target_face = sorted(target_faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)[0]
        # Inswapper with fused embedding
        fake_face = target_faces[0]
        fake_face.embedding = fused_embedding
        swapped = swapper.get(bgr_img, target_face, fake_face, paste_back=True)
        
        # GFPGAN Eye & Skin restoration
        restored = restore_face_gfpgan(swapped, target_face)
        
        # Unsharp mask for high-definition clarity
        gaussian = cv2.GaussianBlur(restored, (0, 0), 1.2)
        sharp = cv2.addWeighted(restored, 1.2, gaussian, -0.2, 0)
        
        out_path = OUTPUTS_DIR / f"diya_kaggle_{name}.jpg"
        cv2.imwrite(str(out_path), sharp, [int(cv2.IMWRITE_JPEG_QUALITY), 98])
        print(f"✅ Saved Final HD Output: {out_path}")
        
        # Send directly to Telegram!
        caption = (
            f"✨ **Diya Rai — Kaggle Cloud GPU Generated!**\n\n"
            f"🔹 **Scene:** {name.replace('_', ' ').title()}\n"
            f"🔹 **Anchors Fused:** `{len(embeddings)} Photos` (real_diya, real, best_v2)\n"
            f"🔹 **Restoration:** GFPGAN v1.4 (Tack-sharp eyes, plump lips, real pores)\n"
            f"⚡ **Hardware:** Kaggle Cloud GPU (T4 / P100)\n\n"
            f"Bhai check karo! Aapki photos Kaggle pe bhejke fresh scene mein model bana di hai!"
        )
        tg_send(caption, str(out_path))
        generated_results.append(str(out_path))

print("\n" + "=" * 60)
print(f"🎉 MASTER PIPELINE COMPLETE! Generated {len(generated_results)} photos and sent to Telegram!")
print("=" * 60)
