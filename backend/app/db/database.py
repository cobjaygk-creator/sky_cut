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
VIDEO_STATUSES = "'uploaded', 'extracting_audio', 'audio_extracted', 'failed'"


def get_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


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
    needs_rebuild = "extracting_audio" not in table_sql or "audio_path" not in table_sql or "error_message" not in table_sql
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
            CASE WHEN status IN ('uploaded', 'failed') THEN status ELSE 'failed' END,
            NULL, NULL, created_at, created_at
        FROM videos_old
        """
    )
    conn.execute("DROP TABLE videos_old")


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
        conn.commit()
