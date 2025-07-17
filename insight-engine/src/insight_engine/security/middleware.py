"""
Enhanced security middleware for comprehensive protection.

This module provides middleware for input validation, file upload security,
CSRF protection, and additional security measures.
"""

import hashlib
import mimetypes
import time
from typing import List, Optional, Set
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, UploadFile, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from insight_engine.config import settings
from insight_engine.exceptions import ValidationException, RateLimitExceededException
from insight_engine.logging_config import get_logger
from insight_engine.security import (
    get_client_ip,
    log_security_event,
    validate_file_type,
    validate_file_size,
)

logger = get_logger(__name__)


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for comprehensive input validation and sanitization.
    
    Validates request parameters, headers, and body content to prevent
    injection attacks and malicious input.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        blocked_patterns: List[str] = None,
        blocked_headers: List[str] = None
    ):
        super().__init__(app)
        self.max_request_size = max_request_size
        self.blocked_patterns = blocked_patterns or [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            r'onclick\s*=',
            r'eval\s*\(',
            r'expression\s*\(',
            r'url\s*\(',
            r'import\s+',
            r'@import',
            r'\\x[0-9a-fA-F]{2}',
            r'&#x[0-9a-fA-F]+;',
        ]
        self.blocked_headers = blocked_headers or [
            'x-forwarded-host',
            'x-original-host',
            'x-rewrite-url'
        ]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = get_client_ip(request)
        
        # Validate request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            log_security_event(
                "request_too_large",
                ip_address=client_ip,
                details={
                    "content_length": content_length,
                    "max_allowed": self.max_request_size,
                    "path": str(request.url.path)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request entity too large"
            )
        
        # Validate headers
        for header_name, header_value in request.headers.items():
            if header_name.lower() in self.blocked_headers:
                log_security_event(
                    "blocked_header_detected",
                    ip_address=client_ip,
                    details={
                        "header": header_name,
                        "value": header_value[:100],  # Truncate for logging
                        "path": str(request.url.path)
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request headers"
                )
            
            # Check for malicious patterns in headers
            if self._contains_malicious_pattern(header_value):
                log_security_event(
                    "malicious_header_pattern",
                    ip_address=client_ip,
                    details={
                        "header": header_name,
                        "path": str(request.url.path)
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request headers"
                )
        
        # Validate query parameters
        for param_name, param_value in request.query_params.items():
            if self._contains_malicious_pattern(param_value):
                log_security_event(
                    "malicious_query_parameter",
                    ip_address=client_ip,
                    details={
                        "parameter": param_name,
                        "path": str(request.url.path)
                    }
                )
                raise ValidationException(
                    message="Invalid query parameter",
                    field=param_name,
                    value=param_value[:100]  # Truncate for security
                )
        
        # Validate URL path
        if self._contains_malicious_pattern(str(request.url.path)):
            log_security_event(
                "malicious_url_path",
                ip_address=client_ip,
                details={"path": str(request.url.path)}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request path"
            )
        
        return await call_next(request)
    
    def _contains_malicious_pattern(self, text: str) -> bool:
        """Check if text contains malicious patterns."""
        import re
        
        text_lower = text.lower()
        for pattern in self.blocked_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False


class FileUploadSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for secure file upload handling.
    
    Validates file types, sizes, and scans for malicious content.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allowed_extensions: List[str] = None,
        max_file_size_mb: int = 100,
        scan_for_malware: bool = True,
        quarantine_suspicious: bool = True
    ):
        super().__init__(app)
        self.allowed_extensions = allowed_extensions or [
            'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv',
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',
            'pdf', 'txt', 'doc', 'docx'
        ]
        self.max_file_size_mb = max_file_size_mb
        self.scan_for_malware = scan_for_malware
        self.quarantine_suspicious = quarantine_suspicious
        
        # Suspicious file signatures (magic bytes)
        self.suspicious_signatures = {
            b'\x4D\x5A': 'PE executable',
            b'\x7F\x45\x4C\x46': 'ELF executable',
            b'\xCA\xFE\xBA\xBE': 'Java class file',
            b'\xFE\xED\xFA\xCE': 'Mach-O executable',
            b'\x50\x4B\x03\x04': 'ZIP archive (potential)',
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Only process requests with file uploads
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            return await call_next(request)
        
        client_ip = get_client_ip(request)
        
        # Note: In a real implementation, you would need to parse the multipart
        # form data to extract files. This is a simplified example.
        # For actual file validation, you'd typically do this in the endpoint
        # using FastAPI's UploadFile dependency.
        
        return await call_next(request)
    
    async def validate_upload_file(
        self,
        file: UploadFile,
        client_ip: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Validate an uploaded file for security.
        
        Args:
            file: The uploaded file
            client_ip: Client IP address
            user_id: User ID if authenticated
        
        Raises:
            ValidationException: If file validation fails
        """
        # Validate file extension
        if not validate_file_type(file.filename, self.allowed_extensions):
            log_security_event(
                "invalid_file_type",
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "filename": file.filename,
                    "content_type": file.content_type
                }
            )
            raise ValidationException(
                message="File type not allowed",
                field="file",
                value=file.filename
            )
        
        # Read file content for validation
        content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        # Validate file size
        file_size = len(content)
        if not validate_file_size(file_size, self.max_file_size_mb):
            log_security_event(
                "file_too_large",
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "filename": file.filename,
                    "size_bytes": file_size,
                    "max_size_mb": self.max_file_size_mb
                }
            )
            raise ValidationException(
                message=f"File too large. Maximum size: {self.max_file_size_mb}MB",
                field="file",
                value=f"{file_size} bytes"
            )
        
        # Validate MIME type matches extension
        expected_mime = mimetypes.guess_type(file.filename)[0]
        if expected_mime and file.content_type != expected_mime:
            log_security_event(
                "mime_type_mismatch",
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "filename": file.filename,
                    "declared_type": file.content_type,
                    "expected_type": expected_mime
                }
            )
            # This might be too strict for some use cases
            logger.warning(
                "MIME type mismatch detected",
                extra={
                    "filename": file.filename,
                    "declared": file.content_type,
                    "expected": expected_mime
                }
            )
        
        # Scan for suspicious file signatures
        if self.scan_for_malware:
            await self._scan_file_content(content, file.filename, client_ip, user_id)
    
    async def _scan_file_content(
        self,
        content: bytes,
        filename: str,
        client_ip: str,
        user_id: Optional[str] = None
    ) -> None:
        """Scan file content for malicious signatures."""
        # Check file signatures
        for signature, description in self.suspicious_signatures.items():
            if content.startswith(signature):
                log_security_event(
                    "suspicious_file_signature",
                    user_id=user_id,
                    ip_address=client_ip,
                    details={
                        "filename": filename,
                        "signature": description,
                        "file_hash": hashlib.sha256(content).hexdigest()[:16]
                    }
                )
                
                if self.quarantine_suspicious:
                    raise ValidationException(
                        message="File contains suspicious content",
                        field="file",
                        value=filename
                    )
        
        # Additional content scanning could be added here
        # - Virus scanning with ClamAV
        # - Content analysis for embedded scripts
        # - Metadata extraction and validation


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for CSRF (Cross-Site Request Forgery) protection.
    
    Validates CSRF tokens for state-changing requests.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        exempt_paths: List[str] = None,
        token_header: str = "X-CSRF-Token",
        cookie_name: str = "csrf_token"
    ):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/docs", "/redoc", "/openapi.json", "/health", "/metrics"
        ]
        self.token_header = token_header
        self.cookie_name = cookie_name
        self.state_changing_methods = {"POST", "PUT", "PATCH", "DELETE"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip CSRF protection for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Skip for safe methods
        if request.method not in self.state_changing_methods:
            return await call_next(request)
        
        client_ip = get_client_ip(request)
        
        # Get CSRF token from header
        csrf_token = request.headers.get(self.token_header)
        if not csrf_token:
            log_security_event(
                "missing_csrf_token",
                ip_address=client_ip,
                details={
                    "method": request.method,
                    "path": str(request.url.path)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token required"
            )
        
        # In a real implementation, you would validate the token
        # against a stored value (in session, database, etc.)
        # For now, we'll just check that it exists and has proper format
        if len(csrf_token) < 32:
            log_security_event(
                "invalid_csrf_token",
                ip_address=client_ip,
                details={
                    "method": request.method,
                    "path": str(request.url.path),
                    "token_length": len(csrf_token)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
        
        return await call_next(request)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Middleware for IP address whitelisting.
    
    Restricts access to specific IP addresses or ranges.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allowed_ips: List[str] = None,
        allowed_networks: List[str] = None,
        exempt_paths: List[str] = None
    ):
        super().__init__(app)
        self.allowed_ips = set(allowed_ips or [])
        self.allowed_networks = allowed_networks or []
        self.exempt_paths = exempt_paths or ["/health"]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Skip if no restrictions configured
        if not self.allowed_ips and not self.allowed_networks:
            return await call_next(request)
        
        client_ip = get_client_ip(request)
        
        # Check if IP is in allowed list
        if client_ip in self.allowed_ips:
            return await call_next(request)
        
        # Check if IP is in allowed networks
        if self._is_ip_in_networks(client_ip):
            return await call_next(request)
        
        log_security_event(
            "ip_access_denied",
            ip_address=client_ip,
            details={
                "path": str(request.url.path),
                "method": request.method
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    def _is_ip_in_networks(self, ip: str) -> bool:
        """Check if IP address is in any of the allowed networks."""
        import ipaddress
        
        try:
            ip_addr = ipaddress.ip_address(ip)
            for network in self.allowed_networks:
                if ip_addr in ipaddress.ip_network(network, strict=False):
                    return True
        except ValueError:
            pass
        
        return False