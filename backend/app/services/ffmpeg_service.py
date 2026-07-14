import shutil
import subprocess
from pathlib import Path


class FFmpegNotAvailableError(RuntimeError):
    pass


class FFprobeNotAvailableError(RuntimeError):
    pass


class FFmpegExtractionError(RuntimeError):
    pass


class FFmpegProbeError(RuntimeError):
    pass


class FFmpegClipError(RuntimeError):
    pass


class FFmpegSubtitleError(RuntimeError):
    pass


class FFmpegNarrationError(RuntimeError):
    pass


class FFmpegSlideshowError(RuntimeError):
    pass


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotAvailableError("FFmpeg is not installed or is not available in PATH.")


def ensure_ffprobe_available() -> None:
    if shutil.which("ffprobe") is None:
        raise FFprobeNotAvailableError("FFprobe is not installed or is not available in PATH. It is usually installed with FFmpeg.")


def get_video_duration_seconds(video_path: str) -> float:
    ensure_ffprobe_available()
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(Path(video_path)),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "FFprobe duration check failed.").strip()
        raise FFmpegProbeError(error[-1000:])
    try:
        duration = float((result.stdout or "").strip())
    except ValueError as exc:
        raise FFmpegProbeError("Could not read video duration from FFprobe output.") from exc
    if duration <= 0:
        raise FFmpegProbeError("Video duration is invalid or empty.")
    return duration


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


def create_image_slideshow(image_paths: list[str], audio_path: str, output_path: str) -> None:
    ensure_ffmpeg_available()
    if not image_paths:
        raise FFmpegSlideshowError("No images were provided for the slideshow.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    audio_duration = get_video_duration_seconds(audio_path)
    per_image_seconds = max(0.5, audio_duration / len(image_paths))

    command = ["ffmpeg", "-y"]
    for image_path in image_paths:
        command += ["-loop", "1", "-t", f"{per_image_seconds:.3f}", "-i", str(Path(image_path))]
    command += ["-i", str(Path(audio_path))]

    filter_parts = []
    for index in range(len(image_paths)):
        filter_parts.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps=30[v{index}]"
        )
    concat_inputs = "".join(f"[v{index}]" for index in range(len(image_paths)))
    filter_parts.append(f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[vout]")
    filter_complex = ";".join(filter_parts)

    command += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        f"{len(image_paths)}:a:0",
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
        "-shortest",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 30)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg slideshow generation failed.").strip()
        raise FFmpegSlideshowError(error[-1000:])


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


def replace_video_audio_with_narration(source_path: str, narration_path: str, output_path: str) -> None:
    ensure_ffmpeg_available()
    source = Path(source_path)
    narration = Path(narration_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-i",
        str(narration),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 30)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg narration merge failed.").strip()
        raise FFmpegNarrationError(error[-1000:])
