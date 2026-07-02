from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: str


class VideoResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    content_type: str
    file_size: int
    status: str
    audio_path: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class VideoStatusResponse(BaseModel):
    id: int
    status: str
    audio_path: str | None = None
    error_message: str | None = None
    updated_at: str


class TranscriptSegmentResponse(BaseModel):
    index: int
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    id: int
    video_id: int
    status: str
    text: str | None = None
    segments: list[TranscriptSegmentResponse] = []
    error_message: str | None = None
    created_at: str
    updated_at: str
