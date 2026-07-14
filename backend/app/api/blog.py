import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.users import get_current_user
from app.db.database import get_connection
from app.db.models import BlogClip, User
from app.db.schemas import BlogClipCreateRequest, BlogClipResponse
from app.services.blog_service import (
    blog_clip_download_path,
    blog_clip_hashtags,
    blog_clip_title_candidates,
    create_blog_short,
    get_blog_clip_for_user,
    get_or_create_blog_metadata,
    list_blog_clips_for_user,
)

router = APIRouter(prefix="/blog-clips", tags=["blog-clips"])


def _to_blog_clip_response(blog_clip: BlogClip) -> BlogClipResponse:
    return BlogClipResponse(
        id=blog_clip.id,
        source_url=blog_clip.source_url,
        blog_title=blog_clip.blog_title,
        narration_script=blog_clip.narration_script,
        subtitle_style=blog_clip.subtitle_style,
        video_path=blog_clip.video_path,
        subtitled_video_path=blog_clip.subtitled_video_path,
        status=blog_clip.status,
        error_message=blog_clip.error_message,
        title_candidates=blog_clip_title_candidates(blog_clip),
        description=blog_clip.description,
        hashtags=blog_clip_hashtags(blog_clip),
        metadata_error=blog_clip.metadata_error,
        created_at=blog_clip.created_at,
        updated_at=blog_clip.updated_at,
    )


@router.post("", response_model=BlogClipResponse, status_code=201)
def create_blog_clip(
    request: BlogClipCreateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = create_blog_short(conn, current_user.id, str(request.url), request.style)
    return _to_blog_clip_response(blog_clip)


@router.get("", response_model=list[BlogClipResponse])
def list_blog_clips(
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BlogClipResponse]:
    blog_clips = list_blog_clips_for_user(conn, current_user.id)
    return [_to_blog_clip_response(blog_clip) for blog_clip in blog_clips]


@router.post("/{blog_clip_id}/metadata", response_model=BlogClipResponse)
def create_blog_clip_metadata(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = get_or_create_blog_metadata(conn, current_user.id, blog_clip_id)
    return _to_blog_clip_response(blog_clip)


@router.get("/{blog_clip_id}/metadata", response_model=BlogClipResponse)
def read_blog_clip_metadata(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    return _to_blog_clip_response(blog_clip)


@router.get("/{blog_clip_id}/download")
def download_blog_clip(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    path = blog_clip_download_path(blog_clip)
    return FileResponse(path=path, media_type="video/mp4", filename=f"new-cut-blog-{blog_clip.id}.mp4")


@router.get("/{blog_clip_id}", response_model=BlogClipResponse)
def read_blog_clip(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    return _to_blog_clip_response(blog_clip)
