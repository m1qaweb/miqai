# Design Document

## Overview

This design document outlines comprehensive improvements to the Insight Engine project to address critical quality, security, performance, and maintainability issues. The improvements are structured around a layered architecture approach that emphasizes separation of concerns, type safety, robust error handling, and production-ready practices.

The current codebase shows signs of rapid development with several areas requiring systematic improvement:

- Inconsistent error handling and logging patterns
- Security vulnerabilities in authentication and input validation
- Missing type annotations and code quality tooling
- Insufficient test coverage and testing infrastructure
- Configuration management issues
- Performance bottlenecks and monitoring gaps

## Architecture

### High-Level Architecture Improvements

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[Next.js App] --> B[API Client]
        B --> C[Error Boundary]
        C --> D[State Management]
    end

    subgraph "API Gateway Layer"
        E[FastAPI Router] --> F[Middleware Stack]
        F --> G[Authentication]
        G --> H[Rate Limiting]
        H --> I[Request Validation]
    end

    subgraph "Service Layer"
        J[Business Logic] --> K[Data Access]
        K --> L[External APIs]
        L --> M[Background Tasks]
    end

    subgraph "Infrastructure Layer"
        N[Database] --> O[Cache]
        O --> P[Message Queue]
        P --> Q[File Storage]
    end

    subgraph "Observability Layer"
        R[Logging] --> S[Metrics]
        S --> T[Tracing]
        T --> U[Health Checks]
    end

    A --> E
    J --> N
    E --> R
```

### Core Design Principles

1. **Fail Fast**: Validate configuration and dependencies at startup
2. **Defense in Depth**: Multiple layers of security validation
3. **Observability First**: Comprehensive logging, metrics, and tracing
4. **Type Safety**: Complete type annotations and validation
5. **Testability**: Dependency injection and mockable interfaces
6. **Scalability**: Async-first design with proper resource management

## Components and Interfaces

### 1. Error Handling and Logging System

#### Custom Exception Hierarchy

```python
class InsightEngineException(Exception):
    """Base exception for all application errors"""
    def __init__(self, message: str, error_code: str, context: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(self.message)

class ValidationError(InsightEngineException):
    """Raised when input validation fails"""
    pass

class AuthenticationError(InsightEngineException):
    """Raised when authentication fails"""
    pass

class ExternalServiceError(InsightEngineException):
    """Raised when external service calls fail"""
    pass
```

#### Structured Logging Framework

```python
class StructuredLogger:
    def __init__(self, name: str, correlation_id_provider: Callable[[], str]):
        self.logger = logging.getLogger(name)
        self.correlation_id_provider = correlation_id_provider

    def log(self, level: int, message: str, **kwargs):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": self.correlation_id_provider(),
            "message": message,
            **kwargs
        }
        self.logger.log(level, json.dumps(log_data))
```

#### Global Exception Handler

```python
@app.exception_handler(InsightEngineException)
async def insight_engine_exception_handler(request: Request, exc: InsightEngineException):
    logger.error(
        "Application error occurred",
        error_code=exc.error_code,
        message=exc.message,
        context=exc.context,
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "correlation_id": get_correlation_id()
            }
        }
    )
```

### 2. Security Framework

#### Enhanced Authentication System

```python
class SecurityConfig(BaseModel):
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15

class AuthenticationService:
    def __init__(self, config: SecurityConfig, user_repository: UserRepository):
        self.config = config
        self.user_repository = user_repository
        self.rate_limiter = RateLimiter()

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        # Rate limiting
        if not await self.rate_limiter.allow_request(f"auth:{username}"):
            raise AuthenticationError("Too many login attempts", "AUTH_RATE_LIMITED")

        # User validation
        user = await self.user_repository.get_by_username(username)
        if not user or not self.verify_password(password, user.password_hash):
            await self.rate_limiter.record_failed_attempt(f"auth:{username}")
            raise AuthenticationError("Invalid credentials", "AUTH_INVALID_CREDENTIALS")

        return user
