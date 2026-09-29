"""
AIInfluencerOS — Video Generation (Wan2.1 1.3B)
Generates short video clips from a face image using image-to-video.
"""

import os
import gc
import numpy as np
from PIL import Image

try:
    import torch  # type: ignore
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

# Wan2.1 imports (available on GPU machine)
try:
    from diffusers import WanImageToVideoPipeline  # type: ignore
    from diffusers.utils import export_to_video  # type: ignore
    WAN_AVAILABLE = True
except ImportError:
    WAN_AVAILABLE = False


_wan_pipeline = None


def init_wan(model_id: str = "Wan-AI/Wan2.1-I2V-14B-480P") -> "WanImageToVideoPipeline":
    """Initialize Wan2.1 pipeline (lazy singleton). Uses 1.3B for T4 GPU."""
    global _wan_pipeline
    if _wan_pipeline is None:
        if not WAN_AVAILABLE:
            raise ImportError("diffusers not installed. Run: pip install diffusers transformers accelerate")
        _wan_pipeline = WanImageToVideoPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
        )
        _wan_pipeline.to("cuda")
        _wan_pipeline.enable_model_cpu_offload()
    return _wan_pipeline


def generate_video_clip(
    image_path: str,
    prompt: str = "A young woman talking naturally, slight head movements, warm expression, indoor setting",
    output_path: str = None,
    num_frames: int = 81,
    guidance_scale: float = 5.0,
    num_inference_steps: int = 30,
    width: int = 480,
    height: int = 832,
    model_id: str = "Wan-AI/Wan2.1-I2V-14B-480P",
    fps: int = 16,
) -> str:
    """
    Generate a short video clip from an image.

    Args:
        image_path: Path to the source face image
        prompt: Motion/action description
        output_path: Where to save output video
        num_frames: Number of frames (~5 sec at 16fps)
        guidance_scale: CFG scale
        num_inference_steps: Denoising steps
        width: Output width
        height: Output height
        model_id: Wan2.1 model ID
        fps: Output FPS

    Returns:
        Path to generated video clip
    """
    if output_path is None:
        output_path = os.path.join("output", "video", "clip.mp4")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Load and prepare image
    image = Image.open(image_path).convert("RGB")
    image = image.resize((width, height), Image.LANCZOS)

    pipe = init_wan(model_id)

    # Generate video
    output = pipe(
        image=image,
        prompt=prompt,
        negative_prompt="ugly, blurry, distorted face, bad anatomy, static, no movement",
        num_frames=num_frames,
        guidance_scale=guidance_scale,
        num_inference_steps=num_inference_steps,
        width=width,
        height=height,
        generator=torch.Generator("cuda").manual_seed(42),
    )

    # Export frames to video
    export_to_video(output.frames[0], output_path, fps=fps)

    # Free VRAM
    gc.collect()
    torch.cuda.empty_cache()

    return output_path


def generate_multiple_clips(
    image_path: str,
    num_clips: int = 6,
    prompts: list = None,
    output_dir: str = "output/video/clips",
    **kwargs,
) -> list:
    """
    Generate multiple 5-sec clips for a 30-sec reel.

    Args:
        image_path: Source face image
        num_clips: Number of clips to generate
        prompts: Per-clip motion prompts (optional)
        output_dir: Directory for clip files

    Returns:
        List of paths to generated clips
    """
    os.makedirs(output_dir, exist_ok=True)

    if prompts is None:
        prompts = [
            "A young woman looking at camera, starts speaking enthusiastically, slight hand gestures",
            "A young woman talking to camera, nodding, natural body language, indoor setting",
            "A young woman speaking passionately, gesturing with hands, warm lighting",
            "A young woman presenting a product, holding something, friendly smile",
            "A young woman laughing, natural expression, warm ambient lighting",
            "A young woman making a heart sign, smiling at camera, positive energy",
        ]

    clip_paths = []
    for i in range(min(num_clips, len(prompts))):
        clip_path = os.path.join(output_dir, f"clip_{i:02d}.mp4")
        generate_video_clip(
            image_path=image_path,
            prompt=prompts[i],
            output_path=clip_path,
            **kwargs,
        )
        clip_paths.append(clip_path)

    return clip_paths
