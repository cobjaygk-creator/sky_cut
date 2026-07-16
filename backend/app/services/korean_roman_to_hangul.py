"""Best-effort Revised Romanization → Hangul for Korean given-name style tokens."""

from __future__ import annotations

import re

_CHOSUNG = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
_JUNGSUNG = [
    "ㅏ",
    "ㅐ",
    "ㅑ",
    "ㅒ",
    "ㅓ",
    "ㅔ",
    "ㅕ",
    "ㅖ",
    "ㅗ",
    "ㅘ",
    "ㅙ",
    "ㅚ",
    "ㅛ",
    "ㅜ",
    "ㅝ",
    "ㅞ",
    "ㅟ",
    "ㅠ",
    "ㅡ",
    "ㅢ",
    "ㅣ",
]
_JONGSUNG = [
    "",
    "ㄱ",
    "ㄲ",
    "ㄳ",
    "ㄴ",
    "ㄵ",
    "ㄶ",
    "ㄷ",
    "ㄹ",
    "ㄺ",
    "ㄻ",
    "ㄼ",
    "ㄽ",
    "ㄾ",
    "ㄿ",
    "ㅀ",
    "ㅁ",
    "ㅂ",
    "ㅄ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]

_VOWELS: list[tuple[str, str]] = [
    ("yae", "ㅒ"),
    ("yeo", "ㅕ"),
    ("wae", "ㅙ"),
    ("woo", "ㅜ"),  # before "wo" so Hyunwoo → 현우 (not 현워오)
    ("ya", "ㅑ"),
    ("ye", "ㅖ"),
    ("yo", "ㅛ"),
    ("yu", "ㅠ"),
    ("wa", "ㅘ"),
    ("wo", "ㅝ"),
    ("we", "ㅞ"),
    ("wi", "ㅟ"),
    ("ui", "ㅢ"),
    ("oe", "ㅚ"),
    ("ae", "ㅐ"),
    ("eo", "ㅓ"),
    ("eu", "ㅡ"),
    ("oo", "ㅜ"),
    ("ee", "ㅣ"),
    ("e", "ㅔ"),
    ("a", "ㅏ"),
    ("o", "ㅗ"),
    ("u", "ㅜ"),
    ("i", "ㅣ"),
]

_INITIALS: list[tuple[str, str]] = [
    ("kk", "ㄲ"),
    ("tt", "ㄸ"),
    ("pp", "ㅃ"),
    ("ss", "ㅆ"),
    ("jj", "ㅉ"),
    ("ch", "ㅊ"),
    ("bb", "ㅃ"),
    ("dd", "ㄸ"),
    ("gg", "ㄲ"),
    ("sh", "ㅅ"),
    ("g", "ㄱ"),
    ("n", "ㄴ"),
    ("d", "ㄷ"),
    ("r", "ㄹ"),
    ("l", "ㄹ"),
    ("m", "ㅁ"),
    ("b", "ㅂ"),
    ("s", "ㅅ"),
    ("j", "ㅈ"),
    ("k", "ㅋ"),
    ("t", "ㅌ"),
    ("p", "ㅍ"),
    ("h", "ㅎ"),
]

_FINALS: list[tuple[str, str]] = [
    ("ng", "ㅇ"),
    ("kk", "ㄲ"),
    ("ss", "ㅆ"),
    ("ch", "ㅊ"),
    ("gs", "ㄳ"),
    ("nj", "ㄵ"),
    ("nh", "ㄶ"),
    ("lg", "ㄺ"),
    ("lm", "ㄻ"),
    ("lb", "ㄼ"),
    ("ls", "ㄽ"),
    ("lt", "ㄾ"),
    ("lp", "ㄿ"),
    ("lh", "ㅀ"),
    ("bs", "ㅄ"),
    ("g", "ㄱ"),
    ("k", "ㄱ"),
    ("n", "ㄴ"),
    ("d", "ㄷ"),
    ("t", "ㄷ"),
    ("l", "ㄹ"),
    ("r", "ㄹ"),
    ("m", "ㅁ"),
    ("b", "ㅂ"),
    ("p", "ㅂ"),
    ("s", "ㅅ"),
    ("j", "ㅈ"),
    ("h", "ㅎ"),
]

_NAME_OVERRIDES: dict[str, str] = {
    "sanghyun": "상현",
    "seohyeon": "서현",
    "juwan": "주완",
    "woony": "우니",
    "eogwool": "억울",
    "okji": "옥지",
    "bboddo": "뽀또",
    "silas": "실라스",
    "minji": "민지",
    "jisoo": "지수",
    "hyunwoo": "현우",
    "yeonwoo": "연우",
}


def _compose(cho: str, jung: str, jong: str = "") -> str:
    return chr(0xAC00 + _CHOSUNG.index(cho) * 588 + _JUNGSUNG.index(jung) * 28 + _JONGSUNG.index(jong))


def _match(text: str, index: int, table: list[tuple[str, str]]) -> tuple[str, str] | None:
    for token, jamo in table:
        if text.startswith(token, index):
            return token, jamo
    return None


def _starts_syllable(text: str, index: int) -> bool:
    if index >= len(text):
        return False
    if text.startswith(("hyun", "hyung"), index):
        return True
    if _match(text, index, _VOWELS):
        return True
    initial = _match(text, index, _INITIALS)
    if not initial:
        return False
    nxt = index + len(initial[0])
    return bool(_match(text, nxt, _VOWELS) or text.startswith(("yun", "yung"), nxt))


def _parse_all(text: str) -> str | None:
    index = 0
    out: list[str] = []
    while index < len(text):
        # Common name spelling: Hyun / Hyung → 현 / 형
        if text.startswith("hyung", index):
            out.append(_compose("ㅎ", "ㅕ", "ㅇ"))
            index += 5
            continue
        if text.startswith("hyun", index):
            out.append(_compose("ㅎ", "ㅕ", "ㄴ"))
            index += 4
            continue

        pos = index
        cho = "ㅇ"
        initial = _match(text, pos, _INITIALS)
        if initial:
            nxt = pos + len(initial[0])
            if _match(text, nxt, _VOWELS) or text.startswith(("yun", "yung"), nxt):
                cho = initial[1]
                pos = nxt

        if cho != "ㅇ" and text.startswith("yung", pos):
            out.append(_compose(cho, "ㅕ", "ㅇ"))
            index = pos + 4
            continue
        if cho != "ㅇ" and text.startswith("yun", pos):
            out.append(_compose(cho, "ㅕ", "ㄴ"))
            index = pos + 3
            continue

        vowel = _match(text, pos, _VOWELS)
        if not vowel:
            return None
        pos += len(vowel[0])
        jung = vowel[1]

        jong = ""
        # If the next consonant can start a new syllable, keep it as onset
        # (jisoo → 지수, not 짓우). Otherwise take a coda when the remainder
        # still parses (sanghyun → 상 + 현, minji → 민 + 지).
        if not _starts_syllable(text, pos):
            final = _match(text, pos, _FINALS)
            if final:
                after = pos + len(final[0])
                if after == len(text) or _starts_syllable(text, after):
                    # Prefer short coda when a longer digraph would leave only a bare vowel
                    # (minji: prefer n+지 over nj+이).
                    short = None
                    for token, jamo in _FINALS:
                        if len(token) == 1 and text.startswith(token, pos):
                            short_after = pos + 1
                            if short_after < len(text) and _starts_syllable(text, short_after):
                                short = (token, jamo, short_after)
                                break
                    if short and len(final[0]) > 1 and _match(text, after, _VOWELS):
                        jong = short[1]
                        pos = short[2]
                    else:
                        jong = final[1]
                        pos = after

        out.append(_compose(cho, jung, jong))
        if pos <= index:
            return None
        index = pos
        if len(out) > 8:
            return None
    return "".join(out)


def romanized_korean_to_hangul(name: str) -> str | None:
    raw = (name or "").strip()
    if not raw:
        return None
    key = re.sub(r"[^A-Za-z]", "", raw).lower()
    if len(key) < 2:
        return None
    if key in _NAME_OVERRIDES:
        return _NAME_OVERRIDES[key]

    hangul = _parse_all(key)
    if not hangul or not re.fullmatch(r"[가-힣]+", hangul):
        return None
    if not (1 <= len(hangul) <= 5):
        return None
    return hangul


def display_voice_name_ko(roman_name: str) -> str:
    return romanized_korean_to_hangul(roman_name) or roman_name.strip()
