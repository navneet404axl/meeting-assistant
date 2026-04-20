import json
import re
import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def build_transcript_text(segments: list[dict]) -> str:
    lines = []

    for segment in segments:
        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        text = segment["text"].strip()
        lines.append(f"[{start}-{end}] {text}")

    return "\n".join(lines)


def extract_json_from_text(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")

    return json.loads(match.group(0))


def extract_meeting_insights(transcript_segments: list[dict]) -> dict:
    transcript_text = build_transcript_text(transcript_segments)

    prompt = f"""
You are a meeting assistant.

Extract a short summary, decisions, and action items from the transcript.

Return ONLY valid JSON. Do not include markdown. Do not include explanation.

Use this exact JSON shape:
{{
  "summary": "string",
  "decisions": [
    {{
      "text": "string",
      "timestamp": "MM:SS or null"
    }}
  ],
  "action_items": [
    {{
      "task": "string",
      "owner": "string or null",
      "due_date_iso": "YYYY-MM-DD or null",
      "evidence_quote": "string",
      "timestamp": "MM:SS or null",
      "priority": "low | medium | high | null"
    }}
  ]
}}

Rules:
- If there are no decisions, return an empty decisions array.
- If there are no action items, return an empty action_items array.
- Use null when owner, due date, timestamp, or priority is unknown.
- evidence_quote should be copied from the transcript.
- Do not invent details.

Transcript:
{transcript_text}
""".strip()

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()
    raw_output = data.get("response", "")

    parsed = extract_json_from_text(raw_output)

    return {
        "summary": parsed.get("summary", ""),
        "decisions": parsed.get("decisions", []),
        "action_items": parsed.get("action_items", []),
        "raw_model_output": raw_output,
    }
