#!/bin/bash
set -e

echo "============================================================"
echo "⚡ Setting up StableAnimator (CVPR 2025) + Real-ESRGAN 4K"
echo "============================================================"

# 1. System packages
apt-get update -qq && apt-get install -y -qq ffmpeg git libgl1 libglib2.0-0

# 2. Python dependencies
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -q diffusers transformers accelerate safetensors yt-dlp opencv-python Pillow edge-tts

# 3. Clone Francis-Rings/StableAnimator
if [ ! -d "StableAnimator" ]; then
    echo "Cloning StableAnimator..."
    git clone https://github.com/Francis-Rings/StableAnimator.git
    cd StableAnimator
    pip install -q -r requirement.txt || true
    cd ..
fi

# 4. Clone pratik227/upscale_video_4k
if [ ! -d "upscale_video_4k" ]; then
    echo "Cloning upscale_video_4k..."
    git clone https://github.com/pratik227/upscale_video_4k.git
    cd upscale_video_4k
    pip install -q realesrgan || true
    cd ..
fi

# 5. Clone mrhan1993/Fooocus-API for 10s Cloud SDXL avatar generation
if [ ! -d "Fooocus-API" ]; then
    echo "Cloning Fooocus-API for Cloud GPU generation..."
    git clone https://github.com/mrhan1993/Fooocus-API.git
    cd Fooocus-API
    pip install -q -r requirements.txt || true
    cd ..
fi

echo "✅ Environment setup complete! GPU ready for inference."
