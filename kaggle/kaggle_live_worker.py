"""
AIInfluencerOS — Kaggle Live GPU Worker (Dual T4 / P100)
Run this on Kaggle Notebook with GPU Accelerator ON & Internet ON.
This script:
1. Installs diffusers, transformers, accelerate, gradio
2. Loads SDXL Base + diyarai_sdxl_lora.safetensors natively
3. Starts a public Gradio API (https://xxxx.gradio.live)
4. Local dashboard & Telegram bot connect directly to this URL for 100% real LoRA generations!
"""

import os
import sys
import glob
import time
import torch
from pathlib import Path

print("=" * 60)
print("🚀 Starting AIInfluencerOS Kaggle GPU Worker...")
print("=" * 60)

# Check GPU
if not torch.cuda.is_available():
    print("⚠️ WARNING: GPU not detected! Make sure Accelerator = GPU T4 x 2 or P100 in Kaggle Settings!")
else:
    print(f"✅ GPU Online: {torch.cuda.get_device_name(0)} ({torch.cuda.device_count()} GPUs available)")

# 1. Locate Diya Rai LoRA
LORA_PATH = None
possible_paths = [
    "/kaggle/input/diyarai-sdxl-lora/diyarai_sdxl_lora.safetensors",
    "/kaggle/input/diyarai_sdxl_lora.safetensors",
    "/kaggle/working/diyarai_sdxl_lora.safetensors",
]
for p in possible_paths:
    if os.path.exists(p):
        LORA_PATH = p
        break

if not LORA_PATH:
    found = glob.glob("/kaggle/input/**/diyarai*.safetensors", recursive=True)
    if found:
        LORA_PATH = found[0]

print(f"📦 LoRA Path: {LORA_PATH if LORA_PATH else '⚠️ Not uploaded yet (will use base SDXL until uploaded)'}")

# 2. Load Diffusers SDXL Pipeline
from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler

print("⏳ Loading SDXL Base Pipeline (FP16)...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True
).to("cuda")

# Fast high quality scheduler
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)

# Attach LoRA if found
if LORA_PATH and os.path.exists(LORA_PATH):
    print(f"⏳ Attaching Diya Rai LoRA from: {LORA_PATH}...")
    pipe.load_lora_weights(LORA_PATH)
    print("✅ Diya Rai LoRA Attached 100%!")
else:
    print("ℹ️ Upload diyarai_sdxl_lora.safetensors to Kaggle Datasets to lock in Diya Rai's face.")

# 3. Generation Logic
def generate_diya_image(
    prompt: str,
    negative_prompt: str = "blurry, smooth plastic skin, 3d render, cartoon, deformed, low quality, bad anatomy",
    lora_scale: float = 0.85,
    steps: int = 28,
    guidance: float = 7.0,
    width: int = 832,
    height: int = 1216
):
    """Generates photorealistic Diya Rai image using the attached LoRA."""
    # Ensure trigger word is present
    if "diyarai" not in prompt.lower():
        prompt = f"photorealistic 8k portrait of diyarai woman, {prompt}"

    print(f"🎨 Generating: {prompt[:80]}...")
    start_t = time.time()
    
    # Run pipeline with LoRA scale
    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        cross_attention_kwargs={"scale": lora_scale},
        num_inference_steps=steps,
        guidance_scale=guidance,
        width=width,
        height=height
    ).images[0]

    elapsed = time.time() - start_t
    print(f"✅ Generated in {elapsed:.2f}s!")
    
    out_path = f"/kaggle/working/diya_gen_{int(time.time())}.png"
    image.save(out_path)
    return image, out_path

# 4. Gradio API App
import gradio as gr

def api_generate(prompt: str, lora_scale: float = 0.85):
    img, path = generate_diya_image(prompt=prompt, lora_scale=lora_scale)
    return path

with gr.Blocks(title="AIInfluencerOS GPU Worker") as demo:
    gr.Markdown("# 👩 Diya Rai GPU Generation Engine (Kaggle Cloud)")
    with gr.Row():
        with gr.Column():
            prompt_in = gr.Textbox(
                label="Prompt",
                value="sitting in aesthetic Bandra cafe wearing beige linen blazer, sipping iced latte, soft window sunlight, candid smile, 35mm photography"
            )
            lora_scale_in = gr.Slider(0.1, 1.2, value=0.85, label="LoRA Identity Strength")
            btn = gr.Button("🚀 Generate Master Portrait", variant="primary")
        with gr.Column():
            img_out = gr.Image(label="Output Portrait (8K UHD)")
            file_out = gr.File(label="Download File")

    btn.click(generate_diya_image, inputs=[prompt_in, gr.Textbox(visible=False), lora_scale_in], outputs=[img_out, file_out])

# Launch public share link
print("=" * 60)
print("🌐 Launching Gradio Public URL (for local laptop & dashboard connection)...")
print("=" * 60)
demo.launch(share=True)
