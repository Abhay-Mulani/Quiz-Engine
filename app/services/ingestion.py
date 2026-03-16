import re
import hashlib
from typing import List, Dict, Any
from pathlib import Path

try:
    import fitz  # PyMuPDF
    PDF_BACKEND = "pymupdf"
except ImportError:
    import pdfplumber
    PDF_BACKEND = "pdfplumber"


DIFFICULTY_MAP = {1: "easy", 2: "easy", 3: "medium", 4: "medium", 5: "hard", 6: "hard"}

SUBJECT_HINTS = {
    "math": ["math", "number", "count", "shape", "addition", "subtraction", "geometry"],
    "science": ["science", "plant", "animal", "biology", "physics", "chemistry", "nature"],
    "english": ["english", "grammar", "vocabulary", "language", "writing", "reading"],
}


def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from a PDF file."""
    if PDF_BACKEND == "pymupdf":
        doc = fitz.open(file_path)
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(pages)
    else:
        with pdfplumber.open(file_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)


def clean_text(text: str) -> str:
    """Remove noise, normalize whitespace."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)   # strip non-ASCII
    text = re.sub(r'\.{3,}', '...', text)          # normalize ellipsis
    text = text.strip()
    return text


def infer_metadata(filename: str, text: str) -> Dict[str, Any]:
    """Infer grade, subject, and dominant topic from filename + text."""
    fname = filename.lower()

    # Grade
    grade = None
    m = re.search(r'grade[\s_]?(\d+)', fname)
    if m:
        grade = int(m.group(1))

    # Subject
    subject = None
    for subj, keywords in SUBJECT_HINTS.items():
        if any(k in fname for k in keywords):
            subject = subj.capitalize()
            break
    if not subject:
        lower_text = text.lower()
        for subj, keywords in SUBJECT_HINTS.items():
            if sum(lower_text.count(k) for k in keywords) > 3:
                subject = subj.capitalize()
                break

    return {"grade": grade, "subject": subject}


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> List[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = []
    current_len = 0

    for sentence in sentences:
        sent_len = len(sentence)
        if current_len + sent_len > chunk_size and current:
            chunks.append(" ".join(current))
            # keep overlap
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_len += len(s)
                else:
                    break
            current = overlap_sentences
            current_len = overlap_len
        current.append(sentence)
        current_len += sent_len

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if len(c.strip()) > 50]


def infer_topic(chunk_text: str) -> str:
    """Very simple keyword-based topic extraction from chunk."""
    topic_keywords = {
        "Shapes": ["triangle", "circle", "square", "rectangle", "shape", "polygon"],
        "Numbers": ["number", "count", "digit", "zero", "one", "two", "hundred"],
        "Addition/Subtraction": ["add", "subtract", "sum", "plus", "minus", "total"],
        "Plants": ["plant", "leaf", "root", "stem", "flower", "photosynthesis", "seed"],
        "Animals": ["animal", "mammal", "reptile", "bird", "insect", "predator", "prey"],
        "Grammar": ["noun", "verb", "adjective", "adverb", "sentence", "paragraph", "tense"],
        "Vocabulary": ["word", "meaning", "synonym", "antonym", "definition", "vocabulary"],
    }
    lower = chunk_text.lower()
    scores = {topic: sum(lower.count(kw) for kw in kws) for topic, kws in topic_keywords.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def compute_fingerprint(text: str) -> str:
    """Hash a normalized version of text for duplicate detection."""
    normalized = re.sub(r'\W+', '', text.lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def ingest_pdf(
    file_path: str,
    filename: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> Dict[str, Any]:
    """
    Full ingestion pipeline for one PDF.
    Returns source metadata + list of chunk dicts.
    """
    raw_text = extract_text_from_pdf(file_path)
    cleaned = clean_text(raw_text)
    metadata = infer_metadata(filename, cleaned)
    chunks_text = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)

    chunks = []
    for i, text in enumerate(chunks_text):
        chunks.append({
            "chunk_index": i,
            "grade": metadata["grade"],
            "subject": metadata["subject"],
            "topic": infer_topic(text),
            "text": text,
            "fingerprint": compute_fingerprint(text),
        })

    return {
        "filename": filename,
        "grade": metadata["grade"],
        "subject": metadata["subject"],
        "total_chunks": len(chunks),
        "chunks": chunks,
    }
