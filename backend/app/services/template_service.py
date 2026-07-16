"""Subtitle template presets (Stage 22) — CRUD + resolve for ASS burn-in."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException, status

from app.db.models import SubtitleTemplate
from app.services.subtitle_utils import (
    AssStyleParams,
    builtin_style_params,
    normalize_hex_color,
)

_TEMPLATE_COLUMNS = """
    id, user_id, name, slug, font_name, font_size, primary_color, outline_color, back_color,
    primary_alpha, outline_alpha, back_alpha, bold, outline, shadow, alignment,
    margin_l, margin_r, margin_v, border_style, created_at, updated_at
"""


def _seed_from_params(params: AssStyleParams) -> dict[str, Any]:
    return {
        "font_name": params.font_name,
        "font_size": params.font_size,
        "primary_color": params.primary_color,
        "outline_color": params.outline_color,
        "back_color": params.back_color,
        "primary_alpha": params.primary_alpha,
        "outline_alpha": params.outline_alpha,
        "back_alpha": params.back_alpha,
        "bold": 1 if params.bold else 0,
        "outline": params.outline,
        "shadow": params.shadow,
        "alignment": params.alignment,
        "margin_l": params.margin_l,
        "margin_r": params.margin_r,
        "margin_v": params.margin_v,
        "border_style": params.border_style,
    }


SYSTEM_TEMPLATE_SEEDS: list[dict[str, Any]] = [
    {"name": "기본", "slug": "basic", **_seed_from_params(builtin_style_params("basic"))},
    {"name": "볼드", "slug": "bold", **_seed_from_params(builtin_style_params("bold"))},
    {"name": "쇼츠", "slug": "shorts", **_seed_from_params(builtin_style_params("shorts"))},
]


def _row_to_template(row: sqlite3.Row) -> SubtitleTemplate:
    return SubtitleTemplate(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        slug=row["slug"],
        font_name=row["font_name"],
        font_size=int(row["font_size"]),
        primary_color=row["primary_color"],
        outline_color=row["outline_color"],
        back_color=row["back_color"],
        primary_alpha=int(row["primary_alpha"]),
        outline_alpha=int(row["outline_alpha"]),
        back_alpha=int(row["back_alpha"]),
        bold=bool(row["bold"]),
        outline=float(row["outline"]),
        shadow=float(row["shadow"]),
        alignment=int(row["alignment"]),
        margin_l=int(row["margin_l"]),
        margin_r=int(row["margin_r"]),
        margin_v=int(row["margin_v"]),
        border_style=int(row["border_style"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def seed_system_templates(conn: sqlite3.Connection) -> None:
    for seed in SYSTEM_TEMPLATE_SEEDS:
        existing = conn.execute(
            "SELECT id FROM subtitle_templates WHERE user_id IS NULL AND slug = ?",
            (seed["slug"],),
        ).fetchone()
        if existing is not None:
            continue
        conn.execute(
            """
            INSERT INTO subtitle_templates (
                user_id, name, slug, font_name, font_size, primary_color, outline_color, back_color,
                primary_alpha, outline_alpha, back_alpha, bold, outline, shadow, alignment,
                margin_l, margin_r, margin_v, border_style
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                seed["name"],
                seed["slug"],
                seed["font_name"],
                seed["font_size"],
                seed["primary_color"],
                seed["outline_color"],
                seed["back_color"],
                seed["primary_alpha"],
                seed["outline_alpha"],
                seed["back_alpha"],
                seed["bold"],
                seed["outline"],
                seed["shadow"],
                seed["alignment"],
                seed["margin_l"],
                seed["margin_r"],
                seed["margin_v"],
                seed["border_style"],
            ),
        )


def template_to_ass_params(template: SubtitleTemplate) -> AssStyleParams:
    return AssStyleParams(
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
    )


