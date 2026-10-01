"""
AI-INFLUENCER-OS — Kaggle Live Cloud GPU Worker (FLUX 4-Step + Wan2.1 + SDXL)
Run on Kaggle Notebook with Accelerator = GPU T4 x 2 or P100.
Automatically launches Gradio tunnel and pings Telegram Bot with live link!
"""

import os
import sys
import time
import json
import subprocess

print("=" * 60)
print("🚀 Launching Diya Rai Cloud GPU Worker (FLUX + Wan2.1 + SDXL)...")
print("=" * 60)

# Check GPU
try:
    import torch
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_count = torch.cuda.device_count()
        print(f"✅ GPU Detected: {gpu_name} ({gpu_count} GPU(s) active)")
    else:
        gpu_name = "CPU (Warning: Enable GPU in Kaggle settings)"
        print("⚠️ Warning: No GPU detected! Turn on GPU in Kaggle Settings.")
except Exception as e:
    gpu_name = "Unknown"
    print("GPU check notice:", e)

# 1. Install & Verify Essential Packages
print("⏳ Verifying dependencies...")
reqs = ["diffusers", "transformers", "accelerate", "sentencepiece", "gradio", "requests", "insightface"]
subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + reqs)

# Telegram Bot Credentials for Instant Notification
BOT_TOKEN = "8564017881:AAHyoqwTe-bNc9LLghXqvNPSFhPNpMrzmw0"
ADMIN_CHAT_ID = "6486771356"


def send_telegram_alert(text: str):
    """Sends a Telegram notification to the owner."""
    try:
        import requests
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram notify failed: {e}")


# 2. FLUX.1 Ultra-Photorealistic Pipeline (4-Step Fast Distillation)
_flux_pipe = None

def get_flux_pipeline():
    global _flux_pipe
    if _flux_pipe is not None:
        return _flux_pipe
    import torch
    from diffusers import FluxPipeline
    print("⏳ Loading FLUX.1 Ultra-Photorealism Pipeline (4-Step Fast Distillation)...")
    try:
        # Load FLUX with CPU offload (perfect for Kaggle 13-16GB VRAM)
        _flux_pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=torch.bfloat16
        )
        _flux_pipe.enable_model_cpu_offload()
        print("✅ FLUX.1 Pipeline successfully active in GPU memory!")
    except Exception as e:
        print(f"Notice loading FLUX ({e}), will fallback to SDXL.")
        _flux_pipe = get_sdxl_pipeline()
    return _flux_pipe


def generate_flux_api(prompt: str, aspect_ratio: str = "Portrait (832x1216)"):
    """Generates ultra-photorealistic portrait using Black Forest Labs FLUX.1."""
    pipe = get_flux_pipeline()
    w, h = (832, 1216) if "Portrait" in aspect_ratio else (1024, 1024)
    flux_prompt = (
        f"A photorealistic editorial portrait of young 22yo Indian woman Diya Rai, hazel almond eyes, "
        f"natural skin texture visible, fine pores, authentic subsurface scattering, {prompt}, "
        f"shot on Canon EOS R5, 85mm f/1.2 lens, shallow depth of field, warm natural sunlight, 4K master quality"
    )
    print(f"🎨 Generating FLUX Portrait: {prompt[:60]}...")
    start_t = time.time()
    try:
        image = pipe(
            prompt=flux_prompt,
            width=w,
            height=h,
            num_inference_steps=4,
            max_sequence_length=256,
            guidance_scale=0.0
        ).images[0]
    except Exception as e:
        print(f"FLUX inference notice ({e}), trying standard guidance...")
        image = pipe(
            prompt=flux_prompt,
            width=w,
            height=h,
            num_inference_steps=4,
            guidance_scale=3.5
        ).images[0]

    out_path = f"/kaggle/working/diya_flux_{int(time.time())}.png"
    image.save(out_path)
    print(f"✅ FLUX Photorealistic Portrait generated in {time.time()-start_t:.1f}s!")
    return out_path


# 3. SDXL Pipeline (Fallback / LoRA Studio)
_sdxl_pipe = None

def get_sdxl_pipeline():
    global _sdxl_pipe
    if _sdxl_pipe is not None:
        return _sdxl_pipe
    import torch
    from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
    print("⏳ Loading SDXL Base Pipeline (FP16)...")
    _sdxl_pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True
    ).to("cuda")
    _sdxl_pipe.scheduler = DPMSolverMultistepScheduler.from_config(_sdxl_pipe.scheduler.config, use_karras_sigmas=True)
    return _sdxl_pipe


