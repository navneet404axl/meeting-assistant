import os
from typing import Iterable


def overlap_duration(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def assign_speakers_to_transcript(transcript_segments: Iterable, speaker_segments: list[dict]) -> None:
    for transcript_segment in transcript_segments:
        best_speaker = None
        best_overlap = 0.0

        for speaker_segment in speaker_segments:
            overlap = overlap_duration(
                transcript_segment.start,
                transcript_segment.end,
                speaker_segment["start"],
                speaker_segment["end"],
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker_segment["speaker_label"]

        transcript_segment.speaker = best_speaker


def diarize_audio(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        from huggingface_hub import login
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "pyannote.audio is not installed. Install it in the backend environment before running diarization."
        ) from exc

    token = os.getenv("PYANNOTE_AUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "PYANNOTE_AUTH_TOKEN is not set. Create a Hugging Face token for pyannote and export it before running diarization."
        )

    login(token=token, add_to_git_credential=False, skip_if_logged_in=True)
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")

    diarization = pipeline(file_path)
    segments = []

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(
            {
                "speaker_label": speaker,
                "start": float(turn.start),
                "end": float(turn.end),
            }
        )

    return segments
