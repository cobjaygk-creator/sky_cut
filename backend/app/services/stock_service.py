"""Pexels stock image search + download for blog-clip boards (Stage 20)."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.models import BlogClipBoard
from app.services.blog_service import (
    _blog_clip_image_dir,
    _require_awaiting_boards_for_mutation,
    get_blog_clip_for_user,
    list_blog_clip_boards,
    update_blog_clip_board,
)

_PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
_ALLOWED_IMAGE_HOSTS = {"images.pexels.com"}
_USER_AGENT = "NewCut/1.0 (blog-clip stock images)"
_MIN_IMAGE_BYTES = 8_000
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _require_pexels_api_key() -> str:
    key = (settings.pexels_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PEXELS_API_KEY가 설정되지 않았습니다. backend/.env에 PEXELS_API_KEY를 추가한 뒤 서버를 재시작하세요.",
        )
    return key


def search_stock_images(query: str, page: int = 1, per_page: int = 12) -> dict:
    api_key = _require_pexels_api_key()
    cleaned = query.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어를 입력하세요.")
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page must be >= 1.")
    per_page = max(1, min(per_page, 24))

    try:
        response = requests.get(
            _PEXELS_SEARCH_URL,
            headers={"Authorization": api_key, "User-Agent": _USER_AGENT},
            params={"query": cleaned, "page": page, "per_page": per_page, "orientation": "portrait"},
            timeout=settings.stock_search_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="스톡 이미지 검색 요청에 실패했습니다.",
        ) from exc

    if response.status_code == 401 or response.status_code == 403:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PEXELS_API_KEY가 유효하지 않습니다. 키를 확인하세요.",
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Pexels 검색이 실패했습니다 (HTTP {response.status_code}).",
        )

    payload = response.json()
    photos = []
    for photo in payload.get("photos") or []:
        src = photo.get("src") or {}
        preview = src.get("medium") or src.get("large") or src.get("original")
        full = src.get("large2x") or src.get("large") or src.get("original") or preview
        if not preview or not full:
            continue
        photos.append(
            {
                "id": photo.get("id"),
                "photographer": photo.get("photographer") or "",
                "alt": photo.get("alt") or cleaned,
                "preview_url": preview,
                "download_url": full,
                "width": photo.get("width"),
                "height": photo.get("height"),
            }
        )

    return {
        "query": cleaned,
        "page": page,
        "per_page": per_page,
        "total_results": int(payload.get("total_results") or 0),
        "photos": photos,
    }


def _assert_pexels_image_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image URL must be http(s).")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in _ALLOWED_IMAGE_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Pexels image URLs (images.pexels.com) can be applied.",
        )
    return url


def download_stock_image_to_clip(user_id: int, blog_clip_id: int, image_url: str) -> Path:
    url = _assert_pexels_image_url(image_url)
    image_dir = _blog_clip_image_dir(user_id, blog_clip_id)
    image_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=settings.stock_search_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="스톡 이미지 다운로드에 실패했습니다.",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"스톡 이미지 다운로드가 실패했습니다 (HTTP {response.status_code}).",
        )

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    extension = _CONTENT_TYPE_EXTENSIONS.get(content_type, ".jpg")
    if len(response.content) < _MIN_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="다운로드한 이미지가 너무 작습니다.")

    destination = image_dir / f"stock_{uuid.uuid4().hex}{extension}"
    destination.write_bytes(response.content)
    return destination


def apply_stock_image_to_board(
    conn: sqlite3.Connection,
    user_id: int,
    blog_clip_id: int,
    board_id: int,
    image_url: str,
) -> BlogClipBoard:
    blog_clip = get_blog_clip_for_user(conn, user_id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    _require_awaiting_boards_for_mutation(blog_clip)

    boards = list_blog_clip_boards(conn, user_id, blog_clip_id)
    if not any(board.id == board_id for board in boards):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")

    saved = download_stock_image_to_clip(user_id, blog_clip_id, image_url)
    return update_blog_clip_board(
        conn,
        user_id,
        blog_clip_id,
        board_id,
        image_path=str(saved),
    )
