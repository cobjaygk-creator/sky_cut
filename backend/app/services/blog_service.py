import json
import re
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
from app.db.models import BlogClip
from app.services.ffmpeg_service import (
    FFmpegNotAvailableError,
    FFmpegSlideshowError,
    FFmpegSubtitleError,
    FFprobeNotAvailableError,
    burn_subtitles_into_video,
    create_image_slideshow,
    get_video_duration_seconds,
)
from app.services.subtitle_utils import clean_subtitle_text, split_text_for_duration, write_ass_file
from app.services.tts_service import synthesize_openai_tts
from app.services.video_service import STORAGE_ROOT

BLOG_ROOT = STORAGE_ROOT / "blog"
BLOG_IMAGE_ROOT = BLOG_ROOT / "images"
BLOG_OUTPUT_ROOT = BLOG_ROOT / "outputs"
BLOG_SUBTITLE_ROOT = BLOG_ROOT / "subtitles"

ALLOWED_SUBTITLE_STYLES = {"basic", "bold", "shorts"}

# (status, progress_stage, progress_percent) checkpoints the pipeline moves through.
PROGRESS_QUEUED = ("pending", "queued", 0)
PROGRESS_SCRAPING = ("processing", "scraping", 10)
PROGRESS_DOWNLOADING_IMAGES = ("processing", "downloading_images", 25)
PROGRESS_GENERATING_SCRIPT = ("processing", "generating_script", 40)
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
    return BlogClip(
        id=row["id"],
        user_id=row["user_id"],
        source_url=row["source_url"],
        blog_title=row["blog_title"],
        narration_script=row["narration_script"],
        subtitle_style=row["subtitle_style"],
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
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_BLOG_CLIP_COLUMNS = """
    id, user_id, source_url, blog_title, narration_script, subtitle_style,
    video_path, subtitled_video_path, status, progress_stage, progress_percent,
    error_message, title_candidates_json, description, hashtags_json, metadata_error,
    created_at, updated_at
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


# --- Blog scraping ------------------------------------------------------------


def _is_naver_blog_url(url: str) -> bool:
    return "blog.naver.com" in urlparse(url).netloc


def _resolve_image_src(img: Tag, base_url: str) -> str | None:
    src = img.get("data-lazy-src") or img.get("data-src") or img.get("data-original") or img.get("src")
    if not src or src.startswith("data:"):
        return None
    return urljoin(base_url, src)


def _extract_image_urls(container: Tag, base_url: str) -> list[str]:
    image_urls: list[str] = []
    for img in container.find_all("img"):
        resolved = _resolve_image_src(img, base_url)
        if resolved and resolved not in image_urls:
            image_urls.append(resolved)
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


def download_blog_images(image_urls: list[str], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for url in image_urls:
        if len(saved) >= settings.blog_image_max_count:
            break
        try:
            response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=settings.blog_fetch_timeout_seconds)
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        extension = _CONTENT_TYPE_EXTENSIONS.get(content_type)
        if extension is None:
            continue
        if len(response.content) < _MIN_IMAGE_BYTES:
            continue

        image_path = dest_dir / f"{uuid.uuid4().hex}{extension}"
        image_path.write_bytes(response.content)
        saved.append(image_path)

    return saved


# --- GPT script + metadata ---------------------------------------------------


def generate_blog_narration_script(blog_title: str, blog_text: str) -> str:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""
Create a short AI narration script for a vertical shorts video summarizing a blog post.

Rules:
- Write in Korean unless the blog text is clearly not Korean.
- Summarize the blog post, do not invent facts that are not in the text.
- Keep it natural when read aloud, like a short-form video voiceover.
- Keep it concise: it will be read aloud in about 30-45 seconds.
- Do not include stage directions, timestamps, markdown, hashtags, or the title text itself.
- Avoid exaggerated or misleading claims.

Blog title: {blog_title}

Blog text:
{blog_text}
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
    script = clean_subtitle_text(script or "")
    if not script:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned an empty narration script.")
    return script[:800]


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


def generate_blog_metadata(blog_title: str, script: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OPENAI_API_KEY is not configured.")

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


# --- Subtitle timing from narration script -----------------------------------


def _narration_subtitle_events(script: str, total_duration: float) -> list[tuple[float, float, str]]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", clean_subtitle_text(script)) if part.strip()]
    if not sentences or total_duration <= 0:
        return []

    total_chars = sum(len(sentence) for sentence in sentences) or 1
    events: list[tuple[float, float, str]] = []
    cursor = 0.0

    for sentence in sentences:
        remaining = total_duration - cursor
        if remaining <= 0:
            break
        share = max(0.8, total_duration * (len(sentence) / total_chars))
        duration = min(share, remaining)
        chunks = split_text_for_duration(sentence, duration, 18)
        if not chunks:
            cursor += duration
            continue
        chunk_duration = duration / len(chunks)
        for chunk in chunks:
            start = cursor
            end = min(total_duration, cursor + chunk_duration)
            if end > start:
                events.append((start, end, chunk))
            cursor = end

    return events


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
) -> None:
    status_value, progress_stage, progress_percent = PROGRESS_DONE
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
            error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status_value, progress_stage, progress_percent, blog_title, narration_script, video_path, subtitled_video_path, blog_clip_id),
    )
    conn.commit()


def create_blog_clip_job(conn: sqlite3.Connection, user_id: int, url: str, style: str) -> BlogClip:
    """Insert a `pending` blog_clips row and return immediately.

    The actual scrape/GPT/TTS/FFmpeg pipeline is not run here — call
    `run_blog_clip_pipeline()` (typically via FastAPI `BackgroundTasks`) to
    execute it after this returns. This split is what makes `POST
    /blog-clips` respond instantly instead of blocking for up to a minute.
    """
    if style not in ALLOWED_SUBTITLE_STYLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subtitle style must be basic, bold, or shorts.")

    status_value, progress_stage, progress_percent = PROGRESS_QUEUED
    cursor = conn.execute(
        """
        INSERT INTO blog_clips (user_id, source_url, subtitle_style, status, progress_stage, progress_percent)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, url, style, status_value, progress_stage, progress_percent),
    )
    conn.commit()
    blog_clip_id = int(cursor.lastrowid)
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Blog short creation failed.")
    return blog_clip


