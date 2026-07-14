import re
import sqlite3
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError, RateLimitError

from app.core.config import settings
from app.services.transcription_service import get_transcript_for_video, transcript_segments
from app.services.video_service import STORAGE_ROOT, get_video_for_user

TTS_ROOT = STORAGE_ROOT / "tts"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clip_transcript_text(conn: sqlite3.Connection, video_id: int, start_time: float, end_time: float) -> str:
    transcript = get_transcript_for_video(conn, video_id)
    if transcript is None or transcript.status != "transcribed" or not transcript.text:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed transcript is required before AI narration.")

    parts: list[str] = []
    for segment in transcript_segments(transcript):
        try:
            segment_start = float(segment.get("start") or 0)
            segment_end = float(segment.get("end") or segment_start)
        except (TypeError, ValueError):
            continue
        if segment_end <= start_time or segment_start >= end_time:
            continue
        text = _clean_text(str(segment.get("text") or ""))
        if text:
            parts.append(text)
    if not parts:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No transcript text overlaps this clip range.")
    return " ".join(parts)[:6000]


def generate_narration_script(conn: sqlite3.Connection, user_id: int, video_id: int, highlight: sqlite3.Row) -> str:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")

    video = get_video_for_user(conn, user_id, video_id)
    source_text = clip_transcript_text(conn, video_id, float(highlight["start_time"]), float(highlight["end_time"]))
    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""
Create a short AI narration script for a vertical shorts clip.

Rules:
- Write in Korean unless the transcript is clearly not Korean.
- Summarize the selected highlight, do not invent facts.
- Keep it natural when read aloud.
- Keep it short enough for the clip duration.
- Do not include stage directions, timestamps, markdown, hashtags, or title text.
- Avoid exaggerated or misleading claims.

Highlight title: {highlight['title'] if 'title' in highlight.keys() else ''}
Highlight reason: {highlight['reason'] if 'reason' in highlight.keys() else ''}
Clip duration: {float(highlight['end_time']) - float(highlight['start_time']):.1f} seconds
Original video: {video.original_filename if video else ''}

Transcript:
{source_text}
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.openai_metadata_model,
            messages=[
                {"role": "system", "content": "You write concise voiceover narration scripts for short-form videos."},
                {"role": "user", "content": prompt},
            ],
        )
    except RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OpenAI rate limit reached. Try again later.") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not connect to OpenAI GPT API.") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OpenAI GPT API error: {exc.status_code}") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Narration script generation failed: {exc}") from exc

    script = response.choices[0].message.content if response.choices else None
    script = _clean_text(script or "")
    if not script:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned an empty narration script.")
    return script[:900]


def synthesize_openai_tts(user_id: int, clip_id: int, script: str) -> str:
    api_key = settings.tts_api_key or settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TTS API key is not configured.")
    if settings.tts_provider.lower() != "openai":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only OpenAI TTS is implemented in this MVP.")

    client = OpenAI(api_key=api_key)
    output_dir = TTS_ROOT / str(user_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"clip_{clip_id}_{uuid.uuid4().hex}.mp3"

    try:
        response = client.audio.speech.create(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            input=script,
            response_format="mp3",
        )
        if hasattr(response, "write_to_file"):
            response.write_to_file(output_path)
        else:
            output_path.write_bytes(response.content)
    except RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OpenAI TTS rate limit reached. Try again later.") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not connect to OpenAI TTS API.") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OpenAI TTS API error: {exc.status_code}") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"TTS generation failed: {exc}") from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="TTS audio file was not created.")
    return str(output_path)
