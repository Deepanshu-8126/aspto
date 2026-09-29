"""
AIInfluencerOS — Image Generation Engine (Fooocus-API + ComfyUI Dual Engine)
Supports SDXL via mrhan1993/Fooocus-API (10s/image, LoRA support, FaceSwap)
with automatic fallback to ComfyUI (SD 1.5).
"""

import os
import json
import time
import uuid
import base64
import logging
import requests
from typing import Optional, List, Dict, Any
from io import BytesIO
from PIL import Image

logger = logging.getLogger("image_gen")

FOOOCUS_URL = "http://127.0.0.1:8888"
COMFYUI_URL = "http://127.0.0.1:8188"


# ════════════════════════════════════════════════════════════════
# 1. FOOOCUS-API ENGINE (mrhan1993/Fooocus-API) — High Quality SDXL
# ════════════════════════════════════════════════════════════════

class FooocusClient:
    """REST API Client for Fooocus-API (Port 8888)."""

    def __init__(self, base_url: str = FOOOCUS_URL):
        self.base_url = base_url.rstrip("/")

    def is_available(self, timeout: float = 2.0) -> bool:
        """Check if Fooocus-API service is responding."""
        try:
            r = requests.get(f"{self.base_url}/docs", timeout=timeout)
            return r.status_code in (200, 301, 302, 404)
        except Exception:
            return False

    def text_to_image(
        self,
        prompt: str,
        negative_prompt: str = "low quality, blurry, deformed, bad anatomy, bad hands, text, watermark",
        styles: Optional[List[str]] = None,
        performance: str = "Quality",
        aspect_ratio: str = "704*1408",
        loras: Optional[List[List[Any]]] = None,
        base_model: str = "juggernautXL_v8Rundiffusion.safetensors",
        guidance_scale: float = 7.0,
        image_number: int = 1,
        seed: int = -1,
    ) -> str:
        """
        Submits text-to-image job to Fooocus-API.
        Returns job_id.
        """
        if styles is None:
            styles = ["Fooocus V2", "Fooocus Masterpiece", "Fooocus Enhance"]
        if loras is None:
            loras = [["my_face.safetensors", 0.9]]

        endpoint = f"{self.base_url}/v1/generation/text-to-image"
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "style_selections": styles,
            "performance_selection": performance,
            "aspect_ratios_selection": aspect_ratio,
            "image_number": image_number,
            "image_seed": seed,
            "guidance_scale": guidance_scale,
            "base_model_name": base_model,
            "loras": [{"model_name": name, "weight": weight} for name, weight in loras]
            if isinstance(loras[0], (list, tuple)) and not isinstance(loras[0], dict)
            else loras,
            "async_process": True,
        }

        # Fallback format if API schema accepts simplified keys
        try:
            resp = requests.post(endpoint, json=payload, timeout=30)
            if resp.status_code >= 400:
                # Try alternative payload schema for different Fooocus-API versions
                simple_payload = {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "styles": styles,
                    "performance": performance,
                    "aspect_ratio": aspect_ratio,
                    "seed": seed,
                    "guidance_scale": guidance_scale,
                    "base_model": base_model,
                    "loras": loras,
                    "image_number": image_number,
                }
                resp = requests.post(endpoint, json=simple_payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("job_id") or data.get("id") or str(data)
        except Exception as e:
            logger.error(f"Fooocus-API submission error: {e}")
            raise

    def query_job(self, job_id: str) -> Dict[str, Any]:
        """Poll job status from Fooocus-API."""
        endpoint = f"{self.base_url}/v1/generation/query-job"
        resp = requests.get(endpoint, params={"job_id": job_id}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def wait_for_job(self, job_id: str, timeout: int = 180, poll_interval: float = 2.0) -> Dict[str, Any]:
        """Poll until job finishes or times out."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_data = self.query_job(job_id)
            state = status_data.get("status", "").upper()
            if state in ("FINISHED", "SUCCESS", "DONE"):
                return status_data
            elif state in ("FAILED", "ERROR"):
                error_msg = status_data.get("error") or status_data.get("message") or "Unknown error"
                raise RuntimeError(f"Fooocus generation failed: {error_msg}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Fooocus job {job_id} timed out after {timeout}s")


def generate_fooocus_image(
    prompt: str,
    lora_name: str = "my_face.safetensors",
    lora_strength: float = 0.9,
    base_model: str = "juggernautXL_v8Rundiffusion.safetensors",
    aspect_ratio: str = "704*1408",
    styles: Optional[List[str]] = None,
    fooocus_url: str = FOOOCUS_URL,
    output_dir: str = "output/images",
) -> str:
    """
    High-level generation using mrhan1993/Fooocus-API.
    Generates consistent face image in ~10 seconds.
    """
    os.makedirs(output_dir, exist_ok=True)
    client = FooocusClient(base_url=fooocus_url)

    logger.info(f"Submitting prompt to Fooocus-API at {fooocus_url}...")
    job_id = client.text_to_image(
        prompt=prompt,
        loras=[[lora_name, lora_strength]],
        base_model=base_model,
        aspect_ratio=aspect_ratio,
        styles=styles or ["Fooocus V2", "Fooocus Masterpiece", "Fooocus Enhance"],
    )

    logger.info(f"Fooocus Job ID: {job_id}. Awaiting completion...")
    result = client.wait_for_job(job_id)

    images = result.get("images") or result.get("data") or []
    if not images:
        raise FileNotFoundError("Fooocus-API reported job finished but returned no images")

    first_image = images[0]
    out_file = os.path.join(output_dir, f"fooocus_{str(uuid.uuid4())[:8]}.png")

    if isinstance(first_image, str) and first_image.startswith("http"):
        img_resp = requests.get(first_image, timeout=30)
        with open(out_file, "wb") as f:
            f.write(img_resp.content)
    elif isinstance(first_image, str) and ";base64," in first_image:
        b64_data = first_image.split(";base64,")[1]
        with open(out_file, "wb") as f:
            f.write(base64.b64decode(b64_data))
    elif isinstance(first_image, dict) and "url" in first_image:
        img_url = first_image["url"]
        if not img_url.startswith("http"):
            img_url = f"{fooocus_url.rstrip('/')}/{img_url.lstrip('/')}"
        img_resp = requests.get(img_url, timeout=30)
        with open(out_file, "wb") as f:
            f.write(img_resp.content)
    elif isinstance(first_image, dict) and "base64" in first_image:
        with open(out_file, "wb") as f:
            f.write(base64.b64decode(first_image["base64"]))
    elif os.path.exists(str(first_image)):
        # Local file path returned by Fooocus
        img = Image.open(str(first_image))
        img.save(out_file)
    else:
        raise ValueError(f"Unrecognized image payload format from Fooocus: {first_image}")

    logger.info(f"Fooocus image successfully saved to {out_file}")
    return out_file


# ════════════════════════════════════════════════════════════════
# 2. COMFYUI ENGINE (SD 1.5 + LoRA) — Modular Fallback
# ════════════════════════════════════════════════════════════════

def build_workflow(
    prompt: str,
    lora_path: str = "my_face.safetensors",
    lora_strength: float = 0.85,
    sd_model: str = "v1-5-pruned.safetensors",
    width: int = 512,
    height: int = 768,
    seed: Optional[int] = None,
    negative_prompt: str = "ugly, deformed, blurry, low quality, bad anatomy, bad hands, text, watermark",
) -> dict:
    """Build ComfyUI workflow JSON for face-consistent image generation."""
    if seed is None:
        seed = int(time.time()) % (2**32)

    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 25,
                "cfg": 7.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_path,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
                "model": ["10", 0],
                "clip": ["10", 1],
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["4", 1],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["10", 2],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "avatar",
                "images": ["8", 0],
            },
        },
        "10": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": sd_model,
            },
        },
    }


def queue_comfyui_prompt(workflow: dict, comfyui_url: str = COMFYUI_URL) -> str:
    """Queue a generation prompt on ComfyUI and return prompt_id."""
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    resp = requests.post(f"{comfyui_url}/prompt", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["prompt_id"]


def wait_for_comfyui(prompt_id: str, comfyui_url: str = COMFYUI_URL, timeout: int = 300) -> dict:
    """Poll ComfyUI until prompt completes."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{comfyui_url}/history/{prompt_id}", timeout=10)
        data = resp.json()
        if prompt_id in data:
            return data[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"ComfyUI generation timed out after {timeout}s")


def download_comfyui_image(prompt_id: str, comfyui_url: str = COMFYUI_URL, output_dir: str = "output/images") -> str:
    """Download generated image from ComfyUI."""
    history = wait_for_comfyui(prompt_id, comfyui_url)
    os.makedirs(output_dir, exist_ok=True)
    outputs = history.get("outputs", {})
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for img_info in node_output["images"]:
                filename = img_info["filename"]
                subfolder = img_info.get("subfolder", "")
                img_resp = requests.get(
                    f"{comfyui_url}/view",
                    params={"filename": filename, "subfolder": subfolder, "type": "output"},
                    timeout=30,
                )
                save_path = os.path.join(output_dir, f"avatar_{prompt_id[:8]}.png")
                with open(save_path, "wb") as f:
                    f.write(img_resp.content)
                return save_path
    raise FileNotFoundError("No output image found in ComfyUI history")


# ════════════════════════════════════════════════════════════════
# 3. UNIFIED AVATAR GENERATION PIPELINE
# ════════════════════════════════════════════════════════════════

def generate_avatar(
    image_prompt: str,
    lora_path: str = "my_face.safetensors",
    lora_strength: float = 0.9,
    engine: str = "fooocus",  # "fooocus" (recommended) or "comfyui"
    fooocus_url: str = FOOOCUS_URL,
    comfyui_url: str = COMFYUI_URL,
    sd_model: str = "v1-5-pruned.safetensors",
    base_model: str = "juggernautXL_v8Rundiffusion.safetensors",
    aspect_ratio: str = "704*1408",
    styles: Optional[List[str]] = None,
    output_dir: str = "output/images",
) -> str:
    """
    High-level avatar generation with automatic engine routing.

    Prioritizes mrhan1993/Fooocus-API (SDXL, 10s generation, cinematic lighting,
    native LoRA), with automatic fallback to ComfyUI if Fooocus is unavailable.

    Args:
        image_prompt: Description of the avatar clothing, pose, setting
        lora_path: Face LoRA filename (e.g. 'my_face.safetensors')
        lora_strength: Influence strength (0.8 - 1.0)
        engine: "fooocus" or "comfyui"
        fooocus_url: URL for Fooocus-API (default: http://127.0.0.1:8888)
        comfyui_url: URL for ComfyUI (default: http://127.0.0.1:8188)
        sd_model: Checkpoint for ComfyUI
        base_model: SDXL Checkpoint for Fooocus
        aspect_ratio: Resolution preset ("704*1408" for vertical reels)
        styles: Visual style presets for Fooocus
        output_dir: Destination folder

    Returns:
        Path to high-resolution 1080x1920 avatar image
    """
    os.makedirs(output_dir, exist_ok=True)
    lora_name = os.path.basename(lora_path)

    enhanced_prompt = (
        f"aesthetic young woman, solo portrait, looking directly at camera, "
        f"instagram influencer photoshoot, {image_prompt}, "
        f"cinematic warm lighting, shallow depth of field, 8k uhd, photorealistic, dslr portrait"
    )

    image_path = None

    # 1. Attempt Fooocus-API first if selected or available
    if engine.lower() == "fooocus":
        try:
            logger.info("Attempting generation via Fooocus-API (SDXL)...")
            image_path = generate_fooocus_image(
                prompt=enhanced_prompt,
                lora_name=lora_name,
                lora_strength=lora_strength,
                base_model=base_model,
                aspect_ratio=aspect_ratio,
                styles=styles,
                fooocus_url=fooocus_url,
                output_dir=output_dir,
            )
        except Exception as fe:
            logger.warning(f"Fooocus-API unavailable or failed ({fe}). Falling back to ComfyUI...")

    # 2. ComfyUI fallback
    if image_path is None:
        try:
            logger.info("Generating via ComfyUI (SD 1.5)...")
            workflow = build_workflow(
                prompt=enhanced_prompt,
                lora_path=lora_name,
                lora_strength=lora_strength,
                sd_model=sd_model,
                width=512,
                height=768,
            )
            prompt_id = queue_comfyui_prompt(workflow, comfyui_url)
            image_path = download_comfyui_image(prompt_id, comfyui_url, output_dir)
        except Exception as ce:
            logger.error(f"ComfyUI generation failed: {ce}")
            # If both servers are offline in local development, generate a clean synthetic placeholder
            placeholder_path = os.path.join(output_dir, f"mock_avatar_{str(uuid.uuid4())[:8]}.png")
            img = Image.new("RGB", (1080, 1920), color=(28, 28, 36))
            img.save(placeholder_path)
            logger.warning(f"Both GPU backends offline — created local development avatar at {placeholder_path}")
            return placeholder_path

    # Standardize to 1080x1920 (9:16 Instagram Reel standard)
    img = Image.open(image_path)
    img_resized = img.resize((1080, 1920), Image.LANCZOS)
    final_path = image_path.replace(".png", "_1080.png")
    img_resized.save(final_path, quality=95)

    return final_path
