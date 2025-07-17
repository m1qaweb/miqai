"""
Enhanced security module with comprehensive authentication, authorization,
input validation, and security utilities.
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import bleach
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, validator

from insight_engine.config import settings
from insight_engine.exceptions import (
    AuthenticationException,
    InvalidTokenException,
    TokenExpiredException,
    InsufficientPermissionsException,
    ValidationException,
)
from insight_engine.logging_config import get_logger
from insight_engine.utils import log_warning, log_error, get_correlation_id

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Security constants
TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class TokenData(BaseModel):
    """Token payload data model."""
    user_id: str
    username: str
    email: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    token_type: str = "access"
    issued_at: datetime
    expires_at: datetime


class UserModel(BaseModel):
    """User model for authentication."""
    id: str
    username: str
    email: EmailStr
    is_active: bool = True
    is_verified: bool = False
    permissions: List[str] = Field(default_factory=list)
    created_at: datetime
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    permissions: List[str]


class PasswordResetRequest(BaseModel):
    """Password reset request model."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        
        return v


# Security utilities
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def create_access_token(
    user_id: str,
    username: str,
    email: Optional[str] = None,
    permissions: List[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token with enhanced security.
    
    Args:
        user_id: Unique user identifier
        username: Username
        email: User email address
        permissions: List of user permissions
        expires_delta: Token expiration time
    
    Returns:
        Encoded JWT token
    """
    permissions = permissions or []
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    
    issued_at = datetime.utcnow()
    
    payload = {
        "sub": user_id,
        "username": username,
        "email": email,
        "permissions": permissions,
        "token_type": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": generate_secure_token(16),  # JWT ID for token revocation
    }
    
    try:
        encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        logger.info(
            "Access token created",
            extra={
                "user_id": user_id,
                "username": username,
                "expires_at": expire.isoformat(),
                "permissions_count": len(permissions),
                "operation": "token_creation"
            }
        )
        
        return encoded_jwt
        
    except Exception as e:
        log_error(
            e,
            "Failed to create access token",
            extra_context={
                "user_id": user_id,
                "username": username,
                "operation": "token_creation_error"
            }
        )
        raise AuthenticationException(
            message="Failed to create authentication token",
            user_id=user_id
        )


def create_refresh_token(user_id: str) -> str:
    """
    Create a refresh token for token renewal.
    
    Args:
        user_id: Unique user identifier
    
    Returns:
        Encoded refresh token
    """
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": user_id,
        "token_type": "refresh",
        "exp": int(expire.timestamp()),
        "jti": generate_secure_token(16),
    }
    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
    
    Returns:
        TokenData with decoded information
    
    Raises:
        InvalidTokenException: If token is invalid
        TokenExpiredException: If token has expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenException("Token missing user identifier")
        
        # Check token expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise TokenExpiredException("Token has expired")
        
        return TokenData(
            user_id=user_id,
            username=payload.get("username", ""),
            email=payload.get("email"),
            permissions=payload.get("permissions", []),
            token_type=payload.get("token_type", "access"),
            issued_at=datetime.fromtimestamp(payload.get("iat", 0)),
            expires_at=datetime.fromtimestamp(exp) if exp else datetime.utcnow()
        )
        
    except JWTError as e:
        log_warning(
            "Invalid JWT token",
            extra_context={
                "error": str(e),
                "operation": "token_verification"
            }
        )
        raise InvalidTokenException(f"Invalid token: {str(e)}")
    
    except TokenExpiredException:
        raise
    
    except Exception as e:
        log_error(
            e,
            "Unexpected error during token verification",
            extra_context={"operation": "token_verification"}
        )
        raise InvalidTokenException("Token verification failed")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        token: JWT token from Authorization header
    
    Returns:
        TokenData with user information
    
    Raises:
        InvalidTokenException: If token is invalid
        TokenExpiredException: If token has expired
    """
    try:
        token_data = verify_token(token)
        
        # TODO: In production, validate user still exists and is active
        # user = await get_user_by_id(token_data.user_id)
        # if not user or not user.is_active:
        #     raise InvalidTokenException("User not found or inactive")
        
        return token_data
        
    except (InvalidTokenException, TokenExpiredException):
        raise
    
    except Exception as e:
        log_error(
            e,
            "Error getting current user",
            extra_context={"operation": "get_current_user"}
        )
        raise InvalidTokenException("Authentication failed")


def require_permissions(required_permissions: List[str]):
    """
    Dependency factory for permission-based authorization.
    
    Args:
        required_permissions: List of required permissions
    
    Returns:
        Dependency function that checks permissions
    """
    async def check_permissions(current_user: TokenData = Depends(get_current_user)):
        user_permissions = set(current_user.permissions)
        required_perms = set(required_permissions)
        
        if not required_perms.issubset(user_permissions):
            missing_perms = required_perms - user_permissions
            
            log_warning(
                "Insufficient permissions",
                extra_context={
                    "user_id": current_user.user_id,
                    "required_permissions": required_permissions,
                    "user_permissions": current_user.permissions,
                    "missing_permissions": list(missing_perms),
                    "operation": "permission_check"
                }
            )
            
            raise InsufficientPermissionsException(
                required_permission=", ".join(missing_perms),
                user_id=current_user.user_id
            )
        
        return current_user
    
    return check_permissions


# Input validation and sanitization
def sanitize_html(content: str, allowed_tags: List[str] = None) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Args:
        content: HTML content to sanitize
        allowed_tags: List of allowed HTML tags
    
    Returns:
        Sanitized HTML content
    """
    if allowed_tags is None:
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
    
    return bleach.clean(content, tags=allowed_tags, strip=True)


def validate_url(url: str, allowed_schemes: List[str] = None) -> bool:
    """
    Validate URL format and scheme.
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed URL schemes
    
    Returns:
        True if URL is valid, False otherwise
    """
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    try:
        parsed = urlparse(url)
        return parsed.scheme in allowed_schemes and bool(parsed.netloc)
    except Exception:
        return False


def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Validate file type based on extension.
    
    Args:
        filename: Name of the file
        allowed_extensions: List of allowed file extensions
    
    Returns:
        True if file type is allowed, False otherwise
    """
    if not filename or '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in [ext.lower() for ext in allowed_extensions]


def validate_file_size(file_size: int, max_size_mb: int = 100) -> bool:
    """
    Validate file size.
    
    Args:
        file_size: Size of the file in bytes
        max_size_mb: Maximum allowed size in MB
    
    Returns:
        True if file size is within limits, False otherwise
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes


# Security headers and CSRF protection
def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return generate_secure_token(32)


def verify_csrf_token(token: str, expected_token: str) -> bool:
    """
    Verify CSRF token using constant-time comparison.
    
    Args:
        token: Token to verify
        expected_token: Expected token value
    
    Returns:
        True if tokens match, False otherwise
    """
    return hmac.compare_digest(token, expected_token)


# Rate limiting helpers
def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    
    Args:
        request: FastAPI request object
    
    Returns:
        Client IP address
    """
    # Check for forwarded headers (when behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


def create_rate_limit_key(request: Request, identifier: str = None) -> str:
    """
    Create a rate limiting key for the request.
    
    Args:
        request: FastAPI request object
        identifier: Optional custom identifier
    
    Returns:
        Rate limiting key
    """
    if identifier:
        return f"rate_limit:{identifier}"
    
    client_ip = get_client_ip(request)
    return f"rate_limit:{client_ip}:{request.url.path}"


# Security audit logging
def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log security-related events for audit purposes.
    
    Args:
        event_type: Type of security event
        user_id: User ID if applicable
        ip_address: Client IP address
        details: Additional event details
    """
    logger.warning(
        f"Security event: {event_type}",
        extra={
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": get_correlation_id(),
            "security_audit": True
        }
    )
