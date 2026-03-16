from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./peblo.db"
    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"       # gemini | groq | anthropic | openai
    LLM_MODEL: str = "gemini-1.5-flash"

    # Chunk settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100

    # Adaptive difficulty thresholds
    CORRECT_STREAK_TO_INCREASE: int = 3
    INCORRECT_STREAK_TO_DECREASE: int = 2

    class Config:
        env_file = ".env"


settings = Settings()
