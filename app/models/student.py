from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
import uuid


def gen_id():
    return str(uuid.uuid4())


class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True)          # student_id provided by client
    current_difficulty = Column(String, default="easy")
    correct_streak = Column(Integer, default=0)
    incorrect_streak = Column(Integer, default=0)
    total_answered = Column(Integer, default=0)
    total_correct = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    answers = relationship("StudentAnswer", back_populates="student", cascade="all, delete-orphan")

    @property
    def accuracy(self) -> float:
        if self.total_answered == 0:
            return 0.0
        return round(self.total_correct / self.total_answered * 100, 2)


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(String, primary_key=True, default=gen_id)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    question_id = Column(String, ForeignKey("quiz_questions.id"), nullable=False)
    selected_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    difficulty_at_attempt = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="answers")
    question = relationship("QuizQuestion", back_populates="answers")
