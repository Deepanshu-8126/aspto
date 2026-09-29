"""
AI-INFLUENCER-OS — Master Brain Agent
Orchestrates: Mem0 Memory + Product RAG + Aisha Persona + LLM Generation.
100% Free, Local SQLite + Gemini 2.0 Flash / Free LLM fallback.
"""

import os
import json
import logging
from typing import Optional

from brain.memory import BrainMemory
from brain.rag import ProductKnowledgeBase
from brain.character import CharacterEngine
from brain.redis_cache import redis_cache
from brain.qdrant_store import vector_store

logger = logging.getLogger("brain_agent")

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class BrainAgent:
    """
    Master 3-Layer Brain Agent:
    - Layer 1: Redis Session & Brand Cache (<1ms)
    - Layer 2: Qdrant Vector Semantic Memory (3ms)
    - Layer 3: Mem0 Relationship Engine & Cold Storage
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        db_path: Optional[str] = None,
        brands_path: Optional[str] = None,
        personality_path: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.memory = BrainMemory(db_path=db_path) if db_path else BrainMemory()
        self.rag = ProductKnowledgeBase(brands_path=brands_path)
        self.character = CharacterEngine(personality_path=personality_path)
        self._gemini_client = None

        if HAS_GENAI and self.api_key and self.api_key != "CHANGE_ME":
            try:
                self._gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def respond(self, user_id: str, message: str, username: str = "", platform: str = "instagram") -> str:
        """
        Process incoming fan DM/comment using 3-layer architecture:
        1. Check Redis Semantic Cache (<1ms hit)
        2. Query Qdrant Dense Vector Memory (3ms)
        3. Retrieve Brand details via Redis Cache
        4. Synthesize with Gemini 2.0 Flash / Persona Engine
        5. Cache & index into Redis + Qdrant + SQLite
        """
        # Step 0: Check Redis Semantic Query Cache (<1ms hit)
        cached_reply = redis_cache.get_cached_reply(user_id, message)
        if cached_reply:
            logger.info(f"⚡ Redis Query Cache hit for user '{user_id}': returning in <1ms")
            return cached_reply

        # Step 1: Record interaction & extract facts (Syncs to Redis & Qdrant)
        user = self.memory.record_interaction(user_id)
        self.memory.extract_facts_heuristic(user_id, message)
        self.memory.record_message(user_id, "user", message)

        # Step 2: Instant Brand Lookup via Redis Cache or Product RAG (<1ms)
        matched_product = None
        for word in message.lower().split():
            cached_brand = redis_cache.get_cached_brand(word)
            if cached_brand:
                matched_product = cached_brand
                break
        if not matched_product:
            matched_product = self.rag.query(message)
            if matched_product:
                redis_cache.cache_brand(matched_product.get("product", ""), matched_product)

        product_ctx = self.rag.format_product_context(matched_product) if matched_product else None

        # Step 3: Dense semantic context with Qdrant vector memory
        memory_summary = self.memory.get_memory_summary(user_id, current_query=message)
        system_prompt = self.character.build_system_prompt(memory_summary, product_ctx)
        history = self.memory.get_recent_history(user_id, limit=6)

        # Step 4: Generate response via LLM / Persona Engine
        reply = self._generate_llm_reply(system_prompt, history, message, user)

        # Step 5: Sanitize response
        clean_reply = self.character.sanitize_response(reply)
        self.memory.record_message(user_id, "assistant", clean_reply)

        # Step 6: Store in Redis semantic cache + Qdrant vector memory
        redis_cache.set_cached_reply(user_id, message, clean_reply, ttl=1800)
        vector_store.store_memory(
            user_id=user_id,
            text=f"Q: {message} | A: {clean_reply}",
            category="conversation",
        )

        logger.info(f"Brain responded to {user.get('relationship_tier')} user '{user_id}': {clean_reply}")
        return clean_reply

    def _generate_llm_reply(self, system_prompt: str, history: list, current_message: str, user: dict) -> str:
        """Query Gemini or use authentic human conversational fallback."""
        if self._gemini_client:
            try:
                # Format conversation for Gemini
                contents = [f"{system_prompt}\n\nCONVERSATION HISTORY:"]
                for h in history[:-1]:  # Exclude current message already in history
                    role_tag = "Fan" if h["role"] == "user" else "Aisha"
                    contents.append(f"{role_tag}: {h['content']}")
                contents.append(f"Fan: {current_message}\nAisha:")

                full_prompt = "\n".join(contents)
                resp = self._gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=full_prompt,
                )
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"Gemini API generation error: {e}")

        # Intelligent Fallback matching relationship tier
        tier = user.get("relationship_tier", "new")
        facts = self.memory.get_facts(user["user_id"])
        product = facts.get("product_interest", "item")

        if tier == "vip":
            return (
                f"Arre meri jaan! 🥰 Tumhara message dekhte hi reply kiya. "
                f"Haan bilkul {product} available hai! Tumhare liye special code: AISHA100 ✨ Aur batao kaise ho?"
            )
        elif tier == "regular":
            return (
                f"Arre tum wapas aa gaye! 😄 Haan wahi {product} abhi stock mein hai. "
                f"Tumhare liye 50 off: code AISHA50 lagao! Link bhejoon kya? 💕"
            )
        else:
            return (
                f"Heyy babe! 💕 {self.character.get_busy_excuse()} "
                f"Haan bilkul! Yeh product maine khud use kiya hai, super aesthetic results hain ✨ Link bio mein hai ya DM karoon?"
            )
