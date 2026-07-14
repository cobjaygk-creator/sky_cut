import json
import re
import sqlite3
from typing import Any

from fastapi import HTTPException, status
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError, RateLimitError

from app.core.config import settings
from app.db.models import ClipMetadata
from app.services.clip_service import get_clip_for_user
from app.services.transcription_service import get_transcript_for_video, transcript_segments
from app.services.video_service import get_video_for_user


def _row_to_metadata(row: sqlite3.Row) -> ClipMetadata:
    return ClipMetadata(
        id=row["id"],
        clip_id=row["clip_id"],
        title_candidates_json=row["title_candidates_json"],
        description=row["description"],
        hashtags_json=row["hashtags_json"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def metadata_title_candidates(metadata: ClipMetadata) -> list[str]:
    try:
        parsed = json.loads(metadata.title_candidates_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def metadata_hashtags(metadata: ClipMetadata) -> list[str]:
    try:
        parsed = json.loads(metadata.hashtags_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def get_metadata_for_clip(conn: sqlite3.Connection, clip_id: int) -> ClipMetadata | None:
    row = conn.execute(
        """
        SELECT id, clip_id, title_candidates_json, description, hashtags_json,
               error_message, created_at, updated_at
        FROM clip_metadata
        WHERE clip_id = ?
        """,
        (clip_id,),
    ).fetchone()
    return _row_to_metadata(row) if row else None


def _get_highlight(conn: sqlite3.Connection, highlight_id: int, video_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, video_id, start_time, end_time, title, reason, content_type, score
        FROM highlights
        WHERE id = ? AND video_id = ?
        """,
        (highlight_id, video_id),
    ).fetchone()


def _clip_transcript_context(conn: sqlite3.Connection, video_id: int, start_time: float, end_time: float) -> str:
    transcript = get_transcript_for_video(conn, video_id)
    if transcript is None or transcript.status != "transcribed" or not transcript.text:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed transcript is required before metadata generation.")

    lines: list[str] = []
    for segment in transcript_segments(transcript):
        try:
            segment_start = float(segment.get("start") or 0)
            segment_end = float(segment.get("end") or segment_start)
        except (TypeError, ValueError):
            continue
        if segment_end <= start_time or segment_start >= end_time:
            continue
        text = str(segment.get("text") or "").strip()
        if text:
            lines.append(f"[{max(segment_start, start_time) - start_time:.1f}-{min(segment_end, end_time) - start_time:.1f}] {text}")
    if not lines:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No transcript text overlaps this clip range.")
    return "\n".join(lines[:120])


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

    titles = [str(item).strip()[:90] for item in raw_titles if str(item).strip()]
    titles = titles[:3]
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


def _generate_metadata_with_openai(video_title: str, highlight: sqlite3.Row, transcript_context: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = (
        "You write practical upload metadata for short-form videos. "
        "Return only valid JSON. Avoid exaggerated, misleading, or unverifiable claims. "
        "Write in Korean unless the transcript is clearly not Korean. "
        "The result must be ready for a beginner to copy into YouTube Shorts, Instagram Reels, or TikTok."
    )
    user_prompt = f"""
Create upload metadata for this short clip.

Return JSON exactly like:
{{"title_candidates":["...","...","..."],"description":"...","hashtags":["#...","#...","#...","#...","#...","#...","#...","#...","#...","#..."]}}

Rules:
- title_candidates must contain exactly 3 natural, non-clickbait titles.
- description must be concise, useful, and safe to paste as-is.
- hashtags must contain exactly 10 relevant hashtags.
- Do not invent facts that are not supported by the transcript.
- Do not promise results, earnings, health effects, or claims not present in the transcript.

Original video filename: {video_title}
Highlight title: {highlight['title']}
Highlight reason: {highlight['reason']}
Highlight content type: {highlight['content_type']}
Clip time range: {float(highlight['start_time']):.1f}-{float(highlight['end_time']):.1f} seconds

Clip transcript:
{transcript_context}
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.openai_metadata_model,
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


def _save_metadata(conn: sqlite3.Connection, clip_id: int, payload: dict[str, Any]) -> ClipMetadata:
    title_candidates_json = json.dumps(payload["title_candidates"], ensure_ascii=False)
    hashtags_json = json.dumps(payload["hashtags"], ensure_ascii=False)
    existing = get_metadata_for_clip(conn, clip_id)
    if existing is None:
        cursor = conn.execute(
            """
            INSERT INTO clip_metadata (clip_id, title_candidates_json, description, hashtags_json, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clip_id, title_candidates_json, payload["description"], hashtags_json, None),
        )
        conn.commit()
        row_id = int(cursor.lastrowid)
        row = conn.execute(
            """
            SELECT id, clip_id, title_candidates_json, description, hashtags_json,
                   error_message, created_at, updated_at
            FROM clip_metadata
            WHERE id = ?
            """,
            (row_id,),
        ).fetchone()
    else:
        conn.execute(
            """
            UPDATE clip_metadata
            SET title_candidates_json = ?, description = ?, hashtags_json = ?,
                error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE clip_id = ?
            """,
            (title_candidates_json, payload["description"], hashtags_json, None, clip_id),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, clip_id, title_candidates_json, description, hashtags_json,
                   error_message, created_at, updated_at
            FROM clip_metadata
            WHERE clip_id = ?
            """,
            (clip_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Metadata save failed.")
    return _row_to_metadata(row)


def get_or_create_clip_metadata(conn: sqlite3.Connection, user_id: int, clip_id: int) -> ClipMetadata:
    clip = get_clip_for_user(conn, user_id, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")

    existing = get_metadata_for_clip(conn, clip_id)
    if existing is not None:
        return existing

    video = get_video_for_user(conn, user_id, clip.video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    highlight = _get_highlight(conn, clip.highlight_id, clip.video_id)
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found.")

    transcript_context = _clip_transcript_context(conn, clip.video_id, float(highlight["start_time"]), float(highlight["end_time"]))
    payload = _generate_metadata_with_openai(video.original_filename, highlight, transcript_context)
    return _save_metadata(conn, clip_id, payload)
