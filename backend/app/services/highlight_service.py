import json
import sqlite3
from typing import Any

from fastapi import HTTPException, status
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError, RateLimitError

from app.core.config import settings
from app.db.models import Highlight
from app.services.transcription_service import get_transcript_for_video, transcript_segments
from app.services.video_service import get_video_for_user

ALLOWED_CONTENT_TYPES = {"정보형", "꿀팁형", "후킹형", "감정형", "논쟁형", "웃긴 장면"}


def _row_to_highlight(row: sqlite3.Row) -> Highlight:
    return Highlight(
        id=row["id"],
        video_id=row["video_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        title=row["title"],
        reason=row["reason"],
        content_type=row["content_type"],
        score=row["score"],
        created_at=row["created_at"],
    )


def list_highlights_for_video(conn: sqlite3.Connection, video_id: int) -> list[Highlight]:
    rows = conn.execute(
        """
        SELECT id, video_id, start_time, end_time, title, reason, content_type, score, created_at
        FROM highlights
        WHERE video_id = ?
        ORDER BY score DESC, start_time ASC, id ASC
        """,
        (video_id,),
    ).fetchall()
    return [_row_to_highlight(row) for row in rows]


def _save_highlights(conn: sqlite3.Connection, video_id: int, highlights: list[dict[str, Any]]) -> list[Highlight]:
    conn.execute("DELETE FROM highlights WHERE video_id = ?", (video_id,))
    for item in highlights:
        conn.execute(
            """
            INSERT INTO highlights (video_id, start_time, end_time, title, reason, content_type, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                item["start_time"],
                item["end_time"],
                item["title"],
                item["reason"],
                item["content_type"],
                item["score"],
            ),
        )
    conn.commit()
    return list_highlights_for_video(conn, video_id)


def _transcript_context(video_title: str, transcript_text: str, segments: list[dict[str, Any]]) -> str:
    segment_lines: list[str] = []
    for segment in segments[:500]:
        start = float(segment.get("start") or 0)
        end = float(segment.get("end") or start)
        text = str(segment.get("text") or "").strip()
        if text:
            segment_lines.append(f"[{start:.1f}-{end:.1f}] {text}")
    joined_segments = "\n".join(segment_lines)
    clipped_text = transcript_text[:12000]
    return f"Video title: {video_title}\n\nTranscript summary source text:\n{clipped_text}\n\nTimestamped segments:\n{joined_segments}"


def _parse_highlight_json(raw_text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to parse GPT highlight JSON.") from exc

    items = payload.get("highlights") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT response did not include highlights array.")

    parsed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            title = str(item["title"]).strip()
            reason = str(item["reason"]).strip()
            content_type = str(item["content_type"]).strip()
            score = float(item["score"])
        except (KeyError, TypeError, ValueError):
            continue

        duration = end_time - start_time
        if start_time < 0 or duration < settings.highlight_min_seconds or duration > settings.highlight_max_seconds:
            continue
        if not title or not reason:
            continue
        if content_type not in ALLOWED_CONTENT_TYPES:
            content_type = "후킹형"
        parsed.append(
            {
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "title": title[:120],
                "reason": reason[:500],
                "content_type": content_type,
                "score": max(0.0, min(100.0, score)),
            }
        )

    parsed = sorted(parsed, key=lambda value: value["score"], reverse=True)[:5]
    if len(parsed) < 3:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT returned too few valid highlight candidates.")
    return parsed


def _generate_highlights_with_openai(video_title: str, transcript_text: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _transcript_context(video_title, transcript_text, segments)
    system_prompt = (
        "You recommend short-form video highlight clips from transcripts. "
        "Return only valid JSON. Recommend 3 to 5 clips. Each clip must be 15 to 60 seconds. "
        "Use Korean titles and reasons. content_type must be one of: 정보형, 꿀팁형, 후킹형, 감정형, 논쟁형, 웃긴 장면. "
        "score must be 0 to 100."
    )
    user_prompt = (
        "Analyze this transcript and choose the best shorts candidates. "
        "Return JSON exactly like: {\"highlights\":[{\"start_time\":0.0,\"end_time\":30.0,\"title\":\"...\",\"reason\":\"...\",\"content_type\":\"후킹형\",\"score\":90}]}\n\n"
        + prompt
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_highlight_model,
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Highlight generation failed: {exc}") from exc

    raw_text = response.choices[0].message.content if response.choices else None
    if not raw_text:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GPT returned an empty highlight response.")
    return _parse_highlight_json(raw_text)


def get_or_create_highlights(conn: sqlite3.Connection, user_id: int, video_id: int) -> list[Highlight]:
    video = get_video_for_user(conn, user_id, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    existing = list_highlights_for_video(conn, video_id)
    if existing:
        return existing

    transcript = get_transcript_for_video(conn, video_id)
    if transcript is None or transcript.status != "transcribed" or not transcript.text:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transcript must be completed before highlight recommendation.")

    segments = transcript_segments(transcript)
    highlight_payload = _generate_highlights_with_openai(video.original_filename, transcript.text, segments)
    return _save_highlights(conn, video_id, highlight_payload)
