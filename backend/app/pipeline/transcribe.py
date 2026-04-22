import os
import subprocess
import tempfile
from pathlib import Path

import whisper


CHUNK_DURATION_SECONDS = 15 * 60


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


def split_media_into_chunks(file_path: str, chunk_seconds: int = CHUNK_DURATION_SECONDS) -> list[tuple[str, float]]:
    source = Path(file_path)
    chunk_dir = Path(tempfile.mkdtemp(prefix=f"{source.stem}_chunks_"))
    output_pattern = chunk_dir / f"{source.stem}_chunk_%03d{source.suffix}"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-c",
        "copy",
        "-map",
        "0",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        str(output_pattern),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    chunk_files = sorted(chunk_dir.glob(f"{source.stem}_chunk_*{source.suffix}"))
    return [
        (str(chunk_file), index * chunk_seconds)
        for index, chunk_file in enumerate(chunk_files)
    ]


def transcribe_audio(file_path: str, model_size: str = "base"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    model = whisper.load_model(model_size)
    duration_seconds = get_media_duration(file_path)

    if duration_seconds <= CHUNK_DURATION_SECONDS:
        result = model.transcribe(file_path)
        return [
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "text": (segment.get("text") or "").strip(),
            }
            for segment in result.get("segments", [])
        ]

    segments = []
    chunk_paths: list[str] = []

    try:
        for chunk_path, chunk_offset in split_media_into_chunks(file_path):
            chunk_paths.append(chunk_path)
            result = model.transcribe(chunk_path)

            for segment in result.get("segments", []):
                segments.append(
                    {
                        "start": float(segment["start"]) + chunk_offset,
                        "end": float(segment["end"]) + chunk_offset,
                        "text": (segment.get("text") or "").strip(),
                    }
                )
    finally:
        for chunk_path in chunk_paths:
            try:
                os.remove(chunk_path)
            except FileNotFoundError:
                pass

        if chunk_paths:
            chunk_dir = Path(chunk_paths[0]).parent
            try:
                chunk_dir.rmdir()
            except OSError:
                pass

    return segments

