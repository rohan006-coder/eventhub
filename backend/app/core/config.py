import os


class Settings:
    """Plain env-driven settings (read at import time)."""

    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/eventhub")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
    REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "")
    SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "")
    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
    SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "300"))
    REMINDER_WINDOW_HOURS = int(os.getenv("REMINDER_WINDOW_HOURS", "24"))


settings = Settings()
