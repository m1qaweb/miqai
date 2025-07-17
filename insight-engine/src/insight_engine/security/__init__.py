"""
Enhanced security module for the Insight Engine application.

This package provides comprehensive security features including:
- JWT authentication and authorization
- Input validation and sanitization
- File upload security
- CSRF protection
- Rate limiting
- Security audit logging
"""

from .middleware import (
    InputValidationMiddleware,
    FileUploadSecurityMiddleware,
    CSRFProtectionMiddleware,
    IPWhitelistMiddleware,
)

# Import from the main security module (now moved to security.py)
from insight_engine.security import (
    TokenData,
    UserModel,
    TokenResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    hash_password,
    verify_password,
    generate_secure_token,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    require_permissions,
    sanitize_html,
    validate_url,
    validate_file_type,
    validate_file_size,
    generate_csrf_token,
    verify_csrf_token,
    get_client_ip,
    create_rate_limit_key,
    log_security_event,
)

__all__ = [
    # Middleware
    "InputValidationMiddleware",
    "FileUploadSecurityMiddleware", 
    "CSRFProtectionMiddleware",
    "IPWhitelistMiddleware",
    
    # Models
    "TokenData",
    "UserModel",
    "TokenResponse",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    
    # Authentication functions
    "hash_password",
    "verify_password",
    "generate_secure_token",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_current_user",
    "require_permissions",
    
    # Validation functions
    "sanitize_html",
    "validate_url",
    "validate_file_type",
    "validate_file_size",
    
    # CSRF protection
    "generate_csrf_token",
    "verify_csrf_token",
    
    # Utilities
    "get_client_ip",
    "create_rate_limit_key",
    "log_security_event",
]