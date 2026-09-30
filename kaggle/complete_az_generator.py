# ================================================================
# DIYA RAI — COMPLETE A-Z FACE-ACCURATE IMAGE GENERATOR
# Kaggle T4 GPU | Fresh Session | Run All Cells in Order
# ================================================================
# WHAT THIS DOES:
#   1. Installs all dependencies
#   2. Loads ALL 27 diya photos -> builds master face embedding
#   3. Generates 5 outfit images with IP-Adapter (body/outfit)
#   4. Face swaps REAL Diya face using InsightFace inswapper
#   5. Enhances + sharpens final output (2x upscale + clarity)
#   6. Shows results side by side
# ================================================================
# DATASET NEEDED: diya-assests (your kaggle dataset)
#   Path: /kaggle/input/datasets/ukboy7u787/diya-assests/
#   Contains: all 27 photos + diyarai_sdxl_lora.safetensors
# ================================================================

# ════════════════════════════════════════════════════
# CELL 1 — INSTALL (run first, ~3 mins)
# ════════════════════════════════════════════════════
import os, sys, subprocess

def pip(pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + pkgs, check=False)

pip(["insightface==0.7.3", "onnxruntime==1.19.2"])
pip(["diffusers==0.30.3", "transformers==4.44.2",
     "accelerate==0.33.0", "peft==0.12.0", "huggingface_hub==0.24.7"])
pip(["git+https://github.com/tencent-ailab/IP-Adapter.git"])
pip(["opencv-python-headless", "Pillow", "numpy==1.26.4"])

print("ALL INSTALLED")

# ════════════════════════════════════════════════════
# CELL 2 — SETUP + FACE EMBEDDING FROM ALL 27 PHOTOS
# ════════════════════════════════════════════════════
import os, sys, gc, glob, json, torch, cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance

# Compat patches
try:
    import torchvision.transforms.functional_tensor
except ImportError:
    import torchvision.transforms.functional as _F
    sys.modules["torchvision.transforms.functional_tensor"] = _F
import transformers.utils as _tu
if not hasattr(_tu, "FLAX_WEIGHTS_NAME"):
    _tu.FLAX_WEIGHTS_NAME = "flax_model.msgpack"
try:
    import peft.import_utils
    peft.import_utils.is_torchao_available = lambda: False
except: pass

# Paths
DIYA     = "/kaggle/input/datasets/ukboy7u787/diya-assests"
LORA     = DIYA + "/diyarai_sdxl_lora.safetensors"
IP_CKPT  = "/kaggle/working/ip_sd15.bin"
SWAP_MDL = "/root/.insightface/models/inswapper_128.onnx"
OUT      = Path("/kaggle/working/outputs"); OUT.mkdir(exist_ok=True)

# ── Build master face embedding from ALL photos ──
from insightface.app import FaceAnalysis

face_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
face_app.prepare(ctx_id=0, det_size=(640, 640))

all_imgs = [p for p in
    glob.glob(DIYA+"/*.png") + glob.glob(DIYA+"/*.jpg") + glob.glob(DIYA+"/*.jpeg")
    if ".safetensors" not in p and ".py" not in p and ".sh" not in p]

print(f"Scanning {len(all_imgs)} photos for face embeddings...")

embeddings = []
best_pil   = None   # Best PIL image for IP-Adapter
best_ref   = None   # Best BGR for face swap source
best_face  = None   # Best face object for swapper
best_score = 0.0

for p in sorted(all_imgs):
    try:
        bgr = cv2.imread(p)
        if bgr is None: continue
        h, w = bgr.shape[:2]
        if max(h,w) > 1500:
            s = 1500/max(h,w)
            bgr = cv2.resize(bgr, (int(w*s), int(h*s)))
        faces = face_app.get(bgr)
        if not faces: print(f"  SKIP (no face): {os.path.basename(p)}"); continue
        face = max(faces, key=lambda f: f.det_score)
        if face.det_score < 0.50: print(f"  SKIP (low conf {face.det_score:.2f}): {os.path.basename(p)}"); continue
        embeddings.append(torch.from_numpy(face.normed_embedding).float())
        print(f"  OK  score={face.det_score:.3f}  {os.path.basename(p)}")
        if face.det_score > best_score:
            best_score = face.det_score
            best_ref   = bgr.copy()
            best_face  = face
            best_pil   = Image.open(p).convert("RGB")
    except Exception as e:
        print(f"  ERR {os.path.basename(p)}: {e}")

