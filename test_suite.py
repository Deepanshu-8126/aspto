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


class TestViralTrendEngine(unittest.TestCase):
    """aman-a-k/viralis + mutonby/openshorts"""
    def test_trend_detection_and_ranking(self):
        from actions.trend_engine import ViralTrendEngine
        engine = ViralTrendEngine()
        trends = engine.fetch_trending_topics(limit=5)
        self.assertGreaterEqual(len(trends), 3)
        top = engine.auto_select_best_trend()
        self.assertIsNotNone(top)
        self.assertIn("score", top)
        self.assertGreaterEqual(top["score"], 0.70)

    def test_openshorts_slicing(self):
        from actions.trend_engine import OpenShortsClipper
        clipper = OpenShortsClipper()
        clips = clipper.detect_viral_segments(duration_sec=60)
        self.assertTrue(len(clips) > 0)
        self.assertIn("start", clips[0])
        self.assertIn("end", clips[0])


class TestFaceEngine(unittest.TestCase):
    """facefusion/facefusion + Gourieff/ComfyUI-ReActor + LoRA"""
    def test_triple_face_lock_pipeline(self):
        from actions.face_engine import FaceFusionEngine, ReActorNodeBuilder
        ff = FaceFusionEngine()
        status = ff.is_installed()
        self.assertIsInstance(status, bool)

        builder = ReActorNodeBuilder()
        workflow = builder.generate_comfyui_workflow("actor_node", "influencer.png")
        self.assertIn("node_id", workflow)
        self.assertEqual(workflow["class_type"], "ReActorFaceSwap")


class TestVoiceEngine(unittest.TestCase):
    """RVC-Boss/GPT-SoVITS + QwenLM/Qwen3-TTS"""
    def test_voice_cloning_manager(self):
        from cloud.voice_engine import VoiceCloningManager
        manager = VoiceCloningManager()
        self.assertIn("qwen3_tts", manager.engines)
        self.assertIn("gpt_sovits", manager.engines)
        # Verify voice synthesis output path structure
        out_path = manager.synthesize("Hello world test voice", engine="qwen3_tts")
        self.assertTrue(str(out_path).endswith(".wav"))


class TestVideoEngine(unittest.TestCase):
    """Wan-Video/Wan2.2 + Lightricks/LTX-2.5 + duixcom/Duix-Avatar"""
    def test_unified_video_manager(self):
        from cloud.video_engine import UnifiedVideoManager
        manager = UnifiedVideoManager()
        engines = manager.list_available_engines()
        self.assertIn("wan2.2", engines)
        self.assertIn("ltx_2.5", engines)
        self.assertIn("duix_avatar", engines)

        res = manager.generate("A chic model walking down the ramp", engine="wan2.2")
        self.assertEqual(res["engine"], "wan2.2")
        self.assertEqual(res["status"], "success")


class TestMultiPublisher(unittest.TestCase):
    """Agentfy-io/Agentfy + cedonulfi/automie + ilias20055/Auto-Reels-Generator"""
    def test_agentfy_5_platform_broadcast(self):
        from actions.multi_publisher import AgentfyMultiPublisher
        publisher = AgentfyMultiPublisher()
        results = publisher.broadcast_to_all(
            content_path="test_reel.mp4",
            caption="Viral AI influencer reel #ai #trending",
            platforms=["instagram", "youtube_shorts", "tiktok", "x_twitter", "whatsapp"]
        )
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r["status"] == "published" for r in results.values()))

    def test_automie_anti_ban_shield(self):
        from actions.multi_publisher import AutomieAntiBanShield
        shield = AutomieAntiBanShield()
        delay = shield.compute_human_delay()
        self.assertGreaterEqual(delay, 2.0)
        self.assertLessEqual(delay, 12.0)
        profile = shield.get_browser_profile()
        self.assertIn("user_agent", profile)
        self.assertIn("viewport", profile)


