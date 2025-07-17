# Insight Engine

[![CI](https://github.com/your-org/insight-engine/workflows/CI/badge.svg)](https://github.com/your-org/insight-engine/actions)
[![Coverage](https://codecov.io/gh/your-org/insight-engine/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/insight-engine)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A premium AI-powered video analysis platform that extracts deep insights from video content using multi-modal AI capabilities.

## 🚀 Features

- **AI Summarization Chat**: Interactive chat interface for video content analysis using RAG
- **Object-Based Clip Extraction**: Automated detection and extraction of clips containing specific objects
- **Multi-Modal RAG Pipeline**: Processes both transcripts and visual data for comprehensive understanding
- **Dynamic AI Decision Engine**: Data-driven model selection for optimal speed/accuracy balance
- **Serverless-Oriented Architecture**: Scalable ingestion pipeline designed for cloud deployment

## 🛠️ Tech Stack

### Backend

- **Python 3.10+** with **FastAPI 0.115.13**
- **ARQ** (Redis-based async task queue)
- **Qdrant** (vector database)
- **LangChain 0.3.26** with Google AI integration
- **OpenTelemetry** for observability

### Frontend

- **Next.js 14.2+** with **TypeScript 5**
- **Radix UI** components with **Tailwind CSS**
- **Zustand** for state management
- **SWR** for data fetching

### Infrastructure

- **Docker & Docker Compose**
- **Redis** for caching and task queue
- **Google Cloud Platform** services

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Poetry (for dependency management)
- Node.js 18+ (for frontend)
- Redis (for caching and task queue)
- Docker & Docker Compose (optional)

### Automated Setup

**Linux/macOS:**

```bash
./scripts/setup-dev.sh
```

**Windows:**

```powershell
.\scripts\setup-dev.ps1
```

### Manual Setup

1. **Install dependencies:**

   ```bash
   poetry install
   ```

2. **Set up development environment:**

   ```bash
   make install-dev
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start the application:**

   ```bash
   # Backend
   make dev

   # Worker (in another terminal)
   make worker

   # Frontend (in another terminal)
   cd frontend && npm run dev
   ```

## 📖 Documentation

- **[Development Guide](DEVELOPMENT.md)** - Comprehensive development setup and workflow
- **[API Documentation](http://localhost:8000/docs)** - Interactive API documentation (when running)
- **[Architecture Overview](docs/architecture.md)** - System architecture and design decisions

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test categories
poetry run pytest -m unit        # Unit tests only
poetry run pytest -m integration # Integration tests only
```

## 🔧 Development

### Available Commands

```bash
make help          # Show all available commands
make dev           # Start development server
make worker        # Start background worker
make test          # Run tests
make test-cov      # Run tests with coverage
make lint          # Run linting checks
make format        # Format code
make type-check    # Run type checking
make quality       # Run all quality checks
make clean         # Clean up cache files
```

### Code Quality

This project enforces strict code quality standards:

- **Black** for code formatting
- **isort** for import sorting
- **Ruff** for fast linting
- **mypy** for type checking
- **pytest** for testing with 80% minimum coverage

All checks run automatically via pre-commit hooks and CI/CD.

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

frontend/
├── src/app/             # Next.js App Router pages
├── src/components/      # Reusable UI components
├── src/lib/             # Utility functions
└── src/hooks/           # Custom React hooks
```

## 🐳 Docker Development

```bash
# Start all services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

## 🔒 Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Database
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and ensure quality: `make quality`
4. Run tests: `make test-cov`
5. Commit your changes: `git commit -m 'feat: add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `test:` - Test additions or changes
- `chore:` - Maintenance tasks

## 📊 Monitoring

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics`
- **API Documentation**: `GET /docs`

## 🔧 Troubleshooting

### Common Issues

1. **Poetry installation fails**: Ensure Python 3.10+ is installed
2. **Pre-commit hooks fail**: Run `make format` to fix formatting
3. **Tests fail**: Ensure Redis is running for integration tests
4. **Import errors**: Ensure you're in the poetry shell: `poetry shell`

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed troubleshooting guide.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- UI components from [Radix UI](https://www.radix-ui.com/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)
- Vector database powered by [Qdrant](https://qdrant.tech/)
- AI orchestration with [LangChain](https://langchain.com/)
