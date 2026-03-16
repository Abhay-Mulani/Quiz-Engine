import json
import re
import hashlib
from typing import List, Dict, Any
from app.core.config import settings

# ---------------------------------------------------------------------------
# Provider-agnostic LLM call
# ---------------------------------------------------------------------------

def _call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)
    message = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.LLM_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return resp.choices[0].message.content


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=settings.LLM_API_KEY)
    model = genai.GenerativeModel(settings.LLM_MODEL or "gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text


def _call_groq(prompt: str) -> str:
    from groq import Groq
    client = Groq(api_key=settings.LLM_API_KEY)
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL or "llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return resp.choices[0].message.content


def call_llm(prompt: str) -> str:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "anthropic":
        return _call_anthropic(prompt)
    elif provider == "openai":
        return _call_openai(prompt)
    elif provider == "gemini":
        return _call_gemini(prompt)
    elif provider == "groq":
        return _call_groq(prompt)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert educational quiz designer for K-6 students.
Generate exactly the number of quiz questions requested.
Return ONLY a valid JSON array — no markdown, no extra text.
Each element must have these exact keys:
  question (string), type (MCQ|TrueFalse|FillBlank),
  options (array of 4 strings for MCQ, null otherwise),
  answer (string — must match one option exactly for MCQ),
  difficulty (easy|medium|hard)
"""


def build_prompt(chunk_text: str, grade: int, subject: str, topic: str, n: int = 5) -> str:
    grade_desc = f"Grade {grade}" if grade else "elementary school"
    return f"""{SYSTEM_PROMPT}

Content context:
- Subject: {subject or 'General'}
- Topic: {topic or 'General'}
- Grade level: {grade_desc}

Educational content:
\"\"\"
{chunk_text[:1500]}
\"\"\"

Generate {n} questions:
- {max(1, n // 3)} Multiple Choice (MCQ)
- {max(1, n // 3)} True/False (TrueFalse)
- {max(1, n - 2*(max(1, n//3)))} Fill in the Blank (FillBlank)

Mix difficulties: easy, medium, hard.
Questions must be answerable solely from the provided content.
"""


# ---------------------------------------------------------------------------
# Parse & validate LLM response
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> List[Dict]:
    # Strip markdown fences if present
    raw = re.sub(r"```json|```", "", raw).strip()
    # Try direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # Fallback: find first JSON array
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        return json.loads(m.group())
    raise ValueError("No valid JSON array found in LLM response")


def _validate_question(q: Dict) -> bool:
    required = {"question", "type", "answer", "difficulty"}
    if not required.issubset(q.keys()):
        return False
    if q["type"] not in ("MCQ", "TrueFalse", "FillBlank"):
        return False
    if q["type"] == "MCQ" and (not q.get("options") or len(q["options"]) < 2):
        return False
    if q["difficulty"] not in ("easy", "medium", "hard"):
        q["difficulty"] = "medium"
    return True


def _fingerprint(question_text: str) -> str:
    normalized = re.sub(r'\W+', '', question_text.lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_questions_for_chunk(
    chunk_id: str,
    chunk_text: str,
    grade: int,
    subject: str,
    topic: str,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Call the LLM and return a list of validated question dicts
    ready to be persisted to the DB.
    """
    prompt = build_prompt(chunk_text, grade, subject, topic, n)
    raw = call_llm(prompt)
    questions = _extract_json(raw)

    results = []
    seen_fingerprints = set()

    for q in questions:
        if not _validate_question(q):
            continue
        fp = _fingerprint(q["question"])
        if fp in seen_fingerprints:
            continue  # deduplicate within batch
        seen_fingerprints.add(fp)
        results.append({
            "chunk_id": chunk_id,
            "question": q["question"],
            "question_type": q["type"],
            "options": q.get("options"),
            "answer": q["answer"],
            "difficulty": q["difficulty"],
            "topic": topic,
            "subject": subject,
            "grade": grade,
            "fingerprint": fp,
        })

    return results
