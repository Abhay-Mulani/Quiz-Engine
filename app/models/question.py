from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
import uuid


def gen_id():
    return str(uuid.uuid4())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(String, primary_key=True, default=gen_id)
    chunk_id = Column(String, ForeignKey("content_chunks.id"), nullable=False)
    question = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)  # MCQ | TrueFalse | FillBlank
    options = Column(JSON, nullable=True)           # list of strings for MCQ
    answer = Column(String, nullable=False)
    difficulty = Column(String, default="medium")   # easy | medium | hard
    topic = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    grade = Column(Integer, nullable=True)
    fingerprint = Column(String, nullable=True, index=True)  # for duplicate detection
    created_at = Column(DateTime, default=datetime.utcnow)

    chunk = relationship("ContentChunk", back_populates="questions")
    answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")
