import os
import whisper

def transcribe_audio(file_path: str, model_size: str = "base"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    model = whisper.load_model(model_size)
    result = model.transcribe(file_path)

    # result["segments"] is a list of dicts with start/end/text
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": (seg.get("text") or "").strip(),
        })

    return segments