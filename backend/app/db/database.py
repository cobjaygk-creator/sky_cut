import sqlite3
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


def _sqlite_path() -> Path:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// database URLs are supported in the local MVP.")
    raw_path = settings.database_url.removeprefix(prefix)
    return Path(raw_path).resolve()


DATABASE_PATH = _sqlite_path()
VIDEO_STATUSES = "'uploaded', 'extracting_audio', 'audio_extracted', 'transcribing', 'transcribed', 'failed'"
TRANSCRIPT_STATUSES = "'transcribing', 'transcribed', 'failed'"
CLIP_STATUSES = "'pending', 'processing', 'completed', 'failed'"
BLOG_CLIP_STATUSES = (
    "'pending', 'processing', 'awaiting_images', 'awaiting_script', 'awaiting_boards', 'completed', 'failed'"
)


def get_connection() -> Generator[sqlite3.Connection, None, None]:
    # FastAPI runs this sync generator dependency's "before yield" and
    # "after yield" halves (and the endpoint itself) via anyio's worker
    # thread pool, which does not guarantee the same OS thread is reused
    # for all three parts. sqlite3 connections are thread-affine by default
    # (check_same_thread=True), so without this flag every request would
    # intermittently fail with "SQLite objects created in a thread can only
    # be used in that same thread." Each request still gets its own
    # connection that is opened and closed within that single request, so
    # disabling the same-thread check here is safe.
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _sqlite_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _current_usage_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _migrate_users_table(conn: sqlite3.Connection) -> None:
    columns = _sqlite_columns(conn, "users")
    if "plan" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    if "monthly_usage" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN monthly_usage INTEGER NOT NULL DEFAULT 0")
    if "usage_limit" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN usage_limit INTEGER NOT NULL DEFAULT 3")
    if "usage_month" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN usage_month TEXT")
    conn.execute("UPDATE users SET plan = LOWER(COALESCE(NULLIF(plan, ''), 'free'))")
    conn.execute("UPDATE users SET usage_limit = 3 WHERE LOWER(plan) = 'free'")
    conn.execute("UPDATE users SET usage_limit = 30 WHERE LOWER(plan) = 'lite'")
    conn.execute("UPDATE users SET usage_limit = 150 WHERE LOWER(plan) = 'pro'")
    conn.execute("UPDATE users SET plan = 'free', usage_limit = 3 WHERE LOWER(plan) NOT IN ('free', 'lite', 'pro')")
    conn.execute("UPDATE users SET usage_month = ? WHERE usage_month IS NULL OR usage_month = ''", (_current_usage_month(),))


def _create_videos_table(conn: sqlite3.Connection, table_name: str = "videos") -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            content_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status IN ({VIDEO_STATUSES})),
            audio_path TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )


def _migrate_videos_table(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'videos'").fetchone()
    if row is None:
        _create_videos_table(conn)
        return

    table_sql = row["sql"] or ""
    needs_rebuild = (
        "transcribing" not in table_sql
        or "transcribed" not in table_sql
        or "audio_path" not in table_sql
        or "error_message" not in table_sql
    )
    if not needs_rebuild:
        return

    conn.execute("ALTER TABLE videos RENAME TO videos_old")
    _create_videos_table(conn)
    conn.execute(
        """
        INSERT INTO videos (
            id, user_id, original_filename, stored_filename, storage_path,
            content_type, file_size, status, audio_path, error_message, created_at, updated_at
        )
        SELECT
            id, user_id, original_filename, stored_filename, storage_path,
            content_type, file_size,
            CASE
                WHEN status IN ('uploaded', 'extracting_audio', 'audio_extracted', 'transcribing', 'transcribed', 'failed') THEN status
                ELSE 'failed'
            END,
            CASE WHEN audio_path IS NULL THEN NULL ELSE audio_path END,
            CASE WHEN error_message IS NULL THEN NULL ELSE error_message END,
            created_at,
            CASE WHEN updated_at IS NULL THEN created_at ELSE updated_at END
        FROM videos_old
        """
    )
    conn.execute("DROP TABLE videos_old")


def _create_transcripts_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK (status IN ({TRANSCRIPT_STATUSES})),
            text TEXT,
            segments_json TEXT NOT NULL DEFAULT '[]',
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
        """
    )


def _create_highlights_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS highlights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            title TEXT NOT NULL,
            reason TEXT NOT NULL,
            content_type TEXT NOT NULL,
            score REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_highlights_video_id ON highlights (video_id)")


def _create_clips_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            highlight_id INTEGER NOT NULL,
            output_path TEXT,
            subtitle_style TEXT,
            subtitle_path TEXT,
            subtitled_output_path TEXT,
            tts_mode TEXT NOT NULL DEFAULT 'original_audio',
            narration_script TEXT,
            narration_audio_path TEXT,
            narrated_output_path TEXT,
            status TEXT NOT NULL CHECK (status IN ({CLIP_STATUSES})),
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (video_id) REFERENCES videos (id),
            FOREIGN KEY (highlight_id) REFERENCES highlights (id)
        )
        """
    )
    columns = _sqlite_columns(conn, "clips")
    if "subtitle_style" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN subtitle_style TEXT")
    if "subtitle_path" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN subtitle_path TEXT")
    if "subtitled_output_path" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN subtitled_output_path TEXT")
    if "tts_mode" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN tts_mode TEXT NOT NULL DEFAULT 'original_audio'")
    if "narration_script" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN narration_script TEXT")
    if "narration_audio_path" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN narration_audio_path TEXT")
    if "narrated_output_path" not in columns:
        conn.execute("ALTER TABLE clips ADD COLUMN narrated_output_path TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_user_id ON clips (user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_highlight_id ON clips (highlight_id)")