```

#### Input Validation and Sanitization

```python
class InputValidator:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        # Remove path traversal attempts and dangerous characters
        sanitized = re.sub(r'[^\w\-_\.]', '', filename)
        if not sanitized or sanitized.startswith('.'):
            raise ValidationError("Invalid filename", "INVALID_FILENAME")
        return sanitized

    @staticmethod
    def validate_video_query(query: str) -> str:
        # Sanitize HTML and limit length
        clean_query = bleach.clean(query, strip=True)
        if len(clean_query) > 1000:
            raise ValidationError("Query too long", "QUERY_TOO_LONG")
        return clean_query
```

### 3. Type Safety and Code Quality System

#### Comprehensive Type Definitions

```python
from typing import Protocol, TypeVar, Generic, Union, Literal
from pydantic import BaseModel, Field, validator

T = TypeVar('T')

class Repository(Protocol[T]):
    async def get_by_id(self, id: str) -> Optional[T]: ...
    async def create(self, entity: T) -> T: ...
    async def update(self, id: str, entity: T) -> T: ...
    async def delete(self, id: str) -> bool: ...

class VideoMetadata(BaseModel):
    id: UUID
    user_id: str
    filename: str
    content_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    upload_timestamp: datetime
    processing_status: Literal["pending", "processing", "completed", "failed"]

    @validator('content_type')
    def validate_content_type(cls, v):
        allowed_types = ['video/mp4', 'video/avi', 'video/mov']
        if v not in allowed_types:
            raise ValueError(f'Content type must be one of {allowed_types}')
        return v
```

#### API Schema Definitions

```python
class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    correlation_id: str
    timestamp: datetime

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total_count: int
    page: int
    page_size: int
    has_next: bool
