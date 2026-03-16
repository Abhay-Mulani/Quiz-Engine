from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.models.student import Student, StudentAnswer
from app.models.question import QuizQuestion
from app.services.adaptive import update_difficulty

router = APIRouter()


class AnswerSubmission(BaseModel):
    student_id: str
    question_id: str
    selected_answer: str


@router.post("/submit-answer", summary="Submit a student answer and get adaptive feedback")
def submit_answer(payload: AnswerSubmission, db: Session = Depends(get_db)):
    # Validate question exists
    question = db.query(QuizQuestion).filter(QuizQuestion.id == payload.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Get or create student
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        student = Student(id=payload.student_id)
        db.add(student)
        db.flush()

    # Check correctness (case-insensitive, strip whitespace)
    is_correct = payload.selected_answer.strip().lower() == question.answer.strip().lower()

    # Record answer
    answer_record = StudentAnswer(
        student_id=student.id,
        question_id=question.id,
        selected_answer=payload.selected_answer,
        is_correct=is_correct,
        difficulty_at_attempt=student.current_difficulty,
    )
    db.add(answer_record)

    # Update adaptive difficulty
    old_difficulty = student.current_difficulty
    new_difficulty = update_difficulty(student, is_correct)

    db.commit()

    return {
        "student_id": student.id,
        "question_id": question.id,
        "selected_answer": payload.selected_answer,
        "correct_answer": question.answer,
        "is_correct": is_correct,
        "feedback": "Correct! Well done." if is_correct else f"Incorrect. The correct answer is: {question.answer}",
        "adaptive": {
            "previous_difficulty": old_difficulty,
            "current_difficulty": new_difficulty,
            "difficulty_changed": old_difficulty != new_difficulty,
            "correct_streak": student.correct_streak,
            "incorrect_streak": student.incorrect_streak,
        },
        "stats": {
            "total_answered": student.total_answered,
            "total_correct": student.total_correct,
            "accuracy_percent": student.accuracy,
        },
    }
