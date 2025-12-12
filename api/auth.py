import os
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from open_notebook.domain.user import User
from open_notebook.utils.jwt_auth import get_user_id_from_token


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check password authentication for all API requests.
    Only active when OPEN_NOTEBOOK_PASSWORD environment variable is set.
    """
    
    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.password = os.environ.get("OPEN_NOTEBOOK_PASSWORD")
        self.excluded_paths = excluded_paths or ["/", "/health", "/docs", "/openapi.json", "/redoc"]
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Skip authentication for CORS preflight requests (OPTIONS)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Check authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            # If no password is set, allow access (backward compatibility)
            if not self.password:
                return await call_next(request)
            
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Expected format: "Bearer {token}"
        try:
            scheme, credentials = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authentication scheme")
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Try JWT authentication first (new multiuser system)
        user_id = get_user_id_from_token(credentials)
        if user_id:
            # Valid JWT token - verify user exists and is active
            try:
                user = await User.get(user_id)
                if user and user.is_active:
                    # Store user info in request state for access in endpoints
                    request.state.user = user
                    request.state.user_id = user.id
                    response = await call_next(request)
                    return response
                else:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "User account is inactive"},
                        headers={"WWW-Authenticate": "Bearer"}
                    )
            except Exception as e:
                logger.warning(f"Error validating user from JWT: {str(e)}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
        
        # Fall back to password authentication (old system)
        if self.password and credentials == self.password:
            # Old password-based auth - no user context
            request.state.user = None
            request.state.user_id = None
            response = await call_next(request)
            return response
        
        # Authentication failed
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"},
            headers={"WWW-Authenticate": "Bearer"}
        )


# Optional: HTTPBearer security scheme for OpenAPI documentation
security = HTTPBearer(auto_error=False)


def check_api_password(credentials: Optional[HTTPAuthorizationCredentials] = None) -> bool:
    """
    Utility function to check API password.
    Can be used as a dependency in individual routes if needed.
    """
    password = os.environ.get("OPEN_NOTEBOOK_PASSWORD")
    
    # No password set, allow access
    if not password:
        return True
    
    # No credentials provided
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check password
    if credentials.credentials != password:
        raise HTTPException(
            status_code=401,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True