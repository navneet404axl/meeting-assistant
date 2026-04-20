import os
import uuid
from app.models.meeting import Meeting
from app.models.transcript import TranscriptSegment
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.pipeline.transcribe import transcribe_audio
from app.db.database import Base, engine, get_db


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Meeting Assistant API")

Base.metadata.create_all(bind=engine)


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
def transcribe_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status == "processing":
        raise HTTPException(status_code=409, detail="Meeting already processing")

    # Set status to processing
    meeting.status = "processing"
    db.commit()

    file_path = os.path.join(UPLOAD_DIR, meeting.filename)

    try:
        segments = transcribe_audio(file_path, model_size="base")

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

        return {"meeting_id": meeting_id, "status": meeting.status, "num_segments": len(segments)}

    except Exception as e:
        meeting.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


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

    return {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "status": meeting.status,
        "transcript_segments": [
            {"start": s.start, "end": s.end, "text": s.text} for s in segments
        ],
    }