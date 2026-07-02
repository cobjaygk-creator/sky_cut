import math
import re
import sqlite3
import textwrap
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.db.models import Clip
from app.services.ffmpeg_service import (
    FFmpegClipError,
    FFmpegNotAvailableError,
    FFmpegSubtitleError,
    burn_subtitles_into_video,
    create_vertical_clip,
)
from app.services.transcription_service import get_transcript_for_video, transcript_segments
from app.services.video_service import STORAGE_ROOT, get_video_for_user

OUTPUT_ROOT = STORAGE_ROOT / "outputs"
SUBTITLE_ROOT = STORAGE_ROOT / "subtitles"
ALLOWED_SUBTITLE_STYLES = {"basic", "bold", "shorts"}


def _row_to_clip(row: sqlite3.Row) -> Clip:
    return Clip(
        id=row["id"],
        user_id=row["user_id"],
        video_id=row["video_id"],
        highlight_id=row["highlight_id"],
        output_path=row["output_path"],
        subtitle_style=row["subtitle_style"],
        subtitle_path=row["subtitle_path"],
        subtitled_output_path=row["subtitled_output_path"],
        status=row["status"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_clip_for_user(conn: sqlite3.Connection, user_id: int, clip_id: int) -> Clip | None:
    row = conn.execute(
        """
        SELECT id, user_id, video_id, highlight_id, output_path, subtitle_style,
               subtitle_path, subtitled_output_path, status, error_message, created_at, updated_at
        FROM clips
        WHERE id = ? AND user_id = ?
        """,
        (clip_id, user_id),
    ).fetchone()
    return _row_to_clip(row) if row else None


def _get_highlight_for_user(conn: sqlite3.Connection, user_id: int, highlight_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT h.id, h.video_id, h.start_time, h.end_time
        FROM highlights h
        JOIN videos v ON v.id = h.video_id
        WHERE h.id = ? AND v.user_id = ?
        """,
        (highlight_id, user_id),
    ).fetchone()


def _get_highlight_for_clip(conn: sqlite3.Connection, clip: Clip) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, video_id, start_time, end_time
        FROM highlights
        WHERE id = ? AND video_id = ?
        """,
        (clip.highlight_id, clip.video_id),
    ).fetchone()


def _update_clip_status(
    conn: sqlite3.Connection,
    clip_id: int,
    status_value: str,
    output_path: str | None = None,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE clips
        SET status = ?, output_path = COALESCE(?, output_path), error_message = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, output_path, error_message, clip_id),
    )
    conn.commit()


def _update_clip_subtitle(
    conn: sqlite3.Connection,
    clip_id: int,
    status_value: str,
    subtitle_style: str | None = None,
    subtitle_path: str | None = None,
    subtitled_output_path: str | None = None,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE clips
        SET status = ?,
            subtitle_style = COALESCE(?, subtitle_style),
            subtitle_path = COALESCE(?, subtitle_path),
            subtitled_output_path = COALESCE(?, subtitled_output_path),
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, subtitle_style, subtitle_path, subtitled_output_path, error_message, clip_id),
    )
    conn.commit()


