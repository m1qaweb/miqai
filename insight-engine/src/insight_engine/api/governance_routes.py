import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from pydantic import BaseModel

from video_ai_system.services.audit_service import AuditService, AuditLogEntry
from video_ai_system.services.drift_detection_service import (
    DriftDetectionService,
    DriftAlert,
)
from video_ai_system.services.model_registry_service import (
    ModelRegistryService,
    ModelVersion,
)
from video_ai_system.services.shadow_testing_service import (
    ShadowTestingService,
    ShadowTestResult,
)

# from video_ai_system.security import get_current_user # Placeholder for auth

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/governance",
    tags=["Governance"],
    # dependencies=[Depends(get_current_user)], # Uncomment when auth is fully implemented
)


# Dependency Injection: Services are retrieved from the application state.
def get_audit_service(request: Request) -> AuditService:
    return request.app.state.services["audit"]


def get_model_registry_service(request: Request) -> ModelRegistryService:
    return request.app.state.services["model_registry"]


def get_shadow_testing_service(request: Request) -> ShadowTestingService:
    return request.app.state.services["shadow_testing"]


def get_drift_detection_service(request: Request) -> DriftDetectionService:
    return request.app.state.services["drift_detection"]


class ModelRolloutDecision(BaseModel):
    model_name: str
    model_version: str
    approved: bool
    reason: str


@router.get("/models", response_model=List[ModelVersion])
async def list_models(
    registry_service: ModelRegistryService = Depends(get_model_registry_service),
):
    """Lists all models, including current and candidate versions."""
    return await registry_service.get_all_models_with_versions()


@router.get(
    "/shadow_results/{model_name}/{model_version}", response_model=ShadowTestResult
)
async def get_shadow_test_results(
    model_name: str,
    model_version: str,
    shadow_service: ShadowTestingService = Depends(get_shadow_testing_service),
):
    """Retrieves the shadow testing results for a specific candidate model."""
    result = await shadow_service.get_results(model_name, model_version)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shadow test results not found for this model version.",
        )
    return result


@router.get("/drift_alerts", response_model=List[DriftAlert])
async def get_drift_alerts(
    drift_service: DriftDetectionService = Depends(get_drift_detection_service),
):
    """Gets all active drift detection alerts."""
    return await drift_service.get_all_alerts()


@router.post("/trigger_retraining/{alert_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_retraining(
    alert_id: str,
    background_tasks: BackgroundTasks,
    drift_service: DriftDetectionService = Depends(get_drift_detection_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Triggers the retraining hook for a model associated with a drift alert.
    This is an asynchronous operation.
    """
    alert = await drift_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drift alert not found."
        )

    logger.info(
        f"Triggering retraining for model '{alert.model_name}' due to alert '{alert_id}'."
    )
    background_tasks.add_task(drift_service.trigger_retraining_hook, alert.model_name)

    # Audit this critical action
    # In a real system, actor would come from the authenticated user token.
    actor = "operator@example.com"
    background_tasks.add_task(
        audit_service.log,
        actor=actor,
        action="RETRAINING_TRIGGERED",
        details={"alert_id": alert_id, "model_name": alert.model_name},
    )

    return {"message": "Retraining process has been initiated."}


@router.post("/rollout_decision", status_code=status.HTTP_202_ACCEPTED)
async def decide_on_rollout(
    decision: ModelRolloutDecision,
    background_tasks: BackgroundTasks,
    registry_service: ModelRegistryService = Depends(get_model_registry_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Allows an operator to approve or reject a model rollout."""
    action = "MODEL_ROLLOUT_APPROVED" if decision.approved else "MODEL_ROLLOUT_REJECTED"
    logger.info(
        f"Processing rollout decision: {action} for model "
        f"'{decision.model_name}' version '{decision.model_version}'"
    )

    if decision.approved:
        # This would typically trigger a CI/CD pipeline or another automated process.
        # For now, we just update the model stage in the registry.
        await registry_service.transition_model_stage(
            name=decision.model_name,
            version=decision.model_version,
            stage="Production",
        )
    else:
        # If rejected, we might move it to an "Archived" or "Rejected" stage.
        await registry_service.transition_model_stage(
            name=decision.model_name,
            version=decision.model_version,
            stage="Archived",
        )

    # Audit the decision
    actor = "operator@example.com"  # Placeholder for authenticated user
    background_tasks.add_task(
        audit_service.log,
        actor=actor,
        action=action,
        details={
            "model_name": decision.model_name,
            "model_version": decision.model_version,
            "reason": decision.reason,
        },
    )

    return {
        "message": f"Decision for model {decision.model_name} v{decision.model_version} has been recorded."
    }


@router.get("/audit_logs", response_model=List[AuditLogEntry])
async def get_all_audit_logs(audit_service: AuditService = Depends(get_audit_service)):
    """Retrieves the full, tamper-evident audit log."""
    return await audit_service.get_all_logs()
