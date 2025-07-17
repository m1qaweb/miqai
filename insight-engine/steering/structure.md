# Project Structure

## Root Directory Layout

```
├── insight-engine/           # Main application directory
│   ├── src/insight_engine/   # Python backend source code
│   ├── frontend/             # Next.js frontend application
│   ├── docs/                 # Documentation
│   ├── tests/                # Test files
│   └── pyproject.toml        # Python dependencies and config
├── qdrant_storage/           # Vector database storage
├── .env                      # Environment variables
├── docker-compose.yml        # Multi-service orchestration
└── Dockerfile               # Backend container definition
```

## Backend Structure (`insight-engine/src/insight_engine/`)

```
├── main.py                   # FastAPI application entry point
├── config.py                 # Application configuration
├── dependencies.py           # FastAPI dependency injection
├── worker.py                 # ARQ background task worker
├── security.py               # Authentication and authorization
├── tracing.py                # OpenTelemetry observability
├── api/                      # REST API endpoints
├── core/                     # Core business logic
├── services/                 # External service integrations
├── modules/                  # Feature-specific modules
├── agents/                   # AI agent implementations
├── tools/                    # Utility tools and helpers
├── plugins/                  # Extensible plugin system
└── schemas/                  # Pydantic data models
```

## Frontend Structure (`insight-engine/frontend/`)

```
├── src/                      # TypeScript source code
│   ├── app/                  # Next.js App Router pages
│   ├── components/           # Reusable UI components
│   ├── lib/                  # Utility functions and configs
│   └── hooks/                # Custom React hooks
├── public/                   # Static assets
├── package.json              # Node.js dependencies
├── tailwind.config.ts        # Tailwind CSS configuration
├── components.json           # shadcn/ui component config
└── tsconfig.json             # TypeScript configuration
```

## Configuration Files

- **Environment**: `.env` files for secrets and config
- **Docker**: `docker-compose.yml` for local development
- **Python**: `pyproject.toml` with Poetry for dependency management
- **Frontend**: `package.json` for Node.js dependencies
- **Styling**: `tailwind.config.ts` for UI theming

## Key Conventions

- **Backend**: Follow FastAPI patterns with dependency injection
- **Frontend**: Use App Router with TypeScript and shadcn/ui components
- **Services**: Organize by domain (video processing, AI agents, etc.)
- **Configuration**: Environment-based config with sensible defaults
- **Containerization**: Multi-stage Docker builds for production optimization