def get_template_by_id(conn: sqlite3.Connection, template_id: int) -> SubtitleTemplate | None:
    row = conn.execute(
        f"SELECT {_TEMPLATE_COLUMNS} FROM subtitle_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    return _row_to_template(row) if row else None


def get_system_template_by_slug(conn: sqlite3.Connection, slug: str) -> SubtitleTemplate | None:
    row = conn.execute(
        f"SELECT {_TEMPLATE_COLUMNS} FROM subtitle_templates WHERE user_id IS NULL AND slug = ?",
        (slug,),
    ).fetchone()
    return _row_to_template(row) if row else None


def list_templates_for_user(conn: sqlite3.Connection, user_id: int) -> list[SubtitleTemplate]:
    rows = conn.execute(
        f"""
        SELECT {_TEMPLATE_COLUMNS} FROM subtitle_templates
        WHERE user_id IS NULL OR user_id = ?
        ORDER BY CASE WHEN user_id IS NULL THEN 0 ELSE 1 END, id ASC
        """,
        (user_id,),
    ).fetchall()
    return [_row_to_template(row) for row in rows]


def _validate_template_fields(
    *,
    name: str,
    font_name: str,
    font_size: int,
    primary_color: str,
    outline_color: str,
    back_color: str,
    primary_alpha: int,
    outline_alpha: int,
    back_alpha: int,
    outline: float,
    shadow: float,
    alignment: int,
    margin_l: int,
    margin_r: int,
    margin_v: int,
    border_style: int,
) -> dict[str, Any]:
    cleaned_name = name.strip()
    if not cleaned_name or len(cleaned_name) > 80:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name must be 1–80 characters.")
    cleaned_font = font_name.strip() or "Malgun Gothic"
    if len(cleaned_font) > 80:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="font_name is too long.")
    if font_size < 24 or font_size > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="font_size must be between 24 and 120.")
    try:
        primary = normalize_hex_color(primary_color, field_name="primary_color")
        outline_c = normalize_hex_color(outline_color, field_name="outline_color")
        back = normalize_hex_color(back_color, field_name="back_color")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    for alpha_name, alpha in (
        ("primary_alpha", primary_alpha),
        ("outline_alpha", outline_alpha),
        ("back_alpha", back_alpha),
    ):
        if alpha < 0 or alpha > 255:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{alpha_name} must be 0–255.")
    if outline < 0 or outline > 12:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="outline must be between 0 and 12.")
    if shadow < 0 or shadow > 12:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="shadow must be between 0 and 12.")
    if alignment not in {1, 2, 3, 4, 5, 6, 7, 8, 9}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="alignment must be 1–9 (numpad).")
    for margin_name, margin in (("margin_l", margin_l), ("margin_r", margin_r), ("margin_v", margin_v)):
        if margin < 0 or margin > 600:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{margin_name} must be 0–600.")
    if border_style not in {1, 3}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="border_style must be 1 (outline) or 3 (box).")
    return {
        "name": cleaned_name,
        "font_name": cleaned_font,
        "font_size": font_size,
        "primary_color": primary,
        "outline_color": outline_c,
        "back_color": back,
        "primary_alpha": primary_alpha,
        "outline_alpha": outline_alpha,
        "back_alpha": back_alpha,
        "outline": outline,
        "shadow": shadow,
        "alignment": alignment,
        "margin_l": margin_l,
        "margin_r": margin_r,
        "margin_v": margin_v,
        "border_style": border_style,
    }


