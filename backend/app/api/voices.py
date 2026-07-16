from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.users import get_current_user
from app.db.models import User
from app.db.schemas import VoiceResponse
from app.services.tts_service import get_or_create_voice_sample, list_voice_catalog, validate_voice_id

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("", response_model=list[VoiceResponse])
def list_voices(current_user: User = Depends(get_current_user)) -> list[VoiceResponse]:
    _ = current_user
    return [VoiceResponse(**item) for item in list_voice_catalog()]


@router.get("/{voice_id}/sample")
def read_voice_sample(voice_id: str, current_user: User = Depends(get_current_user)) -> FileResponse:
    _ = current_user
    voice = validate_voice_id(voice_id)
    path = get_or_create_voice_sample(voice)
    return FileResponse(path=path, media_type="audio/mpeg", filename=f"{voice}-sample.mp3")
