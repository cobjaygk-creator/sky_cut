import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response

from app.api.users import get_current_user
from app.db.database import get_connection
from app.db.models import BlogClip, BlogClipBoard, BlogClipImageCandidate, BlogClipVersion, User
from app.db.schemas import (
    BlogClipCreateRequest,
    BlogClipDefaultVoiceRequest,
    BlogClipImageCandidateResponse,
    BlogClipImageSelectionRequest,
    BlogClipPreviewAudioResponse,
    BlogClipResponse,
    BlogClipSelectScriptRequest,
    BlogClipAudioSettingsRequest,
    BlogClipTemplateApplyRequest,
    BlogClipTtsSettingsRequest,
    BlogClipVersionCreateRequest,
    BlogClipVersionResponse,
    BlogClipStyleCopyRequest,
    BlogClipVisualStyleRequest,
    BlogClipWizardStepRequest,
    BlogShortsPropsResponse,
    BoardCreateRequest,
    BoardReorderRequest,
    BoardResponse,
    BoardUpdateRequest,
    StockImageApplyRequest,
    StockSearchResponse,
)
from app.services.blog_service import (
    BGM_ASSET_UNSET,
    SFX_UNSET,
    SPEAKER_UNSET,
    apply_blog_clip_template,
    blog_clip_download_path,
    blog_clip_hashtags,
    blog_clip_render_spec,
    blog_clip_script_candidates,
    blog_clip_title_candidates,
    blog_clip_version_download_path,
    blog_clip_version_hashtags,
    blog_clip_version_render_spec,
    blog_clip_version_title_candidates,
    build_blog_clip_preview_audio,
    confirm_blog_clip_image_selection,
    create_blog_clip_board,
    create_blog_clip_job,
    create_blog_clip_versions,
    delete_blog_clip_board,
    get_blog_clip_board_image_path,
    get_blog_clip_for_user,
    get_blog_clip_image_candidate_path,
    get_blog_clip_preview_audio_path,
    get_blog_clip_version_for_user,
    get_or_create_blog_metadata,
    get_or_create_blog_version_metadata,
    list_blog_clip_boards,
    list_blog_clip_image_candidates,
    list_blog_clip_versions,
    list_blog_clips_for_user,
    reorder_blog_clip_boards,
    run_blog_clip_pipeline,
    run_blog_clip_render_pipeline,
    run_blog_clip_version_pipeline,
    select_blog_clip_script,
    set_active_blog_clip_version,
    start_blog_clip_render,
    update_blog_clip_audio_settings,
    update_blog_clip_board,
    update_blog_clip_default_voice,
    update_blog_clip_tts_settings,
    update_blog_clip_style_copy,
    update_blog_clip_visual_style,
    update_blog_clip_wizard_step,
)
from app.services.remotion_props_service import build_blog_shorts_props
from app.services.render_queue import run_with_render_slot
from app.services.stock_service import apply_stock_image_to_board, search_stock_images

router = APIRouter(prefix="/blog-clips", tags=["blog-clips"])


def _to_blog_clip_response(blog_clip: BlogClip) -> BlogClipResponse:
    return BlogClipResponse(
        id=blog_clip.id,
        source_url=blog_clip.source_url,
        blog_title=blog_clip.blog_title,
        narration_script=blog_clip.narration_script,
        script_tone=blog_clip.script_tone,
        script_candidates=blog_clip_script_candidates(blog_clip),
        subtitle_style=blog_clip.subtitle_style,
        subtitle_template_id=blog_clip.subtitle_template_id,
        video_path=blog_clip.video_path,
        subtitled_video_path=blog_clip.subtitled_video_path,
        status=blog_clip.status,
        progress_stage=blog_clip.progress_stage,
        progress_percent=blog_clip.progress_percent,
        error_message=blog_clip.error_message,
        title_candidates=blog_clip_title_candidates(blog_clip),
        description=blog_clip.description,
        hashtags=blog_clip_hashtags(blog_clip),
        metadata_error=blog_clip.metadata_error,
        tts_speed=blog_clip.tts_speed,
        bgm_asset_id=blog_clip.bgm_asset_id,
        bgm_volume=blog_clip.bgm_volume,
        active_version_id=blog_clip.active_version_id,
        target_length=blog_clip.target_length,
        narration_language=blog_clip.narration_language,
        script_model=blog_clip.script_model,
        default_voice=blog_clip.default_voice,
        auto_bgm=blog_clip.auto_bgm,
        auto_sfx=blog_clip.auto_sfx,
        wizard_step=blog_clip.wizard_step,
        visual_style=blog_clip.visual_style,
        style_title=blog_clip.style_title,
        style_subtitle=blog_clip.style_subtitle,
        render_spec=blog_clip_render_spec(blog_clip),
        created_at=blog_clip.created_at,
        updated_at=blog_clip.updated_at,
    )


