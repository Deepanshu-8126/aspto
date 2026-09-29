"""
AIInfluencerOS — Gradio Dashboard (Local, Lightweight)
Runs on i5 laptop for monitoring, brand management, and manual control.
"""

import os
import sys
import json
import asyncio

import yaml
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from local import database as db
from local.cloud_client import CloudClient


# ── Config ───────────────────────────────────────────────

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()
db.init_db()

# Seed brands from JSON
brands_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "brands.json")
db.seed_brands_from_json(brands_json)


# ── Dashboard Functions ──────────────────────────────────

def get_status_html():
    """Generate pipeline status HTML."""
    analytics = db.get_analytics()
    today_posts = db.get_today_posts()

    cards = f"""
    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:16px; margin-bottom:24px;">
        <div style="background:linear-gradient(135deg, #667eea, #764ba2); color:white; padding:24px; border-radius:16px; text-align:center;">
            <div style="font-size:32px; font-weight:700;">{analytics['total_posts']}</div>
            <div style="opacity:0.9; margin-top:4px;">Total Posts</div>
        </div>
        <div style="background:linear-gradient(135deg, #f093fb, #f5576c); color:white; padding:24px; border-radius:16px; text-align:center;">
            <div style="font-size:32px; font-weight:700;">{analytics['today_posts']}</div>
            <div style="opacity:0.9; margin-top:4px;">Today</div>
        </div>
        <div style="background:linear-gradient(135deg, #4facfe, #00f2fe); color:white; padding:24px; border-radius:16px; text-align:center;">
            <div style="font-size:32px; font-weight:700;">{analytics['total_views']}</div>
            <div style="opacity:0.9; margin-top:4px;">Views</div>
        </div>
        <div style="background:linear-gradient(135deg, #43e97b, #38f9d7); color:white; padding:24px; border-radius:16px; text-align:center;">
            <div style="font-size:32px; font-weight:700;">{analytics['total_likes']}</div>
            <div style="opacity:0.9; margin-top:4px;">Likes</div>
        </div>
        <div style="background:linear-gradient(135deg, #fa709a, #fee140); color:white; padding:24px; border-radius:16px; text-align:center;">
            <div style="font-size:32px; font-weight:700;">{analytics['total_leads']}</div>
            <div style="opacity:0.9; margin-top:4px;">DM Leads</div>
        </div>
    </div>
    """

    if today_posts:
        rows = ""
        for p in today_posts:
            status_color = {
                "posted": "#43e97b",
                "generated": "#4facfe",
                "pending": "#ffd93d",
                "failed": "#f5576c",
            }.get(p["status"], "#999")

            rows += f"""
            <tr>
                <td style="padding:12px;">{p['id']}</td>
                <td style="padding:12px;">{p['topic'][:40] if p['topic'] else 'N/A'}</td>
                <td style="padding:12px;">
                    <span style="background:{status_color}; color:white; padding:4px 12px; border-radius:20px; font-size:12px;">
                        {p['status']}
                    </span>
                </td>
                <td style="padding:12px;">{p['timestamp'][:16] if p['timestamp'] else ''}</td>
            </tr>
            """

        cards += f"""
        <h3 style="margin-top:16px;">Today's Posts</h3>
        <table style="width:100%; border-collapse:collapse; background:white; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background:#f8f9fa;">
                    <th style="padding:12px; text-align:left;">ID</th>
                    <th style="padding:12px; text-align:left;">Topic</th>
                    <th style="padding:12px; text-align:left;">Status</th>
                    <th style="padding:12px; text-align:left;">Time</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """

    return cards


def get_brands_data():
    """Get brands as a list for the table."""
    brands = db.list_brands(active_only=False)
    return [[b["id"], b["name"], b["product"], b["price"], "✅" if b["active"] else "❌"] for b in brands]


def add_brand_fn(name, product, price, link, pitch):
    if not name or not product:
        return "❌ Name and Product are required", get_brands_data()
    brand_id = db.add_brand(name, product, price, link, pitch)
    return f"✅ Brand #{brand_id} added!", get_brands_data()


def remove_brand_fn(brand_id):
    try:
        db.delete_brand(int(brand_id))
        return f"✅ Brand #{brand_id} deactivated", get_brands_data()
    except Exception as e:
        return f"❌ Error: {e}", get_brands_data()


def trigger_generation(topic, brand_id):
    """Trigger generation via cloud API."""
    try:
        cloud = CloudClient(CONFIG["cloud"]["gradio_url"])
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(cloud.generate(topic, int(brand_id)))
        loop.run_until_complete(cloud.close())
        loop.close()

        if isinstance(result, dict):
            return f"✅ Queued! Task ID: {result.get('task_id', 'unknown')}"
        return f"✅ Queued: {result}"
    except Exception as e:
        return f"❌ Error: {e}"


def get_post_history():
    """Get recent posts for the history table."""
    posts = db.get_recent_posts(50)
    return [
        [p["id"], p["topic"][:30] if p["topic"] else "", p["status"],
         p["ig_url"][:40] if p["ig_url"] else "", p["timestamp"][:16] if p["timestamp"] else ""]
        for p in posts
    ]


