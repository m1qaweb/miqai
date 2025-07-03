# Backend Dependency Upgrade Plan

This document outlines a prioritized plan for upgrading the outdated backend dependencies identified in the recent analysis sprint. The plan is based on research into potential security vulnerabilities, new features, and breaking changes for the most critical packages.

## Prioritized Upgrade List

1.  **Priority 1: `fastapi` and `uvicorn`**

    - **Justification:** As the core of our API gateway, ensuring the web framework is up-to-date is critical for security and performance. While specific vulnerabilities were not identified in the unpinned version, running on the latest stable version is a security best practice. The upgrade is likely to be low-risk.

2.  **Priority 2: `redis`**

    - **Justification:** The upgrade to the latest major version of the Redis client is important for performance and to leverage the newer RESP3 protocol. While no specific vulnerabilities were found for version 5.0.7, a major version jump often includes security hardening.

3.  **Priority 3: `onnxruntime`**

    - **Justification:** The ONNX runtime is critical for model inference performance. Newer versions often include significant performance optimizations and support for newer ONNX opsets, which can be beneficial for future models.

4.  **Priority 4: `opencv-python`**

    - **Justification:** OpenCV is a core component for video processing. Upgrading is important for performance and bug fixes. The risk of breaking changes is moderate.

5.  **Priority 5: `numpy`**
    - **Justification:** This is the highest-risk upgrade due to the major version change from 1.x to 2.x. The official documentation indicates significant breaking changes to the C-API and Python API. This upgrade should be handled with extreme care and thorough testing. It is prioritized last to ensure that the rest of the system is stable before undertaking this complex migration.

## Detailed Library Analysis

### `fastapi`

- **Current Version:** Not Pinned
- **Latest Version:** 0.115.14
- **Findings:**
  - **Security Vulnerabilities:** No specific vulnerabilities were identified for the unpinned version. However, the documentation strongly emphasizes pinning versions to avoid unexpected breaking changes and to ensure security. The use of `secrets.compare_digest` for security comparisons is a highlighted feature.
  - **Key New Features/Performance Gains:** Newer versions of FastAPI often include improvements to dependency injection, pydantic integration, and overall performance. The documentation for recent versions highlights improved support for modern Python features.
  - **Potential Breaking Changes:** The biggest risk comes from unpinned dependencies, especially `pydantic`. Upgrading FastAPI will likely require a corresponding upgrade of `pydantic`, which can introduce breaking changes. The move from Pydantic v1 to v2 is a major migration that affects how models are defined and used.

### `numpy`

- **Current Version:** 1.26.4
- **Latest Version:** 2.3.1
- **Findings:**
  - **Security Vulnerabilities:** No specific vulnerabilities were identified for version 1.26.4 in the provided documentation.
  - **Key New Features/Performance Gains:** The 2.0 release is a major update with significant cleanups and API changes. While specific performance benchmarks were not retrieved, major releases of this nature often include performance improvements due to refactoring and cleanup.
  - **Potential Breaking Changes:** This is a **high-risk** upgrade. The documentation for NumPy 2.0 indicates significant breaking changes, including a new C-API version, changes to broadcasting rules (`np.solve`), boolean casting of strings, and structured array indexing. A migration guide is available, and it should be followed carefully. The `numpy.lib.NumpyVersion` class can be used to handle version-dependent code.

### `opencv-python`

- **Current Version:** 4.9.0.80
- **Latest Version:** 4.11.0.86
- **Findings:**
  - **Security Vulnerabilities:** Information not retrieved.
  - **Key New Features/Performance Gains:** Information not retrieved.
  - **Potential Breaking Changes:** Information not retrieved.
  - **Note:** Due to a tool failure, no specific information was retrieved for `opencv-python`. The upgrade should be approached with standard testing procedures.

### `redis`

- **Current Version:** 5.0.7
- **Latest Version:** 6.2.0
- **Findings:**
  - **Security Vulnerabilities:** No specific vulnerabilities were identified for version 5.0.7 in the provided documentation.
  - **Key New Features/Performance Gains:** The most significant feature in `redis-py` 5.0 and later is support for the RESP3 protocol, which can provide more descriptive and efficient responses from the Redis server. Newer versions also include improvements to connection handling, including various credential providers.
  - **Potential Breaking Changes:** The upgrade from 5.x to 6.x is a major version change and should be tested carefully. While no specific breaking changes were listed in the retrieved documents, changes in connection handling or command arguments are possible.

### `onnxruntime`

- **Current Version:** 1.18.0
- **Latest Version:** 1.22.0
- **Findings:**
  - **Security Vulnerabilities:** No specific vulnerabilities were identified for version 1.18.0 in the provided documentation.
  - **Key New Features/Performance Gains:** Newer versions of ONNX Runtime typically include support for newer ONNX opset versions, which allows for the use of newer model architectures. Performance improvements for different execution providers (CUDA, TensorRT, CPU) are also common. The documentation shows a focus on optimizing models for different hardware and precisions (FP16, INT8).
  - **Potential Breaking Changes:** Breaking changes can occur, especially related to the C/C++ API. The documentation mentions the use of the `\since` tag to document API changes. For Python, changes are less frequent but can happen. The supported ONNX opset version can also change, which might affect model compatibility.

## Proposed Action Plan

1.  **Create a Dedicated Test Environment:** Before any upgrades, create a new virtual environment that mirrors the production environment. All upgrades and testing should be done in this isolated environment.

2.  **Upgrade and Test `api_gateway`:**

    - Pin `fastapi`, `uvicorn`, and `arq` to their latest stable versions in `src/api_gateway/requirements.txt`.
    - Run all existing unit and integration tests for the API gateway.
    - Perform manual testing of all API endpoints.
    - Pay close attention to any pydantic-related errors.

3.  **Upgrade and Test `redis`:**

    - Upgrade the `redis` package in `video-ai-system/requirements.txt`.
    - Run all tests that interact with Redis.
    - Consider enabling RESP3 and testing for any changes in data structures returned from Redis.

4.  **Upgrade and Test `onnxruntime`:**

    - Upgrade the `onnxruntime` package.
    - Run all model inference tests.
    - Benchmark model performance to ensure there are no regressions.

5.  **Upgrade and Test `opencv-python`:**

    - Upgrade the `opencv-python` package.
    - Run all tests related to video loading, preprocessing, and manipulation.

6.  **Plan and Execute `numpy` Upgrade:**

    - This upgrade should be treated as a separate, small project.
    - Thoroughly read the NumPy 2.0 migration guide.
    - Upgrade the `numpy` package in the test environment.
    - Run all tests. Expect failures.
    - Address failures one by one, using the migration guide.
    - Pay special attention to any C/C++ extensions that might be affected by C-API changes.
    - Once all tests are passing, perform extensive benchmarking to check for performance changes.

7.  **Code Review and Staging Deployment:**
    - Once all upgrades are complete and tested in the isolated environment, create a pull request with the updated dependency files.
    - After the PR is reviewed and merged, deploy the changes to a staging environment for a final round of testing before deploying to production.
