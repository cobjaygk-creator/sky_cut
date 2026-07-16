import json
import logging
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from fastapi import HTTPException, status
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError, RateLimitError

from app.core.config import settings
from app.db.database import get_connection
from app.db.models import BlogClip, BlogClipBoard, BlogClipImageCandidate, BlogClipVersion
from app.services.audio_service import (
    DEFAULT_SFX_VOLUME,
    assert_audio_asset_usable,
    clamp_bgm_volume,
    pick_default_bgm,
    pick_default_sfx,
)
from app.services.ffmpeg_service import (
    FFmpegAudioError,
    FFmpegNotAvailableError,
    FFmpegSlideshowError,
    FFmpegSubtitleError,
    FFprobeNotAvailableError,
    burn_subtitles_into_video,
    concat_audio_files,
    create_image_slideshow,
    create_silence_mp3,
    get_video_duration_seconds,
    mix_narration_with_bed,
    pad_audio_to_duration,
)
from app.services.subtitle_utils import clean_subtitle_text, split_text_for_duration, write_ass_file
from app.services.template_service import (
    assert_template_usable,
    get_system_template_by_slug,
    resolve_ass_params_for_blog_clip,
)
from app.services.tts_service import (
    clamp_tts_speed,
    default_tts_voice,
    synthesize_openai_tts,
    validate_voice_id,
)
from app.services.video_service import STORAGE_ROOT

logger = logging.getLogger(__name__)

SPEAKER_UNSET = object()
SFX_UNSET = object()
BGM_ASSET_UNSET = object()

BLOG_ROOT = STORAGE_ROOT / "blog"
BLOG_IMAGE_ROOT = BLOG_ROOT / "images"
BLOG_OUTPUT_ROOT = BLOG_ROOT / "outputs"
BLOG_SUBTITLE_ROOT = BLOG_ROOT / "subtitles"
BLOG_PREVIEW_AUDIO_ROOT = BLOG_ROOT / "preview_audio"

ALLOWED_SUBTITLE_STYLES = {"basic", "bold", "shorts"}
ALLOWED_SCRIPT_TONES = ("summary", "hook", "detailed")
ALLOWED_TARGET_LENGTHS = {"short", "long"}
ALLOWED_NARRATION_LANGUAGES = {"original", "ko", "en", "ja"}
ALLOWED_SCRIPT_MODELS = {"gpt-4o-mini", "gpt-4o"}
ALLOWED_WIZARD_STEPS = {"video_style", "edit_mode", "quick", "ready", "boards", "voice", "style"}
LEGACY_WIZARD_STEPS = {"boards", "voice", "style"}


def _normalize_wizard_step(wizard_step: str | None) -> str | None:
    if wizard_step is None:
        return None
    step = wizard_step.strip().lower()
    if step in LEGACY_WIZARD_STEPS:
        return "edit_mode"
    return step or None


SCRIPT_TONE_LABELS = {
    "summary": "요약형",
    "hook": "후킹형",
    "detailed": "상세형",
}

# (status, progress_stage, progress_percent) checkpoints the pipeline moves through.
PROGRESS_QUEUED = ("pending", "queued", 0)
PROGRESS_SCRAPING = ("processing", "scraping", 10)
PROGRESS_DOWNLOADING_IMAGES = ("processing", "downloading_images", 25)
PROGRESS_GENERATING_SCRIPT = ("processing", "generating_script", 40)
PROGRESS_AWAITING_IMAGES = ("awaiting_images", "awaiting_images", 42)
PROGRESS_AWAITING_SCRIPT = ("awaiting_script", "awaiting_script", 45)
PROGRESS_AWAITING_BOARDS = ("awaiting_boards", "awaiting_boards", 50)
PROGRESS_SYNTHESIZING_AUDIO = ("processing", "synthesizing_audio", 55)
PROGRESS_RENDERING_VIDEO = ("processing", "rendering_video", 75)
PROGRESS_BURNING_SUBTITLES = ("processing", "burning_subtitles", 90)
PROGRESS_DONE = ("completed", "done", 100)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_MIN_IMAGE_BYTES = 15_000
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# Checked in order; the first selector that matches a container with a
# reasonable amount of text wins. Covers common Korean/global blogging
# platforms (Tistory, Velog, brunch, WordPress, Medium, generic news CMSs)
# plus a few framework-agnostic conventions (<article>, [role=main]).
_GENERIC_CONTENT_SELECTORS = [
    "article",
    "[role='main']",
    "main",
    ".entry-content",
    ".post-content",
    ".article-content",
    ".article_view",
    ".article-view",
    "#article-view",
    ".tt_article_useless_p_margin",  # Tistory
    ".sc-b3ea8b5a-0",  # Velog (best-effort; class names are hashed and may drift)
    ".se-main-container",  # Naver, kept as a generic fallback too
    "#content",
    ".content",
    ".post",
    ".post-area",
]
_GENERIC_MIN_CONTAINER_TEXT_LENGTH = 80
_REMOVE_TAG_NAMES = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "button", "svg"]


class BlogFetchError(RuntimeError):
    pass


@dataclass
class BlogContent:
    title: str
    text: str
    image_urls: list[str]


