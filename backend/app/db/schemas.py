from typing import Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl


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
    plan: str
    monthly_usage: int
    usage_limit: int
    usage_month: str
    created_at: str


class UsageResponse(BaseModel):
    plan: str
    plan_name: str
    monthly_usage: int
    usage_limit: int
    remaining: int
    usage_month: str
    max_video_minutes: int


class PlanResponse(BaseModel):
    id: str
    name: str
    monthly_video_limit: int
    max_video_minutes: int
    description: str


class YoutubeImportRequest(BaseModel):
    url: HttpUrl


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


class HighlightResponse(BaseModel):
    id: int
    video_id: int
    start_time: float
    end_time: float
    title: str
    reason: str
    content_type: str
    score: float
    created_at: str


class ClipCreateRequest(BaseModel):
    highlight_id: int


SubtitleStyle = Literal["basic", "bold", "shorts"]
TtsMode = Literal["original_audio", "ai_narration"]


class SubtitleCreateRequest(BaseModel):
    style: SubtitleStyle = "basic"


class NarrationRequest(BaseModel):
    mode: TtsMode = "original_audio"


class ClipResponse(BaseModel):
    id: int
    video_id: int
    highlight_id: int
    output_path: str | None = None
    subtitle_style: str | None = None
    subtitle_path: str | None = None
    subtitled_output_path: str | None = None
    tts_mode: str = "original_audio"
    narration_script: str | None = None
    narration_audio_path: str | None = None
    narrated_output_path: str | None = None
    status: str
    error_message: str | None = None
    created_at: str
    updated_at: str


class ClipMetadataResponse(BaseModel):
    id: int
    clip_id: int
    title_candidates: list[str]
    description: str
    hashtags: list[str]
    error_message: str | None = None
    created_at: str
    updated_at: str


ScriptTone = Literal["summary", "hook", "detailed"]
TargetLength = Literal["short", "long"]
NarrationLanguage = Literal["original", "ko", "en", "ja"]
ScriptModel = Literal["gpt-4o-mini", "gpt-4o"]


class BlogClipCreateRequest(BaseModel):
    url: HttpUrl
    style: SubtitleStyle = "shorts"
    target_length: TargetLength = "short"
    narration_language: NarrationLanguage = "original"
    # Temporary per-job override for narration/metadata GPT calls.
    script_model: ScriptModel = "gpt-4o-mini"


class BlogClipSelectScriptRequest(BaseModel):
    tone: ScriptTone


class BlogClipImageCandidateResponse(BaseModel):
    id: int
    blog_clip_id: int
    order_index: int
    source_url: str | None = None
    selected: bool
    created_at: str
    updated_at: str


class BlogClipImageSelectionRequest(BaseModel):
    image_ids: list[int]


class BoardResponse(BaseModel):
    id: int
    blog_clip_id: int
    order_index: int
    image_path: str
    text: str
    speaker: str | None = None
    duration_seconds: float | None = None
    sfx_asset_id: int | None = None
    created_at: str
    updated_at: str


class BlogShortsBoardProps(BaseModel):
    """Remotion BlogShorts board (see remotion/schemas/blog-shorts-props.schema.json)."""

    boardId: int | None = None
    imageUrl: str | None = None
    text: str
    durationSec: float = Field(gt=0, le=120)
    backgroundColor: str | None = None
    speaker: str | None = None


class BlogShortsPropsResponse(BaseModel):
    """Remotion BlogShorts props exported from a blog clip."""

    blogClipId: int | None = None
    title: str | None = None
    transitionSec: float = 0.35
    source: Literal["dummy", "blog_clip"] = "blog_clip"
    narrationUrl: str | None = None
    boards: list[BlogShortsBoardProps]


class BlogClipPreviewAudioResponse(BaseModel):
    """Result of building TTS+BGM preview audio for the Remotion Player."""

    blog_clip_id: int
    duration_seconds: float
    board_durations: list[float]
    preview_audio_url: str


class BoardCreateRequest(BaseModel):
    image_path: str
    text: str = ""
    order_index: int | None = None


class BoardUpdateRequest(BaseModel):
    image_path: str | None = None
    text: str | None = None
    duration_seconds: float | None = None
    speaker: str | None = None
    sfx_asset_id: int | None = None


class BlogClipTtsSettingsRequest(BaseModel):
    tts_speed: float = Field(ge=0.25, le=4.0)


class BlogClipDefaultVoiceRequest(BaseModel):
    voice_id: str
    tts_speed: float = Field(default=1.0, ge=0.25, le=4.0)
    apply_to_all_boards: bool = True


WizardStep = Literal["edit_mode", "quick", "ready", "boards", "voice", "style"]


class BlogClipWizardStepRequest(BaseModel):
    wizard_step: WizardStep


class BlogClipTemplateApplyRequest(BaseModel):
    template_id: int


class BlogClipAudioSettingsRequest(BaseModel):
    bgm_asset_id: int | None = None
    bgm_volume: float | None = Field(default=None, ge=0.0, le=0.55)
    auto_bgm: bool | None = None
    auto_sfx: bool | None = None


