import json
import sqlite3
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import HTTPException, status
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError, RateLimitError

from app.core.config import settings
from app.db.models import Transcript, Video
from app.services.video_service import get_video_for_user, update_video_status


def _row_to_transcript(row: sqlite3.Row) -> Transcript:
    return Transcript(
        id=row["id"],
        video_id=row["video_id"],
        status=row["status"],
        text=row["text"],
        segments_json=row["segments_json"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_transcript_for_video(conn: sqlite3.Connection, video_id: int) -> Transcript | None:
    row = conn.execute(
        """
        SELECT id, video_id, status, text, segments_json, error_message, created_at, updated_at
        FROM transcripts
        WHERE video_id = ?
        """,
        (video_id,),
    ).fetchone()
    return _row_to_transcript(row) if row else None


def upsert_transcript(
    conn: sqlite3.Connection,
    video_id: int,
    status_value: str,
    text: str | None = None,
    segments: list[dict[str, Any]] | None = None,
    error_message: str | None = None,
) -> Transcript:
    segments_json = json.dumps(segments or [], ensure_ascii=False)
    existing = get_transcript_for_video(conn, video_id)
    if existing is None:
        cursor = conn.execute(
            """
            INSERT INTO transcripts (video_id, status, text, segments_json, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (video_id, status_value, text, segments_json, error_message),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, video_id, status, text, segments_json, error_message, created_at, updated_at
            FROM transcripts
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()
    else:
        conn.execute(
            """
            UPDATE transcripts
            SET status = ?, text = ?, segments_json = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE video_id = ?
            """,
            (status_value, text, segments_json, error_message, video_id),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, video_id, status, text, segments_json, error_message, created_at, updated_at
            FROM transcripts
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcript save failed.")
    return _row_to_transcript(row)


def transcript_segments(transcript: Transcript) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(transcript.segments_json or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _audio_chunks(audio_path: Path, max_bytes: int) -> list[tuple[Path, float]]:
    if audio_path.stat().st_size <= max_bytes:
        return [(audio_path, 0.0)]

    chunks: list[tuple[Path, float]] = []
    temp_dir = TemporaryDirectory()
    # Keep the TemporaryDirectory object alive by attaching it to the function result paths.
    setattr(_audio_chunks, "_last_temp_dir", temp_dir)

    with wave.open(str(audio_path), "rb") as source:
        params = source.getparams()
        bytes_per_frame = params.sampwidth * params.nchannels
        frames_per_chunk = max(1, max_bytes // max(1, bytes_per_frame))
        frame_rate = params.framerate
        chunk_index = 0
        while True:
            start_frame = source.tell()
            frames = source.readframes(frames_per_chunk)
            if not frames:
                break
            chunk_path = Path(temp_dir.name) / f"chunk_{chunk_index:04d}.wav"
            with wave.open(str(chunk_path), "wb") as chunk:
                chunk.setparams(params)
                chunk.writeframes(frames)
            chunks.append((chunk_path, start_frame / frame_rate))
            chunk_index += 1
    return chunks


def _extract_segments(response: Any, offset_seconds: float) -> tuple[str, list[dict[str, Any]]]:
    data = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    text = str(data.get("text") or "")
    raw_segments = data.get("segments") or []
    segments: list[dict[str, Any]] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        start = float(item.get("start") or 0) + offset_seconds
        end = float(item.get("end") or start) + offset_seconds
        segment_text = str(item.get("text") or "").strip()
        if segment_text:
            segments.append({"index": len(segments), "start": start, "end": end, "text": segment_text})
    return text.strip(), segments


def _transcribe_audio_file(audio_path: str) -> tuple[str, list[dict[str, Any]]]:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    max_bytes = settings.transcription_chunk_mb * 1024 * 1024
    combined_text: list[str] = []
    combined_segments: list[dict[str, Any]] = []

    for chunk_path, offset in _audio_chunks(Path(audio_path), max_bytes):
        with chunk_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=audio_file,
                model=settings.openai_transcription_model,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        text, segments = _extract_segments(response, offset)
        if text:
            combined_text.append(text)
        for segment in segments:
            segment["index"] = len(combined_segments)
            combined_segments.append(segment)

    return " ".join(combined_text).strip(), combined_segments


def transcribe_video(conn: sqlite3.Connection, user_id: int, video_id: int) -> Transcript:
    video = get_video_for_user(conn, user_id, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    existing = get_transcript_for_video(conn, video_id)
    if existing is not None and existing.status == "transcribed":
        return existing

    if not video.audio_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Audio must be extracted before transcription.")

    audio_path = Path(video.audio_path)
    if not audio_path.exists():
        update_video_status(conn, video.id, "failed", video.audio_path, "Extracted audio file was not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted audio file was not found.")

    update_video_status(conn, video.id, "transcribing", video.audio_path, None)
    upsert_transcript(conn, video.id, "transcribing", None, [], None)

    try:
        text, segments = _transcribe_audio_file(str(audio_path))
    except HTTPException as exc:
        upsert_transcript(conn, video.id, "failed", None, [], str(exc.detail))
        update_video_status(conn, video.id, "failed", video.audio_path, str(exc.detail))
        raise
    except RateLimitError as exc:
        message = f"OpenAI rate limit reached: {exc}"
        upsert_transcript(conn, video.id, "failed", None, [], message)
        update_video_status(conn, video.id, "failed", video.audio_path, message)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message) from exc
    except APIConnectionError as exc:
        message = "Could not connect to OpenAI Transcription API."
        upsert_transcript(conn, video.id, "failed", None, [], message)
        update_video_status(conn, video.id, "failed", video.audio_path, message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message) from exc
    except APIStatusError as exc:
        message = f"OpenAI Transcription API error: {exc.status_code}"
        upsert_transcript(conn, video.id, "failed", None, [], message)
        update_video_status(conn, video.id, "failed", video.audio_path, message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message) from exc
    except (OpenAIError, OSError, wave.Error) as exc:
        message = f"Transcription failed: {exc}"
        upsert_transcript(conn, video.id, "failed", None, [], message)
        update_video_status(conn, video.id, "failed", video.audio_path, message)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message) from exc

    transcript = upsert_transcript(conn, video.id, "transcribed", text, segments, None)
    update_video_status(conn, video.id, "transcribed", video.audio_path, None)
    return transcript