class TestWan27AndVideoStack(unittest.TestCase):
    """Wan2.7, HappyHorse-1.0, SkyReels-V2, HunyuanVideo-1.5"""
    def test_wan27_first_last_frame_control(self):
        from cloud.video_engine import Wan27ControlEngine
        engine = Wan27ControlEngine()
        out = engine.generate_controlled_video(
            prompt="Influencer transitions from red dress to evening gown",
            first_frame="output/avatar.png",
            last_frame="output/pose.png",
            duration=3,
        )
        self.assertTrue(out.endswith(".mp4"))

    def test_happyhorse_4k(self):
        from cloud.video_engine import HappyHorse10Engine
        engine = HappyHorse10Engine()
        out = engine.generate_4k_cinematic("Ultra realistic 4k influencer catwalk", duration=3)
        self.assertTrue(out.endswith(".mp4"))

    def test_skyreels_expressions(self):
        from cloud.video_engine import SkyReelsV2Engine
        engine = SkyReelsV2Engine()
        self.assertIn("confident_smile", engine.SUPPORTED_EXPRESSIONS)
        self.assertIn("sultry", engine.SUPPORTED_EXPRESSIONS)
        self.assertIn("wink", engine.SUPPORTED_EXPRESSIONS)
        out = engine.generate_expressive_reel(
            prompt="dancing with lively facial cues",
            image_path="output/avatar.png",
            expression="sultry",
            duration=3,
        )
        self.assertTrue(out.endswith(".mp4"))

    def test_hunyuan_75s_continuous(self):
        from cloud.video_engine import HunyuanVideo15Engine
        engine = HunyuanVideo15Engine()
        out = engine.generate_continuous_reel("A full 60-second vlog style walk", duration=60)
        self.assertTrue(out.endswith(".mp4"))

    def test_master_manager_discovery(self):
        from cloud.video_engine import UnifiedVideoManager
        mgr = UnifiedVideoManager()
        engines = mgr.list_available_engines()
        self.assertIn("wan2.2_flf2v", engines)
        self.assertIn("wan2.2", engines)
        self.assertIn("hunyuan_1.5", engines)
        self.assertIn("happyhorse", engines)
        self.assertIn("skyreels_v2", engines)



class TestHyperFrames(unittest.TestCase):
    """HeyGen/HyperFrames HTML/CSS/JS Dynamic Video Overlays"""
    def test_create_html_template(self):
        from actions.hyperframes import HyperFramesRenderer
        renderer = HyperFramesRenderer()
        html_file = renderer.create_html_overlay(
            headline="Top 3 Summer Fits You Need",
            theme_name="luxury_gold",
        )
        self.assertTrue(os.path.exists(html_file))
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Top 3 Summer Fits You Need", content)
        self.assertIn("caption-container", content)


class TestOpenBlurAgent(unittest.TestCase):
    """willhooi/openblur AI Squid Agent"""
    def test_autonomous_storyboard_planner(self):
        from actions.openblur_agent import OpenBlurSquidAgent
        agent = OpenBlurSquidAgent()
        plan = agent.plan_storyboard(topic="old money aesthetic", target_duration=30)
        self.assertEqual(plan["agent"], "willhooi/openblur")
        self.assertGreaterEqual(len(plan["scenes"]), 3)
        self.assertIn("music", plan)
        self.assertEqual(plan["music"]["tempo"], 128)


class TestDaanKieftStudio(unittest.TestCase):
    """DaanKieft/ai-influencer Local-First Studio Adapter"""
    def test_studio_profile_and_vite_export(self):
        from dashboard.studio_adapter import AIInfluencerStudioAdapter
        adapter = AIInfluencerStudioAdapter()
        profile = adapter.get_profile()
        self.assertIn("influencer", profile)
        self.assertEqual(profile["influencer"]["name"], "Aisha Verma")

        # Record generation
        gen = adapter.record_generation(
            topic="glass skin routine",
            video_url="output/video/reel_01.mp4",
            engine="wan2.7",
        )
        self.assertEqual(gen["topic"], "glass skin routine")

        # Vite config export
        vite = adapter.export_vite_config()
        self.assertEqual(vite["appName"], "AI-Influencer Studio")
        self.assertIn("endpoints", vite)


class TestChineseApache2Models(unittest.TestCase):
    """
    Validation for 100% Commercial-Safe, Apache 2.0 Chinese Open-Source Stack:
    - Tongyi-MAI/Z-Image-Turbo (3s / 6GB VRAM, #1 Arena)
    - Alibaba Qwen-Image-Edit (Inpainting & Face Lock)
    - Alibaba Qwen3-TTS (3s clone, 97ms, Emotion Control)
    - OpenBMB/Tsinghua VoxCPM2 & Alibaba CosyVoice 2
    """
    def test_zimage_turbo_and_qwen_image_edit(self):
        from cloud.image_gen import ZImageTurboClient, QwenImageEditClient, generate_zimage_turbo
        client = ZImageTurboClient()
        self.assertIsInstance(client.is_available(), bool)

        out_img = generate_zimage_turbo("ultra photorealistic young woman portrait")
        self.assertTrue(os.path.exists(out_img))
        self.assertTrue(out_img.endswith(".png"))

        editor = QwenImageEditClient()
        res = editor.edit_face_and_outfit(out_img, "change dress to silk cocktail gown")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["model"], "Qwen-Image-Edit-7B")

    def test_qwen3_tts_emotion_control(self):
        from cloud.voice_engine import Qwen3TTSEngine, VoiceCloningManager
        tts = Qwen3TTSEngine()
        self.assertIn("happy", tts.SUPPORTED_EMOTIONS)
        self.assertIn("sultry", tts.SUPPORTED_EMOTIONS)
        self.assertIn("excited", tts.SUPPORTED_EMOTIONS)

        out_happy = tts.clone_voice("Hello guys, welcome to my vlog!", emotion="happy")
        self.assertTrue(os.path.exists(out_happy))

        out_sultry = tts.clone_voice("Special giveaway link in bio!", emotion="sultry")
        self.assertTrue(os.path.exists(out_sultry))

        mgr = VoiceCloningManager()
        self.assertEqual(mgr.default_engine, "qwen3_tts")
        self.assertIn("voxcpm2", mgr.engines)
        self.assertIn("cosyvoice2", mgr.engines)


