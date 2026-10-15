from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    # Your Postgres connection string
    DATABASE_URL: str = ""
    
    FIREBASE_CREDENTIALS_PATH: str = "firebase_credentials.json"
    
    AT_API_KEY: str = ""
    AT_USERNAME: str = "microbondapp"
    ENVIRONMENT: str = "production"
    
    SUMSUB_APP_TOKEN: str = ""
    SUMSUB_SECRET_KEY: str = ""
    SUMSUB_LEVEL_NAME: str = "ld-text-based-level"
    
    PREMBLY_SECRET_KEY: str = ""
    PREMBLY_PUBLIC_KEY: str = ""
    
    # Resend Email Service
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "Microbond <no-reply@mail.crimchart.com>"

    # Public Supabase Storage URL for email assets
    # Format: https://<project-ref>.supabase.co/storage/v1/object/public/email-assets
    EMAIL_ASSET_BASE_URL: str = "https://gibejqmneuccurybpdfv.supabase.co/storage/v1/object/public/email-assets"
    
    # JWT Settings
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        return v or ""
    
    # Sentry Error Logging
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    
    # Redis for Rate Limiting
    REDIS_URL: str = "redis://localhost:6379"
    
    # Internal Task & Scheduler Settings
    INTERNAL_TASKS_KEY: str = ""
    ENABLE_IN_PROCESS_SCHEDULER: bool = False
    
    # External Dedicated Payment Gateway Webhook / Inbound Secret
    PAYMENT_GATEWAY_WEBHOOK_SECRET: str = ""
    
    # Security / CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",        # Local React web testing
        "http://localhost:8000",        # Local development
        "https://app.microbond.com",    # Your future production frontend
        # Android / iOS don't strictly use CORS, but keeping this secure prevents web scraping!
    ]
    
    # Cloudflare R2 Credentials
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_ENDPOINT_URL: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_DOMAIN: str = "" # e.g. "https://pub-xxxx.r2.dev" or custom domain

    # Reads from local .env files (backend root or current working dir)
    model_config = SettingsConfigDict(
        env_file=[str(ENV_FILE), ".env"], 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