master_emb = torch.nn.functional.normalize(
    torch.stack(embeddings).mean(0), dim=0).unsqueeze(0)
print(f"\nMASTER EMBEDDING: built from {len(embeddings)}/{len(all_imgs)} photos")
print(f"Best reference photo score: {best_score:.3f}")

# ════════════════════════════════════════════════════
# CELL 3 — LOAD SD1.5 PIPELINE
# ════════════════════════════════════════════════════
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler

print("Loading Realistic Vision V5.1...")
pipe = StableDiffusionPipeline.from_pretrained(
    "SG161222/Realistic_Vision_V5.1_noVAE",
    torch_dtype=torch.float16,
    safety_checker=None,
)
pipe.scheduler = DPMSolverMultistepScheduler(
    num_train_timesteps=1000, beta_start=0.00085, beta_end=0.012,
    beta_schedule="scaled_linear", use_karras_sigmas=True, algorithm_type="dpmsolver++",
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()
pipe.enable_vae_slicing()
print(f"Pipeline ready! VRAM free: {torch.cuda.mem_get_info()[0]/1024**3:.1f} GB")

# ════════════════════════════════════════════════════
# CELL 4 — LOAD IP-ADAPTER + GENERATE BASE IMAGES
# ════════════════════════════════════════════════════
from ip_adapter.ip_adapter_faceid import IPAdapterFaceIDPlus

if not os.path.exists(IP_CKPT):
    print("Downloading IP-Adapter FaceID Plus SD1.5...")
    os.system(f"wget -q --show-progress -O {IP_CKPT} "
              "https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sd15.bin")

ip = IPAdapterFaceIDPlus(
    pipe, "laion/CLIP-ViT-H-14-laion2B-s32B-b79K", IP_CKPT, "cuda")
print(f"IP-Adapter ready! VRAM free: {torch.cuda.mem_get_info()[0]/1024**3:.1f} GB")

# ── Prompts ──
NEG = ("different person, wrong face, bad anatomy, deformed, blurry, "
       "low quality, watermark, text, ugly, mutation, extra fingers, "
       "cartoon, anime, illustration, plastic skin, ai art, filter")

OUTFITS = [
    ("saree",   "RAW photo of beautiful 22yo Indian woman long straight black hair, elegant maroon silk saree with golden zari border, silver jhumka earrings, soft natural makeup, slight smile, looking at camera, golden hour light, soft bokeh background, DSLR 85mm portrait, film grain, photorealistic", 42),
    ("casual",  "RAW photo of beautiful 22yo Indian woman long wavy black hair, white fitted crop top and high-waist blue denim jeans, layered gold necklace, gold hoops, confident smile, urban terrace background, natural daylight, Sony A7III 35mm, film grain, photorealistic", 1234),
    ("lehenga", "RAW photo of stunning 22yo Indian woman long flowing black hair, royal blue lehenga choli with silver embroidery, heavy kundan necklace, subtle kohl eyes, graceful standing pose, warm palace interior background, Canon 5D 50mm, photorealistic", 7777),
    ("beach",   "RAW photo of beautiful 22yo Indian woman long dark hair blowing in sea breeze, white flowy summer dress, minimal gold jewelry, standing on beach during golden hour sunset, warm skin tone, relaxed soft smile, Fujifilm X-T4 35mm, film grain, photorealistic", 999),
    ("gym",     "RAW photo of fit 22yo Indian woman dark hair in high ponytail, black sports bra and high-waist gym leggings, toned athletic body, confident standing pose, modern gym mirror background, natural rim lighting, sports photography style, sharp details, photorealistic", 2024),
]

print("\nGenerating base images with IP-Adapter...")
base_imgs = {}

for name, prompt, seed in OUTFITS:
    print(f"  Generating: {name}...")
    imgs = ip.generate(
        prompt=prompt,
        negative_prompt=NEG,
        face_image=best_pil,
        faceid_embeds=master_emb,
        shortcut=True,
        s_scale=0.70,           # 0.70 = natural, not AI-overprocessed
        num_inference_steps=45,
        guidance_scale=5.5,
        num_samples=1,
        seed=seed,
        width=512,
        height=768,
    )
    base_imgs[name] = imgs[0]
    imgs[0].save(str(OUT / f"base_{name}.png"), quality=95)
    print(f"  SAVED: base_{name}.png")
    gc.collect(); torch.cuda.empty_cache()

print(f"\n{len(base_imgs)} base images ready!")

# ════════════════════════════════════════════════════
# CELL 5 — FACE SWAP (Real Diya face on every image)
# ════════════════════════════════════════════════════
from insightface.model_zoo import get_model

# Download inswapper if needed
if not os.path.exists(SWAP_MDL):
    os.makedirs(os.path.dirname(SWAP_MDL), exist_ok=True)
    print("Downloading inswapper_128.onnx...")
    os.system(f"wget -q --show-progress -O {SWAP_MDL} "
              "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/inswapper_128.onnx")

swapper = get_model(SWAP_MDL, download=False,
                    providers=["CUDAExecutionProvider","CPUExecutionProvider"])
print("Face swapper loaded!")

swapped_imgs = {}

for name, base_pil in base_imgs.items():
    print(f"\nFace swapping: {name}...")

    target_bgr = cv2.cvtColor(np.array(base_pil), cv2.COLOR_RGB2BGR)
    target_faces = face_app.get(target_bgr)

    if not target_faces:
        print(f"  WARNING: No face in base_{name}.png — saving as-is")
        swapped_imgs[name] = base_pil
        continue

    target_face = max(target_faces, key=lambda f: f.det_score)
    print(f"  Target face det_score={target_face.det_score:.3f}")

    # SWAP: paste Diya's real face onto generated body
    result_bgr = swapper.get(
        target_bgr,
        target_face,
        best_face,      # Diya's real face from best reference photo
        paste_back=True
    )

    result_pil = Image.fromarray(cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB))
    swapped_imgs[name] = result_pil
    result_pil.save(str(OUT / f"swapped_{name}.png"), quality=95)
    print(f"  SAVED: swapped_{name}.png — Real face inserted!")

