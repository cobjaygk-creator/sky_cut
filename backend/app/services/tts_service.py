import logging
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import HTTPException, status
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError, RateLimitError

from app.core.config import settings
from app.services.korean_roman_to_hangul import display_voice_name_ko
from app.services.transcription_service import get_transcript_for_video, transcript_segments
from app.services.video_service import STORAGE_ROOT, get_video_for_user

logger = logging.getLogger(__name__)

# backend/.env — reload on TTS calls so provider/key changes apply without a full process restart.
_BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_last_tts_provider: str | None = None

TTS_ROOT = STORAGE_ROOT / "tts"
SAMPLE_ROOT = TTS_ROOT / "samples"
SAMPLE_SCRIPT = "안녕하세요. 뉴컷 보이스 미리듣기입니다. 이 목소리로 보드 나레이션을 만들 수 있어요."

# OpenAI TTS voice catalog (Stage 21). `id` is the API voice name stored in boards.speaker.
OPENAI_VOICE_CATALOG: list[dict[str, str]] = [
    {"id": "alloy", "name": "알로이", "description": "중립적이고 또렷한 기본 보이스"},
    {"id": "ash", "name": "애쉬", "description": "차분하고 안정적인 톤"},
    {"id": "ballad", "name": "발라드", "description": "부드럽고 이야기하듯 읽히는 보이스"},
    {"id": "coral", "name": "코랄", "description": "밝고 친근한 톤"},
    {"id": "echo", "name": "에코", "description": "또렷하고 또박또박한 남성 톤"},
    {"id": "fable", "name": "페이블", "description": "표현력이 있는 내레이션 톤"},
    {"id": "nova", "name": "노바", "description": "활기 있고 현대적인 여성 톤"},
    {"id": "onyx", "name": "오닉스", "description": "낮고 무게감 있는 톤"},
    {"id": "sage", "name": "세이지", "description": "차분한 안내·설명 톤"},
    {"id": "shimmer", "name": "쉬머", "description": "밝고 가벼운 여성 톤"},
]

_TYPECAST_GENDER_KO = {
    "male": "남성",
    "female": "여성",
    "neutral": "중성",
}
_TYPECAST_AGE_KO = {
    "child": "어린이",
    "teen": "청소년",
    "teenager": "청소년",
    "young adult": "청년",
    "young_adult": "청년",
    "youngadult": "청년",
    "middle age": "중년",
    "middle_age": "중년",
    "middleage": "중년",
    "senior": "시니어",
    "elder": "시니어",
    "old": "시니어",
}
_TYPECAST_USE_CASE_KO = {
    "conversational": "대화형",
    "announcer": "아나운서",
    "narration": "나레이션",
    "audiobook": "오디오북",
    "meditation": "명상",
    "ads": "광고",
    "advertisement": "광고",
    "customer service": "고객응대",
    "customerservice": "고객응대",
    "education": "교육",
    "gaming": "게임",
    "assistant": "어시스턴트",
    "tiktok/reels/shorts": "쇼츠·릴스",
    "tiktok": "쇼츠·릴스",
    "reels": "쇼츠·릴스",
    "shorts": "쇼츠·릴스",
    "youtube": "유튜브",
    "news": "뉴스",
    "storytelling": "스토리텔링",
    "character": "캐릭터",
}

# Backward-compatible alias used by older imports/tests.
VOICE_CATALOG = OPENAI_VOICE_CATALOG
_OPENAI_VOICE_IDS = {item["id"] for item in OPENAI_VOICE_CATALOG}

TTS_SPEED_MIN = 0.25
TTS_SPEED_MAX = 4.0
TTS_SPEED_DEFAULT = 1.0
TYPECAST_TEMPO_MIN = 0.5
TYPECAST_TEMPO_MAX = 2.0
TYPECAST_TEXT_MAX = 2000
TYPECAST_VOICE_CACHE_TTL_SEC = 600