class TestAishaCharacterStudio(unittest.TestCase):
    """
    Tests for Open-Generative-AI inspired Aisha Character Studio & Reference Face Picker.
    """
    def test_character_profile_and_angles(self):
        from actions.character_studio import AishaCharacterStudio
        studio = AishaCharacterStudio()
        profile = studio.get_profile()
        self.assertEqual(profile["name"], "Aisha Verma")
        self.assertEqual(profile["age"], 24)
        self.assertIn("smiling", profile["angles"])
        self.assertIn("front_face", profile["angles"])

        # Test angle picker
        msg = studio.set_active_angle("smiling")
        self.assertIn("Active reference face set to: Smiling", msg)
        ref_path = studio.get_active_reference_image()
        self.assertTrue(os.path.exists(ref_path))

    def test_export_open_generative_ai_json(self):
        from actions.character_studio import AishaCharacterStudio
        studio = AishaCharacterStudio()
        out_json = "data/test_aisha_open_gen.json"
        res_path = studio.export_open_generative_ai_format(output_path=out_json)
        self.assertTrue(os.path.exists(res_path))

        import json
        with open(res_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["app"], "Open-Generative-AI")
        self.assertEqual(data["studio_tab"], "AI Influencer Studio")
        self.assertEqual(data["character"]["name"], "Aisha Verma")
        self.assertIn("promptModifier", data["character"])


class TestDailyBatchGenerator(unittest.TestCase):
    """
    Tests for 5 Posts/Day automated batch generator and schedule orchestration.
    """
    def test_schedule_slots_definition(self):
        from actions.daily_batch_generator import DailyBatchGenerator, DAILY_SCHEDULE_SLOTS
        generator = DailyBatchGenerator()
        slots = generator.get_schedule_slots()
        self.assertEqual(len(slots), 5)
        self.assertEqual(slots[0]["time"], "08:00")
        self.assertEqual(slots[1]["time"], "12:00")
        self.assertEqual(slots[2]["time"], "16:00")
        self.assertEqual(slots[3]["time"], "20:00")
        self.assertEqual(slots[4]["time"], "22:00")

    def test_generate_single_slot(self):
        from actions.daily_batch_generator import DailyBatchGenerator
        from local import database as db
        generator = DailyBatchGenerator()
        res = generator.generate_slot(slot_index=0)
        self.assertIn("post_id", res)
        self.assertGreater(res["post_id"], 0)
        self.assertEqual(res["time"], "08:00")
        self.assertEqual(res["status"], "generated")

        # Verify DB has this post
        db_post = db.get_post(res["post_id"])
        self.assertIsNotNone(db_post)
        self.assertEqual(db_post["status"], "generated")

    def test_export_open_generative_ai_schedule(self):
        from actions.daily_batch_generator import DailyBatchGenerator
        generator = DailyBatchGenerator()
        out_json = "data/test_daily_batch_open_gen.json"
        res_path = generator.export_open_generative_ai_batch(output_path=out_json)
        self.assertTrue(os.path.exists(res_path))

        import json
        with open(res_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["format"], "Open-Generative-AI Workflow Schedule")
        self.assertEqual(len(data["slots"]), 5)


class TestCommentToDMAgent(unittest.TestCase):
    """
    Tests for Xeven777/openinstadm automated comment-to-DM conversion agent.
    """
    def test_trigger_detection_and_dm_routing(self):
        from actions.comment_to_dm import OpenInstaDMAgent
        agent = OpenInstaDMAgent()

        # Trigger detection
        self.assertEqual(agent.detect_trigger("Where can I find the link to this dress?"), "link")
        self.assertEqual(agent.detect_trigger("What is the price of this product?"), "price")
        self.assertEqual(agent.detect_trigger("Love the outfit!"), "outfit")
        self.assertIsNone(agent.detect_trigger("Just a random nice comment"))

        # Process comment & lead conversion
        res = agent.process_comment("priya_sharma", "Can you send me the link please?")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["trigger"], "link")
        self.assertIn("AISHA50", res["dm_text"])
        self.assertGreater(res["lead_id"], 0)


class TestMubertMusicEngine(unittest.TestCase):
    """
    Tests for Mubert royalty-free AI background music generator.
    """
    def test_mood_track_generation(self):
        from actions.music_engine import MubertMusicEngine
        engine = MubertMusicEngine()
        track = engine.get_track_for_mood(mood="chill", duration=5)
        self.assertEqual(track["status"], "success")
        self.assertEqual(track["mood"], "chill")
        self.assertEqual(track["bpm"], 85)
        self.assertTrue(os.path.exists(track["track_path"]))


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Running AI-INFLUENCER-OS Test Suite...")
    print("=" * 60)
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