def _row_to_blog_clip(row: sqlite3.Row) -> BlogClip:
    keys = set(row.keys())
    return BlogClip(
        id=row["id"],
        user_id=row["user_id"],
        source_url=row["source_url"],
        blog_title=row["blog_title"],
        narration_script=row["narration_script"],
        script_tone=row["script_tone"],
        script_candidates_json=row["script_candidates_json"],
        subtitle_style=row["subtitle_style"],
        subtitle_template_id=row["subtitle_template_id"] if "subtitle_template_id" in keys else None,
        video_path=row["video_path"],
        subtitled_video_path=row["subtitled_video_path"],
        status=row["status"],
        progress_stage=row["progress_stage"],
        progress_percent=row["progress_percent"],
        error_message=row["error_message"],
        title_candidates_json=row["title_candidates_json"],
        description=row["description"],
        hashtags_json=row["hashtags_json"],
        metadata_error=row["metadata_error"],
        tts_speed=float(row["tts_speed"]) if "tts_speed" in keys and row["tts_speed"] is not None else 1.0,
        bgm_asset_id=row["bgm_asset_id"] if "bgm_asset_id" in keys else None,
        bgm_volume=float(row["bgm_volume"]) if "bgm_volume" in keys and row["bgm_volume"] is not None else 0.30,
        active_version_id=row["active_version_id"] if "active_version_id" in keys else None,
        target_length=row["target_length"] if "target_length" in keys and row["target_length"] else "short",
        narration_language=(
            row["narration_language"] if "narration_language" in keys and row["narration_language"] else "original"
        ),
        script_model=(
            row["script_model"]
            if "script_model" in keys and row["script_model"]
            else (settings.openai_metadata_model or "gpt-4o-mini")
        ),
        default_voice=row["default_voice"] if "default_voice" in keys else None,
        auto_bgm=bool(row["auto_bgm"]) if "auto_bgm" in keys and row["auto_bgm"] is not None else False,
        auto_sfx=bool(row["auto_sfx"]) if "auto_sfx" in keys and row["auto_sfx"] is not None else False,
        wizard_step=_normalize_wizard_step(row["wizard_step"] if "wizard_step" in keys else None),
        visual_style=(
            row["visual_style"]
            if "visual_style" in keys and row["visual_style"]
            else "fullscreen"
        ),
        render_spec_json=row["render_spec_json"] if "render_spec_json" in keys else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_BLOG_CLIP_COLUMNS = """
    id, user_id, source_url, blog_title, narration_script, script_tone, script_candidates_json,
    subtitle_style, subtitle_template_id, video_path, subtitled_video_path, status, progress_stage,
    progress_percent, error_message, title_candidates_json, description, hashtags_json,
    metadata_error, tts_speed, bgm_asset_id, bgm_volume, active_version_id, target_length,
    narration_language, script_model, default_voice, auto_bgm, auto_sfx, wizard_step, visual_style,
    render_spec_json, created_at, updated_at
"""


def get_blog_clip_for_user(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> BlogClip | None:
    row = conn.execute(
        f"SELECT {_BLOG_CLIP_COLUMNS} FROM blog_clips WHERE id = ? AND user_id = ?",
        (blog_clip_id, user_id),
    ).fetchone()
    return _row_to_blog_clip(row) if row else None


def list_blog_clips_for_user(conn: sqlite3.Connection, user_id: int) -> list[BlogClip]:
    rows = conn.execute(
        f"SELECT {_BLOG_CLIP_COLUMNS} FROM blog_clips WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [_row_to_blog_clip(row) for row in rows]


def blog_clip_download_path(blog_clip: BlogClip) -> Path:
    path_value = blog_clip.subtitled_video_path or blog_clip.video_path
    if not path_value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Blog short output is not ready for download.")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short file was not found.")
    return path


# --- Blog clip versions -------------------------------------------------------


_BLOG_CLIP_VERSION_COLUMNS = """
    id, blog_clip_id, label, source, script_tone, narration_script, video_path, subtitled_video_path,
    status, progress_stage, progress_percent, error_message, title_candidates_json, description,
    hashtags_json, metadata_error, render_spec_json, created_at, updated_at
"""


def _row_to_blog_clip_version(row: sqlite3.Row) -> BlogClipVersion:
    keys = set(row.keys())
    return BlogClipVersion(
        id=row["id"],
        blog_clip_id=row["blog_clip_id"],
        label=row["label"],
        source=row["source"],
        script_tone=row["script_tone"],
        narration_script=row["narration_script"],
        video_path=row["video_path"],
        subtitled_video_path=row["subtitled_video_path"],
        status=row["status"],
        progress_stage=row["progress_stage"],
        progress_percent=row["progress_percent"],
        error_message=row["error_message"],
        title_candidates_json=row["title_candidates_json"],
        description=row["description"],
        hashtags_json=row["hashtags_json"],
        metadata_error=row["metadata_error"],
        render_spec_json=row["render_spec_json"] if "render_spec_json" in keys else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def blog_clip_render_spec(blog_clip: BlogClip) -> dict[str, Any] | None:
    return _parse_render_spec_json(blog_clip.render_spec_json)


def blog_clip_version_render_spec(version: BlogClipVersion) -> dict[str, Any] | None:
    return _parse_render_spec_json(version.render_spec_json)


def _parse_render_spec_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def get_blog_clip_version_for_user(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    version_id: int,
) -> BlogClipVersion | None:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        return None
    row = conn.execute(
        f"""
        SELECT {_BLOG_CLIP_VERSION_COLUMNS}
        FROM blog_clip_versions
        WHERE id = ? AND blog_clip_id = ?
        """,
        (version_id, blog_clip_id),
    ).fetchone()
    return _row_to_blog_clip_version(row) if row else None


def _ensure_legacy_blog_clip_version(conn: sqlite3.Connection, blog_clip: BlogClip) -> None:
    """Backfill a version row for completed clips created before Stage 24."""
    if blog_clip.status != "completed":
        return
    if not (blog_clip.subtitled_video_path or blog_clip.video_path):
        return
    count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM blog_clip_versions WHERE blog_clip_id = ?",
        (blog_clip.id,),
    ).fetchone()
    if count_row and int(count_row["n"]) > 0:
        return

    tone = blog_clip.script_tone
    label = SCRIPT_TONE_LABELS.get(tone or "", "보드 렌더") if tone else "보드 렌더"
    cursor = conn.execute(
        """
        INSERT INTO blog_clip_versions (
            blog_clip_id, label, source, script_tone, narration_script,
            video_path, subtitled_video_path, status, progress_stage, progress_percent,
            title_candidates_json, description, hashtags_json, metadata_error, error_message,
            render_spec_json
        )
        VALUES (?, ?, 'boards', ?, ?, ?, ?, 'completed', 'done', 100, ?, ?, ?, ?, NULL, ?)
        """,
        (
            blog_clip.id,
            label,
            tone,
            blog_clip.narration_script,
            blog_clip.video_path,
            blog_clip.subtitled_video_path,
            blog_clip.title_candidates_json,
            blog_clip.description,
            blog_clip.hashtags_json,
            blog_clip.metadata_error,
            blog_clip.render_spec_json,
        ),
    )
    version_id = int(cursor.lastrowid)
    conn.execute(
        "UPDATE blog_clips SET active_version_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (version_id, blog_clip.id),
    )
    conn.commit()


def list_blog_clip_versions(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> list[BlogClipVersion]:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _ensure_legacy_blog_clip_version(conn, blog_clip)
    rows = conn.execute(
        f"""
        SELECT {_BLOG_CLIP_VERSION_COLUMNS}
        FROM blog_clip_versions
        WHERE blog_clip_id = ?
        ORDER BY id ASC
        """,
        (blog_clip_id,),
    ).fetchall()
    return [_row_to_blog_clip_version(row) for row in rows]


def blog_clip_version_download_path(version: BlogClipVersion) -> Path:
    path_value = version.subtitled_video_path or version.video_path
    if not path_value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version output is not ready for download.")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version file was not found.")
    return path


def blog_clip_version_title_candidates(version: BlogClipVersion) -> list[str]:
    try:
        parsed = json.loads(version.title_candidates_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def blog_clip_version_hashtags(version: BlogClipVersion) -> list[str]:
    try:
        parsed = json.loads(version.hashtags_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _update_version_progress(
    conn: sqlite3.Connection,
    version_id: int,
    checkpoint: tuple[str, str, int],
) -> None:
    status_value, progress_stage, progress_percent = checkpoint
    conn.execute(
        """
        UPDATE blog_clip_versions
        SET status = ?, progress_stage = ?, progress_percent = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, progress_stage, progress_percent, version_id),
    )
    conn.commit()


def _update_version_failed(conn: sqlite3.Connection, version_id: int, error_message: str) -> None:
    conn.execute(
        """
        UPDATE blog_clip_versions
        SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (error_message, version_id),
    )
    conn.commit()


def _sync_parent_from_version(conn: sqlite3.Connection, blog_clip_id: int, version: BlogClipVersion) -> None:
    conn.execute(
        """
        UPDATE blog_clips
        SET narration_script = ?,
            script_tone = ?,
            video_path = ?,
            subtitled_video_path = ?,
            title_candidates_json = ?,
            description = ?,
            hashtags_json = ?,
            metadata_error = ?,
            render_spec_json = ?,
            active_version_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            version.narration_script,
            version.script_tone,
            version.video_path,
            version.subtitled_video_path,
            version.title_candidates_json,
            version.description,
            version.hashtags_json,
            version.metadata_error,
            version.render_spec_json,
            version.id,
            blog_clip_id,
        ),
    )
    conn.commit()


def set_active_blog_clip_version(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    version_id: int,
) -> BlogClipVersion:
    version = get_blog_clip_version_for_user(conn, user_id, blog_clip_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    if version.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only completed versions can be set active.")
    _sync_parent_from_version(conn, blog_clip_id, version)
    refreshed = get_blog_clip_version_for_user(conn, user_id, blog_clip_id, version_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Version refresh failed.")
    return refreshed


def _build_tone_render_boards(
    user_id: int,
    blog_clip_id: int,
    script: str,
    template_boards: list[BlogClipBoard],
) -> list[BlogClipBoard]:
    if template_boards:
        texts = _split_script_into_board_texts(script, len(template_boards))
        return [
            BlogClipBoard(
                id=0,
                blog_clip_id=blog_clip_id,
                order_index=index,
                image_path=board.image_path,
                text=texts[index],
                speaker=board.speaker,
                duration_seconds=None,
                sfx_asset_id=board.sfx_asset_id,
                created_at="",
                updated_at="",
            )
            for index, board in enumerate(template_boards)
        ]

    image_paths = _list_saved_blog_images(user_id, blog_clip_id)
    if not image_paths:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No images available to render this version.")
    texts = _split_script_into_board_texts(script, len(image_paths))
    return [
        BlogClipBoard(
            id=0,
            blog_clip_id=blog_clip_id,
            order_index=index,
            image_path=str(image_path),
            text=texts[index],
            speaker=None,
            duration_seconds=None,
            sfx_asset_id=None,
            created_at="",
            updated_at="",
        )
        for index, image_path in enumerate(image_paths)
    ]


def _insert_pending_version(
    conn: sqlite3.Connection,
    blog_clip_id: int,
    *,
    label: str,
    source: str,
    script_tone: str | None,
    narration_script: str | None,
) -> BlogClipVersion:
    cursor = conn.execute(
        """
        INSERT INTO blog_clip_versions (
            blog_clip_id, label, source, script_tone, narration_script,
            status, progress_stage, progress_percent
        )
        VALUES (?, ?, ?, ?, ?, 'pending', 'queued', 0)
        """,
        (blog_clip_id, label, source, script_tone, narration_script),
    )
    conn.commit()
    row = conn.execute(
        f"SELECT {_BLOG_CLIP_VERSION_COLUMNS} FROM blog_clip_versions WHERE id = ?",
        (int(cursor.lastrowid),),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Version creation failed.")
    return _row_to_blog_clip_version(row)


def create_blog_clip_versions(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    mode: str,
    tone: str | None = None,
) -> list[BlogClipVersion]:
    """Queue one or more additional renders for a completed blog clip."""
    if mode not in {"boards", "tone", "all_tones"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be boards, tone, or all_tones.")

    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Additional versions require a completed blog short. Use POST .../render for the first output.",
        )
    _ensure_legacy_blog_clip_version(conn, blog_clip)

    created: list[BlogClipVersion] = []
    if mode == "boards":
        boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
        if not boards:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="보드가 없습니다. 최소 1개 이상의 보드가 필요합니다.")
        script = " ".join(board.text.strip() for board in boards if board.text.strip()).strip()
        if not script:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one board must contain narration text.")
        created.append(
            _insert_pending_version(
                conn,
                blog_clip_id,
                label="보드 재생성",
                source="boards",
                script_tone=blog_clip.script_tone,
                narration_script=script,
            )
        )
    else:
        candidates = blog_clip_script_candidates(blog_clip)
        if mode == "tone":
            if tone not in ALLOWED_SCRIPT_TONES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Script tone must be summary, hook, or detailed.",
                )
            tones = [tone]
        else:
            tones = [item for item in ALLOWED_SCRIPT_TONES if candidates.get(item)]

        if not tones:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No script tone candidates are available.")

        existing_rows = conn.execute(
            """
            SELECT script_tone, status FROM blog_clip_versions
            WHERE blog_clip_id = ? AND script_tone IS NOT NULL
            """,
            (blog_clip_id,),
        ).fetchall()
        occupied = {
            str(row["script_tone"])
            for row in existing_rows
            if row["script_tone"] and row["status"] in {"pending", "processing", "completed"}
        }

        for tone_key in tones:
            script = (candidates.get(tone_key) or "").strip()
            if not script:
                if mode == "tone":
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected script tone is not available.")
                continue
            if mode == "all_tones" and tone_key in occupied:
                continue
            created.append(
                _insert_pending_version(
                    conn,
                    blog_clip_id,
                    label=SCRIPT_TONE_LABELS.get(tone_key, tone_key),
                    source="tone",
                    script_tone=tone_key,
                    narration_script=script,
                )
            )

        if not created:
            if mode == "all_tones":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="All script tones already have a version. Use mode=tone or boards to regenerate.",
                )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No version was created.")

    return created


# --- Blog clip boards ---------------------------------------------------------


def _row_to_blog_clip_board(row: sqlite3.Row) -> BlogClipBoard:
    keys = set(row.keys())
    return BlogClipBoard(
        id=row["id"],
        blog_clip_id=row["blog_clip_id"],
        order_index=row["order_index"],
        image_path=row["image_path"],
        text=row["text"],
        speaker=row["speaker"],
        duration_seconds=row["duration_seconds"],
        sfx_asset_id=row["sfx_asset_id"] if "sfx_asset_id" in keys else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_BLOG_CLIP_BOARD_COLUMNS = """
    id, blog_clip_id, order_index, image_path, text, speaker, duration_seconds, sfx_asset_id,
    created_at, updated_at
"""


def _blog_clip_image_dir(user_id: int, blog_clip_id: int) -> Path:
    return BLOG_IMAGE_ROOT / str(user_id) / str(blog_clip_id)


def _validate_board_image_path(user_id: int, blog_clip_id: int, image_path: str) -> str:
    image_dir = _blog_clip_image_dir(user_id, blog_clip_id).resolve()
    candidate = Path(image_path).resolve()
    try:
        candidate.relative_to(image_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_path must be a downloaded image for this blog short.",
        ) from exc
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_path does not exist.")
    if candidate.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_path must be a supported image file.")
    return str(candidate)


def _split_script_into_units(script: str) -> list[str]:
    """Split narration into roughly sentence-sized units (Korean-friendly)."""
    cleaned = clean_subtitle_text(script)
    if not cleaned:
        return []
    # Prefer punctuation / newlines; Korean often lacks a space after `.`
    parts = [
        part.strip()
        for part in re.split(r"(?<=[.!?。…])\s*|\n+", cleaned)
        if part.strip()
    ]
    if len(parts) >= 2:
        return parts
    # Fallback: break a single blob into short phrases on spaces / commas.
    soft = [part.strip() for part in re.split(r"(?<=[,，、])\s+|\s{2,}", cleaned) if part.strip()]
    return soft if soft else [cleaned]


def _chunk_text_by_chars(text: str, chunk_count: int) -> list[str]:
    """Split one string into `chunk_count` roughly equal character chunks on word boundaries."""
    if chunk_count <= 1:
        return [text]
    cleaned = text.strip()
    if not cleaned:
        return [""] * chunk_count
    total = len(cleaned)
    chunks: list[str] = []
    start = 0
    for index in range(chunk_count):
        if start >= total:
            chunks.append("")
            continue
        # End target for this chunk (exclusive), leave remainder for later chunks.
        remaining_chunks = chunk_count - index
        remaining_chars = total - start
        ideal_end = start + max(1, round(remaining_chars / remaining_chunks))
        if index == chunk_count - 1 or ideal_end >= total:
            chunks.append(cleaned[start:].strip())
            start = total
            continue
        # Prefer breaking at a nearby space so words aren't cut mid-token.
        window_start = max(start + 1, ideal_end - 12)
        window_end = min(total - 1, ideal_end + 12)
        break_at = ideal_end
        for pos in range(ideal_end, window_start - 1, -1):
            if cleaned[pos].isspace():
                break_at = pos
                break
        else:
            for pos in range(ideal_end, window_end + 1):
                if cleaned[pos].isspace():
                    break_at = pos
                    break
        piece = cleaned[start:break_at].strip()
        chunks.append(piece or cleaned[start:ideal_end].strip())
        start = break_at if break_at > start else ideal_end
    while len(chunks) < chunk_count:
        chunks.append("")
    return chunks[:chunk_count]


def _split_script_into_board_texts(script: str, board_count: int) -> list[str]:
    """Distribute narration across boards by cumulative character targets.

    Empty later boards used to happen because each board compared *its own*
    chunk length to a *cumulative* target — early boards absorbed everything.
    """
    if board_count <= 0:
        return []
    units = _split_script_into_units(script)
    if not units:
        return [""] * board_count

    # Ensure we have at least one unit per board when the script is long enough.
    if len(units) < board_count:
        # Expand by splitting the longest units until we can fill boards.
        while len(units) < board_count:
            longest_index = max(range(len(units)), key=lambda i: len(units[i]))
            longest = units[longest_index]
            if len(longest) < 8:
                break
            pieces = _chunk_text_by_chars(longest, 2)
            if len(pieces) < 2 or not pieces[0] or not pieces[1]:
                break
            units = units[:longest_index] + pieces + units[longest_index + 1 :]

    if len(units) <= board_count:
        # One (or zero) unit per board; pad empties only if we truly can't split further.
        texts = list(units)
        while len(texts) < board_count:
            texts.append("")
        return texts[:board_count]

    total_chars = sum(len(unit) for unit in units) or 1
    cumulative_targets = [max(1, round(total_chars * (index + 1) / board_count)) for index in range(board_count)]
    texts: list[str] = []
    cursor = 0
    cumulative = 0

    for board_index, target in enumerate(cumulative_targets):
        chunk: list[str] = []
        if board_index == board_count - 1:
            # Last board takes whatever remains so nothing is dropped.
            chunk = units[cursor:]
            cursor = len(units)
        else:
            while cursor < len(units):
                # Keep at least one unit if this board is still empty, even if it
                # overshoots the target (avoids starving later boards of tiny leftovers).
                next_unit = units[cursor]
                if chunk and cumulative + len(next_unit) > target:
                    break
                chunk.append(next_unit)
                cumulative += len(next_unit)
                cursor += 1
                if cumulative >= target:
                    break
        texts.append(" ".join(chunk).strip())

    while len(texts) < board_count:
        texts.append("")
    return texts[:board_count]


def _normalize_board_order_indices(conn: sqlite3.Connection, blog_clip_id: int) -> None:
    rows = conn.execute(
        "SELECT id FROM blog_clip_boards WHERE blog_clip_id = ? ORDER BY order_index ASC, id ASC",
        (blog_clip_id,),
    ).fetchall()
    for index, row in enumerate(rows):
        conn.execute(
            "UPDATE blog_clip_boards SET order_index = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (index, row["id"]),
        )
    conn.commit()


def _generate_initial_boards(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    script: str,
) -> list[BlogClipBoard]:
    image_paths = _list_selected_blog_images(conn, user_id, blog_clip_id)
    if len(image_paths) < settings.blog_image_min_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"선택된 이미지가 부족합니다 "
                f"({len(image_paths)}개, 최소 {settings.blog_image_min_count}개 필요)."
            ),
        )

    texts = _split_script_into_board_texts(script, len(image_paths))
    conn.execute("DELETE FROM blog_clip_boards WHERE blog_clip_id = ?", (blog_clip_id,))
    for index, (image_path, text) in enumerate(zip(image_paths, texts)):
        conn.execute(
            """
            INSERT INTO blog_clip_boards (blog_clip_id, order_index, image_path, text, speaker, duration_seconds)
            VALUES (?, ?, ?, ?, NULL, NULL)
            """,
            (blog_clip_id, index, str(image_path), text),
        )
    conn.commit()
    return list_blog_clip_boards(conn, user_id, blog_clip_id)


def _require_awaiting_boards_for_mutation(blog_clip: BlogClip) -> None:
    if blog_clip.status != "awaiting_boards":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="보드는 대본 선택 후 렌더 전까지만 편집할 수 있습니다.",
        )


def list_blog_clip_boards(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> list[BlogClipBoard]:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    rows = conn.execute(
        f"""
        SELECT {_BLOG_CLIP_BOARD_COLUMNS}
        FROM blog_clip_boards
        WHERE blog_clip_id = ?
        ORDER BY order_index ASC, id ASC
        """,
        (blog_clip_id,),
    ).fetchall()
    return [_row_to_blog_clip_board(row) for row in rows]


def get_blog_clip_board_image_path(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    board_id: int,
) -> Path:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")

    row = conn.execute(
        f"SELECT {_BLOG_CLIP_BOARD_COLUMNS} FROM blog_clip_boards WHERE id = ? AND blog_clip_id = ?",
        (board_id, blog_clip_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")

    validated = _validate_board_image_path(user_id, blog_clip_id, row["image_path"])
    return Path(validated)


def create_blog_clip_board(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    image_path: str,
    text: str = "",
    order_index: int | None = None,
) -> BlogClipBoard:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)
    validated_image_path = _validate_board_image_path(user_id, blog_clip_id, image_path)

    if order_index is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(order_index), -1) + 1 AS next_index FROM blog_clip_boards WHERE blog_clip_id = ?",
            (blog_clip_id,),
        ).fetchone()
        resolved_order_index = int(row["next_index"])
    else:
        resolved_order_index = max(0, order_index)
        conn.execute(
            """
            UPDATE blog_clip_boards
            SET order_index = order_index + 1, updated_at = CURRENT_TIMESTAMP
            WHERE blog_clip_id = ? AND order_index >= ?
            """,
            (blog_clip_id, resolved_order_index),
        )

    cursor = conn.execute(
        """
        INSERT INTO blog_clip_boards (blog_clip_id, order_index, image_path, text, speaker, duration_seconds)
        VALUES (?, ?, ?, ?, NULL, NULL)
        """,
        (blog_clip_id, resolved_order_index, validated_image_path, text),
    )
    conn.commit()
    _normalize_board_order_indices(conn, blog_clip_id)

    board_id = int(cursor.lastrowid)
    row = conn.execute(
        f"SELECT {_BLOG_CLIP_BOARD_COLUMNS} FROM blog_clip_boards WHERE id = ?",
        (board_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Board creation failed.")
    return _row_to_blog_clip_board(row)


def update_blog_clip_board(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    board_id: int,
    image_path: str | None = None,
    text: str | None = None,
    duration_seconds: float | None = None,
    speaker: Any = SPEAKER_UNSET,
    sfx_asset_id: Any = SFX_UNSET,
) -> BlogClipBoard:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)

    row = conn.execute(
        f"SELECT {_BLOG_CLIP_BOARD_COLUMNS} FROM blog_clip_boards WHERE id = ? AND blog_clip_id = ?",
        (board_id, blog_clip_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")

    updates: list[str] = []
    values: list[Any] = []
    if image_path is not None:
        updates.append("image_path = ?")
        values.append(_validate_board_image_path(user_id, blog_clip_id, image_path))
    if text is not None:
        updates.append("text = ?")
        values.append(text)
    if duration_seconds is not None:
        updates.append("duration_seconds = ?")
        values.append(duration_seconds)
    if speaker is not SPEAKER_UNSET:
        if speaker is None or (isinstance(speaker, str) and not speaker.strip()):
            updates.append("speaker = NULL")
        else:
            updates.append("speaker = ?")
            values.append(validate_voice_id(str(speaker)))
    if sfx_asset_id is not SFX_UNSET:
        if sfx_asset_id is None:
            updates.append("sfx_asset_id = NULL")
        else:
            assert_audio_asset_usable(conn, user_id, int(sfx_asset_id), kind="sfx")
            updates.append("sfx_asset_id = ?")
            values.append(int(sfx_asset_id))

    if not updates:
        return _row_to_blog_clip_board(row)

    values.append(board_id)
    conn.execute(
        f"UPDATE blog_clip_boards SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values,
    )
    conn.commit()
    if text is not None or duration_seconds is not None or speaker is not SPEAKER_UNSET or sfx_asset_id is not SFX_UNSET:
        _invalidate_preview_audio(user_id, blog_clip_id)

    refreshed = conn.execute(
        f"SELECT {_BLOG_CLIP_BOARD_COLUMNS} FROM blog_clip_boards WHERE id = ?",
        (board_id,),
    ).fetchone()
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Board update failed.")
    return _row_to_blog_clip_board(refreshed)


def update_blog_clip_tts_settings(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    tts_speed: float,
) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)
    speed = clamp_tts_speed(tts_speed)
    conn.execute(
        "UPDATE blog_clips SET tts_speed = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (speed, blog_clip_id),
    )
    conn.commit()
    _invalidate_preview_audio(user_id, blog_clip_id)
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="TTS settings update failed.")
    return refreshed


def update_blog_clip_wizard_step(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    wizard_step: str,
) -> BlogClip:
    """Persist client wizard sub-step while status is awaiting_boards (W5)."""
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "awaiting_boards":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="wizard_step can only be updated while awaiting board confirmation.",
        )
    step = (wizard_step or "").strip().lower()
    if step in LEGACY_WIZARD_STEPS:
        step = "edit_mode"
    if step not in ALLOWED_WIZARD_STEPS - LEGACY_WIZARD_STEPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="wizard_step must be video_style, edit_mode, quick, or ready.",
        )
    conn.execute(
        """
        UPDATE blog_clips
        SET wizard_step = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (step, blog_clip_id),
    )
    conn.commit()
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Wizard step update failed.")
    return refreshed


def update_blog_clip_default_voice(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    *,
    voice_id: str,
    tts_speed: float = 1.0,
    apply_to_all_boards: bool = True,
) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)

    voice = validate_voice_id(voice_id)
    speed = clamp_tts_speed(tts_speed)
    conn.execute(
        """
        UPDATE blog_clips
        SET default_voice = ?, tts_speed = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (voice, speed, blog_clip_id),
    )
    if apply_to_all_boards:
        conn.execute(
            """
            UPDATE blog_clip_boards
            SET speaker = ?, updated_at = CURRENT_TIMESTAMP
            WHERE blog_clip_id = ?
            """,
            (voice, blog_clip_id),
        )
    conn.commit()
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Default voice update failed.")
    return refreshed


def update_blog_clip_audio_settings(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    *,
    bgm_asset_id: Any = BGM_ASSET_UNSET,
    bgm_volume: float | None = None,
    auto_bgm: bool | None = None,
    auto_sfx: bool | None = None,
) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)

    updates: list[str] = []
    values: list[Any] = []
    if bgm_asset_id is not BGM_ASSET_UNSET:
        if bgm_asset_id is None:
            updates.append("bgm_asset_id = NULL")
        else:
            assert_audio_asset_usable(conn, user_id, int(bgm_asset_id), kind="bgm")
            updates.append("bgm_asset_id = ?")
            values.append(int(bgm_asset_id))
            # Manual BGM pick clears auto mode.
            updates.append("auto_bgm = 0")
    if bgm_volume is not None:
        updates.append("bgm_volume = ?")
        values.append(clamp_bgm_volume(bgm_volume))
    if auto_bgm is not None:
        updates.append("auto_bgm = ?")
        values.append(1 if auto_bgm else 0)
        if auto_bgm:
            updates.append("bgm_asset_id = NULL")
    if auto_sfx is not None:
        updates.append("auto_sfx = ?")
        values.append(1 if auto_sfx else 0)

    if not updates:
        return blog_clip

    values.append(blog_clip_id)
    conn.execute(
        f"UPDATE blog_clips SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values,
    )
    conn.commit()
    _invalidate_preview_audio(user_id, blog_clip_id)
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Audio settings update failed.")
    return refreshed


def _apply_auto_audio_for_render(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip: BlogClip,
) -> BlogClip:
    """Resolve auto_bgm / auto_sfx onto concrete asset IDs before Phase 2."""
    if blog_clip.auto_bgm and blog_clip.bgm_asset_id is None:
        bgm = pick_default_bgm(conn, blog_clip.script_tone, blog_clip.target_length)
        if bgm is not None:
            conn.execute(
                "UPDATE blog_clips SET bgm_asset_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (bgm.id, blog_clip.id),
            )

    if blog_clip.auto_sfx:
        boards = list_blog_clip_boards(conn, user_id, blog_clip.id)
        # Place varied SFX at transitions into boards after the first.
        for board_index, board in enumerate(boards[1:], start=1):
            if board.sfx_asset_id is None:
                sfx = pick_default_sfx(conn, board_index=board_index)
                if sfx is None:
                    break
                conn.execute(
                    """
                    UPDATE blog_clip_boards
                    SET sfx_asset_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (sfx.id, board.id),
                )

    conn.commit()
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip.id)
    return refreshed if refreshed is not None else blog_clip


def apply_blog_clip_template(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    template_id: int,
) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)
    template = assert_template_usable(conn, user_id, template_id)
    style = template.slug if template.slug in ALLOWED_SUBTITLE_STYLES else blog_clip.subtitle_style
    conn.execute(
        """
        UPDATE blog_clips
        SET subtitle_template_id = ?, subtitle_style = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (template.id, style, blog_clip_id),
    )
    conn.commit()
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Template apply failed.")
    return refreshed


def update_blog_clip_visual_style(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    visual_style: str,
) -> BlogClip:
    from app.services.visual_style_catalog import ALLOWED_VISUAL_STYLES, normalize_visual_style

    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)
    slug = (visual_style or "").strip().lower()
    if slug not in ALLOWED_VISUAL_STYLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visual_style must be fullscreen, card_news, info_dark, or bold_hook.",
        )
    slug = normalize_visual_style(slug)
    conn.execute(
        """
        UPDATE blog_clips
        SET visual_style = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (slug, blog_clip_id),
    )
    conn.commit()
    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Visual style update failed.")
    return refreshed


def delete_blog_clip_board(conn: sqlite3.Connection, user_id: int, blog_clip_id: int, board_id: int) -> None:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)

    deleted = conn.execute(
        "DELETE FROM blog_clip_boards WHERE id = ? AND blog_clip_id = ?",
        (board_id, blog_clip_id),
    )
    if deleted.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
    conn.commit()
    _normalize_board_order_indices(conn, blog_clip_id)


