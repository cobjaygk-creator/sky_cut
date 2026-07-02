import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.users import get_current_user
from app.db.database import get_connection
from app.db.models import User
from app.db.schemas import VideoResponse, VideoStatusResponse
from app.services.video_service import analyze_video_audio, create_video, get_video_for_user, list_videos_for_user

router = APIRouter(prefix="/videos", tags=["videos"])


def _to_response(video) -> VideoResponse:
    return VideoResponse(
        id=video.id,
        original_filename=video.original_filename,
        stored_filename=video.stored_filename,
        content_type=video.content_type,
        file_size=video.file_size,
        status=video.status,
        audio_path=video.audio_path,
        error_message=video.error_message,
        created_at=video.created_at,
        updated_at=video.updated_at,
    )


def _to_status_response(video) -> VideoStatusResponse:
    return VideoStatusResponse(
        id=video.id,
        status=video.status,
        audio_path=video.audio_path,
        error_message=video.error_message,
        updated_at=video.updated_at,
    )


@router.post("/upload", response_model=VideoResponse, status_code=201)
def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> VideoResponse:
    video = create_video(conn, current_user.id, file)
    return _to_response(video)


@router.get("", response_model=list[VideoResponse])
def list_videos(
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[VideoResponse]:
    return [_to_response(video) for video in list_videos_for_user(conn, current_user.id)]


@router.get("/{video_id}", response_model=VideoResponse)
def read_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> VideoResponse:
    video = get_video_for_user(conn, current_user.id, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return _to_response(video)


@router.post("/{video_id}/analyze", response_model=VideoStatusResponse)
def analyze_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> VideoStatusResponse:
    video = analyze_video_audio(conn, current_user.id, video_id)
    return _to_status_response(video)


@router.get("/{video_id}/status", response_model=VideoStatusResponse)
def read_video_status(
    video_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> VideoStatusResponse:
    video = get_video_for_user(conn, current_user.id, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return _to_status_response(video)
