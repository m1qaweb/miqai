"""
Unit tests for authentication service and security functions.

This module tests JWT token creation, validation, password hashing,
and authentication-related utilities.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from insight_engine.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    generate_secure_token,
    TokenData,
    PasswordResetConfirm,
)
from insight_engine.exceptions import (
    InvalidTokenException,
    TokenExpiredException,
    ValidationException,
)


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_hash_password_creates_hash(self):
        """Test that password hashing creates a hash."""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 20  # bcrypt hashes are long
        assert hashed.startswith("$2b$")  # bcrypt prefix
    
    def test_verify_password_with_correct_password(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_with_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_hash_password_different_results(self):
        """Test that hashing the same password twice gives different results."""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2  # Salt makes them different
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestTokenGeneration:
    """Test JWT token generation and utilities."""
    
    def test_generate_secure_token_default_length(self):
        """Test secure token generation with default length."""
        token = generate_secure_token()
        
        assert isinstance(token, str)
        assert len(token) > 30  # URL-safe base64 encoding
    
    def test_generate_secure_token_custom_length(self):
        """Test secure token generation with custom length."""
        token = generate_secure_token(16)
        
        assert isinstance(token, str)
        # URL-safe base64 encoding makes it longer than input
        assert len(token) >= 16
    
    def test_generate_secure_token_uniqueness(self):
        """Test that generated tokens are unique."""
        token1 = generate_secure_token()
        token2 = generate_secure_token()
        
        assert token1 != token2


class TestJWTTokens:
    """Test JWT token creation and validation."""
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for token creation."""
        return {
            "user_id": "test-user-123",
            "username": "testuser",
            "email": "test@example.com",
            "permissions": ["read", "write"]
        }
    
    def test_create_access_token_success(self, sample_user_data):
        """Test successful access token creation."""
        token = create_access_token(
            user_id=sample_user_data["user_id"],
            username=sample_user_data["username"],
            email=sample_user_data["email"],
            permissions=sample_user_data["permissions"]
        )
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long
        assert token.count('.') == 2  # JWT has 3 parts separated by dots
    
    def test_create_access_token_with_custom_expiration(self, sample_user_data):
        """Test access token creation with custom expiration."""
        expires_delta = timedelta(hours=2)
        token = create_access_token(
            user_id=sample_user_data["user_id"],
            username=sample_user_data["username"],
            expires_delta=expires_delta
        )
        
        assert isinstance(token, str)
        # Verify token can be decoded (basic structure test)
        token_data = verify_token(token)
        assert token_data.user_id == sample_user_data["user_id"]
    
    def test_create_refresh_token_success(self):
        """Test successful refresh token creation."""
        user_id = "test-user-123"
        token = create_refresh_token(user_id)
        
        assert isinstance(token, str)
        assert len(token) > 50
        assert token.count('.') == 2
    
    def test_verify_token_success(self, sample_user_data):
        """Test successful token verification."""
        token = create_access_token(
            user_id=sample_user_data["user_id"],
            username=sample_user_data["username"],
            email=sample_user_data["email"],
            permissions=sample_user_data["permissions"]
        )
        
        token_data = verify_token(token)
        
        assert isinstance(token_data, TokenData)
        assert token_data.user_id == sample_user_data["user_id"]
        assert token_data.username == sample_user_data["username"]
        assert token_data.email == sample_user_data["email"]
        assert token_data.permissions == sample_user_data["permissions"]
        assert token_data.token_type == "access"
    
    def test_verify_token_invalid_format(self):
        """Test token verification with invalid format."""
        invalid_token = "invalid.token.format"
        
        with pytest.raises(InvalidTokenException) as exc_info:
            verify_token(invalid_token)
        
        assert "Invalid token" in str(exc_info.value)
    
    def test_verify_token_missing_user_id(self):
        """Test token verification with missing user ID."""
        # Create a token manually without user ID
        import jwt
        from insight_engine.config import settings
        
        payload = {
            "username": "testuser",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        with pytest.raises(InvalidTokenException) as exc_info:
            verify_token(token)
        
        assert "missing user identifier" in str(exc_info.value)
    
    @patch('insight_engine.security.datetime')
    def test_verify_token_expired(self, mock_datetime, sample_user_data):
        """Test token verification with expired token."""
        # Create token that expires immediately
        past_time = datetime.utcnow() - timedelta(hours=1)
        mock_datetime.utcnow.return_value = past_time
        
        token = create_access_token(
            user_id=sample_user_data["user_id"],
            username=sample_user_data["username"],
            expires_delta=timedelta(seconds=1)
        )
        
        # Reset mock to current time
        mock_datetime.utcnow.return_value = datetime.utcnow()
        
        with pytest.raises(TokenExpiredException):
            verify_token(token)


class TestPasswordValidation:
    """Test password validation and strength checking."""
    
    def test_password_reset_confirm_valid_password(self):
        """Test password reset with valid strong password."""
        reset_data = PasswordResetConfirm(
            token="valid-reset-token",
            new_password="StrongP@ssw0rd123"
        )
        
        assert reset_data.new_password == "StrongP@ssw0rd123"
    
    def test_password_reset_confirm_weak_password(self):
        """Test password reset with weak password."""
        with pytest.raises(ValidationException):
            PasswordResetConfirm(
                token="valid-reset-token",
                new_password="weak"
            )
    
    def test_password_reset_confirm_no_uppercase(self):
        """Test password validation without uppercase letter."""
        with pytest.raises(ValidationException):
            PasswordResetConfirm(
                token="valid-reset-token",
                new_password="lowercase123!"
            )
    
    def test_password_reset_confirm_no_lowercase(self):
        """Test password validation without lowercase letter."""
        with pytest.raises(ValidationException):
            PasswordResetConfirm(
                token="valid-reset-token",
                new_password="UPPERCASE123!"
            )
    
    def test_password_reset_confirm_no_digit(self):
        """Test password validation without digit."""
        with pytest.raises(ValidationException):
            PasswordResetConfirm(
                token="valid-reset-token",
                new_password="NoDigits!"
            )
    
    def test_password_reset_confirm_no_special_char(self):
        """Test password validation without special character."""
        with pytest.raises(ValidationException):
            PasswordResetConfirm(
                token="valid-reset-token",
                new_password="NoSpecialChar123"
            )


class TestAuthenticationIntegration:
    """Integration tests for authentication components."""
    
    @pytest.fixture
    def mock_user_service(self):
        """Mock user service for testing."""
        mock_service = MagicMock()
        mock_service.get_user_by_id.return_value = {
            "id": "test-user-123",
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "permissions": ["read", "write"]
        }
        return mock_service
    
    def test_full_authentication_flow(self, mock_user_service):
        """Test complete authentication flow."""
        # 1. Create user with hashed password
        password = "TestPassword123!"
        hashed_password = hash_password(password)
        
        # 2. Verify password
        assert verify_password(password, hashed_password) is True
        
        # 3. Create access token
        token = create_access_token(
            user_id="test-user-123",
            username="testuser",
            email="test@example.com",
            permissions=["read", "write"]
        )
        
        # 4. Verify token
        token_data = verify_token(token)
        assert token_data.user_id == "test-user-123"
        assert token_data.username == "testuser"
        
        # 5. Create refresh token
        refresh_token = create_refresh_token("test-user-123")
        assert isinstance(refresh_token, str)
    
    def test_token_lifecycle(self):
        """Test token creation, verification, and expiration."""
        user_id = "test-user-123"
        
        # Create short-lived token
        token = create_access_token(
            user_id=user_id,
            username="testuser",
            expires_delta=timedelta(seconds=2)
        )
        
        # Verify token is valid
        token_data = verify_token(token)
        assert token_data.user_id == user_id
        
        # Wait for token to expire (in real test, we'd mock time)
        import time
        time.sleep(3)
        
        # Token should now be expired
        with pytest.raises(TokenExpiredException):
            verify_token(token)


@pytest.mark.unit
class TestSecurityUtilities:
    """Test security utility functions."""
    
    def test_token_data_model_creation(self):
        """Test TokenData model creation and validation."""
        token_data = TokenData(
            user_id="test-user-123",
            username="testuser",
            email="test@example.com",
            permissions=["read", "write"],
            token_type="access",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        assert token_data.user_id == "test-user-123"
        assert token_data.username == "testuser"
        assert token_data.token_type == "access"
        assert len(token_data.permissions) == 2
    
    def test_token_data_model_defaults(self):
        """Test TokenData model with default values."""
        now = datetime.utcnow()
        token_data = TokenData(
            user_id="test-user-123",
            username="testuser",
            token_type="access",
            issued_at=now,
            expires_at=now + timedelta(hours=1)
        )
        
        assert token_data.email is None
        assert token_data.permissions == []
        assert token_data.token_type == "access"