from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.question import QuizQuestion
from app.models.student import Student

router = APIRouter()


@router.get("/quiz", summary="Retrieve quiz questions with optional filters")
def get_quiz(
    topic: Optional[str] = Query(None, description="Filter by topic (partial match)"),
    difficulty: Optional[str] = Query(None, description="easy | medium | hard"),
    subject: Optional[str] = Query(None, description="Filter by subject"),
    grade: Optional[int] = Query(None, description="Filter by grade level"),
    question_type: Optional[str] = Query(None, description="MCQ | TrueFalse | FillBlank"),
    student_id: Optional[str] = Query(None, description="Adapts difficulty to student's current level"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Returns quiz questions. If student_id is provided and difficulty is not,
    uses the student's current adaptive difficulty level.
    """
    # Resolve difficulty from student profile if not explicitly provided
    resolved_difficulty = difficulty
    if student_id and not difficulty:
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            resolved_difficulty = student.current_difficulty

    q = db.query(QuizQuestion)

    if topic:
        q = q.filter(QuizQuestion.topic.ilike(f"%{topic}%"))
    if resolved_difficulty:
        q = q.filter(QuizQuestion.difficulty == resolved_difficulty)
    if subject:
        q = q.filter(QuizQuestion.subject.ilike(f"%{subject}%"))
    if grade:
        q = q.filter(QuizQuestion.grade == grade)
    if question_type:
        q = q.filter(QuizQuestion.question_type == question_type)

    questions = q.limit(limit).all()

    return {
        "count": len(questions),
        "difficulty_applied": resolved_difficulty,
        "questions": [
            {
                "id": qq.id,
                "question": qq.question,
                "type": qq.question_type,
                "options": qq.options,
                "difficulty": qq.difficulty,
                "topic": qq.topic,
                "subject": qq.subject,
                "grade": qq.grade,
                "source_chunk_id": qq.chunk_id,
            }
            for qq in questions
        ],
    }


@router.get("/quiz/{question_id}", summary="Get a single question with its answer")
def get_question(question_id: str, db: Session = Depends(get_db)):
    qq = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not qq:
        raise HTTPException(status_code=404, detail="Question not found.")
    return {
        "id": qq.id,
        "question": qq.question,
        "type": qq.question_type,
        "options": qq.options,
        "answer": qq.answer,
        "difficulty": qq.difficulty,
        "topic": qq.topic,
        "subject": qq.subject,
        "grade": qq.grade,
        "source_chunk_id": qq.chunk_id,
    }


@router.get("/student/{student_id}", summary="Get student profile and adaptive state")
def get_student(student_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {
        "student_id": student.id,
        "current_difficulty": student.current_difficulty,
        "correct_streak": student.correct_streak,
        "incorrect_streak": student.incorrect_streak,
        "total_answered": student.total_answered,
        "total_correct": student.total_correct,
        "accuracy_percent": student.accuracy,
    }


@router.get("/sources", summary="List all ingested source documents")
def list_sources(db: Session = Depends(get_db)):
    from app.models.source import SourceDocument
    sources = db.query(SourceDocument).all()
    return [
        {
            "id": s.id,
            "filename": s.filename,
            "grade": s.grade,
            "subject": s.subject,
            "total_chunks": s.total_chunks,
            "created_at": s.created_at,
        }
        for s in sources
    ]
