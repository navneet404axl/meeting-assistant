import os
import uuid
import json
from typing import Any, cast
from app.pipeline.extract import extract_meeting_insights

from app.models.meeting import Meeting
from app.models.speaker_mapping import SpeakerMapping
from app.models.speaker_segment import SpeakerSegment
from app.models.transcript import TranscriptSegment

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.pipeline.diarize import assign_speakers_to_transcript, diarize_audio
from app.pipeline.transcribe import (
    ALLOWED_WHISPER_MODELS,
    DEFAULT_WHISPER_MODEL,
    transcribe_audio,
)
from app.db.database import Base, engine, get_db


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Meeting Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


def ensure_runtime_schema() -> None:
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(transcript_segments)"))
        }
        if "speaker" not in columns:
            connection.execute(
                text("ALTER TABLE transcript_segments ADD COLUMN speaker VARCHAR")
            )


ensure_runtime_schema()


class SpeakerMappingPayload(BaseModel):
    mapping: dict[str, str]


def get_speaker_display_map(db: Session, meeting_id: int) -> dict[str, str]:
    mappings = (
        db.query(SpeakerMapping)
        .filter(SpeakerMapping.meeting_id == meeting_id)
        .all()
    )
    return {
        cast(str, mapping.speaker_label): cast(str, mapping.display_name)
        for mapping in mappings
    }


def serialize_speaker_segment(segment: SpeakerSegment, display_map: dict[str, str]) -> dict[str, Any]:
    speaker_label = cast(str, segment.speaker_label)
    return {
        "speaker_label": speaker_label,
        "display_name": display_map.get(speaker_label, speaker_label),
        "start": cast(float, segment.start),
        "end": cast(float, segment.end),
    }


def serialize_transcript_segment(segment: TranscriptSegment, display_map: dict[str, str]) -> dict[str, Any]:
    speaker_label = cast(str | None, segment.speaker)
    return {
        "start": cast(float, segment.start),
        "end": cast(float, segment.end),
        "text": cast(str, segment.text),
        "speaker_label": speaker_label,
        "speaker_name": display_map.get(speaker_label, speaker_label) if speaker_label else None,
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/meetings")
async def create_meeting(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".mp3", ".wav", ".m4a", ".mp4", ".webm"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    meeting = Meeting(title=title, filename=safe_name, status="queued")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {"meeting_id": meeting.id, "status": meeting.status}


@app.get("/api/meetings")
def list_meetings(db: Session = Depends(get_db)):
    meetings = (
        db.query(Meeting)
        .order_by(Meeting.created_at.desc(), Meeting.id.desc())
        .all()
    )

    return {
        "meetings": [
            {
                "meeting_id": meeting.id,
                "title": meeting.title,
                "filename": meeting.filename,
                "status": meeting.status,
                "created_at": str(meeting.created_at),
            }
            for meeting in meetings
        ]
    }


@app.get("/api/meetings/{meeting_id}/status")
def get_status(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"meeting_id": meeting.id, "status": meeting.status}


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "filename": meeting.filename,
        "status": meeting.status,
        "created_at": str(meeting.created_at),
    }

@app.post("/api/meetings/{meeting_id}/transcribe")
def transcribe_meeting(
    meeting_id: int,
    model_size: str = Query(default=DEFAULT_WHISPER_MODEL),
    db: Session = Depends(get_db),
):
    if model_size not in ALLOWED_WHISPER_MODELS:
        allowed = ", ".join(sorted(ALLOWED_WHISPER_MODELS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported Whisper model: {model_size}. Allowed models: {allowed}",
        )

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status == "processing":
        raise HTTPException(status_code=409, detail="Meeting already processing")

    # Set status to processing
    meeting.status = "processing"
    db.commit()

    file_path = os.path.join(UPLOAD_DIR, cast(str, meeting.filename))

    try:
        segments = transcribe_audio(file_path, model_size=model_size)

        # Clear old segments if rerun
        db.query(TranscriptSegment).filter(TranscriptSegment.meeting_id == meeting_id).delete()

        for seg in segments:
            db.add(TranscriptSegment(
                meeting_id=meeting_id,
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
            ))

        meeting.status = "done"
        db.commit()

        return {
            "meeting_id": meeting_id,
            "status": meeting.status,
            "model_size": model_size,
            "num_segments": len(segments),
        }

    except Exception as e:
        meeting.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.post("/api/meetings/{meeting_id}/extract")
def extract_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start.asc())
        .all()
    )

    if not segments:
        raise HTTPException(
            status_code=400,
            detail="No transcript segments found. Run transcription first.",
        )

    transcript_segments = [
        {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "speaker": segment.speaker,
            "speaker_name": None,
        }
        for segment in segments
    ]

    display_map = get_speaker_display_map(db, meeting_id)
    for transcript_segment in transcript_segments:
        speaker_label = transcript_segment.get("speaker")
        if speaker_label:
            lbl = cast(str, speaker_label)
            transcript_segment["speaker_name"] = display_map.get(lbl, lbl)

    try:
        insights = extract_meeting_insights(transcript_segments)

        meeting.summary_text = insights["summary"]
        meeting.decisions_json = json.dumps(insights["decisions"])
        meeting.action_items_json = json.dumps(insights["action_items"])
        meeting.raw_model_output = insights["raw_model_output"]

        db.commit()
        db.refresh(meeting)

        return {
            "meeting_id": meeting.id,
            "summary": meeting.summary_text,
            "decisions": insights["decisions"],
            "action_items": insights["action_items"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}",
        )