def reorder_blog_clip_boards(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    board_ids: list[int],
) -> list[BlogClipBoard]:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)

    current_boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
    current_ids = {board.id for board in current_boards}
    requested_ids = set(board_ids)
    if current_ids != requested_ids or len(board_ids) != len(current_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="board_ids must include every current board exactly once.")

    for index, board_id in enumerate(board_ids):
        conn.execute(
            "UPDATE blog_clip_boards SET order_index = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND blog_clip_id = ?",
            (index, board_id, blog_clip_id),
        )
    conn.commit()
    return list_blog_clip_boards(conn, user_id, blog_clip_id)


def start_blog_clip_render(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "awaiting_boards":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Blog short is not waiting for board confirmation.",
        )

    blog_clip = _apply_auto_audio_for_render(conn, user_id, blog_clip)

    boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
    if not boards:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="보드가 없습니다. 최소 1개 이상의 보드가 필요합니다.",
        )

    combined_script = " ".join(board.text.strip() for board in boards if board.text.strip()).strip()
    if not combined_script:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one board must contain narration text.")

    status_value, progress_stage, progress_percent = PROGRESS_SYNTHESIZING_AUDIO
    conn.execute(
        """
        UPDATE blog_clips
        SET narration_script = ?,
            status = ?,
            progress_stage = ?,
            progress_percent = ?,
            error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (combined_script, status_value, progress_stage, progress_percent, blog_clip_id),
    )
    conn.commit()

    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Blog short render start failed.")
    return refreshed


# --- Blog scraping ------------------------------------------------------------


def _is_naver_blog_url(url: str) -> bool:
    return "blog.naver.com" in urlparse(url).netloc


def _resolve_image_src(img: Tag, base_url: str) -> str | None:
    src = img.get("data-lazy-src") or img.get("data-src") or img.get("data-original") or img.get("src")
    if not src or src.startswith("data:"):
        return None
    return urljoin(base_url, src)


def _prefer_high_res_image_url(url: str) -> str:
    """Prefer the largest common Naver CDN width (w966) over editor thumbnails (w466)."""
    host = (urlparse(url).netloc or "").lower()
    if "pstatic.net" not in host and "blogfiles.naver.net" not in host:
        return url

    match = re.search(r"([?&]type=)w(\d+)", url, flags=re.IGNORECASE)
    if match:
        width = int(match.group(2))
        if width < 966:
            return re.sub(r"([?&]type=)w\d+", r"\1w966", url, count=1, flags=re.IGNORECASE)
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}type=w966"


def _extract_image_urls(container: Tag, base_url: str) -> list[str]:
    image_urls: list[str] = []
    for img in container.find_all("img"):
        resolved = _resolve_image_src(img, base_url)
        if not resolved:
            continue
        preferred = _prefer_high_res_image_url(resolved)
        if preferred not in image_urls:
            image_urls.append(preferred)
    return image_urls


def _parse_naver_blog_ids(url: str) -> tuple[str, str]:
    blog_id_match = re.search(r"blogId=([^&]+)", url)
    log_no_match = re.search(r"logNo=([0-9]+)", url)
    if blog_id_match and log_no_match:
        return blog_id_match.group(1), log_no_match.group(1)

    path_match = re.search(r"blog\.naver\.com/([^/?#]+)/([0-9]+)", url)
    if path_match:
        return path_match.group(1), path_match.group(2)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="네이버 블로그 URL에서 블로그 아이디/글 번호를 찾을 수 없습니다.",
    )


def fetch_naver_blog_content(url: str) -> BlogContent:
    blog_id, log_no = _parse_naver_blog_ids(url)
    fetch_url = (
        f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
        "&redirect=Dlog&widgetTypeCall=true&directAccess=false"
    )

    try:
        response = requests.get(
            fetch_url,
            headers={"User-Agent": _USER_AGENT},
            timeout=settings.blog_fetch_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"블로그 페이지를 가져오지 못했습니다: {exc}") from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"블로그 페이지를 가져오지 못했습니다 (HTTP {response.status_code}).",
        )

    soup = BeautifulSoup(response.text, "html.parser")

    container = soup.select_one("div.se-main-container") or soup.select_one("#postViewArea")
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="블로그 본문을 찾을 수 없습니다. 비공개 글이거나 접근이 제한된 게시물일 수 있습니다.",
        )

    title_element = soup.select_one("div.se-title-text") or soup.select_one("#title_1")
    if title_element is not None:
        title = clean_subtitle_text(title_element.get_text(" "))
    else:
        og_title = soup.select_one('meta[property="og:title"]')
        title = clean_subtitle_text(og_title["content"]) if og_title and og_title.get("content") else "블로그 글"

    paragraph_elements = container.select(".se-text-paragraph") or container.find_all(["p", "span"])
    paragraphs = [clean_subtitle_text(element.get_text(" ")) for element in paragraph_elements]
    text = " ".join(paragraph for paragraph in paragraphs if paragraph)
    if not text:
        text = clean_subtitle_text(container.get_text(" "))
    if not text:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="블로그 본문 텍스트를 추출하지 못했습니다.")

    image_urls = _extract_image_urls(container, url)
    return BlogContent(title=title, text=text[:6000], image_urls=image_urls)


def _strip_noise_tags(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(_REMOVE_TAG_NAMES):
        tag.decompose()


def _extract_generic_title(soup: BeautifulSoup) -> str:
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title and og_title.get("content"):
        return clean_subtitle_text(og_title["content"])
    if soup.title and soup.title.string:
        return clean_subtitle_text(soup.title.string)
    h1 = soup.find("h1")
    if h1 is not None:
        return clean_subtitle_text(h1.get_text(" "))
    return "블로그 글"


def _find_generic_content_container(soup: BeautifulSoup) -> Tag:
    for selector in _GENERIC_CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container is not None and len(container.get_text(strip=True)) >= _GENERIC_MIN_CONTAINER_TEXT_LENGTH:
            return container

    # No known platform container matched (or it was too short) — fall back
    # to the <div> with the most text, which works reasonably well for
    # unfamiliar blogging platforms and simple article pages.
    best_container: Tag | None = None
    best_length = 0
    for candidate in soup.find_all("div"):
        text_length = len(candidate.get_text(strip=True))
        if text_length > best_length:
            best_container = candidate
            best_length = text_length
    return best_container or soup.body or soup


def fetch_generic_blog_content(url: str) -> BlogContent:
    """Best-effort scraper for any non-Naver blog/article URL.

    Naver's post structure is fixed and well-known (`fetch_naver_blog_content`
    above targets it exactly), but there is no single markup convention across
    Tistory, Velog, brunch, WordPress, Medium, and plain article pages. This
    uses a prioritized list of common container selectors, falling back to
    "the <div> with the most text" heuristic when none of them match.
    """
    try:
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=settings.blog_fetch_timeout_seconds)
    except requests.RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"블로그 페이지를 가져오지 못했습니다: {exc}") from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"블로그 페이지를 가져오지 못했습니다 (HTTP {response.status_code}).",
        )

    soup = BeautifulSoup(response.text, "html.parser")
    _strip_noise_tags(soup)

    title = _extract_generic_title(soup)
    container = _find_generic_content_container(soup)

    paragraph_elements = container.find_all(["p", "li", "h2", "h3", "blockquote"])
    paragraphs = [clean_subtitle_text(element.get_text(" ")) for element in paragraph_elements]
    text = " ".join(paragraph for paragraph in paragraphs if paragraph)
    if not text:
        text = clean_subtitle_text(container.get_text(" "))
    if not text:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="블로그 본문 텍스트를 추출하지 못했습니다.")

    image_urls = _extract_image_urls(container, url)
    if len(image_urls) < settings.blog_image_min_count:
        # The hero/thumbnail image is sometimes rendered outside the main
        # content container (e.g. a separate header banner) — widen the
        # search to the whole page if the container alone came up short.
        page_image_urls = _extract_image_urls(soup, url)
        image_urls = image_urls + [candidate for candidate in page_image_urls if candidate not in image_urls]

    return BlogContent(title=title, text=text[:6000], image_urls=image_urls)


def fetch_blog_content(url: str) -> BlogContent:
    if _is_naver_blog_url(url):
        return fetch_naver_blog_content(url)
    return fetch_generic_blog_content(url)


def _download_image_bytes(url: str) -> tuple[bytes, str] | None:
    """Return (content, content_type) or None on failure / tiny payload."""
    try:
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=settings.blog_fetch_timeout_seconds)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type not in _CONTENT_TYPE_EXTENSIONS:
        return None
    if len(response.content) < _MIN_IMAGE_BYTES:
        return None
    return response.content, content_type


def download_blog_images(image_urls: list[str], dest_dir: Path) -> list[tuple[Path, str]]:
    """Download images; return (local_path, source_url) pairs up to blog_image_max_count."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[tuple[Path, str]] = []

    for url in image_urls:
        if len(saved) >= settings.blog_image_max_count:
            break
        preferred = _prefer_high_res_image_url(url)
        downloaded = _download_image_bytes(preferred)
        source_used = preferred
        if downloaded is None and preferred != url:
            downloaded = _download_image_bytes(url)
            source_used = url
        if downloaded is None:
            continue

        content, content_type = downloaded
        extension = _CONTENT_TYPE_EXTENSIONS[content_type]
        image_path = dest_dir / f"{uuid.uuid4().hex}{extension}"
        image_path.write_bytes(content)
        saved.append((image_path, source_used))

    return saved


