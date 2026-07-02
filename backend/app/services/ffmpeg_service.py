import shutil
import subprocess
from pathlib import Path


class FFmpegNotAvailableError(RuntimeError):
    pass


class FFmpegExtractionError(RuntimeError):
    pass


class FFmpegClipError(RuntimeError):
    pass


class FFmpegSubtitleError(RuntimeError):
    pass


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotAvailableError("FFmpeg is not installed or is not available in PATH.")


def extract_audio_to_wav(video_path: str, output_path: str) -> None:
    ensure_ffmpeg_available()
    source = Path(video_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 30)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg audio extraction failed.").strip()
        raise FFmpegExtractionError(error[-1000:])


def create_vertical_clip(source_path: str, output_path: str, start_time: float, end_time: float) -> None:
    ensure_ffmpeg_available()
    source = Path(source_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    duration = max(0.1, end_time - start_time)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_time:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 30)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg clip generation failed.").strip()
        raise FFmpegClipError(error[-1000:])


def _escape_subtitles_path(path: Path) -> str:
    escaped = path.resolve().as_posix().replace("\\", "/")
    escaped = escaped.replace(":", "\\:").replace("'", "\\'")
    return escaped


def burn_subtitles_into_video(source_path: str, subtitle_path: str, output_path: str) -> None:
    ensure_ffmpeg_available()
    source = Path(source_path)
    subtitle = Path(subtitle_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    filter_value = f"subtitles='{_escape_subtitles_path(subtitle)}'"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        filter_value,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 30)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg subtitle burn-in failed.").strip()
        raise FFmpegSubtitleError(error[-1000:])
