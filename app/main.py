from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import ingest, quiz, submit
from app.db.database import init_db

app = FastAPI(
    title="Peblo AI Quiz Engine",
    description="Content ingestion and adaptive quiz generation platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()


app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(quiz.router, tags=["Quiz"])
app.include_router(submit.router, tags=["Submission"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Peblo Quiz Engine is running"}
