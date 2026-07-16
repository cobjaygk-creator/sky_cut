"""System visual style presets for Remotion BlogShorts (not ASS subtitle templates)."""

from __future__ import annotations

from typing import Any

DEFAULT_VISUAL_STYLE = "fullscreen"

VISUAL_STYLES: dict[str, dict[str, Any]] = {
    "fullscreen": {
        "slug": "fullscreen",
        "label": "풀스크린",
        "description": "이미지가 화면을 채우고 하단 박스 자막이 올라갑니다.",
        "badge": "추천",
        "previewImage": "/style-previews/fullscreen.svg",
        "layout": "fullscreen",
        "caption": "bottom_box",
        "transitionSec": 0.35,
        "kenBurns": True,
    },
    "card_news": {
        "slug": "card_news",
        "label": "카드뉴스",
        "description": "이미지 위 카드형 텍스트 패널로 정보를 또렷하게 보여줍니다.",
        "badge": "NEW",
        "previewImage": "/style-previews/card_news.svg",
        "layout": "card",
        "caption": "card_title",
        "transitionSec": 0.35,
        "kenBurns": True,
    },
    "info_dark": {
        "slug": "info_dark",
        "label": "정보형 다크",
        "description": "차분한 다크 바 자막으로 설명형 쇼츠에 맞습니다.",
        "badge": None,
        "previewImage": "/style-previews/info_dark.svg",
        "layout": "fullscreen",
        "caption": "dark_bar",
        "transitionSec": 0.35,
        "kenBurns": True,
    },
    "bold_hook": {
        "slug": "bold_hook",
        "label": "볼드 훅",
        "description": "큰 중앙 강조 자막으로 앞부분을 강하게 잡습니다.",
        "badge": None,
        "previewImage": "/style-previews/bold_hook.svg",
        "layout": "fullscreen",
        "caption": "bold_center",
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
        "transitionSec": style["transitionSec"],
        "kenBurns": style["kenBurns"],
    }