def upgrade_blog_clip_images_to_high_res(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> int:
    """Re-download candidate images at Naver w966 when a larger file is available.

    Returns how many storage files were replaced. Safe to call before Remotion render.
    """
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        return 0

    rows = conn.execute(
        """
        SELECT id, storage_path, source_url
        FROM blog_clip_image_candidates
        WHERE blog_clip_id = ?
        """,
        (blog_clip_id,),
    ).fetchall()

    upgraded = 0
    for row in rows:
        source_url = row["source_url"]
        storage_path = row["storage_path"]
        if not source_url or not storage_path:
            continue
        path = Path(storage_path)
        if not path.is_file():
            continue

        preferred = _prefer_high_res_image_url(source_url)
        if preferred == source_url and "type=w966" not in preferred.lower():
            continue

        downloaded = _download_image_bytes(preferred)
        if downloaded is None:
            continue
        content, _content_type = downloaded
        current_size = path.stat().st_size
        # Only replace when the high-res payload is meaningfully larger.
        if len(content) < current_size + 8_192:
            continue

        path.write_bytes(content)
        if preferred != source_url:
            conn.execute(
                """
                UPDATE blog_clip_image_candidates
                SET source_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (preferred, row["id"]),
            )
        upgraded += 1

    if upgraded:
        conn.commit()
        logger.info("Upgraded %s blog images to higher res for clip=%s", upgraded, blog_clip_id)
    return upgraded


# --- GPT script + metadata ---------------------------------------------------


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned invalid narration script JSON.")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned invalid narration script JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned invalid narration script JSON.")
    return parsed


def _narration_hook_guidance() -> str:
    """Extra rules for the promotional 'hook' tone (Shorts/Reels style ads)."""
    return """
Extra rules ONLY for the "hook" key (promotional Shorts voiceover):
- Goal: sound like the short product/service promo clips people scroll past every day
  (car wrap/tint/detailing, beauty, food, local shops, gadgets, B2B services, etc.—
  match whatever the blog is actually about; do not force a car theme).
- Structure (must follow):
  1) HOOK (first sentence, ~1–3 seconds): pick ONE formula that fits the blog facts:
     question | bold twist | number/fact | mini story | curiosity gap | result-first.
  2) VALUE: what it is / why it matters, in plain spoken language.
  3) PROOF or DETAIL: one concrete point from the blog (process, before/after vibe,
     material, price range, tip)—only if present in the source.
  4) SOFT CTA: invite inquiry, visit, save, or try—without fake urgency or fake discounts.