```

### 4. Testing Infrastructure

#### Test Configuration and Fixtures

```python
@pytest.fixture(scope="session")
async def test_db():
    """Create test database for the session"""
    test_db_url = "postgresql://test:test@localhost:5433/test_insight_engine"
    engine = create_async_engine(test_db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def test_client(test_db):
    """Create test client with test database"""
    app.dependency_overrides[get_database] = lambda: test_db
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

#### Integration Test Patterns

```python
class TestVideoUploadFlow:
    async def test_complete_upload_flow(self, test_client, mock_gcs):
        # Test authentication
        auth_response = await test_client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        token = auth_response.json()["access_token"]

        # Test upload URL generation
        upload_response = await test_client.post(
            "/v1/upload",
            json={"file_name": "test.mp4", "content_type": "video/mp4"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert upload_response.status_code == 200

        # Test video processing
        video_id = upload_response.json()["video_id"]
        # Simulate file upload to GCS
        mock_gcs.simulate_upload(video_id, "test.mp4")

        # Test summarization
        summary_response = await test_client.post(
            "/v1/summarize",
            json={"video_id": video_id, "query": "What happens in this video?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert summary_response.status_code == 200
```

### 5. Configuration Management System

#### Environment-Specific Configuration

```python
class DatabaseConfig(BaseModel):
    url: PostgresDsn
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

class RedisConfig(BaseModel):
    url: RedisDsn
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5

class Settings(BaseSettings):
    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Security
    secret_key: SecretStr
    cors_origins: List[str] = ["http://localhost:3000"]

    # Database
    database: DatabaseConfig
    redis: RedisConfig

    # External Services
    gcp_project_id: str
    gcs_bucket_videos: str
    gcs_bucket_clips: str

    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = True
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"

    @validator('debug')
    def debug_must_be_false_in_production(cls, v, values):
        if values.get('environment') == 'production' and v:
            raise ValueError('Debug must be False in production')
        return v
```

### 6. Performance and Monitoring System

#### Caching Strategy

```python
class CacheService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int = 3600
    ) -> T:
        # Try to get from cache
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        # Generate and cache
        value = await factory()
        await self.redis.setex(key, ttl, json.dumps(value, default=str))
        return value

class VideoMetadataService:
    def __init__(self, repository: VideoRepository, cache: CacheService):
        self.repository = repository
        self.cache = cache

    async def get_video_metadata(self, video_id: str) -> VideoMetadata:
        return await self.cache.get_or_set(
            f"video_metadata:{video_id}",
            lambda: self.repository.get_by_id(video_id),
            ttl=1800  # 30 minutes
        )
```

#### Metrics and Health Checks

```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Gauge('active_database_connections', 'Active database connections')

class HealthCheckService:
    def __init__(self, db_engine, redis_client, gcs_client):
        self.db_engine = db_engine
        self.redis_client = redis_client
        self.gcs_client = gcs_client

    async def check_health(self) -> Dict[str, Any]:
        checks = {
            "database": await self._check_database(),
            "redis": await self._check_redis(),
            "gcs": await self._check_gcs(),
        }

        overall_status = "healthy" if all(
            check["status"] == "healthy" for check in checks.values()
        ) else "unhealthy"

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks
        }
```

## Data Models

### Enhanced Database Schema

```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    videos = relationship("Video", back_populates="user")

class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    duration_seconds = Column(Float)
    gcs_path = Column(String(500), nullable=False)
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="videos")
    clips = relationship("VideoClip", back_populates="video")
```

### Pydantic Models with Validation

```python
class VideoCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., regex=r'^video/(mp4|avi|mov|mkv)$')

    @validator('filename')
    def validate_filename(cls, v):
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Filename contains invalid characters')
        return v

class VideoResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    duration_seconds: Optional[float]
    processing_status: ProcessingStatus
    created_at: datetime

    class Config:
        orm_mode = True
```

## Error Handling

### Comprehensive Error Handling Strategy

#### Error Categories and Responses

1. **Validation Errors (400)**: Input validation failures
2. **Authentication Errors (401)**: Invalid or missing credentials
3. **Authorization Errors (403)**: Insufficient permissions
4. **Not Found Errors (404)**: Resource not found
5. **Rate Limit Errors (429)**: Too many requests
6. **Server Errors (500)**: Internal application errors
7. **Service Unavailable (503)**: External service failures

#### Error Response Format

```python
class ErrorResponse(BaseModel):
    error: ErrorDetail
    correlation_id: str
    timestamp: datetime

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    field_errors: Optional[List[FieldError]] = None

class FieldError(BaseModel):
    field: str
    message: str
    rejected_value: Any
```

#### Retry and Circuit Breaker Patterns

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    async def call(self, func: Callable, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise ExternalServiceError("Circuit breaker is open", "CIRCUIT_BREAKER_OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"

            raise ExternalServiceError(f"External service call failed: {str(e)}", "EXTERNAL_SERVICE_ERROR")
```

## Testing Strategy

### Testing Pyramid Implementation

#### Unit Tests (70%)

- Test individual functions and methods in isolation
- Mock external dependencies
- Focus on business logic and edge cases
- Fast execution (< 1 second per test)

#### Integration Tests (20%)

- Test component interactions
- Use test databases and external service mocks
- Verify data flow between layers
- Medium execution time (< 10 seconds per test)

#### End-to-End Tests (10%)

- Test complete user workflows
- Use real or staging environments
- Verify system behavior from user perspective
- Slower execution (< 60 seconds per test)

#### Test Data Management

```python
class TestDataFactory:
    @staticmethod
    def create_user(username: str = None, email: str = None) -> User:
        return User(
            username=username or f"user_{uuid.uuid4().hex[:8]}",
            email=email or f"test_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$test_hash"
        )

    @staticmethod
    def create_video(user: User, filename: str = "test.mp4") -> Video:
        return Video(
            user_id=user.id,
            filename=filename,
            original_filename=filename,
            content_type="video/mp4",
            size_bytes=1024000,
            gcs_path=f"videos/{user.id}/{uuid.uuid4()}/{filename}"
        )
```

This design provides a comprehensive foundation for improving the Insight Engine project's quality, security, and maintainability while maintaining its core functionality and performance requirements.
