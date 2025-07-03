# Design: Shadow Testing & Canary Deployment Strategy

**Version:** 1.0
**Author:** Architect Mode
**Status:** Proposed

## 1. Overview & Strategic Goals

This document outlines a sophisticated, registry-driven architecture for safely validating and deploying new AI models. The strategy incorporates both Shadow Testing for offline validation and Canary Deployments for low-risk, live traffic testing.

### 1.1. Strategic Goals

- **From Validation to Continuous Improvement:** This system is not just a safety net; it's an engine for continuous improvement. By providing high-fidelity comparisons, it will surface subtle regressions and improvements, guiding future research and optimization efforts.
- **Trust and Automation:** The primary goal is to build trust in the automated model lifecycle. The system will enable automated promotions for clear wins while ensuring rigorous, human-in-the-loop governance for complex cases.
- **Decoupled & Scalable Architecture:** The design ensures that adding shadowing and canary capabilities does not degrade the performance or maintainability of the core pipeline.

## 2. Architecture: A Decoupled, Registry-Driven Approach

The architecture is driven by the `Model Registry`, which acts as the single source of truth for model states (`PRODUCTION`, `CANDIDATE`, `SHADOW`, `CANARY`). This decouples the control plane (governance) from the data plane (live requests).

```mermaid
graph TD
    subgraph Control Plane
        MR(Model Registry)
        GD(Governance Dashboard)
        GD -- Manages States --> MR
    end

    subgraph Data Plane
        A[API: /analyze_video] --> B(PipelineService)
        B -- "1. Get Models (prod, shadow?)" --> MR
        B -- "2. Send Request" --> R(Inference Router)

        subgraph Shadowing Flow
            R -- "Fire-and-Forget" --> SS(Shadowing Service)
            SS -- "Async Call" --> IC_Shadow[InferenceService (Candidate)]
            IC_Shadow -- "Result" --> CS(Comparison Service)
            CS -- "Writes Report" --> DB[(Report Database)]
            GD -- "Reads Report" --> DB
        end

        subgraph Live Traffic Flow
            R -- "Weighted Split (e.g., 99% / 1%)" --> IP[InferenceService (Production)]
            R -- " " --> IC_Canary[InferenceService (Canary)]
            IP -- "Result" --> FinalResponse{User Response}
            IC_Canary -- "Result" --> FinalResponse
        end
    end

    subgraph Observability
        IP -- "Metrics" --> M[Observability Stack]
        IC_Canary -- "Metrics" --> M
        M -- "Alerts (Latency, Errors)" --> R
        M -- " " --> GD
    end

    style R fill:#dae8fc
    style SS fill:#f8cecc
    style CS fill:#f5f5f5
```

## 3. Component Design

### 3.1. `InferenceRouter` (Smart Gateway)

A dynamic, policy-driven gateway that directs traffic based on rules from the `Model Registry`.

- **Implementation:** A dedicated lightweight service (e.g., FastAPI) or leveraging a service mesh sidecar (e.g., Istio, Linkerd).
- **Dynamic Configuration:** Periodically polls the `Model Registry` for the current routing table (e.g., `{"model_A": {"production": "v3", "canary": "v4", "canary_percent": 5}}`). This allows for near-instant changes without redeployment.
- **Health-Aware Routing:** Actively probes the health endpoints of all `InferenceService` instances. If a canary instance fails, the router will automatically divert traffic away from it, providing resilience.

### 3.2. `ShadowingService`

This service decouples the `PipelineService` from the complexity of shadowing.

- **Logic:** It receives a fire-and-forget request from the router, calls the candidate model, and orchestrates the comparison. This keeps the main pipeline clean and focused on production delivery.
- **Input:** `(video_id, request_data, production_model_version, candidate_model_version)`
- **Output:** Triggers the `ComparisonService`.

### 3.3. `ComparisonService` (V1: Foundational Metrics)

This service generates a comparison report. The initial version will focus on core stability and performance metrics, with the system designed to easily incorporate more advanced analysis in V2.

- **V1 Metrics Portfolio:**
  - **Performance:** Latency (average, p95, p99), CPU/Memory/GPU usage.
  - **Output Stability (Embeddings):** Cosine similarity between production and candidate embeddings. The service will calculate and log the distribution of similarity scores to catch significant shifts.
  - **Error Rate:** Compares the rate of processing errors or exceptions between the two models.
- **V2 (Future Enhancements):**
  - **Semantic Equivalence:** Use a sentence-transformer model to calculate the semantic similarity score between generated text summaries.
  - **Factual & Hallucination Check:** Count "new entities" in the candidate's summary that are not present in the production summary as a proxy for hallucination.
  - **Safety & Bias:** Run both outputs through a standard toxicity/bias detection model.
- **Report Generation:** The service will produce a structured JSON report that is stored in the Report Database for the Governance Dashboard to consume.

### 3.4. `Model Registry` Integration

The registry is the source of truth. Its schema will be extended to manage the deployment lifecycle.

- **Key States:** `REGISTERED`, `SHADOWING`, `CANARY`, `PRODUCTION`, `ARCHIVED`.
- **Metadata:** Each model version will store metadata including its current state, canary traffic percentage, and links to performance reports.

## 4. Governance & Promotion Workflow

The model lifecycle will be managed as a state machine within the `Model Registry`, visualized and controlled by the Governance Dashboard.

- **Automated Gating & Rollback:**
  - **Shadowing -> Canary:** A promotion can be automatically triggered if a candidate meets a strict set of V1 criteria (e.g., `latency_increase < 5%`, `embedding_similarity > 0.98`).
  - **Canary -> Production:** A progressive rollout will be automated. The system will automatically increase traffic (e.g., 1% -> 10% -> 50%) as long as KPIs remain stable. If a KPI is breached, an automated rollback to the previous stage occurs.
- **Interactive Governance:** The dashboard will show a summary of comparison reports and provide clear "Promote" and "Reject" actions for manual oversight.

## 5. Configuration

The following configuration will be added to the system's configuration schema.

```json
{
  "inference_router": {
    "url": "http://inference-router:8000",
    "config_poll_interval_seconds": 15
  },
  "shadow_testing": {
    "comparison_service_url": "http://comparison-service:8002"
  },
  "canary_deployment": {
    "auto_rollback_thresholds": {
      "latency_increase_percent": 20,
      "error_rate_increase_percent": 5
    },
    "auto_promote_thresholds": {
      "latency_increase_percent": 5,
      "embedding_similarity_min": 0.98
    }
  }
}
```

## 6. Validation Plan

- **Unit Tests:** Each service (`InferenceRouter`, `ShadowingService`, `ComparisonService`) will have comprehensive unit tests.
- **Integration Tests:** A `docker-compose` environment will be used to test the full flow:
  1. Set a model to `SHADOW` in the registry.
  2. Send a video to the API.
  3. Verify the `ComparisonService` generates a report.
  4. Set a model to `CANARY`.
  5. Verify the `InferenceRouter` splits traffic as expected.
- **Chaos Tests:** Simulate failures in the canary `InferenceService` to ensure the `InferenceRouter` correctly diverts traffic and triggers rollback alerts.
