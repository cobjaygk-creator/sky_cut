from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    email: str
    plan: str
    monthly_usage: int
    usage_limit: int
    usage_month: str
    created_at: str


@dataclass(frozen=True)
class Video:
    id: int
    user_id: int
    original_filename: str
    stored_filename: str
    storage_path: str
    content_type: str
    file_size: int
    status: str
    audio_path: str | None
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Transcript:
    id: int
    video_id: int
    status: str
    text: str | None
    segments_json: str
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Highlight:
    id: int
    video_id: int
    start_time: float
    end_time: float
    title: str
    reason: str
    content_type: str
    score: float
    created_at: str


@dataclass(frozen=True)
class Clip:
    id: int
    user_id: int
    video_id: int
    highlight_id: int
    output_path: str | None
    subtitle_style: str | None
    subtitle_path: str | None
    subtitled_output_path: str | None
    tts_mode: str
    narration_script: str | None
    narration_audio_path: str | None
    narrated_output_path: str | None
    status: str
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ClipMetadata:
    id: int
    clip_id: int
    title_candidates_json: str
    description: str
    hashtags_json: str
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BlogClipBoard:
    id: int
    blog_clip_id: int
    order_index: int
    image_path: str
    text: str
    speaker: str | None
    duration_seconds: float | None
    sfx_asset_id: int | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BlogClipImageCandidate:
    id: int
    blog_clip_id: int
    order_index: int
    storage_path: str
    source_url: str | None
    selected: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AudioAsset:
    id: int
    user_id: int | None
    kind: str
    name: str
    slug: str | None
    storage_path: str
    duration_seconds: float | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SubtitleTemplate:
    id: int
    user_id: int | None
    name: str
    slug: str | None
    font_name: str
    font_size: int
    primary_color: str
    outline_color: str
    back_color: str
    primary_alpha: int
    outline_alpha: int
    back_alpha: int
    bold: bool
    outline: float
    shadow: float
    alignment: int
    margin_l: int
    margin_r: int
    margin_v: int
    border_style: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BlogClipVersion:
    id: int
    blog_clip_id: int
    label: str
    source: str
    script_tone: str | None
    narration_script: str | None
    video_path: str | None
    subtitled_video_path: str | None
    status: str
    progress_stage: str
    progress_percent: int
    error_message: str | None
    title_candidates_json: str | None
    description: str | None
    hashtags_json: str | None
    metadata_error: str | None
    render_spec_json: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BlogClip:
    id: int
    user_id: int
    source_url: str
    blog_title: str | None
    narration_script: str | None
    script_tone: str | None
    script_candidates_json: str | None
    subtitle_style: str
    subtitle_template_id: int | None
    video_path: str | None
    subtitled_video_path: str | None
    status: str
    progress_stage: str
    progress_percent: int
    error_message: str | None
    title_candidates_json: str | None
    description: str | None
    hashtags_json: str | None
    metadata_error: str | None
    tts_speed: float
    bgm_asset_id: int | None
    bgm_volume: float
    active_version_id: int | None
    target_length: str
    narration_language: str
    script_model: str
    default_voice: str | None
    auto_bgm: bool
    auto_sfx: bool
    wizard_step: str | None
    visual_style: str
    style_title: str | None
    style_subtitle: str | None
    render_spec_json: str | None
    created_at: str
    updated_at: str
