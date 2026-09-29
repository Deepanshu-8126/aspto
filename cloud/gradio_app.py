"""
AIInfluencerOS — Gradio Cloud API Server
Exposes the generation pipeline as HTTP API endpoints for the local i5 to call.
Run this on Google Colab / Kaggle with GPU.
"""

import os
import json
import threading
import gradio as gr
from cloud.pipeline import run_pipeline, get_task, list_tasks, load_config


# ── Load Config ──────────────────────────────────────────

CONFIG = None

def get_config():
    global CONFIG
    if CONFIG is None:
        CONFIG = load_config()
    return CONFIG


# ── API Functions ────────────────────────────────────────

def api_generate(topic: str, brand_id: int = 0, style: str = "default") -> dict:
    """
    Trigger content generation pipeline.
    Runs in background thread so the API returns immediately.
    """
    config = get_config()

    brand = None
    if brand_id > 0:
        # Load brand from brands.json
        brands_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "brands.json")
        if os.path.exists(brands_path):
            with open(brands_path, "r", encoding="utf-8") as f:
                brands = json.load(f).get("brands", [])
            brand = next((b for b in brands if b["id"] == brand_id), None)

    # Run pipeline in background
    import uuid
    task_id = str(uuid.uuid4())[:8]

    def _run():
        run_pipeline(topic, brand, style, config, task_id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "queued", "topic": topic}


def api_status(task_id: str) -> dict:
    """Get task status and progress."""
    task = get_task(task_id)
    if task is None:
        return {"error": f"Task {task_id} not found"}
    return task.to_dict()


def api_list_tasks() -> list:
    """List all tasks."""
    return list_tasks()


def api_output(task_id: str) -> str:
    """Get path to final output video."""
    task = get_task(task_id)
    if task is None:
        return None
    final = task.artifacts.get("final_reel")
    if final and os.path.exists(final):
        return final
    return None


def api_upload_voice(audio_file) -> dict:
    """Upload a new voice reference sample."""
    config = get_config()
    ref_path = config["paths"]["voice_ref"]
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)

    import shutil
    shutil.copy2(audio_file.name, ref_path)

    return {"status": "success", "voice_ref": ref_path}


# ── Gradio Interface ─────────────────────────────────────

def build_gradio_app() -> gr.Blocks:
    """Build the Gradio API server."""

    with gr.Blocks(
        title="AIInfluencerOS — Cloud Pipeline",
    ) as app:

        gr.Markdown(
            """
            # 🎬 AIInfluencerOS — Cloud Generation Pipeline
            **GPU-powered content generation server** — Called by your local i5 machine.
            """
        )

        with gr.Tab("🚀 Generate"):
            with gr.Row():
                topic_input = gr.Textbox(label="Topic", placeholder="e.g., morning skincare routine")
                brand_input = gr.Number(label="Brand ID (0 = none)", value=0, precision=0)
                style_input = gr.Dropdown(
                    choices=["default", "aesthetic", "bold", "minimal", "dramatic"],
                    value="default",
                    label="Style",
                )
            generate_btn = gr.Button("🎬 Generate Reel", variant="primary", size="lg")
            generate_output = gr.JSON(label="Response")
            generate_btn.click(api_generate, [topic_input, brand_input, style_input], generate_output)

        with gr.Tab("📊 Status"):
            task_id_input = gr.Textbox(label="Task ID")
            status_btn = gr.Button("Check Status")
            status_output = gr.JSON(label="Task Status")
            status_btn.click(api_status, task_id_input, status_output)

            gr.Markdown("---")
            list_btn = gr.Button("List All Tasks")
            list_output = gr.JSON(label="All Tasks")
            list_btn.click(api_list_tasks, None, list_output)

        with gr.Tab("📥 Output"):
            dl_task_id = gr.Textbox(label="Task ID")
            dl_btn = gr.Button("Download Reel")
            dl_output = gr.Video(label="Final Reel")
            dl_btn.click(api_output, dl_task_id, dl_output)

        with gr.Tab("🎤 Voice"):
            voice_upload = gr.File(label="Upload Voice Sample (5s WAV)", file_types=[".wav", ".mp3"])
            voice_btn = gr.Button("Update Voice Model")
            voice_output = gr.JSON(label="Status")
            voice_btn.click(api_upload_voice, voice_upload, voice_output)

    return app


# ── Main ─────────────────────────────────────────────────

def main():
    app = build_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,  # Creates public URL (needed for Colab)
        show_error=True,
    )


if __name__ == "__main__":
    main()