@app.post("/api/meetings/{meeting_id}/diarize")
def diarize_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript_segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start.asc())
        .all()
    )
    if not transcript_segments:
        raise HTTPException(
            status_code=400,
            detail="No transcript segments found. Run transcription first.",
        )

    meeting.status = "processing"
    db.commit()

    file_path = os.path.join(UPLOAD_DIR, cast(str, meeting.filename))

    try:
        diarized_segments = diarize_audio(file_path)

        db.query(SpeakerSegment).filter(SpeakerSegment.meeting_id == meeting_id).delete()
        db.query(SpeakerMapping).filter(SpeakerMapping.meeting_id == meeting_id).delete()

        for diarized_segment in diarized_segments:
            db.add(
                SpeakerSegment(
                    meeting_id=meeting_id,
                    speaker_label=diarized_segment["speaker_label"],
                    start=diarized_segment["start"],
                    end=diarized_segment["end"],
                )
            )

        assign_speakers_to_transcript(transcript_segments, diarized_segments)
        meeting.status = "done"
        db.commit()

        display_map = get_speaker_display_map(db, meeting_id)
        speaker_segments = (
            db.query(SpeakerSegment)
            .filter(SpeakerSegment.meeting_id == meeting_id)
            .order_by(SpeakerSegment.start.asc())
            .all()
        )

        return {
            "meeting_id": meeting.id,
            "status": meeting.status,
            "speaker_segments": [
                serialize_speaker_segment(segment, display_map) for segment in speaker_segments
            ],
        }
    except Exception as exc:
        meeting.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(exc)}")


@app.get("/api/meetings/{meeting_id}/speakers")
def get_speakers(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    display_map = get_speaker_display_map(db, meeting_id)
    speaker_segments = (
        db.query(SpeakerSegment)
        .filter(SpeakerSegment.meeting_id == meeting_id)
        .order_by(SpeakerSegment.start.asc())
        .all()
    )

    seen_labels: set[str] = set()
    speakers = []
    for segment in speaker_segments:
        speaker_label = cast(str, segment.speaker_label)
        if speaker_label in seen_labels:
            continue
        seen_labels.add(speaker_label)
        speakers.append(
            {
                "speaker_label": speaker_label,
                "display_name": display_map.get(speaker_label, speaker_label),
            }
        )

    return {
        "meeting_id": meeting.id,
        "speakers": speakers,
    }


@app.post("/api/meetings/{meeting_id}/speakers")
def update_speakers(
    meeting_id: int,
    payload: SpeakerMappingPayload,
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    speaker_labels = {
        row[0]
        for row in db.query(SpeakerSegment.speaker_label)
        .filter(SpeakerSegment.meeting_id == meeting_id)
        .distinct()
        .all()
    }

    for speaker_label, display_name in payload.mapping.items():
        if speaker_label not in speaker_labels:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown speaker label: {speaker_label}",
            )

        mapping = (
            db.query(SpeakerMapping)
            .filter(
                SpeakerMapping.meeting_id == meeting_id,
                SpeakerMapping.speaker_label == speaker_label,
            )
            .first()
        )

        clean_name = display_name.strip() or speaker_label
        if mapping:
            mapping.display_name = clean_name
        else:
            db.add(
                SpeakerMapping(
                    meeting_id=meeting_id,
                    speaker_label=speaker_label,
                    display_name=clean_name,
                )
            )

    db.commit()
    return get_speakers(meeting_id, db)


@app.get("/api/meetings/{meeting_id}/insights")
def get_insights(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    decisions = json.loads(cast(str, meeting.decisions_json)) if meeting.decisions_json else []
    action_items = json.loads(cast(str, meeting.action_items_json)) if meeting.action_items_json else []

    return {
        "meeting_id": meeting.id,
        "summary": meeting.summary_text,
        "decisions": decisions,
        "action_items": action_items,
    }


@app.get("/api/meetings/{meeting_id}/result")
def get_result(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start.asc())
        .all()
    )
    speaker_segments = (
        db.query(SpeakerSegment)
        .filter(SpeakerSegment.meeting_id == meeting_id)
        .order_by(SpeakerSegment.start.asc())
        .all()
    )

    decisions = json.loads(cast(str, meeting.decisions_json)) if meeting.decisions_json else []
    action_items = json.loads(cast(str, meeting.action_items_json)) if meeting.action_items_json else []
    display_map = get_speaker_display_map(db, meeting_id)

    return {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "status": meeting.status,
        "transcript_segments": [
            serialize_transcript_segment(s, display_map) for s in segments
        ],
        "speaker_segments": [
            serialize_speaker_segment(segment, display_map) for segment in speaker_segments
        ],
        "summary": meeting.summary_text,
        "decisions": decisions,
        "action_items": action_items,
    }
