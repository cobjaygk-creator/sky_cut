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


class FFmpegAudioError(RuntimeError):
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


def _ken_burns_zoompan(index: int, frames: int) -> str:
    """Build a zoompan expression that pans/zooms for `frames` output frames."""
    denom = max(frames - 1, 1)
    pattern = index % 4
    if pattern == 0:
        # Slow zoom-in, centered
        z, x, y = "min(1+0.0015*on,1.2)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif pattern == 1:
        # Slow zoom-out, centered
        z, x, y = "max(1.2-0.0015*on,1)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif pattern == 2:
        # Pan left -> right with slight zoom
        z, x, y = "1.15", f"(iw-iw/zoom)*on/{denom}", "ih/2-(ih/zoom/2)"
    else:
        # Pan top -> bottom with slight zoom
        z, x, y = "1.15", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*on/{denom}"
    return (
        f"scale=2160:3840:force_original_aspect_ratio=increase,"
        f"crop=2160:3840,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s=1080x1920:fps=30,"
        f"setsar=1"
    )


def create_image_slideshow(
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    image_durations: list[float] | None = None,
) -> None:
    ensure_ffmpeg_available()
    if not image_paths:
        raise FFmpegSlideshowError("No images were provided for the slideshow.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    audio_duration = get_video_duration_seconds(audio_path)
    if image_durations is not None:
        if len(image_durations) != len(image_paths):
            raise FFmpegSlideshowError("image_durations length must match image_paths length.")
        per_image_seconds_list = [max(0.5, duration) for duration in image_durations]
    else:
        per_image_seconds = max(0.5, audio_duration / len(image_paths))
        per_image_seconds_list = [per_image_seconds] * len(image_paths)

    # Still images as looped inputs; Ken Burns zoompan emits a fixed frame count
    # per board so each segment has an explicit duration (no -t on the image inputs).
    command = ["ffmpeg", "-y"]
    for image_path in image_paths:
        command += ["-loop", "1", "-i", str(Path(image_path))]
    command += ["-i", str(Path(audio_path))]

    filter_parts = []
    for index, duration in enumerate(per_image_seconds_list):
        frames = max(15, int(round(duration * 30)))
        filter_parts.append(f"[{index}:v]{_ken_burns_zoompan(index, frames)}[v{index}]")
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


def create_silence_mp3(duration_seconds: float, output_path: str) -> None:
    ensure_ffmpeg_available()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.5, float(duration_seconds))
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=mono:sample_rate=24000",
        "-t",
        f"{duration:.3f}",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg silence generation failed.").strip()
        raise FFmpegAudioError(error[-1000:])


def pad_audio_to_duration(audio_path: str, duration_seconds: float, output_path: str) -> None:
    """Pad the end of an audio file with silence up to `duration_seconds` (no truncation)."""
    ensure_ffmpeg_available()
    source = Path(audio_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    current = get_video_duration_seconds(str(source))
    target = max(0.5, float(duration_seconds))
    if target <= current + 0.05:
        destination.write_bytes(source.read_bytes())
        return
    pad = target - current
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-af",
        f"apad=pad_dur={pad:.3f}",
        "-t",
        f"{target:.3f}",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg audio pad failed.").strip()
        raise FFmpegAudioError(error[-1000:])


def mix_narration_with_bed(
    narration_path: str,
    output_path: str,
    *,
    bgm_path: str | None = None,
    bgm_volume: float = 0.30,
    narration_volume: float = 1.0,
    sfx_events: list[tuple[str, float, float]] | None = None,
    duck_bgm: bool = True,
) -> None:
    """Mix narration with optional looped BGM and timed SFX via amix.

    `sfx_events` items are (path, start_seconds, volume). BGM is looped/trimmed
    to the narration duration. When `duck_bgm` is True and BGM is present, BGM is
    sidechain-compressed from the narration so voice stays clear (soft ducking).
    """
    ensure_ffmpeg_available()
    narration = Path(narration_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if not narration.is_file():
        raise FFmpegAudioError("Narration audio file was not found.")

    duration = get_video_duration_seconds(str(narration))
    bgm_vol = max(0.0, min(1.0, float(bgm_volume)))
    nar_vol = max(0.0, min(2.0, float(narration_volume)))
    events = list(sfx_events or [])

    if bgm_path is None and not events:
        destination.write_bytes(narration.read_bytes())
        return

    aformat = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
    command: list[str] = ["ffmpeg", "-y", "-i", str(narration)]
    filter_parts: list[str] = [f"[0:a]volume={nar_vol:.3f},{aformat}[nar0]"]
    mix_labels: list[str] = []
    input_index = 1

    if bgm_path is not None:
        bgm = Path(bgm_path)
        if not bgm.is_file():
            raise FFmpegAudioError("BGM audio file was not found.")
        command += ["-stream_loop", "-1", "-i", str(bgm)]
        filter_parts.append(
            f"[{input_index}:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
            f"volume={bgm_vol:.3f},{aformat}[bgm_raw]"
        )
        input_index += 1
        if duck_bgm:
            filter_parts.append("[nar0]asplit=2[nar_main][nar_sc]")
            # Voice sidechain: lower BGM while narration is present.
            # Milder ducking so beds stay audible under TTS (was ratio=8 / threshold=0.04).
            filter_parts.append(
                "[bgm_raw][nar_sc]sidechaincompress="
                "threshold=0.08:ratio=3.5:attack=120:release=550:makeup=1.1:knee=3[bgm]"
            )
            mix_labels.extend(["[nar_main]", "[bgm]"])
        else:
            mix_labels.extend(["[nar0]", "[bgm_raw]"])
    else:
        mix_labels.append("[nar0]")

    for event_index, (sfx_path, start_seconds, sfx_volume) in enumerate(events):
        sfx = Path(sfx_path)
        if not sfx.is_file():
            raise FFmpegAudioError(f"SFX audio file was not found: {sfx.name}")
        command += ["-i", str(sfx)]
        delay_ms = max(0, int(round(float(start_seconds) * 1000)))
        vol = max(0.0, min(1.5, float(sfx_volume)))
        label = f"sfx{event_index}"
        filter_parts.append(
            f"[{input_index}:a]volume={vol:.3f},adelay={delay_ms}|{delay_ms},"
            f"{aformat}[{label}]"
        )
        mix_labels.append(f"[{label}]")
        input_index += 1

    inputs_n = len(mix_labels)
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={inputs_n}:duration=first:dropout_transition=0:normalize=0[aout]"
    )
    command += [
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[aout]",
        "-t",
        f"{duration:.3f}",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 10)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg audio mix failed.").strip()
        raise FFmpegAudioError(error[-1000:])


def generate_tone_mp3(
    output_path: str,
    *,
    frequency: float,
    duration: float,
    volume: float = 0.25,
    fade_out: float = 0.2,
) -> None:
    """Generate a simple sine-tone MP3 (used to seed free demo BGM/SFX assets)."""
    ensure_ffmpeg_available()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.05, float(duration))
    fade = max(0.0, min(dur, float(fade_out)))
    af = f"volume={max(0.01, min(1.0, volume)):.3f}"
    if fade > 0:
        af += f",afade=t=out:st={max(0.0, dur - fade):.3f}:d={fade:.3f}"
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency:.2f}:sample_rate=44100:duration={dur:.3f}",
        "-af",
        af,
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg tone generation failed.").strip()
        raise FFmpegAudioError(error[-1000:])