# ════════════════════════════════════════════════════
# CELL 6 — ENHANCE + SHARPEN (Final output)
# ════════════════════════════════════════════════════
def enhance(img: Image.Image) -> Image.Image:
    # Step 1: Upscale 2x with Lanczos
    w, h = img.size
    img = img.resize((w*2, h*2), Image.LANCZOS)

    # Step 2: Unsharp mask (sharpen edges)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=3))

    # Step 3: Mild contrast boost
    img = ImageEnhance.Contrast(img).enhance(1.08)

    # Step 4: Mild sharpness boost
    img = ImageEnhance.Sharpness(img).enhance(1.3)

    # Step 5: Clarity pass (local contrast)
    arr = np.array(img).astype(np.float32)
    blur = cv2.GaussianBlur(arr, (0,0), 2.5)
    sharp = cv2.addWeighted(arr, 1.35, blur, -0.35, 0)
    sharp = np.clip(sharp, 0, 255).astype(np.uint8)

    return Image.fromarray(sharp)

print("Enhancing + sharpening final images...")
final_imgs = {}

for name, img in swapped_imgs.items():
    enhanced = enhance(img)
    out_path = OUT / f"FINAL_{name}.png"
    enhanced.save(str(out_path), quality=98)
    final_imgs[name] = enhanced
    print(f"  FINAL_{name}.png  {enhanced.size[0]}x{enhanced.size[1]}")

print("\nALL FINAL IMAGES READY!")

# ════════════════════════════════════════════════════
# CELL 7 — SHOW RESULTS
# ════════════════════════════════════════════════════
from IPython.display import display

print("=== FINAL RESULTS ===\n")
print("Reference face used:")
display(best_pil.resize((200, 300)))

for name in ["saree", "casual", "lehenga", "beach", "gym"]:
    base  = OUT / f"base_{name}.png"
    final = OUT / f"FINAL_{name}.png"
    if not final.exists(): continue

    # Side by side: reference | base | final
    ref_thumb = best_pil.resize((200, 300))
    base_img  = Image.open(base).resize((200, 300))
    fin_img   = Image.open(final).resize((200, 300))

    compare = Image.new("RGB", (620, 330), (15, 15, 15))
    compare.paste(ref_thumb, (5, 25))
    compare.paste(base_img,  (210, 25))
    compare.paste(fin_img,   (415, 25))

    from PIL import ImageDraw
    draw = ImageDraw.Draw(compare)
    draw.text((50, 5),  "REFERENCE",  fill=(200,200,200))
    draw.text((245, 5), "AI BASE",    fill=(180,120,120))
    draw.text((440, 5), "FINAL",      fill=(120,220,120))

    print(f"\n{'='*30} {name.upper()} {'='*30}")
    display(compare)

print("\nDownload FINAL_*.png from /kaggle/working/outputs/")