_typecast_voice_cache: list[dict[str, str]] | None = None
_typecast_voice_cache_at: float = 0.0


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _refresh_tts_env() -> None:
    """Re-read backend/.env into os.environ (overrides stale process Settings cache)."""
    global _last_tts_provider, _typecast_voice_cache, _typecast_voice_cache_at
    if _BACKEND_ENV_PATH.is_file():
        load_dotenv(_BACKEND_ENV_PATH, override=True)
    provider = (os.getenv("TTS_PROVIDER") or settings.tts_provider or "openai").strip().lower()
    if _last_tts_provider is not None and provider != _last_tts_provider:
        _typecast_voice_cache = None
        _typecast_voice_cache_at = 0.0
        logger.info("TTS provider switched %s → %s", _last_tts_provider, provider)
    _last_tts_provider = provider


def tts_provider_name() -> str:
    _refresh_tts_env()
    return (os.getenv("TTS_PROVIDER") or settings.tts_provider or "openai").strip().lower()


def _typecast_api_key() -> str | None:
    _refresh_tts_env()
    return (
        os.getenv("TYPECAST_API_KEY")
        or settings.typecast_api_key
        or os.getenv("TTS_API_KEY")
        or settings.tts_api_key
        or ""
    ).strip() or None


def _typecast_setting(name: str, fallback: str | None) -> str:
    _refresh_tts_env()
    return (os.getenv(name) or fallback or "").strip()


def _typecast_headers() -> dict[str, str]:
    key = _typecast_api_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TYPECAST_API_KEY (or TTS_API_KEY) is not configured.",
        )
    return {"X-API-KEY": key, "Content-Type": "application/json"}


def _normalize_typecast_voice_id(voice_id: str) -> str:
    cleaned = voice_id.strip()
    lower = cleaned.lower()
    if lower.startswith("tc_"):
        return "tc_" + cleaned[3:]
    if lower.startswith("uc_"):
        return "uc_" + cleaned[3:]
    return cleaned


def _typecast_label_ko(value: str, mapping: dict[str, str]) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    if not cleaned:
        return ""
    lower = cleaned.lower()
    spaced = lower.replace("_", " ").replace("-", " ")
    compact = spaced.replace(" ", "")
    return (
        mapping.get(lower)
        or mapping.get(spaced)
        or mapping.get(compact)
        or mapping.get(lower.replace(" ", "_"))
        or cleaned
    )


def _typecast_use_cases_ko(use_cases: object) -> list[str]:
    if not isinstance(use_cases, list):
        return []
    labels: list[str] = []
    for raw in use_cases[:4]:
        text = str(raw).strip()
        if not text:
            continue
        # Normalize common compound tags before lookup.
        normalized = text.replace("TikTok/Reels/Shorts", "쇼츠·릴스")
        label = _typecast_label_ko(normalized, _TYPECAST_USE_CASE_KO)
        if label == normalized and re.fullmatch(r"[A-Za-z0-9 /.&+-]+", normalized):
            # Unknown English tag → skip rather than showing English in the UI.
            continue
        if label and label not in labels:
            labels.append(label)
    return labels


def _typecast_voice_card(item: dict) -> dict[str, str] | None:
    voice_id = _normalize_typecast_voice_id(str(item.get("voice_id") or ""))
    raw_name = str(item.get("voice_name") or voice_id).strip()
    if not voice_id or not raw_name:
        return None

    gender_ko = _typecast_label_ko(str(item.get("gender") or ""), _TYPECAST_GENDER_KO)
    age_ko = _typecast_label_ko(str(item.get("age") or ""), _TYPECAST_AGE_KO)
    use_labels = _typecast_use_cases_ko(item.get("use_cases"))

    # Romanized Typecast names → Hangul when possible (Sanghyun → 상현).
    name_ko = display_voice_name_ko(raw_name)
    name = f"{gender_ko} · {name_ko}" if gender_ko else name_ko
    desc_parts = [part for part in (age_ko, *use_labels) if part]
    description = " · ".join(desc_parts) if desc_parts else "타입캐스트 보이스"
    return {"id": voice_id, "name": name, "description": description}


