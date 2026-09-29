"""
AIInfluencerOS — Full Generation Pipeline
Orchestrates: Script → Image → Voice → Video → LipSync → FFmpeg → Final Reel
"""

import os
import json
import time
import uuid
import shutil
import traceback
from datetime import datetime
from typing import Optional

from cloud.script_gen import generate_script, init_gemini
from cloud.image_gen import generate_avatar
from cloud.voice_gen import generate_voice_chunked, get_audio_duration
from cloud.video_gen import generate_video_clip
from cloud.lipsync import apply_lipsync
from cloud.ffmpeg_merge import create_final_reel, add_text_overlay, get_video_info


# ── Task Tracking ────────────────────────────────────────

_tasks = {}  # task_id -> task_state


class PipelineTask:
    """Tracks a single content generation pipeline run."""

    def __init__(self, task_id: str, topic: str, brand: dict = None, style: str = "default"):
        self.task_id = task_id
        self.topic = topic
        self.brand = brand
        self.style = style
        self.status = "queued"
        self.progress = 0
        self.current_step = "Initializing"
        self.error = None
        self.started_at = datetime.now().isoformat()
        self.completed_at = None
        self.artifacts = {}  # step_name -> file_path

    def update(self, step: str, progress: int):
        self.current_step = step
        self.progress = progress
        self.status = "running"

    def complete(self, output_path: str):
        self.status = "completed"
        self.progress = 100
        self.current_step = "Done"
        self.completed_at = datetime.now().isoformat()
        self.artifacts["final_reel"] = output_path

    def fail(self, error: str):
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "topic": self.topic,
            "brand": self.brand,
            "status": self.status,
            "progress": self.progress,
            "current_step": self.current_step,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "artifacts": self.artifacts,
        }


def get_task(task_id: str) -> Optional[PipelineTask]:
    return _tasks.get(task_id)


def list_tasks() -> list:
    return [t.to_dict() for t in _tasks.values()]


# ── Pipeline Configuration ───────────────────────────────

def load_config(config_path: str = None) -> dict:
    """Load config.yaml."""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.yaml")
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Main Pipeline ────────────────────────────────────────

def run_pipeline(
    topic: str,
    brand: dict = None,
    style: str = "default",
    config: dict = None,
    task_id: str = None,
) -> str:
    """
    Run the full content generation pipeline.

    Steps:
        1. Generate script (Gemini API)
        2. Generate avatar image (ComfyUI + LoRA)
        3. Generate voice (F5-TTS)
        4. Generate video (Wan2.1)
        5. Apply lip-sync (MuseTalk)
        6. Final render (FFmpeg)

    Args:
        topic: Content topic
        brand: Brand dict for product mentions
        style: Visual style override
        config: Config dict (or loads from config.yaml)
        task_id: Custom task ID (or auto-generated)

    Returns:
        task_id for tracking
    """
    if config is None:
        config = load_config()

    if task_id is None:
        task_id = str(uuid.uuid4())[:8]

    task = PipelineTask(task_id, topic, brand, style)
    _tasks[task_id] = task

    # Create output directory for this task
    output_dir = os.path.join(config["paths"]["output_dir"], task_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        # ── Step 1: Script Generation ────────────────────
        task.update("Generating script...", 10)
        init_gemini(config["gemini"]["api_key"])

        script_data = generate_script(
            topic=topic,
            brand=brand,
            api_key=config["gemini"]["api_key"],
            model_name=config["gemini"]["model"],
        )
        task.artifacts["script"] = script_data

        script_path = os.path.join(output_dir, "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

        # ── Step 2: Avatar Image Generation ──────────────
        task.update("Generating avatar image...", 25)

        image_path = generate_avatar(
            image_prompt=script_data.get("image_prompt", f"Young woman, {topic}"),
            lora_path=os.path.basename(config["paths"]["lora_path"]),
            lora_strength=config["pipeline"].get("lora_strength", 0.9),
            engine=config["pipeline"].get("image_engine", "fooocus"),
            fooocus_url=config["pipeline"].get("fooocus_url", "http://127.0.0.1:8888"),
            comfyui_url=config["pipeline"].get("comfyui_url", "http://127.0.0.1:8188"),
            sd_model=config["pipeline"].get("sd_model", "v1-5-pruned.safetensors"),
            base_model=config["pipeline"].get("fooocus_base_model", "juggernautXL_v8Rundiffusion.safetensors"),
            aspect_ratio=config["pipeline"].get("fooocus_aspect_ratio", "704*1408"),
            styles=config["pipeline"].get("fooocus_styles"),
            output_dir=output_dir,
        )
        task.artifacts["avatar"] = image_path

        # ── Step 3: Voice Generation ─────────────────────
        task.update("Generating voice...", 40)

        voice_path = os.path.join(output_dir, "voice.wav")
        generate_voice_chunked(
            script=script_data["script"],
            reference_audio=config["paths"]["voice_ref"],
            output_path=voice_path,
        )
        task.artifacts["voice"] = voice_path
        audio_duration = get_audio_duration(voice_path)

        # ── Step 4: Video Generation ─────────────────────
        task.update("Generating video clips...", 55)

        video_prompt = (
            f"A young woman talking naturally to camera, {topic}, "
            "slight head movements, expressive gestures, warm lighting"
        )

        clip_path = os.path.join(output_dir, "raw_clip.mp4")
        generate_video_clip(
            image_path=image_path,
            prompt=video_prompt,
            output_path=clip_path,
        )
        task.artifacts["raw_video"] = clip_path

        # ── Step 5: Lip-Sync ─────────────────────────────
        task.update("Applying lip-sync...", 75)

        lipsync_path = os.path.join(output_dir, "lipsync.mp4")
        apply_lipsync(
            video_path=clip_path,
            audio_path=voice_path,
            output_path=lipsync_path,
        )
        task.artifacts["lipsync_video"] = lipsync_path

        # ── Step 6: Final Render ─────────────────────────
        task.update("Rendering final reel...", 90)

        final_path = os.path.join(output_dir, "final_reel.mp4")
        create_final_reel(
            video_clips=[lipsync_path],
            audio_path=voice_path,
            output_path=final_path,
            width=config["video"]["width"],
            height=config["video"]["height"],
            fps=config["video"]["fps"],
        )

        # Add CTA text overlay if available
        if script_data.get("cta"):
            cta_path = os.path.join(output_dir, "final_reel_cta.mp4")
            add_text_overlay(final_path, script_data["cta"], cta_path)
            if os.path.exists(cta_path):
                shutil.move(cta_path, final_path)

        task.artifacts["final_reel"] = final_path

        # Verify output
        info = get_video_info(final_path)
        task.artifacts["video_info"] = info

        task.complete(final_path)
        return task_id

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        task.fail(error_msg)
        return task_id
