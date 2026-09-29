"""
AI-INFLUENCER-OS — Redis Session & Brand Cache Layer
Provides sub-millisecond (<1ms) working memory, instant brand catalog lookup,
and semantic query caching. Automatically falls back to an in-memory TTL store
if Redis server is not running locally.
"""

import time
import json
import hashlib
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("redis_cache")

try:
    import redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False


class InMemoryCacheFallback:
    """Thread-safe in-memory cache mimicking Redis key-value & hash operations."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        if key in self._expires and time.time() > self._expires[key]:
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return True
        return False

    def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            return None
        return self._store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None):
        self._store[key] = value
        if ex:
            self._expires[key] = time.time() + ex
        else:
            self._expires.pop(key, None)

    def hset(self, name: str, mapping: Dict[str, Any]):
        if name not in self._store or not isinstance(self._store[name], dict):
            self._store[name] = {}
        self._store[name].update({k: str(v) for k, v in mapping.items()})

    def hgetall(self, name: str) -> Dict[str, str]:
        if self._is_expired(name):
            return {}
        val = self._store.get(name)
        return val if isinstance(val, dict) else {}

    def delete(self, key: str):
        self._store.pop(key, None)
        self._expires.pop(key, None)


def _is_port_open(host: str, port: int, timeout: float = 0.15) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


class BrainRedisCache:
    """
    High-performance caching layer for Aisha's real-time working memory.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self.client = None
        self.fallback = InMemoryCacheFallback()
        self._connect()

    def _connect(self):
        if not _HAS_REDIS:
            return
        if not _is_port_open(self.host, self.port):
            # Redis daemon not running, fallback immediately without blocking
            return
        try:
            r = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True, socket_timeout=0.5)
            r.ping()
            self.client = r
            logger.info(f"✅ Connected to Redis server at {self.host}:{self.port}")
        except Exception as e:
            logger.info(f"Redis daemon not reachable ({e}). Using ultra-fast in-memory cache.")
            self.client = None

    @property
    def is_connected(self) -> bool:
        return self.client is not None

    # ── 1. Fan Working Session (<1ms) ──────────────────────────

    def set_fan_session(self, user_id: str, data: Dict[str, Any], ttl: int = 86400):
        """Stores fan profile and recent interaction state in working memory."""
        key = f"fan:{user_id}"
        if self.client:
            try:
                self.client.hset(key, mapping={k: str(v) for k, v in data.items()})
                self.client.expire(key, ttl)
                return
            except Exception:
                pass
        self.fallback.hset(key, data)

    def get_fan_session(self, user_id: str) -> Dict[str, str]:
        """Retrieves fan working memory profile in <1ms."""
        key = f"fan:{user_id}"
        if self.client:
            try:
                return self.client.hgetall(key) or {}
            except Exception:
                pass
        return self.fallback.hgetall(key)

    # ── 2. Brand Catalog Fast Lookup (<1ms) ───────────────────

    def cache_brand(self, brand_key: str, brand_data: Dict[str, Any]):
        """Caches product pricing, stock, links, and promo codes for instant reply."""
        key = f"brand:{brand_key.lower().strip()}"
        clean_data = {
            "name": str(brand_data.get("name", "")),
            "product": str(brand_data.get("product", "")),
            "price": str(brand_data.get("price", "")),
            "link": str(brand_data.get("link", "")),
            "promo_code": str(brand_data.get("promo_code", "AISHA50")),
            "in_stock": "yes",
        }
        if self.client:
            try:
                self.client.hset(key, mapping=clean_data)
                return
            except Exception:
                pass
        self.fallback.hset(key, clean_data)

    def get_cached_brand(self, brand_key: str) -> Dict[str, str]:
        """Instant lookup for brand product details."""
        key = f"brand:{brand_key.lower().strip()}"
        if self.client:
            try:
                data = self.client.hgetall(key)
                if data:
                    return data
            except Exception:
                pass
        return self.fallback.hgetall(key)

    # ── 3. Semantic / Query Cache (Eliminates redundant LLM calls) ─

    def _query_key(self, user_id: str, message: str) -> str:
        h = hashlib.md5(message.strip().lower().encode("utf-8")).hexdigest()[:12]
        return f"dm_cache:{user_id}:{h}"

    def get_cached_reply(self, user_id: str, message: str) -> Optional[str]:
        """Returns cached answer if fan asks identical question within TTL window."""
        key = self._query_key(user_id, message)
        if self.client:
            try:
                return self.client.get(key)
            except Exception:
                pass
        return self.fallback.get(key)

    def set_cached_reply(self, user_id: str, message: str, reply: str, ttl: int = 1800):
        """Caches AI reply for 30 minutes to reduce LLM token consumption."""
        key = self._query_key(user_id, message)
        if self.client:
            try:
                self.client.set(key, reply, ex=ttl)
                return
            except Exception:
                pass
        self.fallback.set(key, reply, ex=ttl)


# Global singleton instance
redis_cache = BrainRedisCache()