class BlogClipVersionCreateRequest(BaseModel):
    mode: Literal["boards", "tone", "all_tones"] = "boards"
    tone: ScriptTone | None = None
    set_active: bool = False


class AudioAssetResponse(BaseModel):
    id: int
    user_id: int | None = None
    kind: str
    name: str
    slug: str | None = None
    is_system: bool = False
    duration_seconds: float | None = None
    created_at: str
    updated_at: str


class VoiceResponse(BaseModel):
    id: str
    name: str
    description: str


class SubtitleTemplateResponse(BaseModel):
    id: int
    user_id: int | None = None
    name: str
    slug: str | None = None
    is_system: bool = False
    font_name: str
    font_size: int
    primary_color: str
    outline_color: str
    back_color: str
    primary_alpha: int = 0
    outline_alpha: int = 0
    back_alpha: int = 204
    bold: bool = False
    outline: float = 3
    shadow: float = 1
    alignment: int = 2
    margin_l: int = 80
    margin_r: int = 80
    margin_v: int = 150
    border_style: int = 1
    created_at: str
    updated_at: str


class SubtitleTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    font_name: str = "Malgun Gothic"
    font_size: int = Field(default=64, ge=24, le=120)
    primary_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    back_color: str = "#000000"
    primary_alpha: int = Field(default=0, ge=0, le=255)
    outline_alpha: int = Field(default=0, ge=0, le=255)
    back_alpha: int = Field(default=204, ge=0, le=255)
    bold: bool = True
    outline: float = Field(default=4, ge=0, le=12)
    shadow: float = Field(default=1, ge=0, le=12)
    alignment: int = Field(default=2, ge=1, le=9)
    margin_l: int = Field(default=70, ge=0, le=600)
    margin_r: int = Field(default=70, ge=0, le=600)
    margin_v: int = Field(default=180, ge=0, le=600)
    border_style: int = Field(default=1, ge=1, le=3)


class SubtitleTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    font_name: str | None = None
    font_size: int | None = Field(default=None, ge=24, le=120)
    primary_color: str | None = None
    outline_color: str | None = None
    back_color: str | None = None
    primary_alpha: int | None = Field(default=None, ge=0, le=255)
    outline_alpha: int | None = Field(default=None, ge=0, le=255)
    back_alpha: int | None = Field(default=None, ge=0, le=255)
    bold: bool | None = None
    outline: float | None = Field(default=None, ge=0, le=12)
    shadow: float | None = Field(default=None, ge=0, le=12)
    alignment: int | None = Field(default=None, ge=1, le=9)
    margin_l: int | None = Field(default=None, ge=0, le=600)
    margin_r: int | None = Field(default=None, ge=0, le=600)
    margin_v: int | None = Field(default=None, ge=0, le=600)
    border_style: int | None = Field(default=None, ge=1, le=3)


class SubtitleTemplateCloneRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)


class BoardReorderRequest(BaseModel):
    board_ids: list[int]


class StockPhoto(BaseModel):
    id: int | None = None
    photographer: str = ""
    alt: str = ""
    preview_url: str
    download_url: str
    width: int | None = None
    height: int | None = None


class StockSearchResponse(BaseModel):
    query: str
    page: int
    per_page: int
    total_results: int
    photos: list[StockPhoto]


class StockImageApplyRequest(BaseModel):
    download_url: HttpUrl


class BlogClipResponse(BaseModel):
    id: int
    source_url: str
    blog_title: str | None = None
    narration_script: str | None = None
    script_tone: str | None = None
    script_candidates: dict[str, str] = {}
    subtitle_style: str = "shorts"
    subtitle_template_id: int | None = None
    video_path: str | None = None
    subtitled_video_path: str | None = None
    status: str
    progress_stage: str = "queued"
    progress_percent: int = 0
    error_message: str | None = None
    title_candidates: list[str] = []
    description: str | None = None
    hashtags: list[str] = []
    metadata_error: str | None = None
    tts_speed: float = 1.0
    bgm_asset_id: int | None = None
    bgm_volume: float = 0.30
    active_version_id: int | None = None
    target_length: str = "short"
    narration_language: str = "original"
    script_model: str = "gpt-4o-mini"
    default_voice: str | None = None
    auto_bgm: bool = False
    auto_sfx: bool = False
    wizard_step: str | None = None
    # Temporary debug/ops payload from the last successful render (engine, duration, …).
    render_spec: dict | None = None
    created_at: str
    updated_at: str


class BlogClipVersionResponse(BaseModel):
    id: int
    blog_clip_id: int
    label: str
    source: str
    script_tone: str | None = None
    narration_script: str | None = None
    video_path: str | None = None
    subtitled_video_path: str | None = None
    status: str
    progress_stage: str = "queued"
    progress_percent: int = 0
    error_message: str | None = None
    title_candidates: list[str] = []
    description: str | None = None
    hashtags: list[str] = []
    metadata_error: str | None = None
    is_active: bool = False
    render_spec: dict | None = None
    created_at: str
    updated_at: str
