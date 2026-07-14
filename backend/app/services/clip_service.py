import sqlite3
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.db.models import Clip
from app.services.ffmpeg_service import (
    FFmpegClipError,
    FFmpegNotAvailableError,
    FFmpegNarrationError,
    FFmpegSubtitleError,
    burn_subtitles_into_video,
    create_vertical_clip,
    replace_video_audio_with_narration,
)
from app.services.subtitle_utils import clean_subtitle_text, split_text_for_duration, write_ass_file
from app.services.transcription_service import get_transcript_for_video, transcript_segments
from app.services.tts_service import generate_narration_script, synthesize_openai_tts
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
        tts_mode=row["tts_mode"],
        narration_script=row["narration_script"],
        narration_audio_path=row["narration_audio_path"],
        narrated_output_path=row["narrated_output_path"],
        status=row["status"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_clip_for_user(conn: sqlite3.Connection, user_id: int, clip_id: int) -> Clip | None:
    row = conn.execute(
        """
        SELECT id, user_id, video_id, highlight_id, output_path, subtitle_style,
               subtitle_path, subtitled_output_path, tts_mode, narration_script,
               narration_audio_path, narrated_output_path, status, error_message, created_at, updated_at
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

        text = clean_subtitle_text(str(segment.get("text") or ""))
        if not text:
            continue

        relative_start = max(segment_start, clip_start) - clip_start
        relative_end = min(segment_end, clip_end) - clip_start
        duration = max(0.8, relative_end - relative_start)
        chunks = split_text_for_duration(text, duration, 18)
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
        write_ass_file(subtitle_path, style, events)
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



def _update_clip_narration(
    conn: sqlite3.Connection,
    clip_id: int,
    status_value: str,
    tts_mode: str,
    narration_script: str | None = None,
    narration_audio_path: str | None = None,
    narrated_output_path: str | None = None,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE clips
        SET status = ?,
            tts_mode = ?,
            narration_script = ?,
            narration_audio_path = ?,
            narrated_output_path = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, tts_mode, narration_script, narration_audio_path, narrated_output_path, error_message, clip_id),
    )
    conn.commit()


def apply_clip_narration(conn: sqlite3.Connection, user_id: int, clip_id: int, mode: str) -> Clip:
    if mode not in {"original_audio", "ai_narration"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TTS mode must be original_audio or ai_narration.")

    clip = get_clip_for_user(conn, user_id, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    if clip.status != "completed" or not clip.output_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed clip is required before narration can be applied.")

    if mode == "original_audio":
        _update_clip_narration(conn, clip.id, "completed", "original_audio", None, None, None, None)
        refreshed = get_clip_for_user(conn, user_id, clip.id)
        if refreshed is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Clip refresh failed.")
        return refreshed

    highlight = conn.execute(
        """
        SELECT id, video_id, start_time, end_time, title, reason, content_type, score
        FROM highlights
        WHERE id = ? AND video_id = ?
        """,
        (clip.highlight_id, clip.video_id),
    ).fetchone()
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found.")

    source_path = Path(clip.subtitled_output_path or clip.output_path)
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip video file was not found.")

    try:
        _update_clip_narration(conn, clip.id, "processing", "ai_narration", None, None, None, None)
        script = generate_narration_script(conn, user_id, clip.video_id, highlight)
        audio_path = synthesize_openai_tts(user_id, clip.id, script)
        output_path = OUTPUT_ROOT / str(user_id) / f"{source_path.stem}_ai_narration.mp4"
        replace_video_audio_with_narration(str(source_path), audio_path, str(output_path))
    except HTTPException as exc:
        _update_clip_narration(conn, clip.id, "failed", "ai_narration", None, None, None, str(exc.detail))
        raise
    except (FFmpegNotAvailableError, FFmpegNarrationError, TimeoutError) as exc:
        _update_clip_narration(conn, clip.id, "failed", "ai_narration", None, None, None, str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        _update_clip_narration(conn, clip.id, "failed", "ai_narration", None, None, None, "Unexpected AI narration failure.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected AI narration failure.") from exc

    _update_clip_narration(conn, clip.id, "completed", "ai_narration", script, audio_path, str(output_path), None)
    refreshed = get_clip_for_user(conn, user_id, clip.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Clip refresh failed.")
    return refreshed
def clip_download_path(clip: Clip) -> Path:
    if clip.narrated_output_path:
        path = Path(clip.narrated_output_path)
    elif clip.subtitled_output_path:
        path = Path(clip.subtitled_output_path)
    elif clip.output_path:
        path = Path(clip.output_path)
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clip output is not ready for download.")

    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip file was not found.")
    return path