def run_blog_clip_pipeline(blog_clip_id: int, user_id: int, url: str, style: str) -> None:
    """The actual scrape -> GPT -> TTS -> FFmpeg pipeline, run out-of-request.

    Opens its own SQLite connection because the request-scoped connection
    used by the API layer is already closed by the time a FastAPI background
    task runs (background tasks execute after the response has been sent).
    """
    connection_generator = get_connection()
    conn = next(connection_generator)
    try:
        try:
            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_SCRAPING)
            blog_content = fetch_blog_content(url)

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_DOWNLOADING_IMAGES)
            image_dir = BLOG_IMAGE_ROOT / str(user_id) / str(blog_clip_id)
            image_paths = download_blog_images(blog_content.image_urls, image_dir)
            if len(image_paths) < settings.blog_image_min_count:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"블로그에서 사용할 수 있는 이미지가 부족합니다 "
                        f"({len(image_paths)}개, 최소 {settings.blog_image_min_count}개 필요)."
                    ),
                )

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_GENERATING_SCRIPT)
            script = generate_blog_narration_script(blog_content.title, blog_content.text)

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_SYNTHESIZING_AUDIO)
            narration_audio_path = synthesize_openai_tts(user_id, blog_clip_id, script)

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_RENDERING_VIDEO)
            video_dir = BLOG_OUTPUT_ROOT / str(user_id)
            video_dir.mkdir(parents=True, exist_ok=True)
            video_path = video_dir / f"{uuid.uuid4().hex}.mp4"
            create_image_slideshow([str(path) for path in image_paths], narration_audio_path, str(video_path))

            total_duration = get_video_duration_seconds(str(video_path))
            events = _narration_subtitle_events(script, total_duration)
            subtitle_path = BLOG_SUBTITLE_ROOT / str(user_id) / f"blog_{blog_clip_id}_{style}.ass"

            _update_blog_clip_progress(conn, blog_clip_id, PROGRESS_BURNING_SUBTITLES)
            if events:
                write_ass_file(subtitle_path, style, events)
                subtitled_video_path = video_dir / f"{video_path.stem}_subtitled.mp4"
                burn_subtitles_into_video(str(video_path), str(subtitle_path), str(subtitled_video_path))
            else:
                subtitled_video_path = video_path
        except HTTPException as exc:
            _update_blog_clip_failed(conn, blog_clip_id, str(exc.detail))
            return
        except (FFmpegNotAvailableError, FFprobeNotAvailableError, FFmpegSlideshowError, FFmpegSubtitleError, TimeoutError) as exc:
            _update_blog_clip_failed(conn, blog_clip_id, str(exc))
            return
        except Exception:
            _update_blog_clip_failed(conn, blog_clip_id, "Unexpected blog short generation failure.")
            return

        _update_blog_clip_result(conn, blog_clip_id, blog_content.title, script, str(video_path), str(subtitled_video_path))
    finally:
        next(connection_generator, None)


def get_or_create_blog_metadata(conn: sqlite3.Connection, user_id: int, blog_clip_id: int) -> BlogClip:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    if blog_clip.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed blog short is required before metadata generation.")
    if blog_clip.title_candidates_json:
        return blog_clip

    try:
        payload = generate_blog_metadata(blog_clip.blog_title or "블로그 쇼츠", blog_clip.narration_script or "")
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
