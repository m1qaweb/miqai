# Technology Stack

## Backend

- **Language**: Python 3.10+
- **Framework**: FastAPI 0.115.13
- **Server**: Uvicorn 0.34.3
- **Task Queue**: ARQ (Redis-based async task queue)
- **Database**: Qdrant (vector database)
- **Cache**: Redis

## Frontend

- **Framework**: Next.js 14.2+
- **Language**: TypeScript 5
- **UI Library**: Radix UI components
- **Styling**: Tailwind CSS with shadcn/ui
- **State Management**: Zustand
- **HTTP Client**: Axios with SWR for data fetching

## AI/ML Stack

- **LangChain**: 0.3.26 (orchestration framework)
- **Google AI**: Gemini models via langchain-google-genai
- **Vector Store**: Qdrant client 1.7.3
- **ML Ops**: MLflow 2.10+
- **Video Processing**: FFmpeg Python bindings

## Cloud Services (GCP)

- Google Cloud Storage
- Google Cloud Speech-to-Text
- Google Cloud Video Intelligence
- Google Cloud Pub/Sub
- Google Cloud Secret Manager
- Google Cloud DLP

## Development Tools

- **Dependency Management**: Poetry
- **Containerization**: Docker & Docker Compose
- **Observability**: OpenTelemetry
- **Security**: python-jose with cryptography

## Common Commands

### Backend Development

```bash
# Install dependencies
poetry install

# Run development server
uvicorn src.insight_engine.main:app --host 0.0.0.0 --port 8000 --reload

# Run worker
arq src.insight_engine.worker.WorkerSettings

# Run with Docker
docker-compose up
```

### Frontend Development

```bash
# Install dependencies
cd insight-engine/frontend && npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

### Testing & Quality

```bash
# Lint frontend
npm run lint

# Run tests (when available)
pytest
```