def generate_soft_pad_mp3(
    output_path: str,
    duration: float = 12.0,
    *,
    freq_a: float = 196.0,
    freq_b: float = 294.0,
    volume: float = 0.38,
) -> None:
    """Soft two-tone pad used as a bundled demo BGM loop."""
    ensure_ffmpeg_available()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dur = max(2.0, float(duration))
    vol = max(0.05, min(0.8, float(volume)))
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={freq_a:.2f}:sample_rate=44100:duration={dur:.3f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={freq_b:.2f}:sample_rate=44100:duration={dur:.3f}",
        "-filter_complex",
        (
            "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,"
            f"volume={vol:.3f},afade=t=in:st=0:d=1.0,afade=t=out:st={dur - 1.5:.3f}:d=1.5"
        ),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg pad generation failed.").strip()
        raise FFmpegAudioError(error[-1000:])


def generate_pulse_bed_mp3(
    output_path: str,
    duration: float = 12.0,
    *,
    base_freq: float = 110.0,
    pulse_hz: float = 2.0,
    volume: float = 0.34,
) -> None:
    """Low pulse bed for upbeat / promo Shorts (still license-free synthetic)."""
    ensure_ffmpeg_available()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dur = max(2.0, float(duration))
    vol = max(0.05, min(0.8, float(volume)))
    # Tremolo-style amplitude pulse on a low sine + fifth.
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={base_freq:.2f}:sample_rate=44100:duration={dur:.3f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={base_freq * 1.5:.2f}:sample_rate=44100:duration={dur:.3f}",
        "-filter_complex",
        (
            f"[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,"
            f"tremolo=f={pulse_hz:.2f}:d=0.55,volume={vol:.3f},"
            f"afade=t=in:st=0:d=0.6,afade=t=out:st={dur - 1.2:.3f}:d=1.2"
        ),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = (result.stderr or result.stdout or "FFmpeg pulse bed generation failed.").strip()
        raise FFmpegAudioError(error[-1000:])


def concat_audio_files(audio_paths: list[str], output_path: str) -> None:
    ensure_ffmpeg_available()
    if not audio_paths:
        raise FFmpegAudioError("No audio segments were provided for concatenation.")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if len(audio_paths) == 1:
        destination.write_bytes(Path(audio_paths[0]).read_bytes())
        return

    list_path = destination.with_suffix(".concat.txt")
    lines = []
    for path in audio_paths:
        # ffmpeg concat demuxer requires single quotes escaped as '\''
        escaped = str(Path(path).resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(destination),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60 * 10)
        if result.returncode != 0:
            destination.unlink(missing_ok=True)
            error = (result.stderr or result.stdout or "FFmpeg audio concat failed.").strip()
            raise FFmpegAudioError(error[-1000:])
    finally:
        list_path.unlink(missing_ok=True)


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
