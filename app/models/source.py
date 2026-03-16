from sqlalchemy import Column, String, Integer, DateTime, Text, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
import uuid


def gen_id():
    return str(uuid.uuid4())


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(String, primary_key=True, default=gen_id)
    filename = Column(String, nullable=False)
    grade = Column(Integer, nullable=True)
    subject = Column(String, nullable=True)
    total_chunks = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("ContentChunk", back_populates="source", cascade="all, delete-orphan")


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id = Column(String, primary_key=True, default=gen_id)
    source_id = Column(String, ForeignKey("source_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    grade = Column(Integer, nullable=True)
    subject = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    fingerprint = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("SourceDocument", back_populates="chunks")
    questions = relationship("QuizQuestion", back_populates="chunk", cascade="all, delete-orphan")
