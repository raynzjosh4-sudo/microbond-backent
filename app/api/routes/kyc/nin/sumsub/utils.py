import time
import hmac
import hashlib
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

SUMSUB_APP_TOKEN = settings.SUMSUB_APP_TOKEN
SUMSUB_SECRET_KEY = settings.SUMSUB_SECRET_KEY
SUMSUB_BASE_URL = "https://api.sumsub.com"

def generate_sumsub_signature(method: str, path: str, body: bytes = b'') -> dict:
    if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
        logger.warning("Sumsub credentials are not set.")
        
    ts = str(int(time.time()))
    data_to_sign = ts.encode('utf-8') + method.encode('utf-8') + path.encode('utf-8') + body
    
    if SUMSUB_SECRET_KEY:
        signature = hmac.new(SUMSUB_SECRET_KEY.encode('utf-8'), data_to_sign, hashlib.sha256).hexdigest()
    else:
        signature = "mock_signature"
        
    return {
        "X-App-Token": SUMSUB_APP_TOKEN if SUMSUB_APP_TOKEN else "mock_token",
        "X-App-Access-Sig": signature,
        "X-App-Access-Ts": ts,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