- Voice: punchy, spoken, confident, slightly salesy but not spammy. Short sentences.
- Avoid weak openings like "오늘은", "이번 글에서는", "안녕하세요", or reading the title.
- Do NOT invent stats, reviews, rankings, "No.1", guarantees, or prices missing from the blog.
- If the post is educational, still frame the hook as a problem → solution promo for that tip.
""".strip()


def _narration_length_guidance(target_length: str) -> str:
    if target_length == "long":
        return """
Length target: longer short-form (~30-45 seconds overall).
Tone rules:
- "summary": calm factual overview. About 25-35 seconds when read aloud.
- "hook": promotional Shorts script (see hook rules below). About 30-40 seconds.
- "detailed": richer explanation with 1-2 concrete details from the post. About 35-45 seconds.
""".strip()
    return """
Length target: short short-form (~10-20 seconds overall). Keep every tone concise.
Tone rules:
- "summary": calm factual overview. About 10-15 seconds when read aloud.
- "hook": promotional Shorts script (see hook rules below). About 12-18 seconds.
- "detailed": one concrete detail from the post, still brief. About 15-20 seconds.
""".strip()


def _narration_language_guidance(narration_language: str) -> str:
    if narration_language == "ko":
        return "Write every script in Korean."
    if narration_language == "en":
        return "Write every script in English."
    if narration_language == "ja":
        return "Write every script in Japanese."
    return "Write in the same language as the blog text (match the source). If unclear, prefer Korean."


def _resolve_script_model(model: str | None) -> str:
    resolved = (model or settings.openai_metadata_model or "gpt-4o-mini").strip()
    if resolved not in ALLOWED_SCRIPT_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="script_model must be gpt-4o-mini or gpt-4o.",
        )
    return resolved


def generate_blog_narration_script_candidates(
    blog_title: str,
    blog_text: str,
    *,
    target_length: str = "short",
    narration_language: str = "original",
    model: str | None = None,
) -> dict[str, str]:
    """Generate three tone variants (summary / hook / detailed) in one GPT call."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")
    if target_length not in ALLOWED_TARGET_LENGTHS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_length must be short or long.")
    if narration_language not in ALLOWED_NARRATION_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="narration_language must be original, ko, en, or ja.",
        )
    script_model = _resolve_script_model(model)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""
Create three short AI narration scripts for a vertical shorts video based on one blog post.
Return ONLY valid JSON with exactly these keys: "summary", "hook", "detailed".

{_narration_length_guidance(target_length)}

{_narration_hook_guidance()}

Shared rules for every tone:
- {_narration_language_guidance(narration_language)}
- Use only facts present in the blog text. Do not invent claims.
- Keep it natural when read aloud as a short-form voiceover.
- Do not include stage directions, timestamps, markdown, hashtags, or the title text itself.
- Avoid exaggerated or misleading claims.
- Each value must be a plain string (the full narration script for that tone).

Blog title: {blog_title}

Blog text:
{blog_text}
""".strip()

    try:
        response = client.chat.completions.create(
            model=script_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write voiceover narration for vertical Shorts/Reels. "
                        "For the hook tone, write like a polished product or local-service promo short. "
                        "Respond with JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OpenAI rate limit reached. Try again later.") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not connect to OpenAI GPT API.") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OpenAI GPT API error: {exc.status_code}") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Narration script generation failed: {exc}") from exc

    raw = response.choices[0].message.content if response.choices else None
    payload = _extract_json_object(raw or "")
    candidates: dict[str, str] = {}
    for tone in ALLOWED_SCRIPT_TONES:
        script = clean_subtitle_text(str(payload.get(tone, "")))
        if not script:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI returned an empty '{tone}' narration script.",
            )
        candidates[tone] = script[:900]
    return candidates


def blog_clip_script_candidates(blog_clip: BlogClip) -> dict[str, str]:
    try:
        parsed = json.loads(blog_clip.script_candidates_json or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        tone: clean_subtitle_text(str(parsed[tone]))
        for tone in ALLOWED_SCRIPT_TONES
        if tone in parsed and str(parsed[tone]).strip()
    }


def _normalize_hashtag(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value.strip())
    cleaned = cleaned.lstrip("#")
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_]+", "", cleaned)
    if not cleaned:
        return ""
    return f"#{cleaned[:40]}"


def _parse_metadata_json(raw_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to parse GPT metadata JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT metadata response was not a JSON object.")

    raw_titles = payload.get("title_candidates")
    raw_description = payload.get("description")
    raw_hashtags = payload.get("hashtags")
    if not isinstance(raw_titles, list) or not isinstance(raw_description, str) or not isinstance(raw_hashtags, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT metadata response is missing required fields.")

    titles = [str(item).strip()[:90] for item in raw_titles if str(item).strip()][:3]
    hashtags: list[str] = []
    for item in raw_hashtags:
        tag = _normalize_hashtag(str(item))
        if tag and tag not in hashtags:
            hashtags.append(tag)
        if len(hashtags) == 10:
            break

    description = raw_description.strip()[:700]
    if len(titles) != 3 or not description or len(hashtags) != 10:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT returned incomplete metadata.")
    return {"title_candidates": titles, "description": description, "hashtags": hashtags}


def generate_blog_metadata(blog_title: str, script: str, *, model: str | None = None) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")
    script_model = _resolve_script_model(model)

    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = (
        "You write practical upload metadata for short-form videos. "
        "Return only valid JSON. Avoid exaggerated, misleading, or unverifiable claims. "
        "Write in Korean unless the script is clearly not Korean. "
        "The result must be ready for a beginner to copy into YouTube Shorts, Instagram Reels, or TikTok."
    )
    user_prompt = f"""
Create upload metadata for this short video, which summarizes a blog post.

