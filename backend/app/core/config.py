import os
from pydantic import BaseModel


class Settings(BaseModel):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://agentguard:agentguard_password@localhost:5432/agentguard",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme_secret_key_jwt_dev_only_32b!")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    AGENTGUARD_ENV: str = os.getenv("AGENTGUARD_ENV", "development")


settings = Settings()
