"""
AI-INFLUENCER-OS — Kaggle GPU Pipeline Runner
Interacts with Kaggle API to run StableAnimator on free T4 GPU (30 hrs/week).
"""

import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kaggle_runner")


class KaggleRunner:
    """Controls Kaggle GPU execution from GitHub Actions."""

    def __init__(self, username: Optional[str] = None, key: Optional[str] = None):
        self.username = username or os.environ.get("KAGGLE_USERNAME")
        self.key = key or os.environ.get("KAGGLE_KEY")

        if self.username and self.key:
            os.environ["KAGGLE_USERNAME"] = self.username
            os.environ["KAGGLE_KEY"] = self.key

    def is_configured(self) -> bool:
        return bool(self.username and self.key and self.username != "CHANGE_ME")

    def run_gpu_job(
        self,
        reel_url: str,
        dress: str,
        bg: str,
        topic: str,
        output_dir: str = "/tmp/kaggle_out",
    ) -> Optional[str]:
        """
        Pushes kernel to Kaggle, waits for GPU run, and downloads 4K video.
        """
        if not self.is_configured():
            logger.warning("Kaggle credentials not provided. Using fallback.")
            return None

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Write job configuration into kaggle/job_config.json
        job_cfg = {
            "reel_url": reel_url,
            "dress": dress,
            "bg": bg,
            "topic": topic,
        }
        with open("kaggle/job_config.json", "w", encoding="utf-8") as f:
            json.dump(job_cfg, f, indent=2)

        try:
            logger.info("Pushing kernel to Kaggle GPU...")
            push_cmd = ["kaggle", "kernels", "push", "-p", "kaggle/"]
            subprocess.run(push_cmd, check=True)

            kernel_id = f"{self.username}/ai-influencer-animator"
            logger.info(f"Waiting for Kaggle GPU kernel {kernel_id} to complete...")

            # Poll kernel status
            for minute in range(30):
                status_cmd = ["kaggle", "kernels", "status", kernel_id]
                res = subprocess.run(status_cmd, capture_output=True, text=True)
                status = res.stdout.lower()

                if "complete" in status:
                    logger.info("✅ Kaggle GPU kernel execution finished!")
                    break
                elif "error" in status or "failed" in status:
                    raise RuntimeError(f"Kaggle kernel failed: {res.stdout}")

                logger.info(f"Waiting for GPU render... ({minute+1}/30 min)")
                time.sleep(60)

            # Download output files
            logger.info("Downloading rendered 4K video from Kaggle...")
            dl_cmd = ["kaggle", "kernels", "output", kernel_id, "-p", str(out_path)]
            subprocess.run(dl_cmd, check=True)

            video_files = list(out_path.glob("*.mp4"))
            if video_files:
                logger.info(f"Retrieved 4K reel: {video_files[0]}")
                return str(video_files[0])

        except Exception as e:
            logger.error(f"Kaggle GPU runner error: {e}")

        return None
