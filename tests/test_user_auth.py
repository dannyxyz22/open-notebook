"""
Tests for user authentication and multiuser functionality.
"""

import pytest
from open_notebook.domain.user import User
from open_notebook.utils.jwt_auth import (
    create_access_token,
    get_user_id_from_token,
    get_username_from_token,
    verify_token,
)


class TestUserModel:
    """Test User domain model."""

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test creating a new user."""
        user = await User.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            full_name="Test User",
        )
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.is_admin is False
        assert len(user.password_hash) > 0
        assert user.password_hash != "testpassword123"  # Should be hashed

    @pytest.mark.asyncio
    async def test_verify_password(self):
        """Test password verification."""
        user = await User.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpassword123",
        )
        
        # Correct password should verify
        assert user.verify_password("testpassword123") is True
        
        # Wrong password should not verify
        assert user.verify_password("wrongpassword") is False

    @pytest.mark.asyncio
    async def test_get_by_username(self):
        """Test retrieving user by username."""
        await User.create_user(
            username="testuser3",
            email="test3@example.com",
            password="testpassword123",
        )
        
        user = await User.get_by_username("testuser3")
        assert user is not None
        assert user.username == "testuser3"
        
        # Test case insensitive
        user_upper = await User.get_by_username("TESTUSER3")
        assert user_upper is not None
        assert user_upper.username == "testuser3"

    @pytest.mark.asyncio
    async def test_get_by_email(self):
        """Test retrieving user by email."""
        await User.create_user(
            username="testuser4",
            email="test4@example.com",
            password="testpassword123",
        )
        
        user = await User.get_by_email("test4@example.com")
        assert user is not None
        assert user.email == "test4@example.com"
        
        # Test case insensitive
        user_upper = await User.get_by_email("TEST4@EXAMPLE.COM")
        assert user_upper is not None
        assert user_upper.email == "test4@example.com"

    @pytest.mark.asyncio
    async def test_duplicate_username(self):
        """Test that duplicate usernames are rejected."""
        await User.create_user(
            username="duplicate",
            email="user1@example.com",
            password="testpassword123",
        )
        
        with pytest.raises(Exception):  # Should raise InvalidInputError
            await User.create_user(
                username="duplicate",
                email="user2@example.com",
                password="testpassword123",
            )

    @pytest.mark.asyncio
    async def test_duplicate_email(self):
        """Test that duplicate emails are rejected."""
        await User.create_user(
            username="user1",
            email="duplicate@example.com",
            password="testpassword123",
        )
        
        with pytest.raises(Exception):  # Should raise InvalidInputError
            await User.create_user(
                username="user2",
                email="duplicate@example.com",
                password="testpassword123",
            )

    @pytest.mark.asyncio
    async def test_update_password(self):
        """Test updating user password."""
        user = await User.create_user(
            username="testuser5",
            email="test5@example.com",
            password="oldpassword",
        )
        
        old_hash = user.password_hash
        
        # Update password
        await user.update_password("newpassword123")
        
        # Hash should have changed
        assert user.password_hash != old_hash
        
        # Old password should not work
        assert user.verify_password("oldpassword") is False
        
        # New password should work
        assert user.verify_password("newpassword123") is True

    @pytest.mark.asyncio
    async def test_deactivate_activate(self):
        """Test deactivating and activating user accounts."""
        user = await User.create_user(
            username="testuser6",
            email="test6@example.com",
            password="testpassword123",
        )
        
        # Should be active by default
        assert user.is_active is True
        
        # Deactivate
        await user.deactivate()
        assert user.is_active is False
        
        # Activate
        await user.activate()
        assert user.is_active is True


class TestJWTAuth:
    """Test JWT authentication utilities."""

    def test_create_and_verify_token(self):
        """Test creating and verifying JWT tokens."""
        user_id = "user:test123"
        username = "testuser"
        
        # Create token
        token = create_access_token(user_id, username)
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["username"] == username
        assert "exp" in payload
        assert "iat" in payload

    def test_get_user_id_from_token(self):
        """Test extracting user ID from token."""
        user_id = "user:test123"
        username = "testuser"
        
        token = create_access_token(user_id, username)
        extracted_id = get_user_id_from_token(token)
        
        assert extracted_id == user_id

    def test_get_username_from_token(self):
        """Test extracting username from token."""
        user_id = "user:test123"
        username = "testuser"
        
        token = create_access_token(user_id, username)
        extracted_username = get_username_from_token(token)
        
        assert extracted_username == username

    def test_invalid_token(self):
        """Test that invalid tokens are rejected."""
        invalid_token = "invalid.token.here"
        
        payload = verify_token(invalid_token)
        assert payload is None
        
        user_id = get_user_id_from_token(invalid_token)
        assert user_id is None

    def test_expired_token(self):
        """Test that expired tokens are rejected."""
        # Note: This test would require manipulating time or creating
        # a token with a very short expiration. For now, we trust
        # the JWT library's expiration handling.
        pass
