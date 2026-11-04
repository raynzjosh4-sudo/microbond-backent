from fastapi.security import HTTPBearer

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)
