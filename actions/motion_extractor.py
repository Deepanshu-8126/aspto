"""
AI-INFLUENCER-OS — Advanced Queue Parser & Motion Parameter Extractor
Parses /copy commands, topics.txt, and links.txt with auto-rotation.
"""

import os
import re
import shlex
from typing import Optional, Dict


def parse_line(line: str) -> Optional[Dict[str, str]]:
    """Parse a single command or queue line into structured parameters."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Strip /copy command prefix if user copied directly from Telegram
    if line.startswith("/copy "):
        line = line[len("/copy "):].strip()

    result = {
        "url": "",
        "dress": "chic aesthetic trendy outfit",
        "bg": "luxury modern penthouse balcony",
        "topic": "viral dance aesthetic",
    }

    try:
        parts = shlex.split(line)
    except Exception:
        parts = line.split()

    if not parts:
        return None

    result["url"] = parts[0]

    i = 1
    while i < len(parts):
        token = parts[i]
        if token == "--dress" and i + 1 < len(parts):
            result["dress"] = parts[i + 1]
            i += 2
        elif token == "--bg" and i + 1 < len(parts):
            result["bg"] = parts[i + 1]
            i += 2
        elif token == "--topic" and i + 1 < len(parts):
            result["topic"] = parts[i + 1]
            i += 2
        else:
            i += 1

    return result


def get_next_target(primary_file: str = "topics.txt", fallback_file: str = "links.txt") -> Optional[Dict[str, str]]:
    """
    Retrieves the next reel to process, checking topics.txt then links.txt.
    Rotates the processed item to the end of the file so queue stays alive forever.
    """
    target_path = primary_file if os.path.exists(primary_file) else fallback_file
    if not os.path.exists(target_path):
        return None

    with open(target_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    target_idx = None
    target_data = None

    for idx, line in enumerate(lines):
        parsed = parse_line(line)
        if parsed and parsed.get("url"):
            target_idx = idx
            target_data = parsed
            break

    if target_data and target_idx is not None:
        try:
            # Rotate line to bottom to cycle queue
            popped = lines.pop(target_idx)
            lines.append(popped.strip() + "\n")
            with open(target_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception as e:
            print(f"Queue rotate note: {e}")

    return target_data