def generate_sdxl_api(prompt: str):
    pipe = get_sdxl_pipeline()
    full_prompt = f"hyperrealistic 8k portrait of young 22yo Indian model Diya Rai, hazel eyes, natural skin texture, {prompt}, 35mm photograph, soft lighting"
    neg = "blurry, smooth plastic skin, 3d render, cartoon, deformed, low quality, bad anatomy"
    image = pipe(prompt=full_prompt, negative_prompt=neg, num_inference_steps=25, guidance_scale=6.5, width=832, height=1216).images[0]
    out_path = f"/kaggle/working/diya_sdxl_{int(time.time())}.jpg"
    image.save(out_path, quality=96)
    return out_path


# 4. Wan2.1 Video Engine
def generate_video_api(prompt: str, duration: int = 5):
    """Generates AI video clip using Wan2.1 / video synthesis."""
    out_path = f"/kaggle/working/diya_video_{int(time.time())}.mp4"
    try:
        import torch
        from diffusers import WanPipeline
        from diffusers.utils import export_to_video
        print("⏳ Running Wan2.1 Video generation...")
        wan_pipe = WanPipeline.from_pretrained("Wan-AI/Wan2.1-T2V-1.3B-Diffusers", torch_dtype=torch.float16).to("cuda")
        output = wan_pipe(
            prompt=f"Indian girl Diya Rai, {prompt}, cinematic, 4k",
            negative_prompt="blurry, distorted, low quality",
            height=480, width=832, num_frames=min(81, duration * 16), guidance_scale=5.0
        ).frames[0]
        export_to_video(output, out_path, fps=16)
        return out_path
    except Exception as e:
        print(f"Wan model notice ({e}), using fast motion video synthesizer...")
        img_p = generate_flux_api(prompt)
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_p,
            "-vf", "scale=720:1280,zoompan=z='min(zoom+0.0015,1.1)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_path


# 5. Gradio Interface
import gradio as gr

with gr.Blocks(title="Diya Rai Cloud GPU Engine") as demo:
    gr.Markdown("# 👑 Diya Rai — Cloud GPU Generation Hub\n**FLUX.1 Photorealism + Wan2.1 Video + SDXL running on Kaggle GPU!**")

    with gr.Tab("🌟 FLUX.1 Ultra-Photorealism (4-Step)"):
        f_prompt = gr.Textbox(
            label="Portrait Prompt",
            value="standing on balcony of South Mumbai apartment at dusk, wearing emerald green silk kurta, soft city bokeh lights, candid expression"
        )
        f_ratio = gr.Radio(["Portrait (832x1216)", "Square (1024x1024)"], value="Portrait (832x1216)", label="Dimensions")
        f_btn = gr.Button("🚀 Generate FLUX Master Portrait", variant="primary")
        f_out = gr.Image(label="FLUX 4K Output (Pores & Canon EOS Bokeh)")
        f_btn.click(generate_flux_api, inputs=[f_prompt, f_ratio], outputs=f_out)

    with gr.Tab("🎬 AI Video Generation (Wan2.1)"):
        v_prompt = gr.Textbox(label="Video Prompt", value="walking gracefully on Mumbai sea link in evening sunset, windy hair, smiling at camera")
        v_dur = gr.Slider(3, 10, value=5, step=1, label="Duration (seconds)")
        v_btn = gr.Button("🚀 Generate AI Video Reel", variant="primary")
        v_out = gr.Video(label="Generated Reel")
        v_btn.click(generate_video_api, inputs=[v_prompt, v_dur], outputs=v_out)

    with gr.Tab("📸 SDXL Studio"):
        p_prompt = gr.Textbox(label="Photo Prompt", value="wearing royal blue silk saree with gold borders in palace courtyard, golden hour glow")
        p_btn = gr.Button("✨ Generate SDXL Portrait", variant="primary")
        p_out = gr.Image(label="Output SDXL Portrait")
        p_btn.click(generate_sdxl_api, inputs=[p_prompt], outputs=p_out)


print("=" * 60)
print("🌐 Launching Gradio Public Share URL...")
print("=" * 60)

# Launch and capture share URL
share_url = demo.launch(share=True, quiet=False, prevent_thread_lock=True)[1]
print(f"🎉 LIVE GRADIO URL: {share_url}")

# Send Telegram notification
send_telegram_alert(
    f"🚀 **Diya Rai Kaggle Cloud GPU Worker LIVE!**\n\n"
    f"🌐 **Gradio URL:** `{share_url}`\n"
    f"⚡ **GPU:** `{gpu_name}`\n"
    f"🌟 **Top Engine:** FLUX.1 Ultra-Photorealism (4-Step Fast)\n"
    f"🎬 **Video Engine:** Wan2.1 Cinematic Video\n\n"
    f"👉 Tumhare system se ab direct photorealistic FLUX & Wan video generate ho sakti hai!"
)

# Keep alive loop
try:
    while True:
        time.sleep(30)
except KeyboardInterrupt:
    print("Worker stopped.")
