# AI Quiz Engine

A backend system that ingests educational PDFs, extracts structured content, generates quiz questions using an LLM, and serves an adaptive quiz API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
├──────────────┬──────────────────────┬───────────────────────────┤
│  POST /ingest│  POST /generate-quiz │  GET /quiz                │
│  (PDF Upload)│  (LLM Question Gen)  │  POST /submit-answer      │
└──────┬───────┴──────────┬───────────┴───────────────┬───────────┘
       │                  │                           │
       ▼                  ▼                           ▼
┌─────────────┐   ┌──────────────┐          ┌────────────────────┐
│  Ingestion  │   │  LLM Service │          │  Adaptive Engine   │
│  Service    │   │  (Anthropic/ │          │  (streak tracking, │
│  - Extract  │   │   OpenAI)    │          │   difficulty up/   │
│  - Clean    │   │  - Prompt    │          │   down logic)      │
│  - Chunk    │   │  - Parse     │          └────────────────────┘
│  - Metadata │   │  - Validate  │
└──────┬──────┘   └──────┬───────┘
       │                  │
       ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SQLite / PostgreSQL                       │
│  source_documents │ content_chunks │ quiz_questions             │
│  students         │ student_answers                             │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingest** — Upload a PDF → text extracted (PyMuPDF) → cleaned → chunked (800 chars, 100 overlap) → metadata inferred (grade, subject, topic) → stored in DB
2. **Generate** — For each chunk → LLM prompt sent → JSON array of questions returned → validated + deduplicated → stored in DB
3. **Quiz** — Client calls `GET /quiz` with optional filters → questions returned (optionally filtered by student's current adaptive difficulty)
4. **Submit** — Student answer received → correctness checked → streak updated → difficulty level adjusted → response returned

---

## Project Structure

```
peblo-quiz-engine/
├── app/
│   ├── main.py               # FastAPI app + startup
│   ├── api/
│   │   ├── ingest.py         # POST /ingest, POST /generate-quiz
│   │   ├── quiz.py           # GET /quiz, GET /quiz/{id}, GET /sources
│   │   └── submit.py         # POST /submit-answer
│   ├── core/
│   │   └── config.py         # Pydantic settings (reads .env)
│   ├── db/
│   │   └── database.py       # SQLAlchemy engine, session, init_db
│   ├── models/
│   │   ├── source.py         # SourceDocument + ContentChunk ORM models
│   │   ├── question.py       # QuizQuestion ORM model
│   │   └── student.py        # Student + StudentAnswer ORM models
│   └── services/
│       ├── ingestion.py      # PDF extraction, chunking, topic inference
│       ├── llm.py            # LLM call, prompt building, response parsing
│       └── adaptive.py       # Adaptive difficulty engine
├── sample_outputs/
│   └── sample_outputs.json   # Example API responses
├── .env.example              # Environment variable template
├── requirements.txt
└── README.md
```

---

## Database Schema

### `source_documents`
| Column | Type | Description |
|---|---|---|
| id | UUID (PK) | Auto-generated |
| filename | String | Original PDF filename |
| grade | Integer | Inferred grade level |
| subject | String | Inferred subject |
| total_chunks | Integer | Number of chunks extracted |
| created_at | DateTime | Ingestion timestamp |

### `content_chunks`
| Column | Type | Description |
|---|---|---|
| id | UUID (PK) | Auto-generated |
| source_id | FK → source_documents | Parent document |
| chunk_index | Integer | Position in document |
| grade | Integer | Inherited from source |
| subject | String | Inherited from source |
| topic | String | Inferred from chunk text |
| text | Text | Chunk content |
| fingerprint | String | SHA-256 hash for deduplication |

### `quiz_questions`
| Column | Type | Description |
|---|---|---|
| id | UUID (PK) | Auto-generated |
| chunk_id | FK → content_chunks | Traceable source |
| question | Text | Question text |
| question_type | String | MCQ \| TrueFalse \| FillBlank |
| options | JSON | Array of options (MCQ only) |
| answer | String | Correct answer |
| difficulty | String | easy \| medium \| hard |
| topic | String | |
| subject | String | |
| grade | Integer | |
| fingerprint | String | For duplicate detection |

### `students`
| Column | Type | Description |
|---|---|---|
| id | String (PK) | Client-provided student ID |
| current_difficulty | String | easy \| medium \| hard |
| correct_streak | Integer | Consecutive correct answers |
| incorrect_streak | Integer | Consecutive wrong answers |
| total_answered | Integer | Lifetime total |
| total_correct | Integer | Lifetime correct |

### `student_answers`
| Column | Type | Description |
|---|---|---|
| id | UUID (PK) | Auto-generated |
| student_id | FK → students | |
| question_id | FK → quiz_questions | |
| selected_answer | String | What the student chose |
| is_correct | Boolean | Evaluated at submission time |
| difficulty_at_attempt | String | Difficulty level at time of attempt |
| submitted_at | DateTime | |

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Abhay-Mulani/Quiz-Engine
cd peblo-quiz-engine
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
LLM_PROVIDER=anthropic          # or openai
LLM_API_KEY=sk-ant-...          # your API key
LLM_MODEL=claude-sonnet-4-20250514
DATABASE_URL=sqlite:///./peblo.db
```

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now live at **http://localhost:8000**

Interactive docs: **http://localhost:8000/docs**

---

## API Reference

### `POST /ingest`
Upload a PDF to extract and store content chunks.

**Request:** `multipart/form-data`
- `file` — PDF file

**Response:**
```json
{
  "source_id": "abc123",
  "filename": "peblo_pdf_grade1_math_numbers.pdf",
  "grade": 1,
  "subject": "Math",
  "total_chunks": 12,
  "new_chunks_stored": 12,
  "message": "Ingestion complete."
}
```

---

### `POST /generate-quiz?source_id=abc123&questions_per_chunk=5`
Generate quiz questions for all chunks of a source document.

| Query Param | Default | Description |
|---|---|---|
| source_id | required | ID returned from `/ingest` |
| questions_per_chunk | 5 | Questions to generate per chunk (1–10) |

**Response:**
```json
{
  "source_id": "abc123",
  "chunks_processed": 12,
  "questions_generated": 58,
  "questions_skipped_duplicates": 2,
  "message": "Quiz generation complete."
}
```

---

### `GET /quiz`
Retrieve quiz questions with optional filters.

| Query Param | Description |
|---|---|
| topic | Partial match on topic (e.g. `shapes`) |
| difficulty | `easy` \| `medium` \| `hard` |
| subject | Partial match (e.g. `math`) |
| grade | Integer grade level |
| question_type | `MCQ` \| `TrueFalse` \| `FillBlank` |
| student_id | Adapts difficulty to student's current level |
| limit | Max results (default 10, max 50) |

**Example:** `GET /quiz?topic=shapes&difficulty=easy&limit=5`

**Response:**
```json
{
  "count": 3,
  "difficulty_applied": "easy",
  "questions": [
    {
      "id": "Q001",
      "question": "How many sides does a triangle have?",
      "type": "MCQ",
      "options": ["2", "3", "4", "5"],
      "difficulty": "easy",
      "topic": "Shapes",
      "subject": "Math",
      "grade": 1,
      "source_chunk_id": "chunk-id-here"
    }
  ]
}
```

---

### `POST /submit-answer`
Submit a student's answer and receive adaptive feedback.

**Request body:**
```json
{
  "student_id": "S001",
  "question_id": "Q001",
  "selected_answer": "3"
}
```

**Response:**
```json
{
  "student_id": "S001",
  "question_id": "Q001",
  "selected_answer": "3",
  "correct_answer": "3",
  "is_correct": true,
  "feedback": "Correct! Well done.",
  "adaptive": {
    "previous_difficulty": "easy",
    "current_difficulty": "easy",
    "difficulty_changed": false,
    "correct_streak": 1,
    "incorrect_streak": 0
  },
  "stats": {
    "total_answered": 1,
    "total_correct": 1,
    "accuracy_percent": 100.0
  }
}
```

---

### `GET /student/{student_id}`
Get a student's current profile and adaptive state.

### `GET /sources`
List all ingested source documents.

### `GET /quiz/{question_id}`
Get a single question including its answer.

---

## Adaptive Difficulty Logic

Students start at `easy`. The engine adjusts difficulty based on streaks:

```
correct_streak >= 3  →  difficulty increases  (easy → medium → hard)
incorrect_streak >= 2  →  difficulty decreases  (hard → medium → easy)
```

When `GET /quiz?student_id=S001` is called without an explicit `difficulty` param, the API automatically returns questions at the student's current level.

Thresholds are configurable via `.env`:
```env
CORRECT_STREAK_TO_INCREASE=3
INCORRECT_STREAK_TO_DECREASE=2
```

---

## Testing Endpoints (curl examples)

```bash
# 1. Ingest a PDF
curl -X POST http://localhost:8000/ingest \
  -F "file=@peblo_pdf_grade1_math_numbers.pdf"

# 2. Generate quiz questions (use source_id from step 1)
curl -X POST "http://localhost:8000/generate-quiz?source_id=YOUR_SOURCE_ID&questions_per_chunk=5"

# 3. Get easy quiz questions on shapes
curl "http://localhost:8000/quiz?topic=shapes&difficulty=easy&limit=5"

# 4. Submit an answer
curl -X POST http://localhost:8000/submit-answer \
  -H "Content-Type: application/json" \
  -d '{"student_id":"S001","question_id":"YOUR_QUESTION_ID","selected_answer":"3"}'

# 5. Check student adaptive state
curl http://localhost:8000/student/S001

# 6. Get adaptive quiz for student (auto-resolves difficulty)
curl "http://localhost:8000/quiz?student_id=S001&limit=10"
```

---

## Optional Features Implemented

- ✅ **Duplicate question detection** — SHA-256 fingerprint on normalized question text, checked at both generation and storage time
- ✅ **Duplicate chunk detection** — fingerprint on chunk text prevents re-ingesting the same content
- ✅ **Question validation** — LLM responses are parsed, type-checked, and rejected if malformed
- ✅ **Source traceability** — every question references its `chunk_id` which references its `source_id`
- ✅ **Provider-agnostic LLM** — swap between Anthropic and OpenAI via `.env`

---

## Notes

- No secrets are committed — use `.env` (gitignored) with `.env.example` as template
- The system defaults to SQLite for zero-config local development; swap `DATABASE_URL` for PostgreSQL in production
- All questions generated by the LLM are validated before storage — malformed responses are silently skipped
