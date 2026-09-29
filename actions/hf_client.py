"""
AI-INFLUENCER-OS — Hugging Face Multi-Account Client with Auto-Rotation
Rotates across multiple Hugging Face tokens if rate limits or ZeroGPU quotas are hit.
"""

import os
import time
import logging
from typing import Optional, List
from gradio_client import Client, handle_file

logger = logging.getLogger("hf_client")


class MultiAccountHFClient:
    """Manages Hugging Face API interactions with multi-token failover."""

    def __init__(
        self,
        video_space: str,
        upscaler_space: str,
        tokens: Optional[List[str]] = None,
    ):
        self.video_space = video_space.strip()
        self.upscaler_space = upscaler_space.strip()

        # Parse tokens from environment or argument
        if tokens:
            self.tokens = [t.strip() for t in tokens if t.strip()]
        else:
            raw_tokens = os.environ.get("HF_TOKENS", "") or os.environ.get("HF_TOKEN", "")
            # Supports comma-separated tokens or individual HF_TOKEN_1, HF_TOKEN_2
            self.tokens = [t.strip() for t in raw_tokens.split(",") if t.strip()]
            for i in range(1, 10):
                extra = os.environ.get(f"HF_TOKEN_{i}")
                if extra and extra not in self.tokens:
                    self.tokens.append(extra.strip())

        if not self.tokens:
            logger.warning("No HF tokens found. Using public/unauthenticated access.")
            self.tokens = [""]

        self.current_idx = 0
        logger.info(f"Loaded {len(self.tokens)} Hugging Face account tokens for rotation.")

    @property
    def current_token(self) -> str:
        return self.tokens[self.current_idx] if self.tokens else ""

    def rotate_token(self):
        """Switch to next Hugging Face token upon rate limit."""
        if len(self.tokens) > 1:
            self.current_idx = (self.current_idx + 1) % len(self.tokens)
            logger.warning(f"🔄 Switched to Hugging Face Token #{self.current_idx + 1}")
        else:
            logger.warning("Single token in use, cannot rotate.")

    def generate_video(
        self,
        instagram_url: str,
        dress: str,
        bg: str,
        topic: str,
        max_retries: int = 3,
    ) -> tuple[str, str]:
        """
        Calls the video-gen space to generate reel.
        Returns: (downloaded_video_path, caption)
        """
        for attempt in range(max_retries):
            token = self.current_token
            try:
                logger.info(f"Connecting to {self.video_space} (Attempt {attempt+1}/{max_retries})...")
                client = Client(self.video_space, hf_token=token if token else None)
                
                result = client.predict(
                    instagram_url=instagram_url,
                    dress=dress,
                    bg=bg,
                    topic=topic,
                    hf_token=token,
                    api_name="/predict",
                )
                # Gradio returns: (video_path, caption, status)
                video_path = result[0]
                caption = result[1]
                logger.info(f"✅ Video generated from Space: {video_path}")
                return video_path, caption

            except Exception as e:
                err_str = str(e).lower()
                logger.error(f"Error on token #{self.current_idx + 1}: {e}")
                if "rate limit" in err_str or "quota" in err_str or "429" in err_str or "gpu" in err_str:
                    logger.warning("Quota/Rate limit hit on Hugging Face! Rotating token...")
                    self.rotate_token()
                    time.sleep(5)
                else:
                    time.sleep(10)

        raise RuntimeError(f"Failed to generate video after {max_retries} attempts across all HF accounts.")

    def upscale_to_4k(self, video_path: str) -> str:
        """
        Calls the upscaler space to upscale video to 4K.
        """
        try:
            logger.info(f"Connecting to upscaler {self.upscaler_space}...")
            token = self.current_token
            client = Client(self.upscaler_space, hf_token=token if token else None)

            result = client.predict(
                input_video_path=handle_file(video_path),
                scale=2,
                api_name="/predict",
            )
            logger.info(f"✅ 4K Upscale completed: {result}")
            return result
        except Exception as e:
            logger.warning(f"Upscaler Space failed ({e}). Using 1080p source video.")
            return video_path
