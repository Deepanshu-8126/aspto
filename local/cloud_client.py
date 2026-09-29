"""
AIInfluencerOS — Cloud Client
HTTP client that calls the Colab/Kaggle Gradio API from the local i5 machine.
"""

import os
import time
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger("cloud_client")


class CloudClient:
    """Async HTTP client for the cloud GPU Gradio API."""

    def __init__(self, gradio_url: str, timeout: int = 900, retry_attempts: int = 3, retry_delay: int = 30):
        self.base_url = gradio_url.rstrip("/")
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=30))

    async def close(self):
        await self._client.aclose()

    async def _call_api(self, fn_index: int, data: list) -> dict:
        """Call a Gradio API endpoint with retry logic."""
        url = f"{self.base_url}/api/predict"
        payload = {"fn_index": fn_index, "data": data}

        for attempt in range(1, self.retry_attempts + 1):
            try:
                resp = await self._client.post(url, json=payload)
                resp.raise_for_status()
                result = resp.json()
                return result.get("data", [result])[0] if isinstance(result.get("data"), list) else result
            except httpx.ConnectError:
                logger.warning(f"Cloud GPU unreachable (attempt {attempt}/{self.retry_attempts})")
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise ConnectionError("Cloud GPU is offline. Check Colab session.")
            except httpx.TimeoutException:
                logger.warning(f"Request timed out (attempt {attempt}/{self.retry_attempts})")
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise TimeoutError(f"Cloud API timed out after {self.timeout}s")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e.response.status_code}")
                raise

    async def generate(self, topic: str, brand_id: int = 0, style: str = "default") -> dict:
        """
        Trigger content generation on cloud GPU.

        Returns:
            {"task_id": str, "status": "queued"}
        """
        return await self._call_api(fn_index=0, data=[topic, brand_id, style])

    async def get_status(self, task_id: str) -> dict:
        """
        Check generation task status.

        Returns:
            {"task_id": str, "progress": int, "current_step": str, "status": str}
        """
        return await self._call_api(fn_index=1, data=[task_id])

    async def wait_for_completion(self, task_id: str, poll_interval: int = 15) -> dict:
        """
        Poll until task is complete or failed.

        Returns:
            Final task status dict
        """
        start = time.time()
        while time.time() - start < self.timeout:
            status = await self.get_status(task_id)

            if isinstance(status, dict):
                state = status.get("status", "")
                if state == "completed":
                    return status
                elif state == "failed":
                    raise RuntimeError(f"Pipeline failed: {status.get('error', 'Unknown error')}")

                progress = status.get("progress", 0)
                step = status.get("current_step", "")
                logger.info(f"[{task_id}] {progress}% — {step}")

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} timed out after {self.timeout}s")

    async def download_output(self, task_id: str, output_dir: str = "output/video") -> Optional[str]:
        """
        Download the final reel from cloud.

        Returns:
            Local path to downloaded file, or None if not available
        """
        os.makedirs(output_dir, exist_ok=True)

        # Get the output video path from Gradio
        result = await self._call_api(fn_index=2, data=[task_id])

        if result is None:
            return None

        # If result is a file path on the cloud, download via Gradio file endpoint
        if isinstance(result, str) and result.startswith("/"):
            file_url = f"{self.base_url}/file={result}"
        elif isinstance(result, dict) and "url" in result:
            file_url = result["url"]
        else:
            file_url = f"{self.base_url}/file={result}"

        try:
            resp = await self._client.get(file_url)
            resp.raise_for_status()

            local_path = os.path.join(output_dir, f"reel_{task_id}.mp4")
            with open(local_path, "wb") as f:
                f.write(resp.content)

            return local_path
        except Exception as e:
            logger.error(f"Failed to download output: {e}")
            return None

    async def upload_voice(self, audio_path: str) -> dict:
        """Upload a new voice reference sample to the cloud."""
        url = f"{self.base_url}/upload"
        with open(audio_path, "rb") as f:
            files = {"files": (os.path.basename(audio_path), f, "audio/wav")}
            resp = await self._client.post(url, files=files)
            resp.raise_for_status()
            return resp.json()

    async def health_check(self) -> bool:
        """Check if the cloud GPU is reachable."""
        try:
            resp = await self._client.get(f"{self.base_url}/", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    async def generate_and_wait(self, topic: str, brand_id: int = 0, style: str = "default",
                                 output_dir: str = "output/video") -> Optional[str]:
        """
        Full flow: trigger generation → wait → download.

        Returns:
            Local path to downloaded reel, or None on failure
        """
        try:
            result = await self.generate(topic, brand_id, style)
            task_id = result.get("task_id") if isinstance(result, dict) else str(result)

            await self.wait_for_completion(task_id)
            return await self.download_output(task_id, output_dir)

        except Exception as e:
            logger.error(f"Generate-and-wait failed: {e}")
            return None