def create_clip_from_highlight(conn: sqlite3.Connection, user_id: int, highlight_id: int) -> Clip:
    highlight = _get_highlight_for_user(conn, user_id, highlight_id)
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found.")

    video = get_video_for_user(conn, user_id, int(highlight["video_id"]))
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    start_time = float(highlight["start_time"])
    end_time = float(highlight["end_time"])
    if end_time <= start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Highlight time range is invalid.")

    cursor = conn.execute(
        """
        INSERT INTO clips (user_id, video_id, highlight_id, output_path, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, video.id, highlight_id, None, "pending", None),
    )
    conn.commit()

    clip_id = int(cursor.lastrowid)
    output_dir = OUTPUT_ROOT / str(user_id)
    output_path = output_dir / f"{uuid.uuid4().hex}.mp4"
    _update_clip_status(conn, clip_id, "processing", None, None)

    try:
        create_vertical_clip(video.storage_path, str(output_path), start_time, end_time)
    except (FFmpegNotAvailableError, FFmpegClipError, TimeoutError) as exc:
        _update_clip_status(conn, clip_id, "failed", None, str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        _update_clip_status(conn, clip_id, "failed", None, "Unexpected clip generation failure.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected clip generation failure.") from exc

    _update_clip_status(conn, clip_id, "completed", str(output_path), None)
    clip = get_clip_for_user(conn, user_id, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Clip status refresh failed.")
    return clip


def _clean_subtitle_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_long_word(word: str, size: int) -> list[str]:
    return [word[index : index + size] for index in range(0, len(word), size)]


def _wrap_subtitle_text(text: str, max_chars: int) -> str:
    text = _clean_subtitle_text(text)
    if not text:
        return ""

    words: list[str] = []
    for word in text.split(" "):
        if len(word) > max_chars:
            words.extend(_chunk_long_word(word, max_chars))
        else:
            words.append(word)

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == 2:
            break
    if current and len(lines) < 2:
        lines.append(current)

    return r"\N".join(lines[:2])


def _split_text_for_duration(text: str, duration: float, max_chars: int) -> list[str]:
    text = _clean_subtitle_text(text)
    if not text:
        return []
    chunk_size = max_chars * 2
    chunk_count = max(1, min(4, math.ceil(len(text) / chunk_size)))
    if chunk_count == 1:
        return [_wrap_subtitle_text(text, max_chars)]
    raw_chunks = textwrap.wrap(text, width=chunk_size, break_long_words=True, break_on_hyphens=False)
    return [_wrap_subtitle_text(chunk, max_chars) for chunk in raw_chunks[:chunk_count] if chunk.strip()]


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    centiseconds = int(round(seconds * 100))
    hours = centiseconds // 360000
    centiseconds %= 360000
    minutes = centiseconds // 6000
    centiseconds %= 6000
    whole_seconds = centiseconds // 100
    centiseconds %= 100
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def _ass_style(style: str) -> str:
    styles = {
        "basic": "Style: Default,Malgun Gothic,58,&H00FFFFFF,&H000000FF,&HAA000000,&HCC000000,0,0,0,0,100,100,0,0,1,3,1,2,80,80,150,1",
        "bold": "Style: Default,Malgun Gothic,66,&H00FFFFFF,&H000000FF,&H99000000,&HDD000000,-1,0,0,0,100,100,0,0,1,4,1,2,70,70,155,1",
        "shorts": "Style: Default,Malgun Gothic,72,&H0000FFFF,&H000000FF,&H00000000,&HCC000000,-1,0,0,0,100,100,0,0,1,5,2,2,58,58,210,1",
    }
    return styles[style]


def _ass_header(style: str) -> str:
    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            _ass_style(style),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def _subtitle_events_for_clip(conn: sqlite3.Connection, clip: Clip) -> list[tuple[float, float, str]]:
    highlight = _get_highlight_for_clip(conn, clip)
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found.")

    transcript = get_transcript_for_video(conn, clip.video_id)
    if transcript is None or transcript.status != "transcribed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed transcript is required before subtitles can be created.")

    clip_start = float(highlight["start_time"])
    clip_end = float(highlight["end_time"])
    clip_duration = max(0.1, clip_end - clip_start)
    events: list[tuple[float, float, str]] = []

    for segment in transcript_segments(transcript):
        try:
            segment_start = float(segment.get("start") or 0)
            segment_end = float(segment.get("end") or segment_start)
        except (TypeError, ValueError):
            continue
        if segment_end <= clip_start or segment_start >= clip_end:
            continue

        text = _clean_subtitle_text(str(segment.get("text") or ""))
        if not text:
            continue

        relative_start = max(segment_start, clip_start) - clip_start
        relative_end = min(segment_end, clip_end) - clip_start
        duration = max(0.8, relative_end - relative_start)
        chunks = _split_text_for_duration(text, duration, 18)
        if not chunks:
            continue

        chunk_duration = duration / len(chunks)
        for index, chunk in enumerate(chunks):
            start = min(clip_duration, relative_start + index * chunk_duration)
            end = min(clip_duration, relative_start + (index + 1) * chunk_duration)
            if end - start < 0.4:
                end = min(clip_duration, start + 0.8)
            if end > start:
                events.append((start, end, chunk))

    if not events:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No transcript segments overlap this clip range.")
    return events


def _write_ass_file(path: Path, style: str, events: list[tuple[float, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_ass_header(style)]
    for start, end, text in events:
        safe_text = text.replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{safe_text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def create_subtitled_clip(conn: sqlite3.Connection, user_id: int, clip_id: int, style: str) -> Clip:
    if style not in ALLOWED_SUBTITLE_STYLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subtitle style must be basic, bold, or shorts.")

    clip = get_clip_for_user(conn, user_id, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    if clip.status != "completed" or not clip.output_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed clip is required before subtitles can be burned in.")

    source_path = Path(clip.output_path)
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip video file was not found.")

    subtitle_path = SUBTITLE_ROOT / str(user_id) / f"clip_{clip.id}_{style}.ass"
    output_path = OUTPUT_ROOT / str(user_id) / f"{source_path.stem}_{style}_subtitled.mp4"

    try:
        events = _subtitle_events_for_clip(conn, clip)
        _write_ass_file(subtitle_path, style, events)
        _update_clip_subtitle(conn, clip.id, "processing", style, str(subtitle_path), None, None)
        burn_subtitles_into_video(str(source_path), str(subtitle_path), str(output_path))
    except HTTPException:
        raise
    except (FFmpegNotAvailableError, FFmpegSubtitleError, TimeoutError) as exc:
        _update_clip_subtitle(conn, clip.id, "failed", style, str(subtitle_path), None, str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        _update_clip_subtitle(conn, clip.id, "failed", style, str(subtitle_path), None, "Unexpected subtitle burn-in failure.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected subtitle burn-in failure.") from exc

    _update_clip_subtitle(conn, clip.id, "completed", style, str(subtitle_path), str(output_path), None)
    refreshed = get_clip_for_user(conn, user_id, clip.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Clip refresh failed.")
    return refreshed


def clip_download_path(clip: Clip) -> Path:
    if clip.subtitled_output_path:
        path = Path(clip.subtitled_output_path)
    elif clip.output_path:
        path = Path(clip.output_path)
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clip output is not ready for download.")

    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip file was not found.")
    return path
