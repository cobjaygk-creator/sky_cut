"""Shared ASS subtitle building helpers.

These were originally part of clip_service.py (used for burning transcript-timed
captions onto highlight clips) and are reused as-is by blog_service.py to burn
narration-script-timed captions onto blog image slideshows. Keeping them here
avoids duplicating the exact font/style/wrapping conventions in two places.
"""

import math
import re
import textwrap
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


def ass_style(style: str) -> str:
    styles = {
        "basic": "Style: Default,Malgun Gothic,58,&H00FFFFFF,&H000000FF,&HAA000000,&HCC000000,0,0,0,0,100,100,0,0,1,3,1,2,80,80,150,1",
        "bold": "Style: Default,Malgun Gothic,66,&H00FFFFFF,&H000000FF,&H99000000,&HDD000000,-1,0,0,0,100,100,0,0,1,4,1,2,70,70,155,1",
        "shorts": "Style: Default,Malgun Gothic,72,&H0000FFFF,&H000000FF,&H00000000,&HCC000000,-1,0,0,0,100,100,0,0,1,5,2,2,58,58,210,1",
    }
    return styles[style]


def ass_header(style: str) -> str:
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
            ass_style(style),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def write_ass_file(path: Path, style: str, events: list[tuple[float, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [ass_header(style)]
    for start, end, text in events:
        safe_text = text.replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{safe_text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
