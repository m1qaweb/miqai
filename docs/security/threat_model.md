# Threat Model

## Assets

- Raw video data
- Embeddings
- Model parameters
- Annotation data
- Audit logs
- Governance dashboard

## Threats

- Data leakage
- Unauthorized access
- Tampering of pipelines/models
- Adversarial input attacks

## Risk Assessments & Mitigations

### R-SEC-1: Broken Authentication due to Misconfiguration

- **Threat**: A misconfiguration in the settings management could lead to the API key not being loaded, effectively disabling authentication and allowing unauthorized access.
- **Vulnerability**: The `Settings.api_key` property was dependent on an environment variable (`API_KEY_SECRET_FILE`) that was not consistently set across all environments (e.g., local testing vs. Docker). This could cause the application to fail open or deny all requests.
- **Mitigation**: The `API_KEY_SECRET_FILE` setting was updated to have a required default value (`/run/secrets/api_key`), ensuring that the application will fail to start if the secret file is not present at the expected location. This enforces a secure-by-default posture.
- **Status**: Mitigated.
