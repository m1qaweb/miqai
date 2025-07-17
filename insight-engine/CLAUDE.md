# CLAUDE.md - The Insight Engine Project Rules

## 🔄 Project Awareness & Context
- **Always read `PLANNING.md``PLANNING-BACKEND.md``product.md``structure.md``tech.md`** at the start of a new conversation to understand the project's architecture, goals, style, and constraints.
- **Check `TASK.md`** before starting a new task. If the task isn't listed, add it with a brief description and today's date.
- **Use consistent naming conventions, file structure, and architecture patterns** as described in `PLANNING.md`.
- **Use venv_linux** (the virtual environment) whenever executing Python commands, including for unit tests.

## 🏗️ Multi-Modal AI Architecture Principles
- **RAG-First Approach**: Every AI feature must be grounded in retrieved context to prevent hallucinations
- **Multi-Modal Integration**: Always process both visual and textual content from videos in parallel
- **Streaming by Default**: Implement server-sent events for all AI responses to provide real-time user feedback
- **Cost-Aware Processing**: Use Vision API for timestamp generation, never brute-force frame-by-frame analysis
- **Scalable AI Pipelines**: Design for 100+ concurrent video processing requests from day one

## 🧱 Code Structure & Modularity
- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility:
  - `orchestrator/` - FastAPI coordination and routing logic
  - `pipelines/` - RAG and clip extraction processing chains
  - `ai_engine/` - AI Decision Engine and model selection
  - `services/` - External API integrations (Vision, Speech-to-Text, etc.)
  - `storage/` - Vector database, Redis cache, and GCS operations
  - `ui/` - Next.js frontend components and streaming handlers
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use python_dotenv and load_dotenv()** for environment variables.
- **Implement proper async/await patterns** for all I/O operations, especially video processing.

## 🤖 AI & LangChain Integration
- **Use LangChain for all AI pipelines** - Never implement custom chain logic from scratch
- **Implement comprehensive logging** at every LangChain step for debugging complex chains
- **Use LangSmith for distributed tracing** of AI pipeline execution
- **Version all prompts** using MLflow with systematic A/B testing
- **Implement graceful fallback mechanisms** for chain failures (e.g., if vision fails, continue with audio-only)
- **Use Pydantic models** for all LangChain input/output validation
- **Implement proper chain state management** with error recovery and retry logic

## 🔧 Infrastructure & DevOps
- **Infrastructure as Code**: Use Terraform for all GCP resources - never manually configure cloud services
- **Containerize everything**: All services must run in containers with multi-stage builds
- **Implement CI/CD gates**: Trivy security scanning, pytest coverage >80%, performance benchmarks
- **Use semantic versioning** for all deployments with proper rollback capabilities
- **Implement proper secret management** with Google Secret Manager
- **Monitor resource usage** with custom Prometheus metrics and Grafana dashboards

## 🧪 Testing & Reliability
- **Always create Pytest unit tests for new features** (functions, classes, routes, etc).
- **After updating any logic**, check whether existing unit tests need to be updated. If so, do it.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
- **Include comprehensive test coverage**:
  - 1 test for expected use case
  - 1 edge case test
  - 1 failure case test
  - 1 integration test for AI pipelines
  - 1 performance test for video processing
- **Mock external APIs** (Vision API, Speech-to-Text) in unit tests using `pytest-mock`
- **Use fixtures** for common test data (sample videos, transcripts, embeddings)
- **Test async functions** properly with `pytest-asyncio`

## 📊 Monitoring & Observability
- **Implement custom Prometheus metrics** for:
  - Video processing latency per pipeline
  - AI model response times and costs
  - Cache hit rates (Redis semantic caching)
  - Vector search performance (Qdrant queries)
- **Use structured logging** with JSON format for all services
- **Implement distributed tracing** with LangSmith for AI pipeline debugging
- **Track business metrics** in MLflow:
  - Prompt performance scores
  - User satisfaction ratings
  - Cost per video processed
- **Set up alerting** for critical failures and performance degradation

## 🔐 Security & Compliance
- **Implement PII redaction** using Cloud DLP for all video transcripts
- **Validate all file uploads** with strict format checking and malware scanning
- **Use rate limiting** per user/API key to prevent abuse
- **Implement proper authentication** with JWT tokens and refresh logic
- **Scan container images** with Trivy - block deployments with HIGH/CRITICAL vulnerabilities
- **Use least privilege** principles for all service accounts and IAM roles
- **Encrypt all data** at rest and in transit

## 💰 Cost Optimization & FinOps
- **Track costs per operation** using custom metrics and Looker Studio dashboards
- **Implement intelligent caching** with Redis for semantic search results
- **Use Vision API efficiently** - batch requests and cache results for similar queries
- **Monitor AI model costs** in real-time with automatic alerts for budget overruns
- **Implement usage-based billing** with Stripe integration from Stage 1
- **Optimize vector storage** - use appropriate embedding dimensions and compression

## ✅ Task Completion
- **Mark completed tasks in `TASK.md`** immediately after finishing them.
- **Add new sub-tasks or TODOs** discovered during development to `TASK.md` under a "Discovered During Work" section.
- **Update progress** on multi-day tasks with specific completion percentages.
- **Link related code changes** to task completion (e.g., "Completed Task X - see commit abc123").

## 📎 Style & Conventions
- **Use Python 3.10+** as the primary language with modern type hints.
- **Follow PEP8** and format with `black` (line length: 100).
- **Use `pydantic` for all data validation** and API models.
- **Use `FastAPI` for all API endpoints** with proper OpenAPI documentation.
- **Use `SQLAlchemy` with `asyncpg`** for database operations.
- **Use `asyncio` and `aiohttp`** for all external API calls.
- **Write comprehensive docstrings** for every function using Google style:
  ```python
  async def process_video(video_path: str, user_id: str) -> ProcessingResult:
      """
      Process video through multi-modal RAG pipeline.
      
      Args:
          video_path: GCS path to uploaded video file
          user_id: Authenticated user identifier for billing
          
      Returns:
          ProcessingResult: Contains transcript, embeddings, and metadata
          
      Raises:
          VideoProcessingError: If video format is unsupported
          APIQuotaError: If external API limits are exceeded
      """
  ```

## 📚 Documentation & Explainability
- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Maintain API documentation** with FastAPI automatic OpenAPI generation.
- **Document all AI prompts** with version history and performance metrics.
- **Create architecture diagrams** for complex multi-service interactions.
- **Comment non-obvious code** especially AI pipeline logic and async operations.
- **Add inline `# Reason:` comments** for complex business logic decisions.

## 🚀 Performance & Scalability
- **Design for horizontal scaling** from day one - use stateless services.
- **Implement proper connection pooling** for database and external APIs.
- **Use caching strategically** - Redis for hot data, vector similarity for semantic queries.
- **Optimize video processing** - stream processing, parallel execution, temporary file cleanup.
- **Implement graceful degradation** - if one AI service fails, provide partial results.
- **Monitor and optimize** database queries - use proper indexing and query optimization.

## 🧠 AI Behavior Rules
- **Never assume missing context** - Ask specific questions about video formats, user requirements, or business logic.
- **Never hallucinate libraries, APIs, or functions** - Only use verified, documented endpoints and packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed or part of a task from `TASK.md`.
- **Always consider the cost implications** of AI API calls when implementing features.
- **Implement proper error handling** for all external API integrations with specific error types.
- **Use type hints everywhere** - especially for complex AI pipeline data structures.
- **Consider async/await patterns** for all I/O operations and external API calls.