def _create_clip_metadata_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clip_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL UNIQUE,
            title_candidates_json TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '',
            hashtags_json TEXT NOT NULL DEFAULT '[]',
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clip_id) REFERENCES clips (id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_metadata_clip_id ON clip_metadata (clip_id)")


def _create_blog_clips_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS blog_clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            blog_title TEXT,
            narration_script TEXT,
            script_tone TEXT,
            script_candidates_json TEXT,
            subtitle_style TEXT NOT NULL DEFAULT 'shorts',
            subtitle_template_id INTEGER,
            video_path TEXT,
            subtitled_video_path TEXT,
            status TEXT NOT NULL CHECK (status IN ({BLOG_CLIP_STATUSES})),
            progress_stage TEXT NOT NULL DEFAULT 'queued',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            title_candidates_json TEXT,
            description TEXT,
            hashtags_json TEXT,
            metadata_error TEXT,
            tts_speed REAL NOT NULL DEFAULT 1.0,
            bgm_asset_id INTEGER,
            bgm_volume REAL NOT NULL DEFAULT 0.18,
            active_version_id INTEGER,
            target_length TEXT NOT NULL DEFAULT 'short',
            narration_language TEXT NOT NULL DEFAULT 'original',
            script_model TEXT NOT NULL DEFAULT 'gpt-4o-mini',
            default_voice TEXT,
            auto_bgm INTEGER NOT NULL DEFAULT 0,
            auto_sfx INTEGER NOT NULL DEFAULT 0,
            wizard_step TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_clips_user_id ON blog_clips (user_id)")


def _create_blog_clip_boards_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blog_clip_boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_clip_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            speaker TEXT,
            duration_seconds REAL,
            sfx_asset_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (blog_clip_id) REFERENCES blog_clips (id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_clip_boards_blog_clip_id ON blog_clip_boards (blog_clip_id)")


def _migrate_blog_clip_boards_table(conn: sqlite3.Connection) -> None:
    columns = _sqlite_columns(conn, "blog_clip_boards")
    if "sfx_asset_id" not in columns:
        conn.execute("ALTER TABLE blog_clip_boards ADD COLUMN sfx_asset_id INTEGER")


def _migrate_blog_clips_table(conn: sqlite3.Connection) -> None:
    columns = _sqlite_columns(conn, "blog_clips")
    if "progress_stage" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN progress_stage TEXT NOT NULL DEFAULT 'queued'")
    if "progress_percent" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN progress_percent INTEGER NOT NULL DEFAULT 0")
    if "script_tone" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN script_tone TEXT")
    if "script_candidates_json" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN script_candidates_json TEXT")
    if "tts_speed" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN tts_speed REAL NOT NULL DEFAULT 1.0")
    if "subtitle_template_id" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN subtitle_template_id INTEGER")
    if "bgm_asset_id" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN bgm_asset_id INTEGER")
    if "bgm_volume" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN bgm_volume REAL NOT NULL DEFAULT 0.18")
    if "active_version_id" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN active_version_id INTEGER")
    if "target_length" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN target_length TEXT NOT NULL DEFAULT 'short'")
    if "narration_language" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN narration_language TEXT NOT NULL DEFAULT 'original'")
    if "default_voice" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN default_voice TEXT")
    if "auto_bgm" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN auto_bgm INTEGER NOT NULL DEFAULT 0")
    if "auto_sfx" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN auto_sfx INTEGER NOT NULL DEFAULT 0")
    if "wizard_step" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN wizard_step TEXT")
    conn.execute("UPDATE blog_clips SET progress_stage = 'done', progress_percent = 100 WHERE status = 'completed' AND progress_percent < 100")
    _migrate_blog_clips_awaiting_script_status(conn)
    _migrate_blog_clips_awaiting_boards_status(conn)
    _migrate_blog_clips_awaiting_images_status(conn)
    # After status rebuilds (they recreate the table without newer columns).
    columns = _sqlite_columns(conn, "blog_clips")
    if "render_spec_json" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN render_spec_json TEXT")
    if "script_model" not in columns:
        conn.execute("ALTER TABLE blog_clips ADD COLUMN script_model TEXT NOT NULL DEFAULT 'gpt-4o-mini'")


def _migrate_blog_clip_versions_table(conn: sqlite3.Connection) -> None:
    columns = _sqlite_columns(conn, "blog_clip_versions")
    if not columns:
        return
    if "render_spec_json" not in columns:
        conn.execute("ALTER TABLE blog_clip_versions ADD COLUMN render_spec_json TEXT")


def _migrate_blog_clips_awaiting_script_status(conn: sqlite3.Connection) -> None:
    """SQLite cannot ALTER CHECK constraints — rebuild the table when needed."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'blog_clips'").fetchone()
    if row is None or "awaiting_script" in (row[0] or ""):
        return

    conn.execute("ALTER TABLE blog_clips RENAME TO blog_clips_old")
    _create_blog_clips_table(conn)
    old_columns = set(_sqlite_columns(conn, "blog_clips_old"))
    new_columns = [
        "id",
        "user_id",
        "source_url",
        "blog_title",
        "narration_script",
        "script_tone",
        "script_candidates_json",
        "subtitle_style",
        "subtitle_template_id",
        "video_path",
        "subtitled_video_path",
        "status",
        "progress_stage",
        "progress_percent",
        "error_message",
        "title_candidates_json",
        "description",
        "hashtags_json",
        "metadata_error",
        "tts_speed",
        "bgm_asset_id",
        "bgm_volume",
        "active_version_id",
        "target_length",
        "narration_language",
        "default_voice",
        "auto_bgm",
        "auto_sfx",
        "wizard_step",
        "created_at",
        "updated_at",
    ]
    shared = [column for column in new_columns if column in old_columns]
    shared_sql = ", ".join(shared)
    conn.execute(f"INSERT INTO blog_clips ({shared_sql}) SELECT {shared_sql} FROM blog_clips_old")
    conn.execute("DROP TABLE blog_clips_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_clips_user_id ON blog_clips (user_id)")


def _migrate_blog_clips_awaiting_boards_status(conn: sqlite3.Connection) -> None:
    """SQLite cannot ALTER CHECK constraints — rebuild when awaiting_boards is missing."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'blog_clips'").fetchone()
    if row is None or "awaiting_boards" in (row[0] or ""):
        return

    conn.execute("ALTER TABLE blog_clips RENAME TO blog_clips_old")
    _create_blog_clips_table(conn)
    old_columns = set(_sqlite_columns(conn, "blog_clips_old"))
    new_columns = [
        "id",
        "user_id",
        "source_url",
        "blog_title",
        "narration_script",
        "script_tone",
        "script_candidates_json",
        "subtitle_style",
        "subtitle_template_id",
        "video_path",
        "subtitled_video_path",
        "status",
        "progress_stage",
        "progress_percent",
        "error_message",
        "title_candidates_json",
        "description",
        "hashtags_json",
        "metadata_error",
        "tts_speed",
        "bgm_asset_id",
        "bgm_volume",
        "active_version_id",
        "target_length",
        "narration_language",
        "default_voice",
        "auto_bgm",
        "auto_sfx",
        "wizard_step",
        "created_at",
        "updated_at",
    ]
    shared = [column for column in new_columns if column in old_columns]
    shared_sql = ", ".join(shared)
    conn.execute(f"INSERT INTO blog_clips ({shared_sql}) SELECT {shared_sql} FROM blog_clips_old")
    conn.execute("DROP TABLE blog_clips_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_clips_user_id ON blog_clips (user_id)")


def _migrate_blog_clips_awaiting_images_status(conn: sqlite3.Connection) -> None:
    """SQLite cannot ALTER CHECK constraints — rebuild when awaiting_images is missing."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'blog_clips'").fetchone()
    if row is None or "awaiting_images" in (row[0] or ""):
        return

    conn.execute("ALTER TABLE blog_clips RENAME TO blog_clips_old")
    _create_blog_clips_table(conn)
    old_columns = set(_sqlite_columns(conn, "blog_clips_old"))
    new_columns = [
        "id",
        "user_id",
        "source_url",
        "blog_title",
        "narration_script",
        "script_tone",
        "script_candidates_json",
        "subtitle_style",
        "subtitle_template_id",
        "video_path",
        "subtitled_video_path",
        "status",
        "progress_stage",
        "progress_percent",
        "error_message",
        "title_candidates_json",
        "description",
        "hashtags_json",
        "metadata_error",
        "tts_speed",
        "bgm_asset_id",
        "bgm_volume",
        "active_version_id",
        "target_length",
        "narration_language",
        "default_voice",
        "auto_bgm",
        "auto_sfx",
        "wizard_step",
        "created_at",
        "updated_at",
    ]
    shared = [column for column in new_columns if column in old_columns]
    shared_sql = ", ".join(shared)
    conn.execute(f"INSERT INTO blog_clips ({shared_sql}) SELECT {shared_sql} FROM blog_clips_old")
    conn.execute("DROP TABLE blog_clips_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_clips_user_id ON blog_clips (user_id)")


def _create_blog_clip_image_candidates_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blog_clip_image_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_clip_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            storage_path TEXT NOT NULL,
            source_url TEXT,
            selected INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (blog_clip_id) REFERENCES blog_clips (id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_blog_clip_image_candidates_blog_clip_id "
        "ON blog_clip_image_candidates (blog_clip_id)"
    )


def _create_subtitle_templates_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subtitle_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT,
            font_name TEXT NOT NULL DEFAULT 'Malgun Gothic',
            font_size INTEGER NOT NULL,
            primary_color TEXT NOT NULL,
            outline_color TEXT NOT NULL,
            back_color TEXT NOT NULL,
            primary_alpha INTEGER NOT NULL DEFAULT 0,
            outline_alpha INTEGER NOT NULL DEFAULT 0,
            back_alpha INTEGER NOT NULL DEFAULT 204,
            bold INTEGER NOT NULL DEFAULT 0,
            outline REAL NOT NULL DEFAULT 3,
            shadow REAL NOT NULL DEFAULT 1,
            alignment INTEGER NOT NULL DEFAULT 2,
            margin_l INTEGER NOT NULL DEFAULT 80,
            margin_r INTEGER NOT NULL DEFAULT 80,
            margin_v INTEGER NOT NULL DEFAULT 150,
            border_style INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_subtitle_templates_system_slug "
        "ON subtitle_templates (slug) WHERE user_id IS NULL AND slug IS NOT NULL"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subtitle_templates_user_id ON subtitle_templates (user_id)")


def _create_blog_clip_versions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blog_clip_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_clip_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'boards',
            script_tone TEXT,
            narration_script TEXT,
            video_path TEXT,
            subtitled_video_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            progress_stage TEXT NOT NULL DEFAULT 'queued',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            title_candidates_json TEXT,
            description TEXT,
            hashtags_json TEXT,
            metadata_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (blog_clip_id) REFERENCES blog_clips (id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_blog_clip_versions_blog_clip_id ON blog_clip_versions (blog_clip_id)"
    )


def _create_audio_assets_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT NOT NULL CHECK (kind IN ('bgm', 'sfx')),
            name TEXT NOT NULL,
            slug TEXT,
            storage_path TEXT NOT NULL,
            duration_seconds REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_audio_assets_system_slug "
        "ON audio_assets (slug) WHERE user_id IS NULL AND slug IS NOT NULL"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audio_assets_user_id ON audio_assets (user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audio_assets_kind ON audio_assets (kind)")


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                monthly_usage INTEGER NOT NULL DEFAULT 0,
                usage_limit INTEGER NOT NULL DEFAULT 3,
                usage_month TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _migrate_users_table(conn)
        _migrate_videos_table(conn)
        _create_transcripts_table(conn)
        _create_highlights_table(conn)
        _create_clips_table(conn)
        _create_clip_metadata_table(conn)
        _create_blog_clips_table(conn)
        _migrate_blog_clips_table(conn)
        _create_blog_clip_boards_table(conn)
        _migrate_blog_clip_boards_table(conn)
        _create_blog_clip_image_candidates_table(conn)
        _create_blog_clip_versions_table(conn)
        _migrate_blog_clip_versions_table(conn)
        _create_subtitle_templates_table(conn)
        _create_audio_assets_table(conn)
        from app.services.audio_service import seed_system_audio_assets
        from app.services.template_service import seed_system_templates

        seed_system_templates(conn)
        seed_system_audio_assets(conn)
        conn.commit()