def _to_version_response(version: BlogClipVersion, active_version_id: int | None) -> BlogClipVersionResponse:
    return BlogClipVersionResponse(
        id=version.id,
        blog_clip_id=version.blog_clip_id,
        label=version.label,
        source=version.source,
        script_tone=version.script_tone,
        narration_script=version.narration_script,
        video_path=version.video_path,
        subtitled_video_path=version.subtitled_video_path,
        status=version.status,
        progress_stage=version.progress_stage,
        progress_percent=version.progress_percent,
        error_message=version.error_message,
        title_candidates=blog_clip_version_title_candidates(version),
        description=version.description,
        hashtags=blog_clip_version_hashtags(version),
        metadata_error=version.metadata_error,
        is_active=active_version_id == version.id,
        render_spec=blog_clip_version_render_spec(version),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _to_board_response(board: BlogClipBoard) -> BoardResponse:
    return BoardResponse(
        id=board.id,
        blog_clip_id=board.blog_clip_id,
        order_index=board.order_index,
        image_path=board.image_path,
        text=board.text,
        speaker=board.speaker,
        duration_seconds=board.duration_seconds,
        sfx_asset_id=board.sfx_asset_id,
        created_at=board.created_at,
        updated_at=board.updated_at,
    )


@router.post("", response_model=BlogClipResponse, status_code=201)
def create_blog_clip(
    request: BlogClipCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    url = str(request.url)
    blog_clip = create_blog_clip_job(
        conn,
        current_user.id,
        url,
        request.style,
        target_length=request.target_length,
        narration_language=request.narration_language,
        script_model=request.script_model,
    )
    background_tasks.add_task(run_blog_clip_pipeline, blog_clip.id, current_user.id, url, request.style)
    return _to_blog_clip_response(blog_clip)


@router.get("", response_model=list[BlogClipResponse])
def list_blog_clips(
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BlogClipResponse]:
    blog_clips = list_blog_clips_for_user(conn, current_user.id)
    return [_to_blog_clip_response(blog_clip) for blog_clip in blog_clips]


def _to_image_candidate_response(candidate: BlogClipImageCandidate) -> BlogClipImageCandidateResponse:
    return BlogClipImageCandidateResponse(
        id=candidate.id,
        blog_clip_id=candidate.blog_clip_id,
        order_index=candidate.order_index,
        source_url=candidate.source_url,
        selected=candidate.selected,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


@router.get("/{blog_clip_id}/images", response_model=list[BlogClipImageCandidateResponse])
def list_blog_clip_images_endpoint(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BlogClipImageCandidateResponse]:
    candidates = list_blog_clip_image_candidates(conn, current_user.id, blog_clip_id)
    return [_to_image_candidate_response(candidate) for candidate in candidates]


@router.put("/{blog_clip_id}/images/selection", response_model=BlogClipResponse)
def confirm_blog_clip_images_endpoint(
    blog_clip_id: int,
    request: BlogClipImageSelectionRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = confirm_blog_clip_image_selection(
        conn,
        current_user.id,
        blog_clip_id,
        request.image_ids,
    )
    return _to_blog_clip_response(blog_clip)


@router.get("/{blog_clip_id}/images/{image_id}/file")
def read_blog_clip_image_file(
    blog_clip_id: int,
    image_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    path = get_blog_clip_image_candidate_path(conn, current_user.id, blog_clip_id, image_id)
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=path, media_type=media_type, filename=path.name)


@router.post("/{blog_clip_id}/select-script", response_model=BlogClipResponse)
def select_blog_clip_script_endpoint(
    blog_clip_id: int,
    request: BlogClipSelectScriptRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = select_blog_clip_script(conn, current_user.id, blog_clip_id, request.tone)
    return _to_blog_clip_response(blog_clip)


@router.get("/{blog_clip_id}/boards", response_model=list[BoardResponse])
def list_blog_clip_boards_endpoint(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BoardResponse]:
    boards = list_blog_clip_boards(conn, current_user.id, blog_clip_id)
    return [_to_board_response(board) for board in boards]


@router.get("/{blog_clip_id}/remotion-props", response_model=BlogShortsPropsResponse)
def read_blog_clip_remotion_props(
    blog_clip_id: int,
    materialize: bool = Query(
        True,
        description="Copy board images into remotion/public/clips/{id}/ for Remotion staticFile().",
    ),
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogShortsPropsResponse:
    """Export BlogShorts Remotion props from real boards (R1). FastAPI render path unchanged."""
    payload = build_blog_shorts_props(
        conn,
        current_user.id,
        blog_clip_id,
        materialize=materialize,
    )
    return BlogShortsPropsResponse.model_validate(payload)


@router.get("/{blog_clip_id}/preview-audio")
def read_blog_clip_preview_audio(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    """Serve cached TTS+BGM mix used by Remotion Player / final render audio path."""
    path = get_blog_clip_preview_audio_path(conn, current_user.id, blog_clip_id)
    return FileResponse(path=path, media_type="audio/mpeg", filename=path.name)


@router.post("/{blog_clip_id}/preview-audio", response_model=BlogClipPreviewAudioResponse)
def create_blog_clip_preview_audio(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipPreviewAudioResponse:
    """Generate TTS + ducked BGM (+ SFX) and persist board durations for timeline sync."""
    from app.services.ffmpeg_service import get_video_duration_seconds

    path, board_durations = build_blog_clip_preview_audio(conn, current_user.id, blog_clip_id)
    return BlogClipPreviewAudioResponse(
        blog_clip_id=blog_clip_id,
        duration_seconds=get_video_duration_seconds(str(path)),
        board_durations=board_durations,
        preview_audio_url=f"/blog-clips/{blog_clip_id}/preview-audio",
    )


@router.post("/{blog_clip_id}/boards", response_model=BoardResponse, status_code=201)
def create_blog_clip_board_endpoint(
    blog_clip_id: int,
    request: BoardCreateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BoardResponse:
    board = create_blog_clip_board(
        conn,
        current_user.id,
        blog_clip_id,
        request.image_path,
        request.text,
        request.order_index,
    )
    return _to_board_response(board)


@router.patch("/{blog_clip_id}/boards/{board_id}", response_model=BoardResponse)
def update_blog_clip_board_endpoint(
    blog_clip_id: int,
    board_id: int,
    request: BoardUpdateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BoardResponse:
    payload = request.model_dump(exclude_unset=True)
    board = update_blog_clip_board(
        conn,
        current_user.id,
        blog_clip_id,
        board_id,
        image_path=payload.get("image_path"),
        text=payload.get("text"),
        duration_seconds=payload.get("duration_seconds"),
        speaker=payload["speaker"] if "speaker" in payload else SPEAKER_UNSET,
        sfx_asset_id=payload["sfx_asset_id"] if "sfx_asset_id" in payload else SFX_UNSET,
    )
    return _to_board_response(board)


@router.patch("/{blog_clip_id}/tts-settings", response_model=BlogClipResponse)
def update_blog_clip_tts_settings_endpoint(
    blog_clip_id: int,
    request: BlogClipTtsSettingsRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = update_blog_clip_tts_settings(conn, current_user.id, blog_clip_id, request.tts_speed)
    return _to_blog_clip_response(blog_clip)


@router.patch("/{blog_clip_id}/default-voice", response_model=BlogClipResponse)
def update_blog_clip_default_voice_endpoint(
    blog_clip_id: int,
    request: BlogClipDefaultVoiceRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = update_blog_clip_default_voice(
        conn,
        current_user.id,
        blog_clip_id,
        voice_id=request.voice_id,
        tts_speed=request.tts_speed,
        apply_to_all_boards=request.apply_to_all_boards,
    )
    return _to_blog_clip_response(blog_clip)


@router.patch("/{blog_clip_id}/wizard-step", response_model=BlogClipResponse)
def update_blog_clip_wizard_step_endpoint(
    blog_clip_id: int,
    request: BlogClipWizardStepRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = update_blog_clip_wizard_step(
        conn,
        current_user.id,
        blog_clip_id,
        request.wizard_step,
    )
    return _to_blog_clip_response(blog_clip)


@router.patch("/{blog_clip_id}/template", response_model=BlogClipResponse)
def apply_blog_clip_template_endpoint(
    blog_clip_id: int,
    request: BlogClipTemplateApplyRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = apply_blog_clip_template(conn, current_user.id, blog_clip_id, request.template_id)
    return _to_blog_clip_response(blog_clip)


@router.patch("/{blog_clip_id}/visual-style", response_model=BlogClipResponse)
def update_blog_clip_visual_style_endpoint(
    blog_clip_id: int,
    request: BlogClipVisualStyleRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = update_blog_clip_visual_style(
        conn,
        current_user.id,
        blog_clip_id,
        request.visual_style,
    )
    return _to_blog_clip_response(blog_clip)


@router.patch("/{blog_clip_id}/style-copy", response_model=BlogClipResponse)
def update_blog_clip_style_copy_endpoint(
    blog_clip_id: int,
    request: BlogClipStyleCopyRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    payload = request.model_dump(exclude_unset=True)
    blog_clip = update_blog_clip_style_copy(
        conn,
        current_user.id,
        blog_clip_id,
        style_title=payload.get("style_title"),
        style_subtitle=payload.get("style_subtitle"),
        title_set="style_title" in payload,
        subtitle_set="style_subtitle" in payload,
    )
    return _to_blog_clip_response(blog_clip)


@router.patch("/{blog_clip_id}/audio-settings", response_model=BlogClipResponse)
def update_blog_clip_audio_settings_endpoint(
    blog_clip_id: int,
    request: BlogClipAudioSettingsRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    payload = request.model_dump(exclude_unset=True)
    blog_clip = update_blog_clip_audio_settings(
        conn,
        current_user.id,
        blog_clip_id,
        bgm_asset_id=payload["bgm_asset_id"] if "bgm_asset_id" in payload else BGM_ASSET_UNSET,
        bgm_volume=payload.get("bgm_volume"),
        auto_bgm=payload.get("auto_bgm"),
        auto_sfx=payload.get("auto_sfx"),
    )
    return _to_blog_clip_response(blog_clip)


@router.delete("/{blog_clip_id}/boards/{board_id}", status_code=204)
def delete_blog_clip_board_endpoint(
    blog_clip_id: int,
    board_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> Response:
    delete_blog_clip_board(conn, current_user.id, blog_clip_id, board_id)
    return Response(status_code=204)


@router.get("/{blog_clip_id}/boards/{board_id}/image")
def read_blog_clip_board_image(
    blog_clip_id: int,
    board_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    path = get_blog_clip_board_image_path(conn, current_user.id, blog_clip_id, board_id)
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=path, media_type=media_type, filename=path.name)


@router.put("/{blog_clip_id}/boards/reorder", response_model=list[BoardResponse])
def reorder_blog_clip_boards_endpoint(
    blog_clip_id: int,
    request: BoardReorderRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BoardResponse]:
    boards = reorder_blog_clip_boards(conn, current_user.id, blog_clip_id, request.board_ids)
    return [_to_board_response(board) for board in boards]


@router.get("/{blog_clip_id}/stock-search", response_model=StockSearchResponse)
def stock_search_endpoint(
    blog_clip_id: int,
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> StockSearchResponse:
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    result = search_stock_images(query, page=page, per_page=per_page)
    return StockSearchResponse(**result)


@router.post("/{blog_clip_id}/boards/{board_id}/stock-image", response_model=BoardResponse)
def apply_stock_image_endpoint(
    blog_clip_id: int,
    board_id: int,
    request: StockImageApplyRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BoardResponse:
    board = apply_stock_image_to_board(
        conn,
        current_user.id,
        blog_clip_id,
        board_id,
        str(request.download_url),
    )
    return _to_board_response(board)


@router.post("/{blog_clip_id}/render", response_model=BlogClipResponse)
def render_blog_clip_endpoint(
    blog_clip_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipResponse:
    blog_clip = start_blog_clip_render(conn, current_user.id, blog_clip_id)
    background_tasks.add_task(
        run_with_render_slot,
        run_blog_clip_render_pipeline,
        blog_clip.id,
        current_user.id,
    )
    return _to_blog_clip_response(blog_clip)


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


@router.get("/{blog_clip_id}/versions", response_model=list[BlogClipVersionResponse])
def list_blog_clip_versions_endpoint(
    blog_clip_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BlogClipVersionResponse]:
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    if blog_clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog short not found.")
    versions = list_blog_clip_versions(conn, current_user.id, blog_clip_id)
    # Re-read in case legacy backfill set active_version_id.
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id) or blog_clip
    return [_to_version_response(version, blog_clip.active_version_id) for version in versions]


@router.post("/{blog_clip_id}/versions", response_model=list[BlogClipVersionResponse], status_code=201)
def create_blog_clip_versions_endpoint(
    blog_clip_id: int,
    request: BlogClipVersionCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[BlogClipVersionResponse]:
    versions = create_blog_clip_versions(
        conn,
        current_user.id,
        blog_clip_id,
        request.mode,
        request.tone,
    )
    for version in versions:
        background_tasks.add_task(
            run_with_render_slot,
            run_blog_clip_version_pipeline,
            blog_clip_id,
            current_user.id,
            version.id,
            set_active=request.set_active,
        )
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    active_id = blog_clip.active_version_id if blog_clip else None
    return [_to_version_response(version, active_id) for version in versions]


@router.post("/{blog_clip_id}/versions/{version_id}/set-active", response_model=BlogClipVersionResponse)
def set_active_blog_clip_version_endpoint(
    blog_clip_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipVersionResponse:
    version = set_active_blog_clip_version(conn, current_user.id, blog_clip_id, version_id)
    return _to_version_response(version, version.id)


@router.post("/{blog_clip_id}/versions/{version_id}/metadata", response_model=BlogClipVersionResponse)
def create_blog_clip_version_metadata(
    blog_clip_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> BlogClipVersionResponse:
    version = get_or_create_blog_version_metadata(conn, current_user.id, blog_clip_id, version_id)
    blog_clip = get_blog_clip_for_user(conn, current_user.id, blog_clip_id)
    active_id = blog_clip.active_version_id if blog_clip else None
    return _to_version_response(version, active_id)


@router.get("/{blog_clip_id}/versions/{version_id}/download")
def download_blog_clip_version(
    blog_clip_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> FileResponse:
    version = get_blog_clip_version_for_user(conn, current_user.id, blog_clip_id, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    path = blog_clip_version_download_path(version)
    return FileResponse(
        path=path,
        media_type="video/mp4",
        filename=f"new-cut-blog-{blog_clip_id}-v{version_id}.mp4",
    )


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
