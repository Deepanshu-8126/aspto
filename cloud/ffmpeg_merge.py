"""
AIInfluencerOS — FFmpeg Video Merge & Render
Merges clips, overlays audio, formats to 9:16 (1080x1920) H.264 30fps.
"""

import os
import subprocess
import tempfile


def merge_clips(
    clip_paths: list,
    output_path: str = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    codec: str = "libx264",
) -> str:
    """
    Concatenate multiple video clips into a single video.

    Args:
        clip_paths: List of video file paths to concatenate
        output_path: Output file path
        width: Target width
        height: Target height
        fps: Target FPS
        codec: Video codec

    Returns:
        Path to merged video
    """
    if output_path is None:
        output_path = os.path.join("output", "video", "merged.mp4")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if len(clip_paths) == 1:
        # Single clip — just scale it
        return scale_video(clip_paths[0], output_path, width, height, fps, codec)

    # Create concat list file
    concat_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    try:
        for path in clip_paths:
            abs_path = os.path.abspath(path).replace("\\", "/")
            concat_file.write(f"file '{abs_path}'\n")
        concat_file.close()

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file.name,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                   f"fps={fps}",
            "-c:v", codec,
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")

    finally:
        os.unlink(concat_file.name)

    return output_path


def scale_video(
    input_path: str,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    codec: str = "libx264",
) -> str:
    """Scale a single video to target resolution."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
               f"fps={fps}",
        "-c:v", codec,
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg scale failed: {result.stderr}")

    return output_path


def overlay_audio(
    video_path: str,
    audio_path: str,
    output_path: str = None,
) -> str:
    """
    Overlay audio on a video (replace existing audio).

    Returns:
        Path to output video with audio
    """
    if output_path is None:
        output_path = video_path.replace(".mp4", "_audio.mp4")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio overlay failed: {result.stderr}")

    return output_path


def create_final_reel(
    video_clips: list,
    audio_path: str,
    output_path: str = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> str:
    """
    Full reel assembly: concat clips → scale to 9:16 → overlay audio.

    Args:
        video_clips: List of video clip paths
        audio_path: Path to the voice audio
        output_path: Final output path

    Returns:
        Path to final reel MP4
    """
    if output_path is None:
        output_path = os.path.join("output", "video", "final_reel.mp4")

    # Step 1: Merge clips
    merged_path = output_path.replace(".mp4", "_merged.mp4")
    merge_clips(video_clips, merged_path, width, height, fps)

    # Step 2: Overlay audio
    overlay_audio(merged_path, audio_path, output_path)

    # Cleanup intermediate
    if os.path.exists(merged_path):
        os.remove(merged_path)

    return output_path


def add_text_overlay(
    video_path: str,
    text: str,
    output_path: str = None,
    position: str = "bottom",
    font_size: int = 42,
    font_color: str = "white",
    bg_opacity: float = 0.5,
) -> str:
    """Add text overlay to video (for captions/CTAs)."""
    if output_path is None:
        output_path = video_path.replace(".mp4", "_text.mp4")

    y_pos = "h-th-80" if position == "bottom" else "80"

    # Escape text for FFmpeg
    escaped_text = text.replace("'", "\\'").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", (
            f"drawtext=text='{escaped_text}':"
            f"fontsize={font_size}:fontcolor={font_color}:"
            f"x=(w-tw)/2:y={y_pos}:"
            f"box=1:boxcolor=black@{bg_opacity}:boxborderw=10"
        ),
        "-c:v", "libx264",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg text overlay failed: {result.stderr}")

    return output_path


def get_video_info(video_path: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {}

    import json
    data = json.loads(result.stdout)
    video_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), {})

    return {
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "duration": float(data.get("format", {}).get("duration", 0)),
        "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream.get("r_frame_rate") else 0,
        "codec": video_stream.get("codec_name", ""),
        "size_mb": round(int(data.get("format", {}).get("size", 0)) / (1024 * 1024), 2),
    }