def create_template(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    name: str,
    font_name: str = "Malgun Gothic",
    font_size: int = 64,
    primary_color: str = "#FFFFFF",
    outline_color: str = "#000000",
    back_color: str = "#000000",
    primary_alpha: int = 0,
    outline_alpha: int = 0,
    back_alpha: int = 0xCC,
    bold: bool = True,
    outline: float = 4.0,
    shadow: float = 1.0,
    alignment: int = 2,
    margin_l: int = 70,
    margin_r: int = 70,
    margin_v: int = 180,
    border_style: int = 1,
) -> SubtitleTemplate:
    fields = _validate_template_fields(
        name=name,
        font_name=font_name,
        font_size=font_size,
        primary_color=primary_color,
        outline_color=outline_color,
        back_color=back_color,
        primary_alpha=primary_alpha,
        outline_alpha=outline_alpha,
        back_alpha=back_alpha,
        outline=outline,
        shadow=shadow,
        alignment=alignment,
        margin_l=margin_l,
        margin_r=margin_r,
        margin_v=margin_v,
        border_style=border_style,
    )
    cursor = conn.execute(
        """
        INSERT INTO subtitle_templates (
            user_id, name, slug, font_name, font_size, primary_color, outline_color, back_color,
            primary_alpha, outline_alpha, back_alpha, bold, outline, shadow, alignment,
            margin_l, margin_r, margin_v, border_style
        ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            fields["name"],
            fields["font_name"],
            fields["font_size"],
            fields["primary_color"],
            fields["outline_color"],
            fields["back_color"],
            fields["primary_alpha"],
            fields["outline_alpha"],
            fields["back_alpha"],
            1 if bold else 0,
            fields["outline"],
            fields["shadow"],
            fields["alignment"],
            fields["margin_l"],
            fields["margin_r"],
            fields["margin_v"],
            fields["border_style"],
        ),
    )
    conn.commit()
    template = get_template_by_id(conn, int(cursor.lastrowid))
    if template is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Template creation failed.")
    return template


def update_template(
    conn: sqlite3.Connection,
    user_id: int,
    template_id: int,
    updates: dict[str, Any],
) -> SubtitleTemplate:
    template = get_template_by_id(conn, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    if template.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="시스템 프리셋은 수정할 수 없습니다. 복제 후 편집하세요.")
    if template.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    merged = {
        "name": updates.get("name", template.name),
        "font_name": updates.get("font_name", template.font_name),
        "font_size": updates.get("font_size", template.font_size),
        "primary_color": updates.get("primary_color", template.primary_color),
        "outline_color": updates.get("outline_color", template.outline_color),
        "back_color": updates.get("back_color", template.back_color),
        "primary_alpha": updates.get("primary_alpha", template.primary_alpha),
        "outline_alpha": updates.get("outline_alpha", template.outline_alpha),
        "back_alpha": updates.get("back_alpha", template.back_alpha),
        "outline": updates.get("outline", template.outline),
        "shadow": updates.get("shadow", template.shadow),
        "alignment": updates.get("alignment", template.alignment),
        "margin_l": updates.get("margin_l", template.margin_l),
        "margin_r": updates.get("margin_r", template.margin_r),
        "margin_v": updates.get("margin_v", template.margin_v),
        "border_style": updates.get("border_style", template.border_style),
    }
    bold = updates.get("bold", template.bold)
    fields = _validate_template_fields(**merged)
    conn.execute(
        """
        UPDATE subtitle_templates SET
            name = ?, font_name = ?, font_size = ?, primary_color = ?, outline_color = ?, back_color = ?,
            primary_alpha = ?, outline_alpha = ?, back_alpha = ?, bold = ?, outline = ?, shadow = ?,
            alignment = ?, margin_l = ?, margin_r = ?, margin_v = ?, border_style = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            fields["name"],
            fields["font_name"],
            fields["font_size"],
            fields["primary_color"],
            fields["outline_color"],
            fields["back_color"],
            fields["primary_alpha"],
            fields["outline_alpha"],
            fields["back_alpha"],
            1 if bold else 0,
            fields["outline"],
            fields["shadow"],
            fields["alignment"],
            fields["margin_l"],
            fields["margin_r"],
            fields["margin_v"],
            fields["border_style"],
            template_id,
        ),
    )
    conn.commit()
    refreshed = get_template_by_id(conn, template_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Template update failed.")
    return refreshed


def delete_template(conn: sqlite3.Connection, user_id: int, template_id: int) -> None:
    template = get_template_by_id(conn, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    if template.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="시스템 프리셋은 삭제할 수 없습니다.")
    if template.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    conn.execute(
        "UPDATE blog_clips SET subtitle_template_id = NULL WHERE subtitle_template_id = ? AND user_id = ?",
        (template_id, user_id),
    )
    conn.execute("DELETE FROM subtitle_templates WHERE id = ? AND user_id = ?", (template_id, user_id))
    conn.commit()


def clone_template(conn: sqlite3.Connection, user_id: int, template_id: int, name: str | None = None) -> SubtitleTemplate:
    source = get_template_by_id(conn, template_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    if source.user_id is not None and source.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    clone_name = (name or f"{source.name} 복사").strip()
    return create_template(
        conn,
        user_id,
        name=clone_name,
        font_name=source.font_name,
        font_size=source.font_size,
        primary_color=source.primary_color,
        outline_color=source.outline_color,
        back_color=source.back_color,
        primary_alpha=source.primary_alpha,
        outline_alpha=source.outline_alpha,
        back_alpha=source.back_alpha,
        bold=source.bold,
        outline=source.outline,
        shadow=source.shadow,
        alignment=source.alignment,
        margin_l=source.margin_l,
        margin_r=source.margin_r,
        margin_v=source.margin_v,
        border_style=source.border_style,
    )


def assert_template_usable(conn: sqlite3.Connection, user_id: int, template_id: int) -> SubtitleTemplate:
    template = get_template_by_id(conn, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    if template.user_id is not None and template.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return template


def resolve_ass_params_for_blog_clip(
    conn: sqlite3.Connection,
    user_id: int,
    subtitle_template_id: int | None,
    subtitle_style: str,
) -> AssStyleParams:
    if subtitle_template_id is not None:
        template = assert_template_usable(conn, user_id, subtitle_template_id)
        return template_to_ass_params(template)
    system = get_system_template_by_slug(conn, subtitle_style)
    if system is not None:
        return template_to_ass_params(system)
    try:
        return builtin_style_params(subtitle_style)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subtitle style must be basic, bold, or shorts.",
        ) from exc
