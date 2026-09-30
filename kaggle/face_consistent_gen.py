import os, sys, json, gc, glob, torch
import numpy as np
from pathlib import Path
from PIL import Image
import cv2

OUTPUT_DIR    = Path("/kaggle/working/outputs")
DIYA_FOLDER   = "/kaggle/input/datasets/ukboy7u787/diya-assests"
LORA_PATH     = DIYA_FOLDER + "/diyarai_sdxl_lora.safetensors"
IP_CKPT_PATH  = "/kaggle/working/ip_faceid_sdxl.bin"
FACE_SIM_THRESHOLD = 0.32

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
except Exception:
    pass

print("[OK] Compat patches applied")

def install():
    os.system("pip install -q insightface==0.7.3 onnxruntime-gpu")
    os.system("pip install -q diffusers==0.27.2 transformers==4.40.2 accelerate==0.30.1 peft==0.11.1")
    os.system("pip install -q git+https://github.com/tencent-ailab/IP-Adapter.git")
    print("[OK] Dependencies installed")

install()

from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler, AutoencoderKL
from insightface.app import FaceAnalysis

def build_master_embedding(diya_folder):
    app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    exts = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
    all_imgs = []
    for ext in exts:
        all_imgs.extend(glob.glob(os.path.join(diya_folder, ext)))
    all_imgs = sorted(set(all_imgs))
    all_imgs = [p for p in all_imgs if ".safetensors" not in p and ".py" not in p]

    print(f"[FACE] Found {len(all_imgs)} images")

    embeddings = []
    best_pil = None
    best_score = 0.0

    for img_path in all_imgs:
        try:
            img_bgr = cv2.imread(img_path)
            if img_bgr is None:
                continue
            h, w = img_bgr.shape[:2]
            if max(h, w) > 1500:
                scale = 1500 / max(h, w)
                img_bgr = cv2.resize(img_bgr, (int(w*scale), int(h*scale)))
            faces = app.get(img_bgr)
            if not faces:
                print(f"  [SKIP] No face: {os.path.basename(img_path)}")
                continue
            face = sorted(faces, key=lambda f: f.det_score, reverse=True)[0]
            if face.det_score < 0.5:
                print(f"  [SKIP] Low conf {face.det_score:.2f}: {os.path.basename(img_path)}")
                continue
            emb = torch.from_numpy(face.normed_embedding).float()
            embeddings.append(emb)
            print(f"  [OK]   score={face.det_score:.3f} -> {os.path.basename(img_path)}")
            if face.det_score > best_score:
                best_score = face.det_score
                best_pil = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"  [ERR] {os.path.basename(img_path)}: {e}")

    if not embeddings:
        raise ValueError("No valid face embeddings found!")

    master_emb = torch.stack(embeddings).mean(dim=0)
    master_emb = torch.nn.functional.normalize(master_emb, dim=0).unsqueeze(0)
    print(f"[FACE] Master embedding from {len(embeddings)}/{len(all_imgs)} images")
    return master_emb, best_pil, app

def load_pipe():
    print("[LOADING] RealVisXL V4.0...")
    vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "SG161222/RealVisXL_V4.0", vae=vae,
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True,
    )
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="sde-dpmsolver++",
    )
    if os.path.exists(LORA_PATH):
        try:
            pipe.load_lora_weights(LORA_PATH, adapter_name="diya")
            pipe.set_adapters(["diya"], adapter_weights=[0.7])
            print("[LORA] Loaded weight=0.7")
        except Exception as e:
            print(f"[LORA] Skipped: {e}")
    pipe = pipe.to("cuda")
    pipe.enable_xformers_memory_efficient_attention()
    pipe.enable_vae_slicing()
    print("[OK] Pipeline ready")
    return pipe

def load_ipadapter(pipe):
    from ip_adapter.ip_adapter_faceid import IPAdapterFaceIDPlusXL
    if not os.path.exists(IP_CKPT_PATH):
        url = "https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl.bin"
        print("[DOWNLOAD] IP-Adapter FaceID Plus (~700MB)...")
        os.system(f"wget -q --show-progress -O {IP_CKPT_PATH} {url}")
    ip = IPAdapterFaceIDPlusXL(
        sd_pipe=pipe,
        image_encoder_path="laion/CLIP-ViT-H-14-laion2B-s32B-b79K",
        ip_ckpt=IP_CKPT_PATH,
        device="cuda",
        num_tokens=16,
    )
    print("[OK] IP-Adapter ready")
    return ip

