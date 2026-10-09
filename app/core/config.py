from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Your Postgres connection string
    DATABASE_URL: str = "postgresql+psycopg2://postgres.gibejqmneuccurybpdfv:Joshraynz4%40gmail.com@aws-1-eu-central-1.pooler.supabase.com:6543/postgres"
    
    FIREBASE_CREDENTIALS_PATH: str = "firebase_credentials.json"
    
    AT_API_KEY: str = ""
    AT_USERNAME: str = "microbondapp"
    ENVIRONMENT: str = "production"
    
    SUMSUB_APP_TOKEN: str = ""
    SUMSUB_SECRET_KEY: str = ""
    
    PREMBLY_SECRET_KEY: str = ""
    PREMBLY_PUBLIC_KEY: str = ""
    
    # JWT Settings
    SECRET_KEY: str = "a_very_secret_and_long_string_for_production_jwt" # In production, set this in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days

    # Reads from a local .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
