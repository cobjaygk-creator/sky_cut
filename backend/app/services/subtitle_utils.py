"""Shared ASS subtitle building helpers.

These were originally part of clip_service.py (used for burning transcript-timed
captions onto highlight clips) and are reused as-is by blog_service.py to burn
narration-script-timed captions onto blog image slideshows. Keeping them here
avoids duplicating the exact font/style/wrapping conventions in two places.
"""

from __future__ import annotations

import math
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path


def clean_subtitle_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_long_word(word: str, size: int) -> list[str]:
    return [word[index : index + size] for index in range(0, len(word), size)]


def wrap_subtitle_text(text: str, max_chars: int) -> str:
    text = clean_subtitle_text(text)
    if not text:
        return ""

    words: list[str] = []
    for word in text.split(" "):
        if len(word) > max_chars:
            words.extend(_chunk_long_word(word, max_chars))
        else:
            words.append(word)

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == 2:
            break
    if current and len(lines) < 2:
        lines.append(current)

    return r"\N".join(lines[:2])


def split_text_for_duration(text: str, duration: float, max_chars: int) -> list[str]:
    text = clean_subtitle_text(text)
    if not text:
        return []
    chunk_size = max_chars * 2
    chunk_count = max(1, min(4, math.ceil(len(text) / chunk_size)))
    if chunk_count == 1:
        return [wrap_subtitle_text(text, max_chars)]
    raw_chunks = textwrap.wrap(text, width=chunk_size, break_long_words=True, break_on_hyphens=False)
    return [wrap_subtitle_text(chunk, max_chars) for chunk in raw_chunks[:chunk_count] if chunk.strip()]


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    centiseconds = int(round(seconds * 100))
    hours = centiseconds // 360000
    centiseconds %= 360000
    minutes = centiseconds // 6000
    centiseconds %= 6000
    whole_seconds = centiseconds // 100
    centiseconds %= 100
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


@dataclass(frozen=True)
class AssStyleParams:
    font_name: str = "Malgun Gothic"
    font_size: int = 58
    primary_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    back_color: str = "#000000"
    primary_alpha: int = 0  # 00 opaque .. FF transparent (ASS)
    outline_alpha: int = 0
    back_alpha: int = 0xCC
    bold: bool = False
    outline: float = 3.0
    shadow: float = 1.0
    alignment: int = 2
    margin_l: int = 80
    margin_r: int = 80
    margin_v: int = 150
    border_style: int = 1  # 1=outline+shadow, 3=opaque box


_HEX_RE = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def normalize_hex_color(value: str, *, field_name: str = "color") -> str:
    cleaned = (value or "").strip()
    if not _HEX_RE.match(cleaned):
        raise ValueError(f"{field_name} must be #RRGGBB or #AARRGGBB")
    if len(cleaned) == 7:
        return cleaned.upper()
    # #AARRGGBB → keep as-is but normalize case; alpha is separate in ASS params for API simplicity
    return f"#{cleaned[3:].upper()}"


def hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR."""
    cleaned = normalize_hex_color(hex_color)
    red = cleaned[1:3]
    green = cleaned[3:5]
    blue = cleaned[5:7]
    alpha_hex = f"{max(0, min(255, int(alpha))):02X}"
    return f"&H{alpha_hex}{blue}{green}{red}"


def builtin_style_params(style: str) -> AssStyleParams:
    presets = {
        "basic": AssStyleParams(
            font_size=58,
            primary_color="#FFFFFF",
            outline_color="#000000",
            back_color="#000000",
            outline_alpha=0xAA,
            back_alpha=0xCC,
            bold=False,
            outline=3,
            shadow=1,
            margin_l=80,
            margin_r=80,
            margin_v=150,
            border_style=1,
        ),
        "bold": AssStyleParams(
            font_size=66,
            primary_color="#FFFFFF",
            outline_color="#000000",
            back_color="#000000",
            outline_alpha=0x99,
            back_alpha=0xDD,
            bold=True,
            outline=4,
            shadow=1,
            margin_l=70,
            margin_r=70,
            margin_v=155,
            border_style=1,
        ),
        "shorts": AssStyleParams(
            font_size=72,
            primary_color="#FFFF00",
            outline_color="#000000",
            back_color="#000000",
            outline_alpha=0,
            back_alpha=0xCC,
            bold=True,
            outline=5,
            shadow=2,
            margin_l=58,
            margin_r=58,
            margin_v=210,
            border_style=1,
        ),
    }
    if style not in presets:
        raise KeyError(style)
    return presets[style]


def ass_style_line(params: AssStyleParams) -> str:
    bold_flag = -1 if params.bold else 0
    primary = hex_to_ass_color(params.primary_color, params.primary_alpha)
    secondary = "&H000000FF"
    outline = hex_to_ass_color(params.outline_color, params.outline_alpha)
    back = hex_to_ass_color(params.back_color, params.back_alpha)
    font = (params.font_name or "Malgun Gothic").replace(",", " ")
    return (
        f"Style: Default,{font},{int(params.font_size)},"
        f"{primary},{secondary},{outline},{back},"
        f"{bold_flag},0,0,0,100,100,0,0,"
        f"{int(params.border_style)},{params.outline:g},{params.shadow:g},"
        f"{int(params.alignment)},{int(params.margin_l)},{int(params.margin_r)},"
        f"{int(params.margin_v)},1"
    )


def ass_style(style: str) -> str:
    """Legacy helper: builtin style key → ASS Style line."""
    return ass_style_line(builtin_style_params(style))


def ass_header_from_params(params: AssStyleParams) -> str:
    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            ass_style_line(params),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def ass_header(style: str) -> str:
    return ass_header_from_params(builtin_style_params(style))


def write_ass_file(
    path: Path,
    style: str | AssStyleParams,
    events: list[tuple[float, float, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    params = style if isinstance(style, AssStyleParams) else builtin_style_params(style)
    lines = [ass_header_from_params(params)]
    for start, end, text in events:
        safe_text = text.replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{safe_text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
