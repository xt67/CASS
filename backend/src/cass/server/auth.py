"""Deployment authentication. Anonymous access requires an explicit local opt-in."""
import os
import secrets
from fastapi import HTTPException, Request


async def require_auth(request: Request):
    if request.url.path == "/":
        return
    key = os.environ.get("CASS_API_KEY", "")
    if not key:
        if os.environ.get("CASS_ALLOW_ANONYMOUS") == "1":
            return
        raise HTTPException(503, "Configure CASS_API_KEY, or explicitly enable local anonymous development")
    supplied = request.headers.get("Authorization", "")
    if not secrets.compare_digest(supplied, f"Bearer {key}"):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
