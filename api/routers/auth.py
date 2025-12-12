"""
Authentication router for Open Notebook API.
Provides endpoints for user authentication and registration.
"""

import os

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from api.models import (
    PasswordChange,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from open_notebook.domain.user import User
from open_notebook.exceptions import InvalidInputError
from open_notebook.utils.jwt_auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def get_auth_status():
    """
    Check if authentication is enabled.
    Returns whether password or multiuser authentication is enabled.
    """
    # Check if old password auth is enabled
    password_auth = bool(os.environ.get("OPEN_NOTEBOOK_PASSWORD"))
    
    # Check if multiuser is enabled by checking if any users exist
    multiuser_enabled = False
    try:
        users = await User.get_all()
        multiuser_enabled = len(users) > 0
    except Exception:
        pass

    return {
        "auth_enabled": password_auth or multiuser_enabled,
        "multiuser_enabled": multiuser_enabled,
        "password_auth_enabled": password_auth,
        "message": "Authentication is required" if (password_auth or multiuser_enabled) else "Authentication is disabled"
    }


@router.post("/register", response_model=TokenResponse)
async def register_user(user_data: UserRegister):
    """
    Register a new user account.
    """
    try:
        # Create the user
        user = await User.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            is_admin=False,
        )
        
        # Generate JWT token
        token = create_access_token(user.id, user.username)
        
        # Update last login
        await user.update_last_login()
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(**user.to_dict_safe())
        )
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
async def login_user(credentials: UserLogin):
    """
    Login with username/email and password.
    Returns a JWT token for authentication.
    """
    try:
        # Try to find user by username first, then by email
        user = await User.get_by_username(credentials.username)
        if not user:
            user = await User.get_by_email(credentials.username)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Verify password
        if not user.verify_password(credentials.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(status_code=401, detail="User account is inactive")
        
        # Generate JWT token
        token = create_access_token(user.id, user.username)
        
        # Update last login
        await user.update_last_login()
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(**user.to_dict_safe())
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request):
    """
    Get the current authenticated user's profile.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return UserResponse(**user.to_dict_safe())


@router.put("/me", response_model=UserResponse)
async def update_current_user(request: Request, user_update: UserUpdate):
    """
    Update the current user's profile.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Update fields
        if user_update.email:
            # Check if email is already taken by another user
            existing_user = await User.get_by_email(user_update.email)
            if existing_user and existing_user.id != user.id:
                raise HTTPException(status_code=400, detail="Email already in use")
            user.email = user_update.email
        
        if user_update.full_name is not None:
            user.full_name = user_update.full_name
        
        await user.save()
        
        return UserResponse(**user.to_dict_safe())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail="Update failed")


@router.post("/change-password")
async def change_password(request: Request, password_data: PasswordChange):
    """
    Change the current user's password.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Verify current password
        if not user.verify_password(password_data.current_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Update password
        await user.update_password(password_data.new_password)
        
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail="Password change failed")
