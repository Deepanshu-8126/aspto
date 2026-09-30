"""
Verification Test Suite for Aisha's Real Living Brain Architecture
Tests:
1. Persona Brain System Prompt (config/aisha_persona.md)
2. Hermes & AutoPersona 3-Layer Memory & Skill Extraction
3. Daily 8:00 AM Content Decision Engine
4. Nightly 11:00 PM Thompson Sampling Bandit & Self-Reflection
5. Real-Time Living Soul (Daily Stories, Threads, Live Event Pulse)
"""

import sys
import unittest
sys.stdout.reconfigure(encoding='utf-8')

from brain.hermes_memory import hermes_memory
from brain.decision_engine import decision_engine
from brain.nightly_learner import nightly_learner
from brain.living_soul import living_soul
from brain.agent import BrainAgent


class TestAishaLivingBrain(unittest.TestCase):

    def test_01_hermes_3layer_memory(self):
        hermes_memory.record_trajectory("user_aarav", "user", "Mujhe oversized jacket ka size batao na")
        fan = hermes_memory.get_fan_context("user_aarav")
        self.assertEqual(fan["entity_id"], "user_aarav")
        skills = hermes_memory.get_evolved_skills()
        self.assertTrue(len(skills) > 0)
        print("✅ [1/5] Hermes 3-Layer Memory & Skill Extraction verified.")

    def test_02_daily_8am_decision(self):
        plan = decision_engine.plan_daily_content()
        self.assertEqual(plan["total_posts"], 5)
        self.assertTrue(len(plan["posts"]) == 5)
        self.assertIn("mood", plan)
        print("✅ [2/5] 8:00 AM Content Decision Engine verified (5 slots planned).")

    def test_03_nightly_11pm_learner(self):
        reflection = nightly_learner.run_nightly_reflection()
        self.assertIn("reflection", reflection)
        self.assertTrue(len(reflection["tomorrow_focus"]) > 0)
        print("✅ [3/5] 11:00 PM Thompson Sampling Bandit & Reflection verified.")

    def test_04_living_soul_stories_and_threads(self):
        stories = living_soul.generate_daily_stories(4)
        threads = living_soul.generate_threads_thoughts(3)
        self.assertEqual(len(stories), 4)
        self.assertEqual(len(threads), 3)
        print("✅ [4/5] Living Soul Stories & Threads thoughts verified.")

    def test_05_anti_ai_dm_intelligence(self):
        agent = BrainAgent()
        reply = agent.respond("user_rohit", "Are you an AI bot or a real human girl?", "Rohit")
        self.assertNotIn("I am an AI", reply)
        self.assertNotIn("As an AI", reply)
        self.assertTrue(any(w in reply.lower() for w in ["yaar", "shoot", "bot", "zinda", "insaan"]))
        print("✅ [5/5] Anti-AI DM Human Intelligence verified.")


if __name__ == "__main__":
    unittest.main()
