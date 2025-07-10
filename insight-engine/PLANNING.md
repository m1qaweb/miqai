# PLANNING.md - The Insight Engine

## FEATURE:

Build **The Insight Engine**—a premium AI-powered video analysis platform featuring two core playgrounds:

### Playground 1: AI Summarization Chat

* **Multi-modal RAG Pipeline:** Users upload videos and receive intelligent summaries via a chat interface.
* **Advanced Processing:** Parallel Speech‑to‑Text and Vision API extraction for transcript and visual context.
* **Streaming Response:** Real-time, word‑by‑word AI summaries over server-sent events.
* **Context-Grounded:** RAG-based retrieval of vectorized multi-modal metadata to prevent hallucinations.
* **Trust Verification:** Display provenance and confidence scores for summary accuracy.

### Playground 2: Object-Based Clip Extraction

* **Intelligent Object Detection:** Users request objects (e.g., “logos,” “cars”) and receive timestamped clips.
* **Cost-Optimized Processing:** Use Vision API for timestamps instead of frame-by-frame analysis.
* **Scalable Clip Generation:** Serverless FFmpeg service for parallel extraction.
* **Real-time UI Updates:** Progressive clip display as they’re generated.
* **Semantic Caching:** Cache similar object requests to reduce cost and latency.

### Core Architecture Components

1. **FastAPI Orchestrator:** Central router for summarization and clip-extraction pipelines.
2. **AI Decision Engine:** Dynamic selection of models based on performance and cost metrics.
3. **Serverless Ingestion Pipeline:** Cloud Run + GCS ingestion with automatic PII redaction.
4. **Vector RAG Pipeline:** Qdrant/Vertex AI Matching Engine storage with OpenAI embedding API.
5. **Clip Extraction Service:** Scalable FFmpeg workers for clip slicing.
6. **Next.js Chat UI:** Frontend with streaming and interactive controls.
7. **Prompt Library:** Version-controlled, configurable prompt templates.

## EXAMPLES:

### `examples/agent/`

* `agent.py` — Orchestrator agent switching between summarization and clip extraction.
* `tools.py` — Video-processing and API-call helper functions.
* `prompts.py` — System and user prompts for both workflows.

### `examples/api/`

* `fastapi_orchestrator.py` — FastAPI app with async endpoints.
* `streaming_response.py` — SSE implementation for streaming updates.
* `error_handling.py` — Video-processing error management.

### `examples/video_processing/`

* `multimodal_extractor.py` — Parallel speech and vision analysis.
* `clip_generator.py` — FFmpeg-based clip slicing.
* `vector_storage.py` — Embedding generation and vector DB operations.

### `examples/ui/`

* `chat_interface.py` — React/Next.js streaming chat component.
* `clip_carousel.py` — Progressive clip display widget.
* `upload_handler.py` — Secure video upload with progress.

### `examples/infrastructure/`

* `terraform_main.tf` — GCP IaC.
* `cloud_run_config.py` — Serverless deployment settings.
* `vector_db_setup.py` — Qdrant/Matching Engine init.
* `redis_cache.py` — Redis config for semantic cache.

### `examples/tests/`

* `test_rag_pipeline.py` — Tests for RAG workflow.
* `test_clip_extraction.py` — Tests for object and clip logic.
* `test_orchestrator.py` — End-to-end orchestrator tests.
* `test_langchain_pipeline.py` — LangChain integration tests.
* `test_security_dlp.py` — PII redaction tests.

## DOCUMENTATION:

### AI/ML APIs

