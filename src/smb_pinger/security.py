import hmac
import logging
import secrets
from collections.abc import Awaitable, Callable

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
security = HTTPBasic()


def verify_admin(password_hash: str) -> Callable[..., str]:
    """Create an auth dependency that verifies admin credentials."""

    def _verify(credentials: HTTPBasicCredentials = Depends(security)) -> str:  # noqa: B008
        if not password_hash:
            raise HTTPException(status_code=503, detail="Admin auth not configured")
        if not _bcrypt.checkpw(
            credentials.password.encode(), password_hash.encode()
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    return _verify


# CSRF protection
CSRF_TOKEN_LENGTH = 32
CSRF_HEADER = "X-CSRFToken"
CSRF_FIELD = "csrf_token"


def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    return secrets.token_hex(CSRF_TOKEN_LENGTH)


def validate_csrf_token(request_token: str, session_token: str) -> bool:
    """Constant-time comparison of CSRF tokens."""
    return hmac.compare_digest(request_token, session_token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' https://unpkg.com https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'"
        )
        return response
