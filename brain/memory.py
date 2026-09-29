"""
AI-INFLUENCER-OS — Memory Layer (Mem0 Pattern)
Persistent, self-hosted, zero-cost memory engine for fan relationships.
Stores user preferences, facts, contradiction overrides, and interaction history.
"""

import os
import re
import json
import sqlite3
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager

from brain.redis_cache import redis_cache
from brain.qdrant_store import vector_store

MEMORY_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db")


class BrainMemory:
    """Mem0-inspired persistent memory system for each fan/follower."""

    def __init__(self, db_path: str = MEMORY_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    platform TEXT DEFAULT 'instagram',
                    relationship_tier TEXT DEFAULT 'new',
                    total_interactions INTEGER DEFAULT 0,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, fact_key)
                );

                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id);
                CREATE INDEX IF NOT EXISTS idx_hist_user ON message_history(user_id);
            """)

    def get_user(self, user_id: str) -> Optional[dict]:
        """Fetch existing user record without updating interaction count."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_or_create_user(self, user_id: str, username: str = "", platform: str = "instagram") -> dict:
        """Get or initialize user profile."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)

            conn.execute(
                "INSERT INTO users (user_id, username, platform, relationship_tier, total_interactions) VALUES (?, ?, ?, 'new', 0)",
                (user_id, username or user_id, platform),
            )
            return {
                "user_id": user_id,
                "username": username or user_id,
                "platform": platform,
                "relationship_tier": "new",
                "total_interactions": 0,
            }

    def record_interaction(self, user_id: str) -> dict:
        """Record an interaction and update relationship tier across SQLite & Redis."""
        with self._conn() as conn:
            self.get_or_create_user(user_id)
            conn.execute(
                "UPDATE users SET last_seen = CURRENT_TIMESTAMP, total_interactions = total_interactions + 1 WHERE user_id = ?",
                (user_id,),
            )
            row = conn.execute("SELECT total_interactions FROM users WHERE user_id = ?", (user_id,)).fetchone()
            count = row["total_interactions"]
            tier = "vip" if count >= 8 else ("regular" if count >= 3 else "new")
            conn.execute("UPDATE users SET relationship_tier = ? WHERE user_id = ?", (tier, user_id))
            updated = dict(conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())

            # Sync to Redis working memory (<1ms)
            redis_cache.set_fan_session(user_id, {
                "user_id": user_id,
                "tier": tier,
                "total_interactions": str(count),
                "last_seen": datetime.now().isoformat(),
            })
            return updated

    def save_fact(self, user_id: str, fact_key: str, fact_value: str, category: str = "general"):
        """Save or override a fact (contradiction handling: new value overrides old) across SQLite & Qdrant."""
        clean_key = fact_key.lower().strip()
        clean_val = str(fact_value).strip()

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO facts (user_id, category, fact_key, fact_value, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id, fact_key) DO UPDATE SET
                   fact_value = excluded.fact_value,
                   category = excluded.category,
                   updated_at = excluded.updated_at""",
                (user_id, category, clean_key, clean_val),
            )

        # Sync to Qdrant vector memory for dense semantic recall (3ms)
        vector_store.store_memory(
            user_id=user_id,
            text=f"{clean_key}: {clean_val}",
            category=category,
            metadata={"fact_key": clean_key, "fact_value": clean_val},
        )

    def get_semantic_memories(self, user_id: str, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Dense semantic memory retrieval from Qdrant vector store."""
        return vector_store.search_memories(user_id, query_text, limit=limit)

    def get_facts(self, user_id: str) -> Dict[str, str]:
        """Get all stored facts for a user."""
        with self._conn() as conn:
            rows = conn.execute("SELECT fact_key, fact_value FROM facts WHERE user_id = ?", (user_id,)).fetchall()
            return {r["fact_key"]: r["fact_value"] for r in rows}

    def record_message(self, user_id: str, role: str, content: str):
        """Append to conversation history."""
        with self._conn() as conn:
            conn.execute("INSERT INTO message_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))

    def get_recent_history(self, user_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Fetch last N messages for conversation context."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM message_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def extract_facts_heuristic(self, user_id: str, text: str):
        """Fast local pattern-based fact extraction (budget, sizes, favorite colors, product interest)."""
        lower = text.lower()

        # 1. Budget extraction
        budget_match = re.search(r'(?:budget|paisa|rupaye|rs\.?|inr)\s*(?:is|h|hai|around)?\s*(\d{2,5})', lower)
        if budget_match:
            self.save_fact(user_id, "budget", f"₹{budget_match.group(1)}", "shopping")

        # 2. Size extraction (XS, S, M, L, XL, XXL)
        size_match = re.search(r'\b(?:size|fit)\s*(?:is|h|hai|chahiye)?\s*(xs|s|m|l|xl|xxl|small|medium|large)\b', lower)
        if size_match:
            self.save_fact(user_id, "size_preference", size_match.group(1).upper(), "clothing")

        # 3. Product interest (serum, lipstick, dress, top, cream, perfume)
        for prod in ["serum", "lipstick", "dress", "saree", "kurti", "top", "cream", "sunscreen", "perfume"]:
            if prod in lower:
                self.save_fact(user_id, "product_interest", prod, "shopping")

        # 4. Color preference
        for color in ["red", "black", "pink", "white", "blue", "yellow", "purple"]:
            if f"{color} color" in lower or f"{color} dress" in lower or f"{color} pasand" in lower:
                self.save_fact(user_id, "favorite_color", color, "preferences")

    def get_memory_summary(self, user_id: str, current_query: str = "") -> str:
        """Compact memory context string formatted for LLM injection."""
        user = self.get_or_create_user(user_id)
        facts = self.get_facts(user_id)
        tier = user.get("relationship_tier", "new").upper()
        interactions = user.get("total_interactions", 1)

        summary_parts = [f"FAN STATUS: {tier} tier ({interactions} chats)"]
        if facts:
            fact_lines = [f"{k}: {v}" for k, v in facts.items()]
            summary_parts.append(f"KNOWN FACTS: {', '.join(fact_lines)}")

        if current_query:
            semantic_hits = self.get_semantic_memories(user_id, current_query, limit=3)
            if semantic_hits:
                hit_texts = [h["text"] for h in semantic_hits]
                summary_parts.append(f"SEMANTIC RECALL (Qdrant): {'; '.join(hit_texts)}")

        return " | ".join(summary_parts)
