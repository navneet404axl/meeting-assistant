import os
import subprocess
import tempfile
from pathlib import Path


from faster_whisper import WhisperModel


CHUNK_DURATION_SECONDS = 15 * 60
ALLOWED_WHISPER_MODELS = {"small.en", "medium.en", "large-v3-turbo"}
DEFAULT_WHISPER_MODEL = "small.en"
TEMP_AUDIO_SUFFIX = ".wav"


def get_media_duration(file_path: str) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return float(result.stdout.strip())


def extract_audio_chunk(
    file_path: str,
    chunk_dir: Path,
    start_seconds: float,
    duration_seconds: float,
    chunk_index: int,
) -> str:
    source = Path(file_path)
    output_path = chunk_dir / f"{source.stem}_audio_{chunk_index:03d}{TEMP_AUDIO_SUFFIX}"

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_seconds),
        "-t",
        str(duration_seconds),
        "-i",
        file_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return str(output_path)


def build_audio_chunks(file_path: str, duration_seconds: float) -> tuple[Path, list[tuple[str, float]]]:
    source = Path(file_path)
    chunk_dir = Path(tempfile.mkdtemp(prefix=f"{source.stem}_audio_chunks_"))
    chunks = []
    chunk_index = 0
    start_seconds = 0.0

    try:
        while start_seconds < duration_seconds:
            chunk_duration = min(CHUNK_DURATION_SECONDS, duration_seconds - start_seconds)
            chunk_path = extract_audio_chunk(
                file_path=file_path,
                chunk_dir=chunk_dir,
                start_seconds=start_seconds,
                duration_seconds=chunk_duration,
                chunk_index=chunk_index,
            )
            chunks.append((chunk_path, start_seconds))
            chunk_index += 1
            start_seconds += CHUNK_DURATION_SECONDS
    except Exception:
        cleanup_audio_chunks(chunk_dir)
        raise

    return chunk_dir, chunks


def cleanup_audio_chunks(chunk_dir: Path) -> None:
    for chunk_path in chunk_dir.glob(f"*{TEMP_AUDIO_SUFFIX}"):
        try:
            chunk_path.unlink()
        except FileNotFoundError:
            pass

    try:
        chunk_dir.rmdir()
    except OSError:
        pass


def validate_model_size(model_size: str) -> str:
    clean_model_size = model_size.strip()
    if clean_model_size not in ALLOWED_WHISPER_MODELS:
        allowed = ", ".join(sorted(ALLOWED_WHISPER_MODELS))
        raise ValueError(f"Unsupported Whisper model: {model_size}. Allowed models: {allowed}")

    return clean_model_size


def transcribe_file(model: WhisperModel, file_path: str, offset: float = 0.0) -> list[dict]:
    segments, _ = model.transcribe(
        file_path,
        language="en",
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return [
        {
            "start": float(segment.start) + offset,
            "end": float(segment.end) + offset,
            "text": (segment.text or "").strip(),
        }
        for segment in segments
    ]


def transcribe_audio(file_path: str, model_size: str = DEFAULT_WHISPER_MODEL):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    model_size = validate_model_size(model_size)
    model = WhisperModel(model_size, device="auto", compute_type="auto")
    duration_seconds = get_media_duration(file_path)
    chunk_dir, audio_chunks = build_audio_chunks(file_path, duration_seconds)

    try:
        segments = []
        for chunk_path, chunk_offset in audio_chunks:
            segments.extend(transcribe_file(model, chunk_path, chunk_offset))
        return segments
    finally:
        cleanup_audio_chunks(chunk_dir)