* **Speech-to-Text:** [https://cloud.google.com/speech-to-text/docs](https://cloud.google.com/speech-to-text/docs)
* **Vision API:** [https://cloud.google.com/vision/docs](https://cloud.google.com/vision/docs)
* **Vertex AI:** [https://cloud.google.com/vertex-ai/docs](https://cloud.google.com/vertex-ai/docs)
* **OpenAI Embeddings:** [https://platform.openai.com/docs/guides/embeddings](https://platform.openai.com/docs/guides/embeddings)
* **Gemini API:** [https://ai.google.dev/gemini-api/docs](https://ai.google.dev/gemini-api/docs)

### Infrastructure & DevOps

* **Cloud Run:** [https://cloud.google.com/run/docs](https://cloud.google.com/run/docs)
* **Cloud Storage:** [https://cloud.google.com/storage/docs](https://cloud.google.com/storage/docs)
* **DLP:** [https://cloud.google.com/dlp/docs](https://cloud.google.com/dlp/docs)
* **Qdrant:** [https://qdrant.tech/documentation/](https://qdrant.tech/documentation/)
* **Memorystore (Redis):** [https://cloud.google.com/memorystore/docs/redis](https://cloud.google.com/memorystore/docs/redis)
* **Terraform:** [https://registry.terraform.io/providers/hashicorp/google/latest/docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
* **GitHub Actions:** [https://docs.github.com/en/actions](https://docs.github.com/en/actions)

### Frameworks & Libraries

* **FastAPI:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
* **Next.js:** [https://nextjs.org/docs](https://nextjs.org/docs)
* **LangChain:** [https://python.langchain.com/docs/get\_started/introduction](https://python.langchain.com/docs/get_started/introduction)
* **Pydantic:** [https://docs.pydantic.dev/](https://docs.pydantic.dev/)
* **SQLAlchemy:** [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
* **ffmpeg-python:** [https://github.com/kkroening/ffmpeg-python](https://github.com/kkroening/ffmpeg-python)
* **SSE Responses:** [https://fastapi.tiangolo.com/advanced/custom-response/](https://fastapi.tiangolo.com/advanced/custom-response/)

### Monitoring & Observability

* **Cloud Monitoring:** [https://cloud.google.com/monitoring/docs](https://cloud.google.com/monitoring/docs)
* **Stripe API:** [https://stripe.com/docs/api](https://stripe.com/docs/api)
* **MLflow:** [https://mlflow.org/docs/latest/index.html](https://mlflow.org/docs/latest/index.html)
* **Prometheus:** [https://prometheus.io/docs](https://prometheus.io/docs)
* **Grafana:** [https://grafana.com/docs](https://grafana.com/docs)
* **Looker Studio:** [https://support.google.com/looker-studio](https://support.google.com/looker-studio)
* **Trivy:** [https://aquasecurity.github.io/trivy/](https://aquasecurity.github.io/trivy/)

## OTHER CONSIDERATIONS:

### Technical Gotchas

1. **Memory Management:** Stream and chunk large videos; avoid full in-memory loads.
2. **Partial Failures:** Speech or vision failure should not abort entire workflow.
3. **Serverless Limits:** Chunk long videos; implement retry and resume for FFmpeg tasks.
4. **Async Complexity:** Ensure proper cancellation and cleanup on disconnect.

### LangChain Complexity

5. **State Management:** Use LangSmith tracing and detailed logs.
6. **Prompt Versioning:** Track via MLflow; A/B test before deploy.
7. **Embedding Consistency:** Align model versions and dimensions.
8. **Streaming Edge Cases:** Handle client disconnects gracefully.

### Infra & DevOps Gotchas

9. **Remote Tfstate:** Use GCS backend and state locking.
10. **Container Security:** Trivy scan in CI; block critical findings.
11. **Cache Invalidation:** Tune similarity thresholds to avoid stale data.
12. **Experiment Tracking:** Tag MLflow runs per feature and version.

### Performance Targets

* **Summarization:** <30 s for 10 min videos
* **Clip Extraction:** <10 s per clip
* **Concurrency:** 100+ parallel uploads
* **Cost:** <\$0.10 per video hour for Vision API
* **Cache Hit:** >80% Redis hit rate
* **Latency:** <100 ms vector search

### Security & Compliance

* **PII Redaction:** DLP for transcripts.
* **File Validation:** Strict format checks and malware scanning.
* **Rate Limiting:** Per-user API quotas.
* **Key Management:** Secure storage and rotation.
* **Network Policies:** Terraform-managed security groups.

### AI QA

* **Grounding:** Always cite RAG sources.
* **Confidence:** Thresholds for detection.
* **Feedback Loops:** Collect user feedback in UI.
* **Versioning:** Record prompt/model combos.

### Scalability

* **Sharding:** Plan vector DB for >1M embeddings.
* **CDN:** Use CloudFront for clip delivery.
* **Auto-scaling:** Configure Cloud Run concurrency.
* **Cost Dashboard:** Track per-user/feature costs.

### Stage Notes

* **Stage 1 (Wks 1–4):** MVP features over optimizations.
* **Stage 2 (Wks 5–10):** Decision Engine and feedback loops.
* **Stage 3 (Wks 11+):** Monetization, API docs, portal.

### Testing Strategy

* **Unit Tests:** Component isolation.
* **Integration Tests:** E2E workflows.
* **Performance Tests:** Load with realistic video sizes.
* **Cost Tests:** Validate real cost vs. estimates.
