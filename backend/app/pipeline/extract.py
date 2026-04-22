import json
import re

import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"
SUMMARY_WINDOW_SECONDS = 10 * 60


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


def chunk_transcript_segments(transcript_segments: list[dict], window_seconds: int = SUMMARY_WINDOW_SECONDS) -> list[list[dict]]:
    if not transcript_segments:
        return []

    chunks = []
    current_chunk = []
    current_window_start = transcript_segments[0]["start"]
    current_window_end = current_window_start + window_seconds

    for segment in transcript_segments:
        if current_chunk and segment["start"] >= current_window_end:
            chunks.append(current_chunk)
            current_chunk = []
            current_window_start = segment["start"]
            current_window_end = current_window_start + window_seconds

        current_chunk.append(segment)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def call_ollama(prompt: str) -> tuple[dict, str]:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=180,
    )
    response.raise_for_status()

    data = response.json()
    raw_output = data.get("response", "")
    return extract_json_from_text(raw_output), raw_output


def build_window_prompt(transcript_text: str, window_start: float, window_end: float) -> str:
    return f"""
You are a meeting assistant.

Analyze this transcript window and return a detailed explanation of the important discussion in this time range.

Return ONLY valid JSON. Do not include markdown. Do not include explanation outside the JSON.

Use this exact JSON shape:
{{
  "summary": "2-4 detailed paragraphs or 4-8 detailed bullet-style sentences explaining what happened, what mattered, and any important context in this window.",
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
- The summary must be explanatory and specific, not short or vague.
- Focus on the important parts of this time window.
- Include decisions only if the transcript clearly contains them.
- Include action items only if someone is expected to do something.
- Use null when owner, due date, timestamp, or priority is unknown.
- evidence_quote must come directly from the transcript.
- Do not invent details.

Time window:
{format_timestamp(window_start)} - {format_timestamp(window_end)}

Transcript:
{transcript_text}
""".strip()


def merge_window_summaries(window_results: list[dict]) -> str:
    lines = []

    for window in window_results:
        lines.append(
            f"{window['label']}\n{window['summary']}".strip()
        )

    return "\n\n".join(lines)


def extract_meeting_insights(transcript_segments: list[dict]) -> dict:
    window_chunks = chunk_transcript_segments(transcript_segments)

    if not window_chunks:
        return {
            "summary": "",
            "decisions": [],
            "action_items": [],
            "raw_model_output": "",
        }

    merged_decisions = []
    merged_action_items = []
    raw_outputs = []
    window_results = []

    for chunk in window_chunks:
        transcript_text = build_transcript_text(chunk)
        window_start = chunk[0]["start"]
        window_end = chunk[-1]["end"]
        prompt = build_window_prompt(transcript_text, window_start, window_end)
        parsed, raw_output = call_ollama(prompt)

        window_results.append(
            {
                "label": f"{format_timestamp(window_start)} - {format_timestamp(window_end)}",
                "summary": parsed.get("summary", "").strip(),
            }
        )
        merged_decisions.extend(parsed.get("decisions", []))
        merged_action_items.extend(parsed.get("action_items", []))
        raw_outputs.append(raw_output)

    return {
        "summary": merge_window_summaries(window_results),
        "decisions": merged_decisions,
        "action_items": merged_action_items,
        "raw_model_output": "\n\n=== WINDOW OUTPUT ===\n\n".join(raw_outputs),
    }

