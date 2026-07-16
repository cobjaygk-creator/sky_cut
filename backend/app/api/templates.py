import sqlite3

from fastapi import APIRouter, Depends, Response

from app.api.users import get_current_user
from app.db.database import get_connection
from app.db.models import SubtitleTemplate, User
from app.db.schemas import (
    SubtitleTemplateCloneRequest,
    SubtitleTemplateCreateRequest,
    SubtitleTemplateResponse,
    SubtitleTemplateUpdateRequest,
)
from app.services.template_service import (
    clone_template,
    create_template,
    delete_template,
    list_templates_for_user,
    update_template,
)

router = APIRouter(prefix="/subtitle-templates", tags=["subtitle-templates"])


def _to_template_response(template: SubtitleTemplate) -> SubtitleTemplateResponse:
    return SubtitleTemplateResponse(
        id=template.id,
        user_id=template.user_id,
        name=template.name,
        slug=template.slug,
        is_system=template.user_id is None,
        font_name=template.font_name,
        font_size=template.font_size,
        primary_color=template.primary_color,
        outline_color=template.outline_color,
        back_color=template.back_color,
        primary_alpha=template.primary_alpha,
        outline_alpha=template.outline_alpha,
        back_alpha=template.back_alpha,
        bold=template.bold,
        outline=template.outline,
        shadow=template.shadow,
        alignment=template.alignment,
        margin_l=template.margin_l,
        margin_r=template.margin_r,
        margin_v=template.margin_v,
        border_style=template.border_style,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("", response_model=list[SubtitleTemplateResponse])
def list_subtitle_templates(
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[SubtitleTemplateResponse]:
    templates = list_templates_for_user(conn, current_user.id)
    return [_to_template_response(template) for template in templates]


@router.post("", response_model=SubtitleTemplateResponse, status_code=201)
def create_subtitle_template(
    request: SubtitleTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> SubtitleTemplateResponse:
    template = create_template(
        conn,
        current_user.id,
        name=request.name,
        font_name=request.font_name,
        font_size=request.font_size,
        primary_color=request.primary_color,
        outline_color=request.outline_color,
        back_color=request.back_color,
        primary_alpha=request.primary_alpha,
        outline_alpha=request.outline_alpha,
        back_alpha=request.back_alpha,
        bold=request.bold,
        outline=request.outline,
        shadow=request.shadow,
        alignment=request.alignment,
        margin_l=request.margin_l,
        margin_r=request.margin_r,
        margin_v=request.margin_v,
        border_style=request.border_style,
    )
    return _to_template_response(template)


@router.patch("/{template_id}", response_model=SubtitleTemplateResponse)
def update_subtitle_template(
    template_id: int,
    request: SubtitleTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> SubtitleTemplateResponse:
    updates = request.model_dump(exclude_unset=True)
    template = update_template(conn, current_user.id, template_id, updates)
    return _to_template_response(template)


@router.post("/{template_id}/clone", response_model=SubtitleTemplateResponse, status_code=201)
def clone_subtitle_template(
    template_id: int,
    request: SubtitleTemplateCloneRequest,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> SubtitleTemplateResponse:
    template = clone_template(conn, current_user.id, template_id, request.name)
    return _to_template_response(template)


@router.delete("/{template_id}", status_code=204)
def delete_subtitle_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_connection),
) -> Response:
    delete_template(conn, current_user.id, template_id)
    return Response(status_code=204)