NEG = (
    "deformed face, bad anatomy, bad eyes, extra fingers, mutation, blurry, "
    "low quality, watermark, text, ugly, distorted, different person, clone face, "
    "plastic skin, bad proportions, wrong identity, multiple faces"
)

PROMPTS = [
    ("traditional_saree",
     "beautiful 22yo Indian woman long black hair, maroon silk saree golden zari border, "
     "silver jhumka earrings, warm glowing skin, soft smile looking at camera, "
     "golden hour bokeh, cinematic portrait, 8k RAW photo, photorealistic", 42),
    ("modern_casual",
     "beautiful 22yo Indian woman long wavy black hair, beige crop top high-waist denim, "
     "minimal gold jewelry, confident smile, urban rooftop, natural daylight, "
     "lifestyle photography, 8k RAW photo, photorealistic", 1234),
    ("royal_lehenga",
     "stunning 22yo Indian woman long black hair, royal blue lehenga choli embroidery, "
     "heavy silver kundan jewelry, kohl eyes, graceful pose, palace interior, "
     "fashion photography, 8k RAW photo, photorealistic", 7777),
    ("beach_golden",
     "beautiful 22yo Indian woman hair blowing in breeze, flowy white summer dress, "
     "beach at golden sunset, relaxed soft smile, warm tones, "
     "lifestyle photography, 8k RAW photo, photorealistic", 999),
    ("gym_fit",
     "fit 22yo Indian woman hair in ponytail, black sports bra high-waist leggings, "
     "toned body confident pose, modern gym, sports photography, "
     "8k RAW photo, photorealistic ultra sharp", 2024),
]

def generate_one(ip, emb, face_pil, name, prompt, seed, scale=0.85):
    gen = torch.Generator("cuda").manual_seed(seed)
    print(f"[GEN] {name} seed={seed} scale={scale}")
    imgs = ip.generate(
        prompt=prompt, negative_prompt=NEG,
        face_image=face_pil, faceid_embeds=emb,
        shortcut=True, s_scale=scale,
        num_inference_steps=35, guidance_scale=7.5,
        num_samples=1, width=832, height=1216, generator=gen,
    )
    return imgs[0]

def verify(face_app, master_emb, gen_img, threshold=FACE_SIM_THRESHOLD):
    arr = cv2.cvtColor(np.array(gen_img), cv2.COLOR_RGB2BGR)
    faces = face_app.get(arr)
    if not faces:
        print("  [VERIFY] No face in output!")
        return 0.0, False
    emb = torch.nn.functional.normalize(torch.from_numpy(faces[0].normed_embedding).float(), dim=0)
    sim = torch.nn.functional.cosine_similarity(emb.unsqueeze(0), master_emb.squeeze(0).unsqueeze(0)).item()
    ok = sim >= threshold
    print(f"  [VERIFY] face_sim={sim:.3f} {'PASS' if ok else 'RETRY'}")
    return sim, ok

def main():
    print("=== DIYA RAI FACE-LOCKED GENERATOR ===")
    master_emb, best_face_pil, face_app = build_master_embedding(DIYA_FOLDER)
    pipe = load_pipe()
    ip = load_ipadapter(pipe)
    results = []
    for name, prompt, seed in PROMPTS:
        try:
            img = generate_one(ip, master_emb, best_face_pil, name, prompt, seed, scale=0.85)
            sim, ok = verify(face_app, master_emb, img)
            if not ok:
                print("  [RETRY] scale=0.95...")
                img = generate_one(ip, master_emb, best_face_pil, name, prompt, seed+100, scale=0.95)
                sim, ok = verify(face_app, master_emb, img)
            out = OUTPUT_DIR / f"diya_{name}_s{seed}.png"
            img.save(str(out), quality=95)
            print(f"  [SAVED] {out.name} score={sim:.3f}")
            results.append({"name": name, "file": str(out), "face_score": round(sim,3), "pass": ok, "seed": seed})
        except Exception as e:
            import traceback
            print(f"[ERROR] {name}: {e}")
            traceback.print_exc()
        gc.collect()
        torch.cuda.empty_cache()

    print("\n=== RESULTS ===")
    for r in results:
        print(f"  {'OK' if r['pass'] else 'DRIFT'} | {r['name']} | score={r['face_score']}")
    (OUTPUT_DIR / "report.json").write_text(json.dumps(results, indent=2))
    print(f"[DONE] {len(results)} images in {OUTPUT_DIR}")
    return results

main()