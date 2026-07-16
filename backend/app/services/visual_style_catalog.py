"""System visual style presets for Remotion BlogShorts (not ASS subtitle templates)."""

from __future__ import annotations

from typing import Any

DEFAULT_VISUAL_STYLE = "fullscreen"

VISUAL_STYLES: dict[str, dict[str, Any]] = {
    "fullscreen": {
        "slug": "fullscreen",
        "label": "풀스크린",
        "description": "풀스크린 배경과 임팩트 자막.",
        "badge": "추천",
        "previewImage": "/style-previews/fullscreen.svg",
        "layout": "fullscreen",
        "caption": "bottom_box",
        "header": "overlay",
        "accent": "#FFE566",
        "transitionSec": 0.35,
        "kenBurns": True,
    },
    "card_news": {
        "slug": "card_news",
        "label": "카드형",
        "description": "흰 배경 상단 타이틀 + 액자 영상.",
        "badge": "NEW",
        "previewImage": "/style-previews/card_news.svg",
        "layout": "card",
        "caption": "card_bottom",
        "header": "card_white",
        "accent": "#1f6b4a",
        "transitionSec": 0.35,
        "kenBurns": True,
    },
    "info_dark": {
        "slug": "info_dark",
        "label": "정보형 다크",
        "description": "진한 상단 타이틀 바와 정보형 자막.",
        "badge": None,
        "previewImage": "/style-previews/info_dark.svg",
        "layout": "fullscreen",
        "caption": "dark_bar",
        "header": "info_navy",
        "accent": "#7CFFB2",
        "transitionSec": 0.35,
        "kenBurns": True,
    },
    "bold_hook": {
        "slug": "bold_hook",
        "label": "볼드 훅",
        "description": "상단 훅 타이틀과 큰 중앙 강조 자막.",
        "badge": None,
        "previewImage": "/style-previews/bold_hook.svg",
        "layout": "fullscreen",
        "caption": "bold_center",
        "header": "viral_black",
        "accent": "#5EF2D0",
        "transitionSec": 0.25,
        "kenBurns": True,
    },
}

ALLOWED_VISUAL_STYLES = set(VISUAL_STYLES.keys())


def list_visual_styles() -> list[dict[str, Any]]:
    return [dict(item) for item in VISUAL_STYLES.values()]


def normalize_visual_style(slug: str | None) -> str:
    if slug and slug in ALLOWED_VISUAL_STYLES:
        return slug
    return DEFAULT_VISUAL_STYLE


def resolve_visual_style(slug: str | None) -> dict[str, Any]:
    return dict(VISUAL_STYLES[normalize_visual_style(slug)])


def remotion_style_payload(slug: str | None) -> dict[str, Any]:
    style = resolve_visual_style(slug)
    return {
        "layout": style["layout"],
        "caption": style["caption"],
        "header": style["header"],
        "accent": style["accent"],
        "transitionSec": style["transitionSec"],
        "kenBurns": style["kenBurns"],
    }