def _fetch_typecast_voices(*, force: bool = False) -> list[dict[str, str]]:
    global _typecast_voice_cache, _typecast_voice_cache_at
    now = time.time()
    if (
        not force
        and _typecast_voice_cache is not None
        and now - _typecast_voice_cache_at < TYPECAST_VOICE_CACHE_TTL_SEC
    ):
        return _typecast_voice_cache

    base = _typecast_setting("TYPECAST_BASE_URL", settings.typecast_base_url) or "https://api.typecast.ai"
    base = base.rstrip("/")
    model = _typecast_setting("TYPECAST_MODEL", settings.typecast_model) or "ssfm-v30"
    try:
        response = requests.get(
            f"{base}/v2/voices",
            headers=_typecast_headers(),
            params={"model": model},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not connect to Typecast voices API: {exc}",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Typecast API key is invalid.")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Typecast voices API error ({response.status_code}): {response.text[:300]}",
        )

    payload = response.json()
    if not isinstance(payload, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Typecast voices API returned invalid JSON.")

    catalog: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        card = _typecast_voice_card(item)
        if card is not None:
            catalog.append(card)

    if not catalog:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Typecast returned an empty voice list.")

    _typecast_voice_cache = catalog
    _typecast_voice_cache_at = now
    logger.info("Loaded %s Typecast voices (model=%s)", len(catalog), model)
    return catalog


def list_voice_catalog() -> list[dict[str, str]]:
    if tts_provider_name() == "typecast":
        return [dict(item) for item in _fetch_typecast_voices()]
    return [dict(item) for item in OPENAI_VOICE_CATALOG]


def is_known_voice(voice_id: str) -> bool:
    try:
        validate_voice_id(voice_id)
        return True
    except HTTPException:
        return False


def validate_voice_id(voice_id: str) -> str:
    if tts_provider_name() == "typecast":
        cleaned = _normalize_typecast_voice_id(voice_id)
        known = {item["id"] for item in _fetch_typecast_voices()}
        if cleaned not in known:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown Typecast voice '{voice_id}'. Use GET /voices for the catalog.",
            )
        return cleaned

    cleaned = voice_id.strip().lower()
    if cleaned not in _OPENAI_VOICE_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown voice '{voice_id}'. Use GET /voices for the catalog.",
        )
    return cleaned


def clamp_tts_speed(speed: float | None) -> float:
    if speed is None:
        return TTS_SPEED_DEFAULT
    try:
        value = float(speed)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tts_speed must be a number.") from exc
    if value < TTS_SPEED_MIN or value > TTS_SPEED_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tts_speed must be between {TTS_SPEED_MIN} and {TTS_SPEED_MAX}.",
        )
    return round(value, 3)


def _speed_to_typecast_tempo(speed: float) -> float:
    return round(max(TYPECAST_TEMPO_MIN, min(TYPECAST_TEMPO_MAX, float(speed))), 3)


def default_tts_voice() -> str:
    if tts_provider_name() == "typecast":
        configured = _typecast_setting("TYPECAST_VOICE_ID", settings.typecast_voice_id)
        if configured:
            try:
                return validate_voice_id(configured)
            except HTTPException:
                pass
        catalog = _fetch_typecast_voices()
        return catalog[0]["id"]

    configured = (settings.openai_tts_voice or "alloy").strip().lower()
    return configured if configured in _OPENAI_VOICE_IDS else "alloy"


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


