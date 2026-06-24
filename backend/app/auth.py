import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.config import settings

security = HTTPBasic()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """
    Validates Basic Authentication credentials.
    Raises 401 Unauthorized if validation fails.
    """
    correct_username = secrets.compare_digest(credentials.username, settings.API_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, settings.API_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials provided.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