Return JSON exactly like:
{{"title_candidates":["...","...","..."],"description":"...","hashtags":["#...","#...","#...","#...","#...","#...","#...","#...","#...","#..."]}}

Rules:
- title_candidates must contain exactly 3 natural, non-clickbait titles.
- description must be concise, useful, and safe to paste as-is.
- hashtags must contain exactly 10 relevant hashtags.
- Do not invent facts that are not supported by the script.

Blog title: {blog_title}

Narration script:
{script}
""".strip()

    try:
        response = client.chat.completions.create(
            model=script_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OpenAI rate limit reached. Try again later.") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not connect to OpenAI GPT API.") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OpenAI GPT API error: {exc.status_code}") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Metadata generation failed: {exc}") from exc

    raw_text = response.choices[0].message.content if response.choices else None
    if not raw_text:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT returned an empty metadata response.")
    return _parse_metadata_json(raw_text)


# --- Subtitle timing from boards -----------------------------------------------


def _board_voice_id(board: BlogClipBoard, default_voice: str | None = None) -> str:
    if board.speaker and board.speaker.strip():
        return validate_voice_id(board.speaker)
    if default_voice and default_voice.strip():
        return validate_voice_id(default_voice)
    return default_tts_voice()


def _synthesize_blog_clip_narration(
    user_id: int,
    blog_clip_id: int,
    boards: list[BlogClipBoard],
    tts_speed: float,
    *,
    default_voice: str | None = None,
) -> tuple[str, list[float]]:
    """Build narration audio for boards.

    Always synthesizes per board then concatenates so each board's durationSec
    matches its audio segment — captions and narration stay in sync in Remotion.
    (Merged single-TTS + duration splitting drifted after the first few boards.)
    """
    speed = clamp_tts_speed(tts_speed)
    spoken = [board for board in boards if board.text.strip()]
    if not spoken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one board must contain narration text.")

    work_dir = STORAGE_ROOT / "tts" / str(user_id) / f"blog_{blog_clip_id}_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    use_legacy_default_voice = all(not (board.speaker and board.speaker.strip()) for board in spoken) and not (
        default_voice and default_voice.strip()
    )

    segment_paths: list[str] = []
    durations: list[float] = []
    for index, board in enumerate(boards):
        text = board.text.strip()
        segment_path = work_dir / f"seg_{index:03d}.mp3"
        if text:
            if use_legacy_default_voice:
                raw_path = synthesize_openai_tts(user_id, blog_clip_id, text, speed=speed)
            else:
                voice = _board_voice_id(board, default_voice)
                raw_path = synthesize_openai_tts(user_id, blog_clip_id, text, voice=voice, speed=speed)
            # TTS length is the source of truth for A/V sync — do not pad to stale
            # board.duration_seconds from a previous preview/edit.
            segment_path.write_bytes(Path(raw_path).read_bytes())
            duration = get_video_duration_seconds(str(segment_path))
        else:
            duration = max(0.5, float(board.duration_seconds) if board.duration_seconds is not None else 0.5)
            create_silence_mp3(duration, str(segment_path))
            duration = get_video_duration_seconds(str(segment_path))
        segment_paths.append(str(segment_path))
        durations.append(duration)

    output_path = work_dir / "narration_concat.mp3"
    concat_audio_files(segment_paths, str(output_path))
    return str(output_path), durations


def _board_subtitle_events(boards: list[BlogClipBoard], board_durations: list[float]) -> list[tuple[float, float, str]]:
    events: list[tuple[float, float, str]] = []
    cursor = 0.0

    for board, duration in zip(boards, board_durations):
        text = clean_subtitle_text(board.text)
        if not text or duration <= 0:
            cursor += duration
            continue
        chunks = split_text_for_duration(text, duration, 18)
        if not chunks:
            cursor += duration
            continue
        chunk_duration = duration / len(chunks)
        for chunk in chunks:
            start = cursor
            end = cursor + chunk_duration
            if end > start:
                events.append((start, end, chunk))
            cursor = end

    return events


def _preview_audio_path(user_id: int, blog_clip_id: int) -> Path:
    return BLOG_PREVIEW_AUDIO_ROOT / str(user_id) / f"{blog_clip_id}.mp3"


def _persist_board_durations(
    conn: sqlite3.Connection,
    boards: list[BlogClipBoard],
    board_durations: list[float],
) -> None:
    """Write TTS-derived lengths onto boards so Player timeline matches final render."""
    if len(boards) != len(board_durations):
        return
    for board, duration in zip(boards, board_durations):
        if board.id is None:
            continue
        conn.execute(
            "UPDATE blog_clip_boards SET duration_seconds = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (max(0.5, float(duration)), board.id),
        )
    conn.commit()


def _mix_blog_clip_audio(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip: BlogClip,
    boards: list[BlogClipBoard],
    narration_audio_path: str,
    board_durations: list[float],
) -> str:
    """Apply BGM (ducked) + timed SFX; return path to mixed (or plain) MP3."""
    mixed_audio_path = narration_audio_path
    bgm_path = None
    if blog_clip.bgm_asset_id is not None:
        bgm_asset = assert_audio_asset_usable(conn, user_id, blog_clip.bgm_asset_id, kind="bgm")
        bgm_path = bgm_asset.storage_path

    sfx_events: list[tuple[str, float, float]] = []
    cursor = 0.0
    for board, duration in zip(boards, board_durations):
        if board.sfx_asset_id is not None:
            sfx_asset = assert_audio_asset_usable(conn, user_id, board.sfx_asset_id, kind="sfx")
            sfx_events.append((sfx_asset.storage_path, cursor, DEFAULT_SFX_VOLUME))
        cursor += duration

    if bgm_path is not None or sfx_events:
        mix_dir = Path(narration_audio_path).parent
        mixed_audio_path = str(mix_dir / f"mixed_{uuid.uuid4().hex}.mp3")
        mix_narration_with_bed(
            narration_audio_path,
            mixed_audio_path,
            bgm_path=bgm_path,
            bgm_volume=clamp_bgm_volume(blog_clip.bgm_volume),
            narration_volume=1.0,
            sfx_events=sfx_events,
            duck_bgm=True,
        )
    return mixed_audio_path


def _cache_preview_audio(user_id: int, blog_clip_id: int, mixed_audio_path: str) -> Path:
    dest = _preview_audio_path(user_id, blog_clip_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mixed_audio_path, dest)
    return dest


def _invalidate_preview_audio(user_id: int, blog_clip_id: int) -> None:
    path = _preview_audio_path(user_id, blog_clip_id)
    path.unlink(missing_ok=True)


def get_blog_clip_preview_audio_path(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> Path:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    path = _preview_audio_path(user_id, blog_clip_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="미리듣기 오디오가 없습니다. TTS/BGM 미리듣기를 먼저 생성하세요.",
        )
    return path


def build_blog_clip_preview_audio(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
) -> tuple[Path, list[float]]:
    """TTS + BGM/SFX mix for Player preview (same mix as final Remotion audio)."""
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)
    # Match final render: resolve auto_bgm / auto_sfx before mixing.
    blog_clip = _apply_auto_audio_for_render(conn, user_id, blog_clip)
    boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
    if not boards:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이 블로그 쇼츠에 보드가 없습니다.")

    narration_audio_path, board_durations = _synthesize_blog_clip_narration(
        user_id,
        blog_clip.id,
        boards,
        blog_clip.tts_speed,
        default_voice=blog_clip.default_voice,
    )
    mixed_audio_path = _mix_blog_clip_audio(
        conn,
        user_id,
        blog_clip,
        boards,
        narration_audio_path,
        board_durations,
    )
    _persist_board_durations(conn, boards, board_durations)
    cached = _cache_preview_audio(user_id, blog_clip.id, mixed_audio_path)
    return cached, board_durations


# --- Orchestration ------------------------------------------------------------


def _update_blog_clip_progress(conn: sqlite3.Connection, blog_clip_id: int, checkpoint: tuple[str, str, int]) -> None:
    status_value, progress_stage, progress_percent = checkpoint
    conn.execute(
        """
        UPDATE blog_clips
        SET status = ?, progress_stage = ?, progress_percent = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, progress_stage, progress_percent, blog_clip_id),
    )
    conn.commit()


def _update_blog_clip_failed(conn: sqlite3.Connection, blog_clip_id: int, error_message: str) -> None:
    conn.execute(
        "UPDATE blog_clips SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (error_message, blog_clip_id),
    )
    conn.commit()


def _update_blog_clip_result(
    conn: sqlite3.Connection,
    blog_clip_id: int,
    blog_title: str,
    narration_script: str,
    video_path: str,
    subtitled_video_path: str,
    *,
    script_tone: str | None = None,
    version_source: str = "boards",
    render_spec: dict[str, Any] | None = None,
) -> int:
    """Mark parent completed and mirror output into a blog_clip_versions row.

    Returns the active version id. Parent path fields stay denormalized for
    Stage 15–23 download/metadata clients.
    """
    status_value, progress_stage, progress_percent = PROGRESS_DONE
    row = conn.execute(
        "SELECT script_tone FROM blog_clips WHERE id = ?",
        (blog_clip_id,),
    ).fetchone()
    tone = script_tone if script_tone is not None else (row["script_tone"] if row else None)
    label = SCRIPT_TONE_LABELS.get(tone or "", "보드 렌더") if tone else "보드 렌더"
    render_spec_json = json.dumps(render_spec, ensure_ascii=False) if render_spec else None

    cursor = conn.execute(
        """
        INSERT INTO blog_clip_versions (
            blog_clip_id, label, source, script_tone, narration_script,
            video_path, subtitled_video_path, status, progress_stage, progress_percent,
            error_message, render_spec_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            blog_clip_id,
            label,
            version_source,
            tone,
            narration_script,
            video_path,
            subtitled_video_path,
            status_value,
            progress_stage,
            progress_percent,
            render_spec_json,
        ),
    )
    version_id = int(cursor.lastrowid)

    conn.execute(
        """
        UPDATE blog_clips
        SET status = ?,
            progress_stage = ?,
            progress_percent = ?,
            blog_title = ?,
            narration_script = ?,
            video_path = ?,
            subtitled_video_path = ?,
            render_spec_json = ?,
            active_version_id = ?,
            error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status_value,
            progress_stage,
            progress_percent,
            blog_title,
            narration_script,
            video_path,
            subtitled_video_path,
            render_spec_json,
            version_id,
            blog_clip_id,
        ),
    )
    conn.commit()
    return version_id


