import sqlite3
from collections.abc import Generator
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


def get_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _sqlite_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_user_id ON clips (user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_highlight_id ON clips (highlight_id)")


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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _migrate_videos_table(conn)
        _create_transcripts_table(conn)
        _create_highlights_table(conn)
        _create_clips_table(conn)
        conn.commit()
