"""
AIInfluencerOS — Enterprise SQLite Database Layer (Production Grade)
Handles high-concurrency WAL mode, automated schema migrations, zero-downtime backups,
affiliate & financial tracking, viral engagement scoring, and audit logging.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

logger = logging.getLogger("database")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "influencer.db")


@contextmanager
def get_connection(timeout: float = 10.0):
    """
    Thread-safe connection context manager with Write-Ahead Logging (WAL)
    and busy timeout to prevent 'database is locked' errors in concurrent jobs.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        conn.close()


def _safe_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """Safely adds a column if it doesn't already exist on pre-existing tables."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # Column already exists


def init_db():
    """
    Create and migrate all database tables to production grade schema.
    Applies non-destructive column migrations before executing indexing.
    """
    with get_connection() as conn:
        # Base table structures
        conn.executescript("""
            -- 1. Brands & Affiliate Monetization
            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                product TEXT NOT NULL,
                price TEXT,
                link TEXT,
                pitch TEXT,
                promo_code TEXT DEFAULT 'AISHA50',
                commission_rate REAL DEFAULT 10.0,
                total_revenue REAL DEFAULT 0.0,
                clicks INTEGER DEFAULT 0,
                category TEXT DEFAULT 'fashion',
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- 2. Multi-Platform Content & Video Generation Pipeline
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                topic TEXT NOT NULL,
                brand_id INTEGER,
                script TEXT,
                caption TEXT,
                hashtags TEXT,
                video_path TEXT,
                ig_url TEXT,
                platform TEXT DEFAULT 'instagram',
                post_type TEXT DEFAULT 'reel',
                resolution TEXT DEFAULT '1080x1920',
                status TEXT DEFAULT 'pending',
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                saves INTEGER DEFAULT 0,
                viral_score REAL DEFAULT 0.0,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                posted_at DATETIME,
                FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
            );

            -- 3. High-Ticket DM Leads & Affiliate Funnel
            CREATE TABLE IF NOT EXISTS dm_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                platform TEXT DEFAULT 'instagram',
                username TEXT NOT NULL,
                message TEXT,
                product_interest TEXT,
                relationship_tier TEXT DEFAULT 'new',
                intent TEXT DEFAULT 'general',
                sentiment TEXT DEFAULT 'positive',
                status TEXT DEFAULT 'new',
                converted INTEGER DEFAULT 0,
                conversion_value REAL DEFAULT 0.0,
                notes TEXT,
                last_contacted DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- 4. Settings & Configuration Store
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                category TEXT DEFAULT 'general',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- 5. Audit & Activity Event Log
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT,
                source TEXT DEFAULT 'system',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- 6. Marketing Campaigns & Brand Collabs
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand_id INTEGER,
                budget REAL DEFAULT 0.0,
                target_reach INTEGER DEFAULT 10000,
                status TEXT DEFAULT 'active',
                start_date DATE DEFAULT (DATE('now')),
                end_date DATE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
            );
        """)

        # Safe Column Additions for older DB versions (Migrator runs before index creation)
        _safe_add_column(conn, "brands", "promo_code", "TEXT DEFAULT 'AISHA50'")
        _safe_add_column(conn, "brands", "commission_rate", "REAL DEFAULT 10.0")
        _safe_add_column(conn, "brands", "total_revenue", "REAL DEFAULT 0.0")
        _safe_add_column(conn, "brands", "clicks", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "brands", "category", "TEXT DEFAULT 'fashion'")
        _safe_add_column(conn, "brands", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")

        _safe_add_column(conn, "posts", "platform", "TEXT DEFAULT 'instagram'")
        _safe_add_column(conn, "posts", "post_type", "TEXT DEFAULT 'reel'")
        _safe_add_column(conn, "posts", "resolution", "TEXT DEFAULT '1080x1920'")
        _safe_add_column(conn, "posts", "shares", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "posts", "saves", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "posts", "viral_score", "REAL DEFAULT 0.0")
        _safe_add_column(conn, "posts", "error_message", "TEXT")
        _safe_add_column(conn, "posts", "retry_count", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "posts", "posted_at", "DATETIME")

        _safe_add_column(conn, "dm_leads", "relationship_tier", "TEXT DEFAULT 'new'")
        _safe_add_column(conn, "dm_leads", "intent", "TEXT DEFAULT 'general'")
        _safe_add_column(conn, "dm_leads", "sentiment", "TEXT DEFAULT 'positive'")
        _safe_add_column(conn, "dm_leads", "converted", "INTEGER DEFAULT 0")
        _safe_add_column(conn, "dm_leads", "conversion_value", "REAL DEFAULT 0.0")
        _safe_add_column(conn, "dm_leads", "notes", "TEXT")
        _safe_add_column(conn, "dm_leads", "last_contacted", "DATETIME DEFAULT CURRENT_TIMESTAMP")

        _safe_add_column(conn, "settings", "category", "TEXT DEFAULT 'general'")

        # Performance Indexes (executed after columns are guaranteed to exist)
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
            CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts(timestamp);
            CREATE INDEX IF NOT EXISTS idx_posts_brand ON posts(brand_id);
            CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
            CREATE INDEX IF NOT EXISTS idx_posts_viral ON posts(viral_score);
            CREATE INDEX IF NOT EXISTS idx_dm_leads_platform ON dm_leads(platform);
            CREATE INDEX IF NOT EXISTS idx_dm_leads_status ON dm_leads(status);
            CREATE INDEX IF NOT EXISTS idx_dm_leads_tier ON dm_leads(relationship_tier);
            CREATE INDEX IF NOT EXISTS idx_dm_leads_username ON dm_leads(username);
            CREATE INDEX IF NOT EXISTS idx_brands_active ON brands(active);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_event ON audit_logs(event_type);
        """)