def _update_blog_clip_awaiting_images(
    conn: sqlite3.Connection,
    blog_clip_id: int,
    blog_title: str,
    candidates: dict[str, str],
) -> None:
    status_value, progress_stage, progress_percent = PROGRESS_AWAITING_IMAGES
    conn.execute(
        """
        UPDATE blog_clips
        SET status = ?,
            progress_stage = ?,
            progress_percent = ?,
            blog_title = ?,
            script_candidates_json = ?,
            error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status_value,
            progress_stage,
            progress_percent,
            blog_title,
            json.dumps(candidates, ensure_ascii=False),
            blog_clip_id,
        ),
    )
    conn.commit()


def _row_to_image_candidate(row: sqlite3.Row) -> BlogClipImageCandidate:
    return BlogClipImageCandidate(
        id=row["id"],
        blog_clip_id=row["blog_clip_id"],
        order_index=row["order_index"],
        storage_path=row["storage_path"],
        source_url=row["source_url"],
        selected=bool(row["selected"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _replace_blog_clip_image_candidates(
    conn: sqlite3.Connection,
    blog_clip_id: int,
    downloaded: list[tuple[Path, str]],
) -> None:
    conn.execute("DELETE FROM blog_clip_image_candidates WHERE blog_clip_id = ?", (blog_clip_id,))
    for index, (path, source_url) in enumerate(downloaded):
        conn.execute(
            """
            INSERT INTO blog_clip_image_candidates (
                blog_clip_id, order_index, storage_path, source_url, selected
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (blog_clip_id, index, str(path), source_url),
        )
    conn.commit()


def list_blog_clip_image_candidates(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
) -> list[BlogClipImageCandidate]:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    rows = conn.execute(
        """
        SELECT id, blog_clip_id, order_index, storage_path, source_url, selected, created_at, updated_at
        FROM blog_clip_image_candidates
        WHERE blog_clip_id = ?
        ORDER BY order_index ASC, id ASC
        """,
        (blog_clip_id,),
    ).fetchall()
    return [_row_to_image_candidate(row) for row in rows]


def get_blog_clip_image_candidate_path(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    image_id: int,
) -> Path:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    row = conn.execute(
        """
        SELECT storage_path FROM blog_clip_image_candidates
        WHERE id = ? AND blog_clip_id = ?
        """,
        (image_id, blog_clip_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image candidate not found.")
    validated = _validate_board_image_path(user_id, blog_clip_id, row["storage_path"])
    return Path(validated)


def _list_selected_blog_images(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> list[Path]:
    rows = conn.execute(
        """
        SELECT storage_path FROM blog_clip_image_candidates
        WHERE blog_clip_id = ? AND selected = 1
        ORDER BY order_index ASC, id ASC
        """,
        (blog_clip_id,),
    ).fetchall()
    paths: list[Path] = []
    for row in rows:
        try:
            paths.append(Path(_validate_board_image_path(user_id, blog_clip_id, row["storage_path"])))
        except HTTPException:
            continue
    return paths


def confirm_blog_clip_image_selection(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    image_ids: list[int],
) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "awaiting_images":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Blog short is not waiting for image selection.",
        )

    unique_ids = list(dict.fromkeys(image_ids))
    if len(unique_ids) < settings.blog_image_min_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Select at least {settings.blog_image_min_count} images.",
        )
    if len(unique_ids) > settings.blog_image_max_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Select at most {settings.blog_image_max_count} images.",
        )

    candidates = list_blog_clip_image_candidates(conn, user_id, blog_clip_id)
    candidate_ids = {item.id for item in candidates}
    if not unique_ids or any(image_id not in candidate_ids for image_id in unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_ids must refer to candidates for this blog short.",
        )

    selected_set = set(unique_ids)
    for candidate in candidates:
        conn.execute(
            """
            UPDATE blog_clip_image_candidates
            SET selected = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if candidate.id in selected_set else 0, candidate.id),
        )

    # Preserve selection order as order_index among selected (and keep unselected after).
    for index, image_id in enumerate(unique_ids):
        conn.execute(
            """
            UPDATE blog_clip_image_candidates
            SET order_index = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (index, image_id),
        )
    remaining = [item for item in candidates if item.id not in selected_set]
    for offset, candidate in enumerate(remaining):
        conn.execute(
            """
            UPDATE blog_clip_image_candidates
            SET order_index = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (len(unique_ids) + offset, candidate.id),
        )

    if not blog_clip_script_candidates(blog_clip):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Script candidates are not ready yet.",
        )

    status_value, progress_stage, progress_percent = PROGRESS_AWAITING_SCRIPT
    conn.execute(
        """
        UPDATE blog_clips
        SET status = ?,
            progress_stage = ?,
            progress_percent = ?,
            error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, progress_stage, progress_percent, blog_clip_id),
    )
    conn.commit()

    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Image selection failed.")
    return refreshed


def _list_saved_blog_images(user_id: int, blog_clip_id: int) -> list[Path]:
    image_dir = BLOG_IMAGE_ROOT / str(user_id) / str(blog_clip_id)
    if not image_dir.exists():
        return []
    return sorted(
        [
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        ]
    )


