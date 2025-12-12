"""
User domain model for multiuser support.
Handles user authentication, authorization, and profile management.
"""

from datetime import datetime
from typing import ClassVar, List, Optional

import bcrypt
from loguru import logger
from pydantic import EmailStr, field_validator

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.base import ObjectModel
from open_notebook.exceptions import InvalidInputError, NotFoundError


class User(ObjectModel):
    """
    User model for authentication and authorization.
    """

    table_name: ClassVar[str] = "user"
    username: str
    email: EmailStr
    password_hash: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    last_login: Optional[datetime] = None

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, v):
        if not v or not v.strip():
            raise InvalidInputError("Username cannot be empty")
        if len(v) < 3:
            raise InvalidInputError("Username must be at least 3 characters")
        if len(v) > 50:
            raise InvalidInputError("Username must be at most 50 characters")
        # Only allow alphanumeric, underscore, and hyphen
        if not all(c.isalnum() or c in "_-" for c in v):
            raise InvalidInputError(
                "Username can only contain letters, numbers, underscore, and hyphen"
            )
        return v.strip().lower()

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        if not v or not v.strip():
            raise InvalidInputError("Email cannot be empty")
        return v.strip().lower()

    @classmethod
    async def get_by_username(cls, username: str) -> Optional["User"]:
        """Get a user by username."""
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE username = $username LIMIT 1",
                {"username": username.lower()},
            )
            if result and len(result) > 0:
                return cls(**result[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by username {username}: {str(e)}")
            return None

    @classmethod
    async def get_by_email(cls, email: str) -> Optional["User"]:
        """Get a user by email."""
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE email = $email LIMIT 1",
                {"email": email.lower()},
            )
            if result and len(result) > 0:
                return cls(**result[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by email {email}: {str(e)}")
            return None

    @classmethod
    async def create_user(
        cls,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        is_admin: bool = False,
    ) -> "User":
        """
        Create a new user with hashed password.
        """
        # Check if username already exists
        existing_user = await cls.get_by_username(username)
        if existing_user:
            raise InvalidInputError(f"Username '{username}' already exists")

        # Check if email already exists
        existing_email = await cls.get_by_email(email)
        if existing_email:
            raise InvalidInputError(f"Email '{email}' already exists")

        # Hash the password
        password_hash = cls.hash_password(password)

        # Create the user
        user = cls(
            username=username.lower(),
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
            is_active=True,
            is_admin=is_admin,
        )

        await user.save()
        return user

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        if not password or len(password) < 6:
            raise InvalidInputError("Password must be at least 6 characters")
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)
        return password_hash.decode("utf-8")

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), self.password_hash.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False

    async def update_password(self, new_password: str) -> None:
        """Update the user's password."""
        self.password_hash = self.hash_password(new_password)
        await self.save()

    async def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login = datetime.now()
        await self.save()

    async def deactivate(self) -> None:
        """Deactivate the user account."""
        self.is_active = False
        await self.save()

    async def activate(self) -> None:
        """Activate the user account."""
        self.is_active = True
        await self.save()

    def to_dict_safe(self) -> dict:
        """Return a dictionary representation without sensitive fields."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created": self.created.isoformat() if self.created else None,
            "updated": self.updated.isoformat() if self.updated else None,
        }
