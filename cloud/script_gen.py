"""
AIInfluencerOS — Script Generation (Gemini API Free Tier)
Generates 30-sec reel scripts with hooks, brand mentions, and captions.
Uses the `google-genai` SDK (the official, non-deprecated client).
"""

import os
import json
import re
from google import genai


_client = None


def load_personality(config_dir: str = None) -> dict:
    """Load personality.json from config directory."""
    if config_dir is None:
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
    path = os.path.join(config_dir, "personality.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def init_gemini(api_key: str):
    """Initialize Gemini client."""
    global _client
    _client = genai.Client(api_key=api_key)


def generate_script(
    topic: str,
    brand: dict = None,
    api_key: str = None,
    model_name: str = "gemini-2.0-flash",
    personality: dict = None,
) -> dict:
    """
    Generate a 30-sec reel script.

    Returns:
        {
            "hook": str,
            "script": str,
            "caption": str,
            "hashtags": list[str],
            "cta": str,
            "image_prompt": str,
        }
    """
    global _client
    if api_key:
        init_gemini(api_key)

    if _client is None:
        raise RuntimeError("Gemini not initialized. Call init_gemini(api_key) first.")

    if personality is None:
        personality = load_personality()

    brand_context = ""
    if brand:
        brand_context = f"""
BRAND TO MENTION:
- Product: {brand.get('product', '')}
- Brand: {brand.get('name', '')}
- Price: {brand.get('price', '')}
- Pitch Style: {brand.get('pitch', '')}
Mention the product casually like recommending to a friend. NO hard sell.
"""

    persona = personality
    prompt = f"""You are {persona['name']}, a {persona['age']}-year-old {persona['niche'][0]} influencer.

PERSONALITY:
- Tone: {persona['tone']['style']}
- Energy: {persona['tone']['energy']}
- Language: {persona['language']['primary']} (mix ratio: {persona['language']['mix_ratio']})
- Filler words: {', '.join(persona['language']['filler_words'])}

CONTENT RULES:
- Max {persona['content_rules']['max_script_words']} words
- Structure: {' → '.join(persona['content_rules']['structure'])}
- Hook style (pick one): {', '.join(persona['content_rules']['hook_styles'])}
- BANNED words: {', '.join(persona['content_rules']['banned_words'])}
{brand_context}

TASK: Write a 30-second Instagram Reel script about "{topic}".

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no code blocks):
{{
    "hook": "First 3 seconds — attention grabber",
    "script": "Full spoken script (max {persona['content_rules']['max_script_words']} words). Include natural pauses marked with [pause].",
    "caption": "Instagram caption (2-3 lines, engaging, with emoji)",
    "hashtags": ["tag1", "tag2", "...up to 20 hashtags"],
    "cta": "Call to action for end of video",
    "image_prompt": "Detailed prompt to generate the avatar image for this reel. Describe outfit, setting, expression, lighting. Style: {persona['visual_identity']['aesthetic']}"
}}
"""

    response = _client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={
            "temperature": 0.85,
            "max_output_tokens": 1024,
        },
    )

    text = response.text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract JSON from response
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            result = json.loads(match.group())
        else:
            result = {
                "hook": topic,
                "script": text[:500],
                "caption": f"✨ {topic} ✨",
                "hashtags": [topic.replace(" ", ""), "reels", "viral", "trending"],
                "cta": "Follow for more!",
                "image_prompt": f"Young woman, {topic}, warm lighting, clean aesthetic",
            }

    # Ensure all keys exist
    for key in ("hook", "script", "caption", "hashtags", "cta", "image_prompt"):
        if key not in result:
            result[key] = ""

    if isinstance(result["hashtags"], str):
        result["hashtags"] = [h.strip("#").strip() for h in result["hashtags"].split() if h]

    return result


def generate_caption_only(topic: str, api_key: str = None, model_name: str = "gemini-2.0-flash") -> dict:
    """Generate just caption + hashtags for a topic."""
    global _client
    if api_key:
        init_gemini(api_key)

    if _client is None:
        raise RuntimeError("Gemini not initialized. Call init_gemini(api_key) first.")

    prompt = f"""Write an Instagram Reel caption for topic: "{topic}"

RESPOND IN JSON:
{{
    "caption": "2-3 line engaging caption with emojis",
    "hashtags": ["15 to 20 relevant hashtags"]
}}"""

    response = _client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    text = response.text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "caption": f"✨ {topic} ✨\nDouble tap if you agree! 💕",
            "hashtags": [topic.replace(" ", ""), "reels", "trending", "viral", "explore"],
        }
