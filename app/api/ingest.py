import os
import shutil
import tempfile
import traceback
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.source import SourceDocument, ContentChunk
from app.services.ingestion import ingest_pdf
from app.core.config import settings

router = APIRouter()


@router.post("/ingest", summary="Ingest a PDF and extract content chunks")
async def ingest_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    suffix = ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = ingest_pdf(
            file_path=tmp_path,
            filename=file.filename,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
    finally:
        os.unlink(tmp_path)

    source = SourceDocument(
        filename=result["filename"],
        grade=result["grade"],
        subject=result["subject"],
        total_chunks=result["total_chunks"],
    )
    db.add(source)
    db.flush()

    existing_fps = {
        fp for (fp,) in db.query(ContentChunk.fingerprint).filter(
            ContentChunk.fingerprint.isnot(None)
        ).all()
    }

    new_chunks = []
    for c in result["chunks"]:
        if c["fingerprint"] in existing_fps:
            continue
        chunk = ContentChunk(
            source_id=source.id,
            chunk_index=c["chunk_index"],
            grade=c["grade"],
            subject=c["subject"],
            topic=c["topic"],
            text=c["text"],
            fingerprint=c["fingerprint"],
        )
        db.add(chunk)
        new_chunks.append(chunk)

    db.commit()

    return {
        "source_id": source.id,
        "filename": source.filename,
        "grade": source.grade,
        "subject": source.subject,
        "total_chunks": source.total_chunks,
        "new_chunks_stored": len(new_chunks),
        "message": "Ingestion complete.",
    }


@router.post("/generate-quiz", summary="Generate quiz questions from stored chunks")
def generate_quiz(
    source_id: str = Query(..., description="Source document ID to generate questions for"),
    questions_per_chunk: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    from app.models.question import QuizQuestion
    from app.services.llm import generate_questions_for_chunk

    source = db.query(SourceDocument).filter(SourceDocument.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source document not found.")

    chunks = db.query(ContentChunk).filter(ContentChunk.source_id == source_id).all()
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found for this source.")

    total_generated = 0
    total_skipped = 0
    errors = []

    existing_fps = {
        fp for (fp,) in db.query(QuizQuestion.fingerprint).filter(
            QuizQuestion.fingerprint.isnot(None)
        ).all()
    }

    for chunk in chunks:
        try:
            questions = generate_questions_for_chunk(
                chunk_id=chunk.id,
                chunk_text=chunk.text,
                grade=chunk.grade,
                subject=chunk.subject,
                topic=chunk.topic,
                n=questions_per_chunk,
            )
        except Exception as e:
            traceback.print_exc()
            errors.append(f"chunk {chunk.chunk_index}: {str(e)}")
            continue

        for q in questions:
            if q["fingerprint"] in existing_fps:
                total_skipped += 1
                continue
            existing_fps.add(q["fingerprint"])
            db.add(QuizQuestion(**q))
            total_generated += 1

    db.commit()

    return {
        "source_id": source_id,
        "chunks_processed": len(chunks),
        "questions_generated": total_generated,
        "questions_skipped_duplicates": total_skipped,
        "errors": errors,
        "message": "Quiz generation complete." if not errors else "Completed with errors — check errors field and server logs.",
    }
