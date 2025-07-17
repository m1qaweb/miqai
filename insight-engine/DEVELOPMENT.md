# Development Guide

This guide will help you set up and contribute to the Insight Engine project.

## Prerequisites

- Python 3.10 or higher
- Poetry (Python dependency management)
- Redis (for caching and task queue)
- Docker and Docker Compose (optional, for containerized development)

## Quick Start

### Automated Setup

For the fastest setup, use our automated setup scripts:

**Linux/macOS:**

```bash
./scripts/setup-dev.sh
```

**Windows:**

```powershell
.\scripts\setup-dev.ps1
```

### Manual Setup

1. **Clone the repository and navigate to the project:**

   ```bash
   cd insight-engine
   ```

2. **Install Poetry** (if not already installed):

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Install dependencies:**

   ```bash
   poetry install
   ```

4. **Set up pre-commit hooks:**

   ```bash
   poetry run pre-commit install
   ```

5. **Create environment file:**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Run initial setup:**
   ```bash
   make install-dev
   ```

## Development Workflow

### Available Commands

Use the Makefile for common development tasks:

```bash
make help          # Show all available commands
make dev           # Start development server
make worker        # Start ARQ background worker
make test          # Run tests
make test-cov      # Run tests with coverage
make lint          # Run linting checks
make format        # Format code
make type-check    # Run type checking
make quality       # Run all quality checks
make clean         # Clean up cache files
```

### Code Quality Standards

This project enforces strict code quality standards:

- **Black** for code formatting
- **isort** for import sorting
- **Ruff** for fast linting
- **mypy** for type checking
- **pytest** for testing with 80% minimum coverage

All checks run automatically via pre-commit hooks and CI/CD.

### Running the Application

1. **Start the development server:**

   ```bash
   make dev
   ```

   The API will be available at http://localhost:8000

2. **Start the background worker** (in another terminal):

   ```bash
   make worker
   ```

3. **Access API documentation:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Testing

#### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
poetry run pytest tests/test_specific.py

# Run tests matching a pattern
poetry run pytest -k "test_pattern"

# Run tests in parallel (faster)
make test-fast
```

#### Test Categories

- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete workflows

Use markers to run specific test categories:

```bash
poetry run pytest -m unit        # Run only unit tests
poetry run pytest -m integration # Run only integration tests
poetry run pytest -m "not slow"  # Skip slow tests
```

#### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names: `test_should_return_error_when_invalid_input`
- Use fixtures for common test data (see `conftest.py`)
- Mock external dependencies
- Aim for 80%+ code coverage

### Code Style and Standards

#### Type Hints

All functions must have complete type annotations:

```python
from typing import List, Optional

def process_video(video_id: str, options: Optional[dict] = None) -> List[str]:
    """Process a video and return list of generated clips."""
    pass
```

#### Error Handling

Use specific exception types and structured error responses:

```python
from src.insight_engine.exceptions import VideoNotFoundError

def get_video(video_id: str) -> Video:
    if not video_exists(video_id):
        raise VideoNotFoundError(f"Video {video_id} not found")
    return load_video(video_id)
```

#### Logging

Use structured logging with context:

```python
import logging

logger = logging.getLogger(__name__)

def process_request(request_id: str):
    logger.info("Processing request", extra={"request_id": request_id})
```

### Docker Development

#### Using Docker Compose

```bash
# Build and start all services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down

# Rebuild images
make docker-build
```

#### Services

- **app**: Main FastAPI application
- **worker**: ARQ background worker
- **redis**: Redis cache and task queue
- **qdrant**: Vector database

### Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Database
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379

# Google Cloud (for production)
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
```

### Project Structure

```
src/insight_engine/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration management
├── dependencies.py      # Dependency injection
├── api/                 # REST API endpoints
├── core/                # Core business logic
├── services/            # External service integrations
├── models/              # Data models
├── exceptions.py        # Custom exceptions
└── utils/               # Utility functions

tests/
├── conftest.py          # Test configuration and fixtures
├── unit/                # Unit tests
├── integration/         # Integration tests
└── e2e/                 # End-to-end tests
```

### Contributing

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and ensure quality:**

   ```bash
   make quality  # Run all quality checks
   ```

3. **Run tests:**

   ```bash
   make test-cov
   ```

4. **Commit your changes:**

   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push and create a pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

### Troubleshooting

#### Common Issues

1. **Poetry installation fails:**

   - Ensure Python 3.10+ is installed
   - Try installing Poetry with pip: `pip install poetry`

2. **Pre-commit hooks fail:**

   - Run `make format` to fix formatting issues
   - Check specific error messages and fix accordingly

3. **Tests fail:**

   - Ensure Redis is running for integration tests
   - Check test database configuration
   - Run tests with `-v` flag for verbose output

4. **Import errors:**
   - Ensure you're in the poetry shell: `poetry shell`
   - Check PYTHONPATH includes the src directory

#### Getting Help

- Check existing issues in the repository
- Review the API documentation at `/docs`
- Ask questions in team chat or create an issue

### Performance Tips

- Use async/await for I/O operations
- Implement caching for frequently accessed data
- Use connection pooling for database operations
- Monitor performance with the `/metrics` endpoint

### Security Considerations

- Never commit secrets to version control
- Use environment variables for configuration
- Validate all user inputs
- Implement proper authentication and authorization
- Keep dependencies updated
