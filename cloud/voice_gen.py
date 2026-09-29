"""
AIInfluencerOS — Voice Generation (F5-TTS Voice Cloning)
Generates speech from text using a cloned voice model.
"""

import os
import re
import tempfile
import subprocess
import numpy as np

try:
    import soundfile as sf  # type: ignore
    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None
    SOUNDFILE_AVAILABLE = False

# F5-TTS imports (available on GPU machine)
try:
    from f5_tts.api import F5TTS  # type: ignore
    F5_AVAILABLE = True
except ImportError:
    F5_AVAILABLE = False


_tts_model = None


def init_f5tts(model_name: str = "F5-TTS") -> "F5TTS":
    """Initialize F5-TTS model (lazy singleton)."""
    global _tts_model
    if _tts_model is None:
        if not F5_AVAILABLE:
            raise ImportError("F5-TTS not installed. Run: pip install f5-tts")
        _tts_model = F5TTS(model_type=model_name)
    return _tts_model


def clean_script_for_tts(script: str) -> str:
    """Clean script text for TTS input."""
    # Remove stage directions and pauses
    text = re.sub(r"\[.*?\]", " ", script)
    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    # Remove emojis (TTS can't speak them)
    text = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F"
        r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
        r"\U00002600-\U000026FF]+",
        " ",
        text,
    )
    return text.strip()


def generate_voice(
    script: str,
    reference_audio: str,
    reference_text: str = "",
    output_path: str = None,
    model_name: str = "F5-TTS",
    speed: float = 1.0,
) -> str:
    """
    Generate speech from script using cloned voice.

    Args:
        script: Text to speak
        reference_audio: Path to reference voice sample (5s WAV)
        reference_text: Transcript of reference audio (optional, improves quality)
        output_path: Where to save output WAV
        model_name: F5-TTS model variant
        speed: Speech speed multiplier

    Returns:
        Path to generated audio file
    """
    if output_path is None:
        output_path = os.path.join("output", "audio", "voice_output.wav")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cleaned_text = clean_script_for_tts(script)

    tts = init_f5tts(model_name)

    # Generate audio
    wav, sample_rate, _ = tts.infer(
        ref_file=reference_audio,
        ref_text=reference_text,
        gen_text=cleaned_text,
        speed=speed,
    )

    # Save output
    sf.write(output_path, wav, sample_rate)

    return output_path


def generate_voice_chunked(
    script: str,
    reference_audio: str,
    reference_text: str = "",
    output_path: str = None,
    model_name: str = "F5-TTS",
    chunk_size: int = 200,
) -> str:
    """
    Generate voice in chunks for longer scripts (>200 chars).
    Splits at sentence boundaries and concatenates.

    Returns:
        Path to final concatenated audio file
    """
    if output_path is None:
        output_path = os.path.join("output", "audio", "voice_output.wav")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cleaned_text = clean_script_for_tts(script)

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", cleaned_text)

    # Group sentences into chunks
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += " " + sentence
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    if not chunks:
        chunks = [cleaned_text]

    # Generate each chunk
    tts = init_f5tts(model_name)
    audio_segments = []
    sample_rate = 24000

    for i, chunk in enumerate(chunks):
        wav, sr, _ = tts.infer(
            ref_file=reference_audio,
            ref_text=reference_text,
            gen_text=chunk,
        )
        audio_segments.append(wav)
        sample_rate = sr

    # Concatenate with small silence gaps
    silence = np.zeros(int(sample_rate * 0.3))  # 300ms pause
    full_audio = []
    for i, seg in enumerate(audio_segments):
        full_audio.append(seg)
        if i < len(audio_segments) - 1:
            full_audio.append(silence)

    final_audio = np.concatenate(full_audio)
    sf.write(output_path, final_audio, sample_rate)

    return output_path


def get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file in seconds."""
    data, sr = sf.read(audio_path)
    return len(data) / sr
