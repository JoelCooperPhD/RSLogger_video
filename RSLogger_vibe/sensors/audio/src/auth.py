"""Simple authentication for RSLogger web interface."""
import hashlib
import secrets
from typing import Optional

# Simple token-based auth - change this secret!
AUTH_TOKEN = "your-secret-token-here"

def verify_token(token: Optional[str]) -> bool:
    """Verify authentication token."""
    return token == AUTH_TOKEN

def generate_secure_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)

# To use with FastAPI:
# from fastapi import Depends, HTTPException, Header
# 
# def verify_auth(authorization: str = Header(None)):
#     if not authorization or not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Missing auth token")
#     token = authorization.replace("Bearer ", "")
#     if not verify_token(token):
#         raise HTTPException(status_code=401, detail="Invalid token")
#     return True