def get_leads_data():
    """Get DM leads for the table."""
    leads = db.get_dm_leads(limit=50)
    return [
        [l["id"], l["platform"], l["username"], l["message"][:40] if l["message"] else "",
         l["status"], l["timestamp"][:16] if l["timestamp"] else ""]
        for l in leads
    ]


# ── Gradio App ───────────────────────────────────────────

def build_dashboard():
    """Build the monitoring dashboard."""

    custom_css = """
    .gradio-container { max-width: 1200px !important; }
    .dashboard-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5em !important;
        font-weight: 800 !important;
    }
    """

    with gr.Blocks(
        title="AIInfluencerOS Dashboard",
    ) as app:

        gr.Markdown("# 🎬 AIInfluencerOS", elem_classes=["dashboard-title"])
        gr.Markdown("*Your AI influencer command center*")

        # ── Tab: Status ──
        with gr.Tab("📊 Status", id="status"):
            status_html = gr.HTML(value=get_status_html)
            refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
            refresh_btn.click(get_status_html, None, status_html)

        # ── Tab: Generate ──
        with gr.Tab("🎬 Generate", id="generate"):
            with gr.Row():
                gen_topic = gr.Textbox(label="Topic", placeholder="morning skincare routine", scale=3)
                gen_brand = gr.Number(label="Brand ID (0 = none)", value=0, precision=0, scale=1)
            gen_btn = gr.Button("🚀 Generate Reel", variant="primary", size="lg")
            gen_output = gr.Textbox(label="Result", interactive=False)
            gen_btn.click(trigger_generation, [gen_topic, gen_brand], gen_output)

        # ── Tab: Brands ──
        with gr.Tab("🏷️ Brands", id="brands"):
            brands_table = gr.Dataframe(
                value=get_brands_data,
                headers=["ID", "Name", "Product", "Price", "Active"],
                interactive=False,
            )

            gr.Markdown("### Add Brand")
            with gr.Row():
                brand_name = gr.Textbox(label="Name", placeholder="GlowUp")
                brand_product = gr.Textbox(label="Product", placeholder="Vitamin C Serum")
                brand_price = gr.Textbox(label="Price", placeholder="₹499")
            with gr.Row():
                brand_link = gr.Textbox(label="Link", placeholder="https://...")
                brand_pitch = gr.Textbox(label="Pitch", placeholder="Casual recommendation text")

            add_brand_btn = gr.Button("➕ Add Brand", variant="primary")
            add_brand_result = gr.Textbox(label="Result", interactive=False)
            add_brand_btn.click(
                add_brand_fn,
                [brand_name, brand_product, brand_price, brand_link, brand_pitch],
                [add_brand_result, brands_table],
            )

            gr.Markdown("### Remove Brand")
            with gr.Row():
                remove_id = gr.Number(label="Brand ID to remove", precision=0)
                remove_btn = gr.Button("🗑️ Remove", variant="stop")
            remove_result = gr.Textbox(label="Result", interactive=False)
            remove_btn.click(remove_brand_fn, remove_id, [remove_result, brands_table])

        # ── Tab: Post History ──
        with gr.Tab("📜 History", id="history"):
            history_table = gr.Dataframe(
                value=get_post_history,
                headers=["ID", "Topic", "Status", "IG URL", "Time"],
                interactive=False,
            )
            refresh_history = gr.Button("🔄 Refresh")
            refresh_history.click(get_post_history, None, history_table)

        # ── Tab: DM Leads ──
        with gr.Tab("📩 DM Leads", id="leads"):
            leads_table = gr.Dataframe(
                value=get_leads_data,
                headers=["ID", "Platform", "Username", "Message", "Status", "Time"],
                interactive=False,
            )
            refresh_leads = gr.Button("🔄 Refresh")
            refresh_leads.click(get_leads_data, None, leads_table)

        # ── Tab: Settings ──
        with gr.Tab("⚙️ Settings", id="settings"):
            gr.Markdown("### Configuration")
            gr.Markdown(f"""
            | Setting | Value |
            |---------|-------|
            | Cloud GPU URL | `{CONFIG['cloud']['gradio_url']}` |
            | IG Username | `{CONFIG['instagram']['username']}` |
            | Max Posts/Day | `{CONFIG['instagram']['max_posts_per_day']}` |
            | Max DMs/Day | `{CONFIG['whatsapp']['max_dms_per_day']}` |
            | Timezone | `{CONFIG['scheduler']['timezone']}` |
            | Video Resolution | `{CONFIG['video']['width']}x{CONFIG['video']['height']}` |
            """)

            gr.Markdown("### Post Schedule")
            times = CONFIG.get("scheduler", {}).get("post_times", [])
            gr.Markdown("  \n".join([f"• **{t}**" for t in times]))

    return app


# ── Main ─────────────────────────────────────────────────

if __name__ == "__main__":
    app = build_dashboard()
    app.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        show_error=True,
    )