def _synthesize_openai_tts(
    user_id: int,
    clip_id: int,
    script: str,
    *,
    voice: str | None = None,
    speed: float | None = None,
) -> str:
    api_key = settings.tts_api_key or settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TTS API key is not configured.")

    if voice:
        resolved_voice = validate_voice_id(voice)
    else:
        resolved_voice = (settings.openai_tts_voice or "alloy").strip().lower() or "alloy"

    resolved_speed = clamp_tts_speed(speed)
    cleaned_script = _clean_text(script)
    if not cleaned_script:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TTS script is empty.")

    client = OpenAI(api_key=api_key)
    output_dir = TTS_ROOT / str(user_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"clip_{clip_id}_{uuid.uuid4().hex}.mp3"

    try:
        response = client.audio.speech.create(
            model=settings.openai_tts_model,
            voice=resolved_voice,
            input=cleaned_script,
            response_format="mp3",
            speed=resolved_speed,
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


def _synthesize_typecast_tts(
    user_id: int,
    clip_id: int,
    script: str,
    *,
    voice: str | None = None,
    speed: float | None = None,
) -> str:
    cleaned_script = _clean_text(script)
    if not cleaned_script:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TTS script is empty.")
    if len(cleaned_script) > TYPECAST_TEXT_MAX:
        cleaned_script = cleaned_script[:TYPECAST_TEXT_MAX].rstrip()

    if voice:
        resolved_voice = validate_voice_id(voice)
    else:
        resolved_voice = default_tts_voice()

    tempo = _speed_to_typecast_tempo(clamp_tts_speed(speed))
    model = _typecast_setting("TYPECAST_MODEL", settings.typecast_model) or "ssfm-v30"
    language = _typecast_setting("TYPECAST_LANGUAGE", settings.typecast_language) or None
    base = (_typecast_setting("TYPECAST_BASE_URL", settings.typecast_base_url) or "https://api.typecast.ai").rstrip("/")

    body: dict = {
        "voice_id": resolved_voice,
        "text": cleaned_script,
        "model": model,
        "output": {
            "volume": 100,
            "audio_pitch": 0,
            "audio_tempo": tempo,
            "audio_format": "mp3",
        },
    }
    if language:
        body["language"] = language

    output_dir = TTS_ROOT / str(user_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"clip_{clip_id}_{uuid.uuid4().hex}.mp3"

    try:
        response = requests.post(
            f"{base}/v1/text-to-speech",
            headers=_typecast_headers(),
            json=body,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not connect to Typecast TTS API: {exc}",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Typecast API key is invalid.")
    if response.status_code == 402:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Typecast credits are insufficient. Check Free plan usage or upgrade.",
        )
    if response.status_code >= 400:
        detail = response.text[:500]
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Typecast TTS error ({response.status_code}): {detail}",
        )

    if not response.content:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Typecast returned empty audio.")

    output_path.write_bytes(response.content)
    return str(output_path)


def synthesize_openai_tts(
    user_id: int,
    clip_id: int,
    script: str,
    *,
    voice: str | None = None,
    speed: float | None = None,
) -> str:
    """Synthesize narration via the configured TTS provider (OpenAI or Typecast).

    Name kept for call-site compatibility; dispatches on TTS_PROVIDER.
    """
    provider = tts_provider_name()
    if provider == "typecast":
        return _synthesize_typecast_tts(user_id, clip_id, script, voice=voice, speed=speed)
    if provider == "openai":
        return _synthesize_openai_tts(user_id, clip_id, script, voice=voice, speed=speed)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported TTS_PROVIDER '{settings.tts_provider}'. Use 'openai' or 'typecast'.",
    )


def get_or_create_voice_sample(voice_id: str) -> Path:
    """Return a cached preview MP3 for a catalog voice (generated once at speed 1.0)."""
    voice = validate_voice_id(voice_id)
    provider = tts_provider_name()
    SAMPLE_ROOT.mkdir(parents=True, exist_ok=True)
    sample_path = SAMPLE_ROOT / f"{provider}_{voice}.mp3"
    if sample_path.exists() and sample_path.stat().st_size > 0:
        return sample_path

    if provider == "typecast":
        synthesized = _synthesize_typecast_tts(0, 0, SAMPLE_SCRIPT, voice=voice, speed=1.0)
        sample_path.write_bytes(Path(synthesized).read_bytes())
        return sample_path

    if provider != "openai":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported TTS_PROVIDER '{settings.tts_provider}'. Use 'openai' or 'typecast'.",
        )

    api_key = settings.tts_api_key or settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TTS API key is not configured.")

    client = OpenAI(api_key=api_key)
    try:
        response = client.audio.speech.create(
            model=settings.openai_tts_model,
            voice=voice,
            input=SAMPLE_SCRIPT,
            response_format="mp3",
            speed=1.0,
        )
        if hasattr(response, "write_to_file"):
            response.write_to_file(sample_path)
        else:
            sample_path.write_bytes(response.content)
    except RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OpenAI TTS rate limit reached. Try again later.") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not connect to OpenAI TTS API.") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OpenAI TTS API error: {exc.status_code}") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"TTS sample generation failed: {exc}") from exc

    if not sample_path.exists() or sample_path.stat().st_size == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="TTS sample file was not created.")
    return sample_path
