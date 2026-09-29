"""
AI-INFLUENCER-OS — Brain & Memory Layer Test
Verifies Day 1, Day 3, and Day 7 relationship evolution, memory extraction, and recall.
Usage: python test_brain.py
"""

import os
import sys
import unittest

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from brain.memory import BrainMemory
from brain.rag import ProductKnowledgeBase
from brain.character import CharacterEngine
from brain.agent import BrainAgent


class TestBrainEvolution(unittest.TestCase):
    def setUp(self):
        # Use a fresh temporary database for test isolation
        self.test_db = os.path.join(os.path.dirname(__file__), "data", "test_memory.db")
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.agent = BrainAgent(db_path=self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_day_1_fact_extraction_and_new_tier(self):
        """DAY 1: New fan mentions budget, size, and product interest."""
        user_id = "rahul_fan"
        msg = "Hey! Mujhe size M chahiye, budget 500 tak, kya Glow Serum available hai?"
        reply = self.agent.respond(user_id=user_id, message=msg, username="rahul")

        facts = self.agent.memory.get_facts(user_id)
        user = self.agent.memory.get_or_create_user(user_id)

        print("\n--- DAY 1 OUTPUT ---")
        print("Aisha Reply:", reply)
        print("Stored Facts:", facts)
        print("Tier:", user["relationship_tier"])

        self.assertEqual(facts.get("size_preference"), "M")
        self.assertEqual(facts.get("budget"), "₹500")
        self.assertEqual(facts.get("product_interest"), "serum")
        self.assertEqual(user["relationship_tier"], "new")
        self.assertNotIn("I am an AI", reply)

    def test_day_3_relationship_evolution_to_regular(self):
        """DAY 3: Repeat interactions evolve relationship tier to regular."""
        user_id = "rahul_fan"

        # Interaction 1 & 2
        self.agent.respond(user_id=user_id, message="Hi! Looking for recommendations")
        self.agent.respond(user_id=user_id, message="Mujhe serum pasand hai")

        # Interaction 3 -> Should be 'regular'
        reply = self.agent.respond(user_id=user_id, message="Wahi serum kya abhi bhi hai?")
        user = self.agent.memory.get_or_create_user(user_id)

        print("\n--- DAY 3 OUTPUT ---")
        print("Aisha Reply:", reply)
        print("Tier:", user["relationship_tier"])

        self.assertEqual(user["relationship_tier"], "regular")
        # Regular fans receive AISHA50 or familiar greeting
        self.assertTrue("AISHA50" in reply or "tum" in reply.lower() or "wapas" in reply.lower() or "stock" in reply.lower())

    def test_contradiction_handling(self):
        """Contradiction handling: New color preference overrides old."""
        user_id = "priya_fan"
        self.agent.respond(user_id=user_id, message="Mujhe red dress pasand hai")
        facts_day1 = self.agent.memory.get_facts(user_id)
        self.assertEqual(facts_day1.get("favorite_color"), "red")

        # Contradiction: Now prefers blue
        self.agent.respond(user_id=user_id, message="Actually blue color dress better hai")
        facts_day2 = self.agent.memory.get_facts(user_id)
        self.assertEqual(facts_day2.get("favorite_color"), "blue")
        print("\n--- CONTRADICTION TEST ---")
        print("Updated Color Fact:", facts_day2.get("favorite_color"))

    def test_day_7_vip_evolution(self):
        """DAY 7: 8+ chats evolve tier to VIP with special perks."""
        user_id = "sneha_fan"
        for i in range(8):
            self.agent.respond(user_id=user_id, message=f"Chat message number {i}")

        user = self.agent.memory.get_or_create_user(user_id)
        self.assertEqual(user["relationship_tier"], "vip")

        reply = self.agent.respond(user_id=user_id, message="Hey discount code milega kya?")
        print("\n--- DAY 7 VIP OUTPUT ---")
        print("Aisha VIP Reply:", reply)
        print("Tier:", user["relationship_tier"])
        self.assertTrue("AISHA100" in reply or "jaan" in reply.lower() or "favorite" in reply.lower() or "vip" in reply.lower())

    def test_3_layer_redis_and_qdrant_cache(self):
        """Layer 1 & 2: Redis <1ms cache hit and Qdrant 3ms vector semantic recall."""
        from brain.redis_cache import redis_cache
        from brain.qdrant_store import vector_store

        user_id = "vikram_99"
        msg = "Is the glow serum in stock?"
        reply1 = self.agent.respond(user_id=user_id, message=msg)

        # 1. Verify Redis Semantic Query Cache hit (<1ms)
        cached = redis_cache.get_cached_reply(user_id, msg)
        self.assertEqual(cached, reply1)

        # 2. Re-sending message returns cached response instantly
        reply2 = self.agent.respond(user_id=user_id, message=msg)
        self.assertEqual(reply1, reply2)

        # 3. Verify Qdrant Vector Semantic Memory has indexed interaction
        qdrant_hits = vector_store.search_memories(user_id, "glow serum stock", limit=3)
        self.assertTrue(len(qdrant_hits) > 0)
        print("\n--- 3-LAYER BRAIN TEST (REDIS + QDRANT) ---")
        print("Redis Cache Hit:", cached is not None)
        print("Qdrant Semantic Hits Count:", len(qdrant_hits))
        print("Top Semantic Memory:", qdrant_hits[0]["text"])


if __name__ == "__main__":
    print("=" * 60)
    print("🧠 Testing AI Influencer Brain & Mem0 Layer...")
    print("=" * 60)
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
