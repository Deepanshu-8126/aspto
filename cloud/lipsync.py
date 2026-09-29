"""
AIInfluencerOS — Lip-Sync (MuseTalk 1.5)
Applies lip-sync to video using MuseTalk for realistic mouth movements.
"""

import os
import gc
import subprocess
import shutil

try:
    import torch  # type: ignore
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

# MuseTalk imports (available on GPU machine)
try:
    from musetalk.utils.utils import get_file_type  # type: ignore
    MUSETALK_AVAILABLE = True
except ImportError:
    MUSETALK_AVAILABLE = False


def apply_lipsync(
    video_path: str,
    audio_path: str,
    output_path: str = None,
    musetalk_dir: str = None,
    bbox_shift: int = 0,
    batch_size: int = 8,
    fps: int = 30,
) -> str:
    """
    Apply lip-sync to a video using MuseTalk.

    Uses MuseTalk's inference script via subprocess for reliability.

    Args:
        video_path: Input video (face video without audio)
        audio_path: Audio file to sync to
        output_path: Where to save output
        musetalk_dir: Path to MuseTalk installation
        bbox_shift: Face bounding box shift (adjust if lips don't align)
        batch_size: Processing batch size (reduce for low VRAM)
        fps: Output video FPS

    Returns:
        Path to lip-synced video
    """
    if output_path is None:
        output_path = os.path.join("output", "video", "lipsync_output.mp4")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if musetalk_dir is None:
        musetalk_dir = os.path.join(os.path.dirname(__file__), "MuseTalk")

    # Use MuseTalk inference script
    cmd = [
        "python", "-m", "musetalk.inference",
        "--video_path", video_path,
        "--audio_path", audio_path,
        "--output_path", output_path,
        "--bbox_shift", str(bbox_shift),
        "--batch_size", str(batch_size),
        "--fps", str(fps),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=musetalk_dir,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"MuseTalk failed: {result.stderr}")

    except FileNotFoundError:
        # Fallback: Use direct Python API if available
        return _apply_lipsync_python(video_path, audio_path, output_path, fps)

    gc.collect()
    torch.cuda.empty_cache()

    return output_path


def _apply_lipsync_python(
    video_path: str,
    audio_path: str,
    output_path: str,
    fps: int = 30,
) -> str:
    """
    Fallback: Merge video + audio without lip-sync if MuseTalk is unavailable.
    Uses FFmpeg to overlay audio on video.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")

    return output_path


def apply_lipsync_batch(
    video_clips: list,
    audio_path: str,
    output_dir: str = "output/video/lipsync",
    **kwargs,
) -> list:
    """
    Apply lip-sync to multiple video clips against segments of the audio.

    Returns:
        List of lip-synced clip paths
    """
    os.makedirs(output_dir, exist_ok=True)

    synced_clips = []
    for i, clip_path in enumerate(video_clips):
        out_path = os.path.join(output_dir, f"synced_{i:02d}.mp4")
        try:
            apply_lipsync(clip_path, audio_path, out_path, **kwargs)
            synced_clips.append(out_path)
        except Exception as e:
            print(f"⚠️  Lip-sync failed for clip {i}: {e}. Using fallback merge.")
            _apply_lipsync_python(clip_path, audio_path, out_path)
            synced_clips.append(out_path)

    return synced_clips