def create_blog_clip_job(
    conn: sqlite3.Connection,
    user_id: int,
    url: str,
    style: str,
    *,
    target_length: str = "short",
    narration_language: str = "original",
    script_model: str = "gpt-4o-mini",
) -> BlogClip:
    """Insert a `pending` blog_clips row and return immediately.

    The actual scrape/GPT/TTS/FFmpeg pipeline is not run here — call
    `run_blog_clip_pipeline()` (typically via FastAPI `BackgroundTasks`) to
    execute it after this returns. This split is what makes `POST
    /blog-clips` respond instantly instead of blocking for up to a minute.
    """
    if style not in ALLOWED_SUBTITLE_STYLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subtitle style must be basic, bold, or shorts.")
    if target_length not in ALLOWED_TARGET_LENGTHS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_length must be short or long.")
    if narration_language not in ALLOWED_NARRATION_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="narration_language must be original, ko, en, or ja.",
        )
    resolved_script_model = _resolve_script_model(script_model)

    system_template = get_system_template_by_slug(conn, style)
    template_id = system_template.id if system_template is not None else None

    status_value, progress_stage, progress_percent = PROGRESS_QUEUED
    cursor = conn.execute(
        """
        INSERT INTO blog_clips (
            user_id, source_url, subtitle_style, subtitle_template_id,
            target_length, narration_language, script_model, status, progress_stage, progress_percent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            url,
            style,
            template_id,
            target_length,
            narration_language,
            resolved_script_model,
            status_value,
            progress_stage,
            progress_percent,
        ),
    )
    conn.commit()
    blog_clip_id = int(cursor.lastrowid)
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Blog short creation failed.")
    return blog_clip


def select_blog_clip_script(conn: sqlite3.Connection, user_id: int, blog_clip_id: int, tone: str) -> BlogClip:
    """Persist the chosen tone/script, generate boards, and pause for board editing."""
    if tone not in ALLOWED_SCRIPT_TONES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Script tone must be summary, hook, or detailed.",
        )

    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "awaiting_script":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Blog short is not waiting for a script tone selection.",
        )

    candidates = blog_clip_script_candidates(blog_clip)
    script = candidates.get(tone)
    if not script:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected script tone is not available.")

    conn.execute(
        """
        UPDATE blog_clips
        SET script_tone = ?,
            narration_script = ?,
            error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (tone, script, blog_clip_id),
    )
    conn.commit()

    _generate_initial_boards(conn, user_id, blog_clip_id, script)

    status_value, progress_stage, progress_percent = PROGRESS_AWAITING_BOARDS
    conn.execute(
        """
        UPDATE blog_clips
        SET status = ?,
            progress_stage = ?,
            progress_percent = ?,
            wizard_step = 'video_style',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, progress_stage, progress_percent, blog_clip_id),
    )
    conn.commit()

    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Blog short script selection failed.")
    return refreshed


def run_blog_clip_pipeline(blog_clip_id: int, user_id: int, url: str, style: str) -> None:
    """Phase 1: scrape -> download image candidates -> GPT scripts -> awaiting_images.

    After this finishes the row is `awaiting_images`. Script tone selection continues
    after `confirm_blog_clip_image_selection()`; TTS/FFmpeg after
    `select_blog_clip_script()` + `run_blog_clip_render_pipeline()`.
    """
    connection_generator = get_connection()
    conn = next(connection_generator)
    try:
        try:
            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_SCRAPING)
            blog_content = fetch_blog_content(url)

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_DOWNLOADING_IMAGES)
            image_dir = BLOG_IMAGE_ROOT / str(user_id) / str(blog_clip_id)
            downloaded = download_blog_images(blog_content.image_urls, image_dir)
            if len(downloaded) < settings.blog_image_min_count:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"블로그에서 사용할 수 있는 이미지가 부족합니다 "
                        f"({len(downloaded)}개, 최소 {settings.blog_image_min_count}개 필요)."
                    ),
                )
            _replace_blog_clip_image_candidates(conn, blog_clip_id, downloaded)

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_GENERATING_SCRIPT)
            blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
            target_length = blog_clip.target_length if blog_clip is not None else "short"
            narration_language = blog_clip.narration_language if blog_clip is not None else "original"
            script_model = blog_clip.script_model if blog_clip is not None else "gpt-4o-mini"
            candidates = generate_blog_narration_script_candidates(
                blog_content.title,
                blog_content.text,
                target_length=target_length,
                narration_language=narration_language,
                model=script_model,
            )
            _update_blog_clip_awaiting_images(conn, blog_clip_id, blog_content.title, candidates)
        except HTTPException as exc:
            _update_blog_clip_failed(conn, blog_clip_id, str(exc.detail))
        except Exception:
            _update_blog_clip_failed(conn, blog_clip_id, "Unexpected blog short generation failure.")
    finally:
        next(connection_generator, None)


def _render_boards_media(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip: BlogClip,
    boards: list[BlogClipBoard],
    *,
    output_tag: str,
    on_progress,
) -> tuple[str, str, str, dict[str, Any]]:
    """Shared TTS/slideshow/subtitle path.

    Returns (script, video_path, subtitled_path, render_spec).
    """
    script = " ".join(board.text.strip() for board in boards if board.text.strip()).strip()
    if not script:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one board must contain narration text.")

    style = blog_clip.subtitle_style
    image_paths = [board.image_path for board in boards]
    ass_params = resolve_ass_params_for_blog_clip(
        conn,
        user_id,
        blog_clip.subtitle_template_id,
        style,
    )

    on_progress(PROGRESS_SYNTHESIZING_AUDIO)
    narration_audio_path, board_durations = _synthesize_blog_clip_narration(
        user_id,
        blog_clip.id,
        boards,
        blog_clip.tts_speed,
        default_voice=blog_clip.default_voice,
    )
    mixed_audio_path = _mix_blog_clip_audio(
        conn,
        user_id,
        blog_clip,
        boards,
        narration_audio_path,
        board_durations,
    )
    _persist_board_durations(conn, boards, board_durations)
    _cache_preview_audio(user_id, blog_clip.id, mixed_audio_path)

    on_progress(PROGRESS_RENDERING_VIDEO)
    video_dir = BLOG_OUTPUT_ROOT / str(user_id)
    video_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / f"{uuid.uuid4().hex}.mp4"

    requested_engine = (settings.blog_render_engine or "remotion").strip().lower()
    fallback_reason: str | None = None
    if requested_engine == "remotion":
        from app.services.remotion_props_service import build_remotion_render_props
        from app.services.remotion_render_service import RemotionRenderError, render_blog_shorts_with_remotion

        try:
            # Prefer Naver w966 (etc.) over tiny editor thumbnails before Remotion encode.
            upgrade_blog_clip_images_to_high_res(conn, user_id, blog_clip.id)
            props = build_remotion_render_props(
                conn,
                user_id,
                blog_clip,
                boards,
                board_durations,
                mixed_audio_path,
            )
            render_blog_shorts_with_remotion(props, video_path)
            # Captions are composed inside Remotion — no separate ASS burn-in.
            spec = _build_render_spec(
                engine="remotion",
                requested_engine=requested_engine,
                fallback_used=False,
                fallback_reason=None,
                blog_clip=blog_clip,
                boards=boards,
                board_durations=board_durations,
                video_path=str(video_path),
                captions="remotion",
            )
            return script, str(video_path), str(video_path), spec
        except RemotionRenderError as exc:
            if not settings.blog_render_ffmpeg_fallback:
                raise
            fallback_reason = str(exc)
            logger.warning(
                "Remotion render failed for blog_clip=%s; falling back to FFmpeg: %s",
                blog_clip.id,
                exc,
            )
            # Fall through to FFmpeg slideshow + ASS.

    create_image_slideshow(image_paths, mixed_audio_path, str(video_path), board_durations)

    events = _board_subtitle_events(boards, board_durations)
    style_label = style if blog_clip.subtitle_template_id is None else f"tpl{blog_clip.subtitle_template_id}"
    subtitle_path = BLOG_SUBTITLE_ROOT / str(user_id) / f"blog_{blog_clip.id}_{style_label}_{output_tag}.ass"

    on_progress(PROGRESS_BURNING_SUBTITLES)
    if events:
        write_ass_file(subtitle_path, ass_params, events)
        subtitled_video_path = video_dir / f"{video_path.stem}_subtitled.mp4"
        burn_subtitles_into_video(str(video_path), str(subtitle_path), str(subtitled_video_path))
        captions = "ass"
    else:
        subtitled_video_path = video_path
        captions = "none"

    spec = _build_render_spec(
        engine="ffmpeg",
        requested_engine=requested_engine,
        fallback_used=requested_engine == "remotion",
        fallback_reason=fallback_reason,
        blog_clip=blog_clip,
        boards=boards,
        board_durations=board_durations,
        video_path=str(subtitled_video_path),
        captions=captions,
    )
    return script, str(video_path), str(subtitled_video_path), spec


def _build_render_spec(
    *,
    engine: str,
    requested_engine: str,
    fallback_used: bool,
    fallback_reason: str | None,
    blog_clip: BlogClip,
    boards: list[BlogClipBoard],
    board_durations: list[float],
    video_path: str,
    captions: str,
) -> dict[str, Any]:
    path = Path(video_path)
    output_bytes = path.stat().st_size if path.is_file() else None
    return {
        "engine": engine,
        "requested_engine": requested_engine,
        "fallback_used": bool(fallback_used),
        "fallback_reason": (fallback_reason[:280] if fallback_reason else None),
        "captions": captions,
        "resolution": "1080x1920",
        "fps": 30,
        "board_count": len(boards),
        "duration_seconds": round(sum(float(d) for d in board_durations), 2),
        "tts_speed": float(blog_clip.tts_speed),
        "bgm": blog_clip.bgm_asset_id is not None,
        "bgm_volume": float(blog_clip.bgm_volume) if blog_clip.bgm_asset_id is not None else None,
        "sfx_boards": sum(1 for board in boards if board.sfx_asset_id is not None),
        "output_bytes": output_bytes,
        "output_file": path.name if path.name else None,
    }


def run_blog_clip_render_pipeline(blog_clip_id: int, user_id: int) -> None:
    """Phase 2: TTS -> slideshow -> subtitle burn-in, after the user confirms boards."""
    connection_generator = get_connection()
    conn = next(connection_generator)
    try:
        blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
        if blog_clip is None:
            return
        blog_title = blog_clip.blog_title or "블로그 쇼츠"
        if not (blog_clip.narration_script or "").strip():
            _update_blog_clip_failed(conn, blog_clip_id, "Selected narration script is missing.")
            return

        try:
            boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
            if not boards:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="보드가 없습니다. 최소 1개 이상의 보드가 필요합니다.",
                )

            script, video_path, subtitled_video_path, render_spec = _render_boards_media(
                conn,
                user_id,
                blog_clip,
                boards,
                output_tag="primary",
                on_progress=lambda checkpoint: _update_blog_clip_progress(conn, blog_clip_id, checkpoint),
            )
        except HTTPException as exc:
            _update_blog_clip_failed(conn, blog_clip_id, str(exc.detail))
            return
        except (
            FFmpegNotAvailableError,
            FFprobeNotAvailableError,
            FFmpegSlideshowError,
            FFmpegSubtitleError,
            FFmpegAudioError,
            TimeoutError,
        ) as exc:
            _update_blog_clip_failed(conn, blog_clip_id, str(exc))
            return
        except Exception as exc:
            from app.services.remotion_render_service import RemotionRenderError

            if isinstance(exc, RemotionRenderError):
                _update_blog_clip_failed(conn, blog_clip_id, str(exc))
                return
            _update_blog_clip_failed(conn, blog_clip_id, "Unexpected blog short generation failure.")
            return

        _update_blog_clip_result(
            conn,
            blog_clip_id,
            blog_title,
            script,
            video_path,
            subtitled_video_path,
            render_spec=render_spec,
        )
    finally:
        next(connection_generator, None)


def run_blog_clip_version_pipeline(blog_clip_id: int, user_id: int, version_id: int, *, set_active: bool = False) -> None:
    """Render a queued blog_clip_versions row without resetting the parent clip status."""
    connection_generator = get_connection()
    conn = next(connection_generator)
    try:
        blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
        version = get_blog_clip_version_for_user(conn, user_id, blog_clip_id, version_id)
        if blog_clip is None or version is None:
            return

        try:
            template_boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
            if version.source == "boards":
                boards = template_boards
                if not boards:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="보드가 없습니다. 최소 1개 이상의 보드가 필요합니다.",
                    )
            else:
                script = (version.narration_script or "").strip()
                if not script:
                    candidates = blog_clip_script_candidates(blog_clip)
                    script = (candidates.get(version.script_tone or "") or "").strip()
                if not script:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version narration script is missing.")
                boards = _build_tone_render_boards(user_id, blog_clip_id, script, template_boards)

            script, video_path, subtitled_video_path, render_spec = _render_boards_media(
                conn,
                user_id,
                blog_clip,
                boards,
                output_tag=f"v{version_id}",
                on_progress=lambda checkpoint: _update_version_progress(conn, version_id, checkpoint),
            )
        except HTTPException as exc:
            _update_version_failed(conn, version_id, str(exc.detail))
            return
        except (
            FFmpegNotAvailableError,
            FFprobeNotAvailableError,
            FFmpegSlideshowError,
            FFmpegSubtitleError,
            FFmpegAudioError,
            TimeoutError,
        ) as exc:
            _update_version_failed(conn, version_id, str(exc))
            return
        except Exception as exc:
            from app.services.remotion_render_service import RemotionRenderError

            if isinstance(exc, RemotionRenderError):
                _update_version_failed(conn, version_id, str(exc))
                return
            _update_version_failed(conn, version_id, "Unexpected blog short version generation failure.")
            return

        status_value, progress_stage, progress_percent = PROGRESS_DONE
        render_spec_json = json.dumps(render_spec, ensure_ascii=False) if render_spec else None
        conn.execute(
            """
            UPDATE blog_clip_versions
            SET status = ?,
                progress_stage = ?,
                progress_percent = ?,
                narration_script = ?,
                video_path = ?,
                subtitled_video_path = ?,
                render_spec_json = ?,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status_value,
                progress_stage,
                progress_percent,
                script,
                video_path,
                subtitled_video_path,
                render_spec_json,
                version_id,
            ),
        )
        conn.commit()

        refreshed = get_blog_clip_version_for_user(conn, user_id, blog_clip_id, version_id)
        if refreshed is None:
            return
        if set_active or blog_clip.active_version_id is None:
            _sync_parent_from_version(conn, blog_clip_id, refreshed)
    finally:
        next(connection_generator, None)


def get_or_create_blog_version_metadata(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    version_id: int,
) -> BlogClipVersion:
    version = get_blog_clip_version_for_user(conn, user_id, blog_clip_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    if version.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed version is required before metadata generation.")
    if version.title_candidates_json:
        return version

    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")

    try:
        payload = generate_blog_metadata(
            blog_clip.blog_title or "블로그 쇼츠",
            version.narration_script or "",
            model=blog_clip.script_model,
        )
    except HTTPException as exc:
        conn.execute(
            "UPDATE blog_clip_versions SET metadata_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(exc.detail), version_id),
        )
        conn.commit()
        raise

    conn.execute(
        """
        UPDATE blog_clip_versions
        SET title_candidates_json = ?, description = ?, hashtags_json = ?, metadata_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(payload["title_candidates"], ensure_ascii=False),
            payload["description"],
            json.dumps(payload["hashtags"], ensure_ascii=False),
            version_id,
        ),
    )
    conn.commit()

    refreshed = get_blog_clip_version_for_user(conn, user_id, blog_clip_id, version_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Version metadata refresh failed.")

    parent = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if parent is not None and parent.active_version_id == version_id:
        _sync_parent_from_version(conn, blog_clip_id, refreshed)

    return refreshed


def get_or_create_blog_metadata(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed blog short is required before metadata generation.")
    if blog_clip.title_candidates_json:
        return blog_clip

    try:
        payload = generate_blog_metadata(
            blog_clip.blog_title or "블로그 쇼츠",
            blog_clip.narration_script or "",
            model=blog_clip.script_model,
        )
    except HTTPException as exc:
        conn.execute(
            "UPDATE blog_clips SET metadata_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(exc.detail), blog_clip_id),
        )
        conn.commit()
        raise

    conn.execute(
        """
        UPDATE blog_clips
        SET title_candidates_json = ?, description = ?, hashtags_json = ?, metadata_error = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(payload["title_candidates"], ensure_ascii=False),
            payload["description"],
            json.dumps(payload["hashtags"], ensure_ascii=False),
            blog_clip_id,
        ),
    )
    conn.commit()

    refreshed = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Blog short metadata refresh failed.")
    return refreshed


def blog_clip_title_candidates(blog_clip: BlogClip) -> list[str]:
    try:
        parsed = json.loads(blog_clip.title_candidates_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def blog_clip_hashtags(blog_clip: BlogClip) -> list[str]:
    try:
        parsed = json.loads(blog_clip.hashtags_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]