# ── Audit Logging ─────────────────────────────────────────────

def log_audit_event(
    event_type: str,
    details: str = "",
    source: str = "system",
    conn: Optional[sqlite3.Connection] = None,
):
    """Appends an event to the immutable audit log."""
    try:
        if conn is not None:
            conn.execute(
                "INSERT INTO audit_logs (event_type, details, source) VALUES (?, ?, ?)",
                (event_type, str(details), source),
            )
        else:
            with get_connection() as c:
                c.execute(
                    "INSERT INTO audit_logs (event_type, details, source) VALUES (?, ?, ?)",
                    (event_type, str(details), source),
                )
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")


# ── Brands CRUD & Affiliate Tracking ──────────────────────────

def add_brand(
    name: str,
    product: str,
    price: str = "",
    link: str = "",
    pitch: str = "",
    promo_code: str = "AISHA50",
    commission_rate: float = 10.0,
    category: str = "fashion",
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO brands (name, product, price, link, pitch, promo_code, commission_rate, category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, product, price, link, pitch, promo_code, commission_rate, category),
        )
        brand_id = cur.lastrowid
        log_audit_event("BRAND_ADDED", f"Brand '{name}' (ID: {brand_id}) added", source="brands", conn=conn)
        return brand_id


def get_brand(brand_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
        return dict(row) if row else None


def list_brands(active_only: bool = True) -> List[dict]:
    with get_connection() as conn:
        query = "SELECT * FROM brands"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name ASC"
        return [dict(r) for r in conn.execute(query).fetchall()]


def update_brand(brand_id: int, **kwargs) -> bool:
    allowed = {"name", "product", "price", "link", "pitch", "promo_code", "commission_rate",
               "total_revenue", "clicks", "category", "active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False
    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE brands SET {set_clause} WHERE id = ?", (*fields.values(), brand_id))
        return True


def track_brand_click(brand_id: int):
    """Increments affiliate click counter for brand."""
    with get_connection() as conn:
        conn.execute("UPDATE brands SET clicks = clicks + 1 WHERE id = ?", (brand_id,))


def add_brand_revenue(brand_id: int, amount: float, conn: Optional[sqlite3.Connection] = None):
    """Records tracked commission earnings from a brand conversion."""
    if conn is not None:
        conn.execute(
            "UPDATE brands SET total_revenue = total_revenue + ? WHERE id = ?",
            (amount, brand_id),
        )
        log_audit_event("REVENUE_RECORDED", f"INR {amount:.2f} credited to Brand ID {brand_id}", source="finance", conn=conn)
    else:
        with get_connection() as c:
            c.execute(
                "UPDATE brands SET total_revenue = total_revenue + ? WHERE id = ?",
                (amount, brand_id),
            )
            log_audit_event("REVENUE_RECORDED", f"INR {amount:.2f} credited to Brand ID {brand_id}", source="finance", conn=c)


def delete_brand(brand_id: int) -> bool:
    with get_connection() as conn:
        conn.execute("UPDATE brands SET active = 0 WHERE id = ?", (brand_id,))
        log_audit_event("BRAND_DEACTIVATED", f"Brand ID {brand_id} set to inactive", source="brands", conn=conn)
        return True


def seed_brands_from_json(json_path: str):
    """Sync brands from config/brands.json into production DB."""
    if not os.path.exists(json_path):
        return
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for b in data.get("brands", []):
        existing = get_brand(b["id"])
        if not existing:
            add_brand(
                name=b["name"],
                product=b["product"],
                price=b.get("price", ""),
                link=b.get("link", ""),
                pitch=b.get("pitch", ""),
                promo_code=b.get("promo_code", "AISHA50"),
                commission_rate=float(b.get("commission_rate", 10.0)),
                category=b.get("category", "fashion"),
            )


# ── Posts & Video Pipeline CRUD ───────────────────────────────

def calculate_viral_score(likes: int, comments: int, shares: int, saves: int, views: int) -> float:
    """
    Industry weighted engagement score normalized per 1,000 views:
    Score = (Likes*1 + Comments*3 + Shares*5 + Saves*4) / (Views + 1) * 1000
    """
    if views <= 0:
        return 0.0
    weighted_interactions = (likes * 1) + (comments * 3) + (shares * 5) + (saves * 4)
    return round((weighted_interactions / views) * 1000, 2)


def create_post(
    topic: str,
    brand_id: Optional[int] = None,
    script: str = "",
    caption: str = "",
    hashtags: str = "",
    video_path: str = "",
    platform: str = "instagram",
    post_type: str = "reel",
    resolution: str = "1080x1920",
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO posts (topic, brand_id, script, caption, hashtags, video_path,
                                  platform, post_type, resolution, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (topic, brand_id, script, caption, hashtags, video_path, platform, post_type, resolution),
        )
        post_id = cur.lastrowid
        log_audit_event("POST_CREATED", f"Post ID {post_id} created for topic '{topic}'", source="pipeline", conn=conn)
        return post_id


def update_post(post_id: int, **kwargs) -> bool:
    allowed = {
        "script", "caption", "hashtags", "video_path", "ig_url", "platform",
        "post_type", "resolution", "status", "views", "likes", "comments",
        "shares", "saves", "viral_score", "error_message", "retry_count", "posted_at"
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    # Recalculate viral score if interaction metrics were updated
    if any(k in fields for k in ("views", "likes", "comments", "shares", "saves")):
        p = get_post(post_id)
        if p:
            v = fields.get("views", p.get("views", 0))
            l = fields.get("likes", p.get("likes", 0))
            c = fields.get("comments", p.get("comments", 0))
            sh = fields.get("shares", p.get("shares", 0))
            sa = fields.get("saves", p.get("saves", 0))
            fields["viral_score"] = calculate_viral_score(l, c, sh, sa, v)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE posts SET {set_clause} WHERE id = ?", (*fields.values(), post_id))
        return True


def record_post_success(post_id: int, ig_url: str):
    """Marks post as successfully posted to Instagram with timestamp."""
    update_post(
        post_id,
        status="posted",
        ig_url=ig_url,
        posted_at=datetime.now().isoformat(),
        error_message="",
    )
    log_audit_event("POST_PUBLISHED", f"Post ID {post_id} published: {ig_url}", source="instagram")


def record_post_failure(post_id: int, error_msg: str):
    """Records posting failure and increments retry counter."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE posts SET status = 'failed', error_message = ?, retry_count = retry_count + 1
               WHERE id = ?""",
            (error_msg, post_id),
        )
        log_audit_event("POST_FAILED", f"Post ID {post_id} failed: {error_msg}", source="instagram", conn=conn)


def get_post(post_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None


def get_recent_posts(limit: int = 20) -> List[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM posts ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_today_posts() -> List[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM posts WHERE DATE(timestamp) = DATE('now', 'localtime') ORDER BY timestamp DESC"
        ).fetchall()]


def get_posts_by_status(status: str) -> List[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM posts WHERE status = ? ORDER BY timestamp DESC", (status,)
        ).fetchall()]


def get_top_performing_posts(limit: int = 10) -> List[dict]:
    """Returns highest viral engagement posts for AI content repurposing."""
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM posts WHERE status = 'posted' ORDER BY viral_score DESC, views DESC LIMIT ?",
            (limit,)
        ).fetchall()]


# ── DM Leads & Affiliate Conversion Funnel ────────────────────

def add_dm_lead(
    platform: str,
    username: str,
    message: str,
    product_interest: str = "",
    relationship_tier: str = "new",
    intent: str = "general",
    sentiment: str = "positive",
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO dm_leads (platform, username, message, product_interest,
                                     relationship_tier, intent, sentiment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (platform, username, message, product_interest, relationship_tier, intent, sentiment),
        )
        lead_id = cur.lastrowid
        log_audit_event("LEAD_CAPTURED", f"Lead ID {lead_id} from @{username} on {platform}", source="dm_funnel", conn=conn)
        return lead_id


def get_dm_leads(platform: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> List[dict]:
    with get_connection() as conn:
        query = "SELECT * FROM dm_leads WHERE 1=1"
        params: list = []
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def update_dm_lead(lead_id: int, status: str, notes: Optional[str] = None) -> bool:
    with get_connection() as conn:
        if notes:
            conn.execute(
                "UPDATE dm_leads SET status = ?, notes = ?, last_contacted = CURRENT_TIMESTAMP WHERE id = ?",
                (status, notes, lead_id),
            )
        else:
            conn.execute(
                "UPDATE dm_leads SET status = ?, last_contacted = CURRENT_TIMESTAMP WHERE id = ?",
                (status, lead_id),
            )
        return True


def record_lead_conversion(lead_id: int, value: float, brand_id: Optional[int] = None) -> bool:
    """Marks a lead as converted and credits revenue to the associated brand."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE dm_leads SET status = 'converted', converted = 1,
                                   conversion_value = ?, last_contacted = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (value, lead_id),
        )
        if brand_id:
            add_brand_revenue(brand_id, value, conn=conn)
        log_audit_event("LEAD_CONVERTED", f"Lead ID {lead_id} converted for INR {value:.2f}", source="dm_funnel", conn=conn)
    return True


# ── Settings & Configuration Store ────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def get_setting_int(key: str, default: int = 0) -> int:
    val = get_setting(key, str(default))
    try:
        return int(val)
    except ValueError:
        return default


def get_setting_bool(key: str, default: bool = False) -> bool:
    val = get_setting(key, str(default)).strip().lower()
    return val in ("true", "1", "yes")


def get_setting_json(key: str, default: Any = None) -> Any:
    val = get_setting(key, "")
    if not val:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def set_setting(key: str, value: str, category: str = "general"):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO settings (key, value, category, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, category = excluded.category,
                                              updated_at = excluded.updated_at""",
            (key, str(value), category),
        )


def set_setting_json(key: str, value: Any, category: str = "general"):
    set_setting(key, json.dumps(value), category=category)


# ── Advanced Analytics & Financial Reporting ──────────────────

def get_analytics() -> Dict[str, Any]:
    """Calculates comprehensive performance, reach, and conversion analytics."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM posts WHERE status = 'posted'").fetchone()["c"]
        today = conn.execute(
            "SELECT COUNT(*) as c FROM posts WHERE status = 'posted' AND DATE(timestamp) = DATE('now', 'localtime')"
        ).fetchone()["c"]
        stats = conn.execute(
            """SELECT COALESCE(SUM(views),0) as views,
                      COALESCE(SUM(likes),0) as likes,
                      COALESCE(SUM(comments),0) as comments,
                      COALESCE(SUM(shares),0) as shares,
                      COALESCE(SUM(saves),0) as saves,
                      COALESCE(AVG(viral_score),0.0) as avg_viral
               FROM posts WHERE status = 'posted'"""
        ).fetchone()

        leads = conn.execute("SELECT COUNT(*) as c FROM dm_leads").fetchone()["c"]
        conversions = conn.execute("SELECT COUNT(*) as c FROM dm_leads WHERE converted = 1").fetchone()["c"]
        total_pipeline_val = conn.execute(
            "SELECT COALESCE(SUM(conversion_value),0.0) as s FROM dm_leads"
        ).fetchone()["s"]

        return {
            "total_posts": total,
            "today_posts": today,
            "total_views": stats["views"],
            "total_likes": stats["likes"],
            "total_comments": stats["comments"],
            "total_shares": stats["shares"],
            "total_saves": stats["saves"],
            "avg_viral_score": round(stats["avg_viral"], 2),
            "total_leads": leads,
            "total_conversions": conversions,
            "conversion_rate_pct": round((conversions / leads * 100), 1) if leads > 0 else 0.0,
            "pipeline_value_inr": round(total_pipeline_val, 2),
        }


def get_financial_summary() -> Dict[str, Any]:
    """Returns financial analytics across brands, affiliate commissions, and deals."""
    with get_connection() as conn:
        brand_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_revenue), 0.0) as rev, COALESCE(SUM(clicks), 0) as clk FROM brands"
        ).fetchone()
        active_brands = conn.execute("SELECT COUNT(*) as c FROM brands WHERE active = 1").fetchone()["c"]
        direct_conversions = conn.execute(
            "SELECT COALESCE(SUM(conversion_value), 0.0) as v FROM dm_leads WHERE converted = 1"
        ).fetchone()["v"]

        return {
            "total_affiliate_revenue_inr": round(brand_revenue["rev"], 2),
            "total_direct_sales_inr": round(direct_conversions, 2),
            "combined_income_inr": round(brand_revenue["rev"] + direct_conversions, 2),
            "total_affiliate_clicks": brand_revenue["clk"],
            "active_partner_brands": active_brands,
        }


# ── Hot Zero-Downtime Backup ──────────────────────────────────

def backup_database(backup_dir: Optional[str] = None) -> str:
    """
    Performs online zero-downtime database snapshot using SQLite's native backup API.
    Guarantees consistent copy without locking or stopping write transactions.
    """
    if backup_dir is None:
        backup_dir = os.path.join(DB_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"influencer_backup_{timestamp}.db")

    with get_connection() as src_conn:
        dest_conn = sqlite3.connect(backup_file)
        try:
            src_conn.backup(dest_conn)
            logger.info(f"Database backup completed: {backup_file}")
            log_audit_event("DB_BACKUP", f"Snapshot saved to {os.path.basename(backup_file)}", source="system")
            return backup_file
        finally:
            dest_conn.close()


# Initialize database automatically on import
init_db()
