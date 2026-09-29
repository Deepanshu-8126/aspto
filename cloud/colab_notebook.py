"""
AIInfluencerOS — Google Colab Setup Script
Copy this entire cell into a Colab notebook and run it.
It sets up the full cloud pipeline with GPU access.
"""

# ════════════════════════════════════════════
# CELL 1: Install Dependencies
# ════════════════════════════════════════════
# !pip install -q gradio google-genai
# !pip install -q diffusers transformers accelerate safetensors
# !pip install -q soundfile librosa f5-tts
# !pip install -q opencv-python imageio imageio-ffmpeg
# !pip install -q einops omegaconf pyyaml httpx
# !pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# ════════════════════════════════════════════
# CELL 2: Clone AIInfluencerOS + Models
# ════════════════════════════════════════════
SETUP_SCRIPT = '''
import os
import subprocess

# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Create project directory
PROJECT_DIR = "/content/ai_influencer"
os.makedirs(PROJECT_DIR, exist_ok=True)

# Clone MuseTalk
if not os.path.exists(f"{PROJECT_DIR}/MuseTalk"):
    subprocess.run(["git", "clone", "https://github.com/TMElyralab/MuseTalk.git", f"{PROJECT_DIR}/MuseTalk"])
    subprocess.run(["pip", "install", "-q", "-e", f"{PROJECT_DIR}/MuseTalk"])

# Setup Fooocus-API (10-second SDXL photorealistic generation)
FOOOCUS_DIR = "/content/Fooocus-API"
if not os.path.exists(FOOOCUS_DIR):
    subprocess.run(["git", "clone", "https://github.com/mrhan1993/Fooocus-API.git", FOOOCUS_DIR])
    subprocess.run(["pip", "install", "-q", "-r", f"{FOOOCUS_DIR}/requirements.txt"])
    # Start Fooocus API on port 8888 in background
    subprocess.Popen(["python", f"{FOOOCUS_DIR}/main.py", "--port", "8888", "--host", "127.0.0.1"])
    print("🚀 Fooocus-API launched on port 8888 in background")

# Create output directories
for d in ["output/images", "output/audio", "output/video", "output/video/clips", "models/lora", "models/voice"]:
    os.makedirs(f"{PROJECT_DIR}/{d}", exist_ok=True)

# Copy config from Drive (if exists)
drive_config = "/content/drive/MyDrive/ai_influencer/config"
if os.path.exists(drive_config):
    subprocess.run(["cp", "-r", drive_config, f"{PROJECT_DIR}/config"])
else:
    os.makedirs(f"{PROJECT_DIR}/config", exist_ok=True)

# Copy models from Drive (if exists)
drive_models = "/content/drive/MyDrive/ai_influencer/models"
if os.path.exists(drive_models):
    subprocess.run(["cp", "-r", drive_models, f"{PROJECT_DIR}/models"])

print("✅ Setup complete!")
print(f"Project dir: {PROJECT_DIR}")
'''

# ════════════════════════════════════════════
# CELL 3: Configuration
# ════════════════════════════════════════════
CONFIG_TEMPLATE = '''
import yaml
import json
import os

PROJECT_DIR = "/content/ai_influencer"

# ── EDIT THESE VALUES ──
config = {
    "gemini": {
        "api_key": "YOUR_GEMINI_API_KEY",  # Get from https://aistudio.google.com
        "model": "gemini-2.0-flash",
        "temperature": 0.8,
    },
    "paths": {
        "output_dir": f"{PROJECT_DIR}/output",
        "models_dir": f"{PROJECT_DIR}/models",
        "lora_path": f"{PROJECT_DIR}/models/lora/my_face.safetensors",
        "voice_ref": f"{PROJECT_DIR}/models/voice/reference.wav",
        "database": f"{PROJECT_DIR}/data/influencer.db",
    },
    "pipeline": {
        "image_engine": "fooocus",
        "fooocus_url": "http://127.0.0.1:8888",
        "fooocus_base_model": "juggernautXL_v8Rundiffusion.safetensors",
        "fooocus_styles": ["Fooocus V2", "Fooocus Masterpiece", "Fooocus Enhance"],
        "fooocus_aspect_ratio": "704*1408",
        "comfyui_url": "http://127.0.0.1:8188",
        "sd_model": "v1-5-pruned.safetensors",
        "lora_strength": 0.90,
        "wan_model": "Wan2.1-T2V-1.3B",
        "musetalk_model": "musetalk_v1.5",
        "f5tts_model": "F5-TTS",
        "video_clip_duration": 5,
        "num_clips": 6,
    },
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "codec": "libx264",
        "format": "mp4",
    },
    "cloud": {
        "gradio_url": "",
        "timeout": 900,
        "retry_attempts": 3,
        "retry_delay": 30,
    },
}

os.makedirs(f"{PROJECT_DIR}/config", exist_ok=True)
with open(f"{PROJECT_DIR}/config/config.yaml", "w") as f:
    yaml.dump(config, f, default_flow_style=False)

print("✅ Config saved!")
'''

# ════════════════════════════════════════════
# CELL 4: Upload Your Models
# ════════════════════════════════════════════
UPLOAD_MODELS = '''
from google.colab import files
import shutil
import os

PROJECT_DIR = "/content/ai_influencer"

print("📤 Upload your LoRA model (.safetensors):")
uploaded = files.upload()
for name, data in uploaded.items():
    path = f"{PROJECT_DIR}/models/lora/{name}"
    with open(path, "wb") as f:
        f.write(data)
    print(f"  ✅ Saved: {path}")

print()
print("📤 Upload your voice reference (.wav, 5 seconds):")
uploaded = files.upload()
for name, data in uploaded.items():
    path = f"{PROJECT_DIR}/models/voice/reference.wav"
    with open(path, "wb") as f:
        f.write(data)
    print(f"  ✅ Saved: {path}")

print()
print("✅ Models ready!")
'''

# ════════════════════════════════════════════
# CELL 5: Start Pipeline Server
# ════════════════════════════════════════════
START_SERVER = '''
import sys
sys.path.insert(0, "/content/ai_influencer")

from cloud.gradio_app import build_gradio_app

app = build_gradio_app()
app.launch(
    server_name="0.0.0.0",
    server_port=7860,
    share=True,  # Creates public ngrok-like URL
    show_error=True,
)
'''


def print_colab_notebook():
    """Print the full Colab notebook setup instructions."""
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("""
+==============================================================+
|           AIInfluencerOS -- Google Colab Setup               |
+==============================================================+
|                                                              |
|  1. Open Google Colab (colab.research.google.com)            |
|  2. Select Runtime -> Change Runtime Type -> T4 GPU          |
|  3. Copy each CELL below into a separate Colab cell          |
|  4. Run cells in order (1 -> 5)                              |
|  5. Copy the public URL from Cell 5 output                   |
|  6. Paste it into config/config.yaml -> cloud.gradio_url     |
|                                                              |
+==============================================================+
    """)

    cells = [
        ("Install Dependencies", "!pip install -q gradio google-genai diffusers transformers accelerate safetensors soundfile librosa f5-tts opencv-python imageio imageio-ffmpeg einops omegaconf pyyaml httpx torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"),
        ("Setup Project", SETUP_SCRIPT),
        ("Configuration", CONFIG_TEMPLATE),
        ("Upload Models", UPLOAD_MODELS),
        ("Start Server", START_SERVER),
    ]

    for i, (title, code) in enumerate(cells, 1):
        print(f"\n{'-' * 60}")
        print(f"CELL {i}: {title}")
        print(f"{'-' * 60}")
        print(code)


if __name__ == "__main__":
    print_colab_notebook()
