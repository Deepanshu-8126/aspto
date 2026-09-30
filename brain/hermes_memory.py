"""
AI-INFLUENCER-OS — Hermes & AutoPersona 3-Layer Self-Evolving Memory
Architectural synthesis of:
- NousResearch/hermes-agent (65K+ Stars): Closed-loop self-evolution, skill extraction, cross-session user memory model.
- Ailta666508/AutoPersona (2026): 3-Layer Memory (Trajectory Memory, Workspace Memory, Persona Memory).
- BAI-LAB/MemoryOS (EMNLP 2025): Hierarchical consolidation & contextual retrieval.
100% Free, Local SQLite + Vector indexing. Zero paid APIs.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("hermes_memory")


class HermesMemoryEngine:
    """
    3-Layer Self-Evolving Memory Engine for Aisha:
    - Layer 1: Trajectory Memory (conversations, tool executions, feedback)
    - Layer 2: Workspace Memory (active content plans, current brand products, daily tasks)
    - Layer 3: Persona Memory (persistent self-narrative, relationships, fan mental models)
    """

    def __init__(self, db_path: str = "data/hermes_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Layer 1: Trajectory Memory (episodic & interaction turns)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trajectory_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    extracted_skills TEXT,
                    sentiment TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Layer 2: Workspace Memory (current tasks, active draft, daily mood)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Layer 3: Persona Memory (fan models, personal lore, relationships)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS persona_memory (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT, -- fan, friend, cat_mochi, mom, brand
                    name TEXT,
                    facts TEXT,
                    relationship_tier TEXT,
                    interaction_count INTEGER DEFAULT 1,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Self-Evolution Skills & Patterns Registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evolved_skills (
                    skill_id TEXT PRIMARY KEY,
                    skill_name TEXT,
                    description TEXT,
                    success_rate REAL DEFAULT 1.0,
                    usage_count INTEGER DEFAULT 1,
                    learned_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # ---------------------------------------------------------
    # Layer 1: Trajectory Memory & Skill Extraction (Hermes Pattern)
    # ---------------------------------------------------------
    def record_trajectory(self, user_id: str, role: str, content: str, session_id: str = "default"):
        """Records conversational trajectory turn and extracts reusable skills."""
        skills = self._extract_skills_heuristic(content, role)
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO trajectory_memory (session_id, user_id, role, content, extracted_skills)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, role, content, json.dumps(skills)),
            )
            conn.commit()

        # Update evolved skills registry
        for skill in skills:
            self._register_evolved_skill(skill)

    def _extract_skills_heuristic(self, content: str, role: str) -> List[str]:
        """Hermes self-evolution: identifies conversational skills learned from interactions."""
        skills = []
        c_lower = content.lower()
        if "size" in c_lower or "outfit" in c_lower or "pehna" in c_lower:
            skills.append("outfit_sizing_guidance")
        if "discount" in c_lower or "code" in c_lower:
            skills.append("discount_negotiation_incentive")
        if any(w in c_lower for w in ["ai", "bot", "fake", "robot"]):
            skills.append("playful_human_deflection")
        if any(w in c_lower for w in ["cafe", "travel", "waterfall", "beach"]):
            skills.append("lifestyle_recommendation")
        return skills

    def _register_evolved_skill(self, skill_name: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO evolved_skills (skill_id, skill_name, description, usage_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(skill_id) DO UPDATE SET
                    usage_count = usage_count + 1
                """,
                (skill_name, skill_name, f"Evolved conversational skill: {skill_name}"),
            )
            conn.commit()

    # ---------------------------------------------------------
    # Layer 2: Workspace Memory (AutoPersona)
    # ---------------------------------------------------------
    def set_workspace_state(self, key: str, value: Any):
        """Sets active workspace context (e.g. current mood, planned posts, active brand)."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO workspace_memory (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value) if not isinstance(value, str) else value),
            )
            conn.commit()

    def get_workspace_state(self, key: str, default: Any = None) -> Any:
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM workspace_memory WHERE key = ?", (key,)).fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]

    # ---------------------------------------------------------
    # Layer 3: Persona Memory & Fan Models (MemoryOS Consolidation)
    # ---------------------------------------------------------
    def update_fan_model(self, user_id: str, name: str = "", new_fact: Optional[str] = None):
        """Builds deep cross-session memory model for each follower (Hermes + Mem0)."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM persona_memory WHERE entity_id = ?", (user_id,)).fetchone()
            facts = []
            count = 1
            tier = "new"
            display_name = name or user_id

            if row:
                count = row["interaction_count"] + 1
                display_name = name or row["name"] or user_id
                try:
                    facts = json.loads(row["facts"])
                except Exception:
                    facts = []

            if new_fact and new_fact not in facts:
                facts.append(new_fact)

            # Evolve relationship tiers based on true engagement
            if count >= 10:
                tier = "vip"
            elif count >= 3:
                tier = "regular"

            conn.execute(
                """
                INSERT INTO persona_memory (entity_id, entity_type, name, facts, relationship_tier, interaction_count, last_seen)
                VALUES (?, 'fan', ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(entity_id) DO UPDATE SET
                    name = excluded.name,
                    facts = excluded.facts,
                    relationship_tier = excluded.relationship_tier,
                    interaction_count = excluded.interaction_count,
                    last_seen = CURRENT_TIMESTAMP
                """,
                (user_id, display_name, json.dumps(facts), tier, count),
            )
            conn.commit()

    def get_fan_context(self, user_id: str) -> Dict[str, Any]:
        """Retrieves cross-session mental model of a follower."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM persona_memory WHERE entity_id = ?", (user_id,)).fetchone()
            if not row:
                return {
                    "entity_id": user_id,
                    "name": user_id,
                    "relationship_tier": "new",
                    "facts": [],
                    "interaction_count": 0,
                }
            return {
                "entity_id": row["entity_id"],
                "name": row["name"],
                "relationship_tier": row["relationship_tier"],
                "facts": json.loads(row["facts"]) if row["facts"] else [],
                "interaction_count": row["interaction_count"],
            }

    def get_evolved_skills(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM evolved_skills ORDER BY usage_count DESC").fetchall()
            return [dict(r) for r in rows]


# Global singleton
hermes_memory = HermesMemoryEngine()
