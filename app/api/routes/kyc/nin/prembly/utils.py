from app.core.config import settings

PREMBLY_SECRET_KEY = settings.PREMBLY_SECRET_KEY
PREMBLY_BASE_URL = "https://api.prembly.com"

def get_prembly_headers():
    return {
        "x-api-key": PREMBLY_SECRET_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
