"""
AI-INFLUENCER-OS — Full Automated Test Suite
Runs end-to-end unit and integration tests across all modules.
Usage: python test_suite.py
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


class TestMotionExtractor(unittest.TestCase):
    def test_parse_copy_command(self):
        from actions.motion_extractor import parse_line
        cmd = '/copy https://instagram.com/reel/123/ --dress "red satin gown" --bg "cyberpunk neon" --topic "epic dance"'
        res = parse_line(cmd)
        self.assertIsNotNone(res)
        self.assertEqual(res["url"], "https://instagram.com/reel/123/")
        self.assertEqual(res["dress"], "red satin gown")
        self.assertEqual(res["bg"], "cyberpunk neon")
        self.assertEqual(res["topic"], "epic dance")

    def test_parse_raw_line(self):
        from actions.motion_extractor import parse_line
        line = 'https://instagram.com/reel/456/ --dress "summer dress"'
        res = parse_line(line)
        self.assertIsNotNone(res)
        self.assertEqual(res["url"], "https://instagram.com/reel/456/")
        self.assertEqual(res["dress"], "summer dress")


class TestScriptGenerator(unittest.TestCase):
    def test_script_generation(self):
        from actions.generate_script import generate_script_and_caption
        data = generate_script_and_caption("dance vibes", "neon outfit")
        self.assertIn("caption", data)
        self.assertIn("hashtags", data)
        self.assertTrue(len(data["hashtags"]) > 0)


class TestHFClientRotation(unittest.TestCase):
    def test_token_rotation(self):
        from actions.hf_client import MultiAccountHFClient
        client = MultiAccountHFClient(
            video_space="user/video-gen",
            upscaler_space="user/upscaler",
            tokens=["token_alpha", "token_beta", "token_gamma"],
        )
        self.assertEqual(client.current_token, "token_alpha")
        client.rotate_token()
        self.assertEqual(client.current_token, "token_beta")
        client.rotate_token()
        self.assertEqual(client.current_token, "token_gamma")
        client.rotate_token()
        self.assertEqual(client.current_token, "token_alpha")


class TestDatabaseOperations(unittest.TestCase):
    def test_db_lifecycle(self):
        from local import database as db
        db.init_db()
        brand_id = db.add_brand("TestBrand", "TestPerfume", "49", "https://brand.com")
        self.assertGreater(brand_id, 0)
        brands = db.list_brands(active_only=True)
        self.assertTrue(any(b["id"] == brand_id for b in brands))

        post_id = db.create_post("dance", brand_id=brand_id)
        self.assertGreater(post_id, 0)
        db.update_post(post_id, status="posted", ig_url="https://instagram.com/reel/999/")
        post = db.get_post(post_id)
        self.assertEqual(post["status"], "posted")


class TestDashboardBuild(unittest.TestCase):
    def test_dashboard_blocks(self):
        from dashboard.app import build_dashboard
        app = build_dashboard()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Running AI-INFLUENCER-OS Test Suite...")
    print("=" * 60)
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
