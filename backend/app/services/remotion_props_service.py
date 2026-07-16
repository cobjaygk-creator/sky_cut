"""Build BlogShorts Remotion props from blog_clip boards (R1/R3)."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.models import BlogClip, BlogClipBoard
from app.services.visual_style_catalog import normalize_visual_style, remotion_style_payload

DEFAULT_BOARD_DURATION_SEC = 2.5
DEFAULT_TRANSITION_SEC = 0.35

# backend/app/services → parents[3] = repo root
_DEFAULT_REMOTION_PUBLIC = Path(__file__).resolve().parents[3] / "remotion" / "public"


def remotion_public_dir() -> Path:
    configured = (settings.remotion_public_dir or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return _DEFAULT_REMOTION_PUBLIC.resolve()


def resolve_board_duration_sec(board: BlogClipBoard) -> float:
    if board.duration_seconds is not None and float(board.duration_seconds) > 0:
        return float(board.duration_seconds)
    return DEFAULT_BOARD_DURATION_SEC


def build_blog_shorts_props(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    *,
    materialize: bool = True,
) -> dict:
    """
    Return Remotion BlogShorts props for a clip that already has boards.

    When materialize=True, copies board images into remotion/public/clips/{id}/
    and sets imageUrl to a staticFile-relative path (e.g. clips/3/board-12.jpg).
    """
    from app.services.blog_service import (
        get_blog_clip_board_image_path,
        get_blog_clip_for_user,
        list_blog_clip_boards,
    )

    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")

    boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
    if not boards:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이 블로그 쇼츠에 보드가 없습니다. 대본 선택 후 보드가 생성된 클립만 Remotion props로 내보낼 수 있습니다.",
        )

    return _props_from_boards(
        conn,
        user_id,
        blog_clip,
        boards,
        materialize=materialize,
        duration_overrides=None,
        narration_audio_path=None,
    )


def build_remotion_render_props(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip: BlogClip,
    boards: list[BlogClipBoard],
    board_durations: list[float],
    narration_audio_path: str,
) -> dict:
    """Props for final Remotion render: TTS lengths + narration audio in public/."""
    if len(board_durations) != len(boards):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Board duration count does not match board count.",
        )
    return _props_from_boards(
        conn,
        user_id,
        blog_clip,
        boards,
        materialize=True,
        duration_overrides=[float(d) for d in board_durations],
        narration_audio_path=narration_audio_path,
    )


def _props_from_boards(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip: BlogClip,
    boards: list[BlogClipBoard],
    *,
    materialize: bool,
    duration_overrides: list[float] | None,
    narration_audio_path: str | None,
) -> dict:
    from app.services.blog_service import _validate_board_image_path, get_blog_clip_board_image_path

    public_root = remotion_public_dir()
    clip_public = public_root / "clips" / str(blog_clip.id)
    if materialize:
        clip_public.mkdir(parents=True, exist_ok=True)

    board_props: list[dict] = []
    for index, board in enumerate(boards):
        image_url: str | None = None
        if materialize:
            src: Path | None = None
            if board.id:
                try:
                    src = get_blog_clip_board_image_path(conn, user_id, blog_clip.id, board.id)
                except HTTPException:
                    src = None
            if src is None and board.image_path:
                try:
                    src = Path(_validate_board_image_path(user_id, blog_clip.id, board.image_path))
                except HTTPException:
                    candidate = Path(board.image_path)
                    src = candidate if candidate.is_file() else None
            if src is not None and src.is_file():
                dest_name = f"board-{board.id or index}{src.suffix.lower()}"
                dest = clip_public / dest_name
                shutil.copy2(src, dest)
                image_url = f"clips/{blog_clip.id}/{dest_name}"
        else:
            base = settings.public_api_base_url.rstrip("/")
            image_url = f"{base}/blog-clips/{blog_clip.id}/boards/{board.id}/image"

        if duration_overrides is not None:
            duration_sec = max(0.5, float(duration_overrides[index]))
        else:
            duration_sec = resolve_board_duration_sec(board)

        board_props.append(
            {
                "boardId": board.id,
                "imageUrl": image_url,
                "text": board.text or "",
                "durationSec": duration_sec,
                "backgroundColor": None,
                "speaker": board.speaker,
            }
        )

    narration_url: str | None = None
    if narration_audio_path and materialize:
        src_audio = Path(narration_audio_path)
        if src_audio.is_file():
            dest_audio = clip_public / f"narration{src_audio.suffix.lower() or '.mp3'}"
            shutil.copy2(src_audio, dest_audio)
            narration_url = f"clips/{blog_clip.id}/{dest_audio.name}"

    title = _pick_title(blog_clip)
    style_title = (getattr(blog_clip, "style_title", None) or title or "").strip() or None
    style_subtitle = (getattr(blog_clip, "style_subtitle", None) or "").strip() or None
    visual_style = normalize_visual_style(getattr(blog_clip, "visual_style", None))
    style = remotion_style_payload(visual_style)
    return {
        "blogClipId": blog_clip.id,
        "title": title,
        "styleTitle": style_title,
        "styleSubtitle": style_subtitle,
        "transitionSec": float(style.get("transitionSec", DEFAULT_TRANSITION_SEC)),
        "source": "blog_clip",
        "narrationUrl": narration_url,
        "visualStyle": visual_style,
        "style": style,
        "boards": board_props,
    }


def _pick_title(blog_clip: BlogClip) -> str | None:
    if blog_clip.blog_title and blog_clip.blog_title.strip():
        return blog_clip.blog_title.strip()
    return None
