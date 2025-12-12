"""
JWT authentication utilities for user authentication.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from loguru import logger

# Secret key for JWT - should be configured via environment variable
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production-please-use-a-secure-random-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "168"))  # 7 days default


def create_access_token(user_id: str, username: str) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: The unique identifier of the user
        username: The username of the user
        
    Returns:
        str: The JWT token
    """
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expires_at,
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Optional[dict]: The decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during JWT verification: {str(e)}")
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract the user ID from a JWT token.
    
    Args:
        token: The JWT token
        
    Returns:
        Optional[str]: The user ID if valid, None otherwise
    """
    payload = verify_token(token)
    if payload:
        return payload.get("sub")
    return None


def get_username_from_token(token: str) -> Optional[str]:
    """
    Extract the username from a JWT token.
    
    Args:
        token: The JWT token
        
    Returns:
        Optional[str]: The username if valid, None otherwise
    """
    payload = verify_token(token)
    if payload:
        return payload.get("username")
    return None
