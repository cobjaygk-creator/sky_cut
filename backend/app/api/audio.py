import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.users import get_current_user
from app.db.database import get_connection
from app.db.models import AudioAsset, User
from app.db.schemas import AudioAssetResponse
from app.services.audio_service import (
    assert_audio_asset_usable,
    create_user_audio_asset,
    delete_user_audio_asset,
    list_audio_assets,
)

router = APIRouter(prefix="/audio-assets", tags=["audio-assets"])


def _to_asset_response(asset: AudioAsset) -> AudioAssetResponse:
    return AudioAssetResponse(
        id=asset.id,
        user_id=asset.user_id,
        kind=asset.kind,
        name=asset.name,
        slug=asset.slug,
        is_system=asset.user_id is None,
        duration_seconds=asset.duration_seconds,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


@router.get("", response_model=list[AudioAssetResponse])
def list_audio_assets_endpoint(
    kind: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[AudioAssetResponse]:
    assets = list_audio_assets(conn, current_user.id, kind=kind)
    return [_to_asset_response(asset) for asset in assets]


@router.post("", response_model=AudioAssetResponse, status_code=201)
async def upload_audio_asset(
    kind: str = Form(...),
    name: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> AudioAssetResponse:
    asset = await create_user_audio_asset(conn, current_user.id, kind=kind, name=name, upload=file)
    return _to_asset_response(asset)


@router.get("/{asset_id}/file")
def read_audio_asset_file(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    asset = assert_audio_asset_usable(conn, current_user.id, asset_id)
    media_type = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
    }.get(Path(asset.storage_path).suffix.lower(), "application/octet-stream")
    return FileResponse(path=asset.storage_path, media_type=media_type, filename=Path(asset.storage_path).name)


@router.delete("/{asset_id}", status_code=204)
def delete_audio_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> Response:
    delete_user_audio_asset(conn, current_user.id, asset_id)
    return Response(status_code=204)
