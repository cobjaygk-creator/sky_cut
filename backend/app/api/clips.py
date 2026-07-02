import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.users import get_current_user
from app.db.database import get_connection
from app.db.models import User
from app.db.schemas import ClipCreateRequest, ClipResponse, SubtitleCreateRequest
from app.services.clip_service import clip_download_path, create_clip_from_highlight, create_subtitled_clip, get_clip_for_user

router = APIRouter(prefix="/clips", tags=["clips"])


def _to_clip_response(clip) -> ClipResponse:
    return ClipResponse(
        id=clip.id,
        video_id=clip.video_id,
        highlight_id=clip.highlight_id,
        output_path=clip.output_path,
        subtitle_style=clip.subtitle_style,
        subtitle_path=clip.subtitle_path,
        subtitled_output_path=clip.subtitled_output_path,
        status=clip.status,
        error_message=clip.error_message,
        created_at=clip.created_at,
        updated_at=clip.updated_at,
    )


@router.post("/create", response_model=ClipResponse, status_code=201)
def create_clip(
    request: ClipCreateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> ClipResponse:
    clip = create_clip_from_highlight(conn, current_user.id, request.highlight_id)
    return _to_clip_response(clip)


@router.post("/{clip_id}/subtitles", response_model=ClipResponse)
def burn_clip_subtitles(
    clip_id: int,
    request: SubtitleCreateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> ClipResponse:
    clip = create_subtitled_clip(conn, current_user.id, clip_id, request.style)
    return _to_clip_response(clip)


@router.get("/{clip_id}/download")
def download_clip(
    clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    clip = get_clip_for_user(conn, current_user.id, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    path = clip_download_path(clip)
    suffix = "subtitled" if clip.subtitled_output_path else "clip"
    return FileResponse(path=path, media_type="video/mp4", filename=f"new-cut-{suffix}-{clip.id}.mp4")


@router.get("/{clip_id}", response_model=ClipResponse)
def read_clip(
    clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> ClipResponse:
    clip = get_clip_for_user(conn, current_user.id, clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    return _to_clip_response(clip)
