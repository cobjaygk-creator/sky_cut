import shutil
import subprocess
from pathlib import Path


class FFmpegNotAvailableError(RuntimeError):
    pass


class FFmpegExtractionError(RuntimeError):
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
