import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from video_ai_system.adaptation_controller import AdaptationController

PROMETHEUS_URL = "http://prometheus:9090"

@pytest.fixture
def mock_rules():
    """Provides a standard set of rules for testing, sorted by severity."""
    return [
        {
            "metric": "inference_latency_seconds",
            "operator": ">",
            "threshold": 1.0,
            "level": "CRITICAL",
            "target_model": "yolov8n-tiny",
        },
        {
            "metric": "inference_latency_seconds",
            "operator": ">",
            "threshold": 0.5,
            "level": "DEGRADED",
            "target_model": "yolov8n-light",
        },
        {
            "metric": "cpu_usage_percent",
            "operator": ">",
            "threshold": 85,
            "level": "DEGRADED",
            "target_model": "yolov8n-light",
        },
    ]

@pytest.fixture
def mock_inference_router():
    """Mocks the InferenceRouter."""
    router = MagicMock()
    router.set_active_model = AsyncMock()
    router.get_current_model_name = MagicMock(return_value="yolov8n-balanced")
    return router

def mock_prom_query_result(value: float):
    """Helper to create a mock Prometheus query result."""
    return [{"value": [time.time(), str(value)]}]

@pytest.mark.asyncio
@patch("prometheus_api_client.PrometheusConnect.async_custom_query")
async def test_controller_switches_model_when_critical_threshold_breached(
    mock_async_query, mock_rules, mock_inference_router
):
    """
    Verify the controller calls set_active_model with the correct model
    when a critical metric threshold is breached.
    """
    # Arrange
    mock_async_query.return_value = mock_prom_query_result(1.5)  # Breaches CRITICAL
    controller = AdaptationController(
        rules=mock_rules,
        inference_router=mock_inference_router,
        prometheus_url=PROMETHEUS_URL,
    )

    # Act
    await controller._evaluate_rules()

    # Assert
    mock_inference_router.set_active_model.assert_awaited_once_with("yolov8n-tiny")
    mock_async_query.assert_awaited_once_with(query="avg_over_time(inference_latency_seconds[1m])")

@pytest.mark.asyncio
@patch("prometheus_api_client.PrometheusConnect.async_custom_query")
async def test_controller_switches_model_when_degraded_threshold_breached(
    mock_async_query, mock_rules, mock_inference_router
):
    """
    Verify the controller calls set_active_model for a DEGRADED level.
    """
    # Arrange
    mock_async_query.return_value = mock_prom_query_result(0.7) # Breaches DEGRADED
    controller = AdaptationController(
        rules=mock_rules,
        inference_router=mock_inference_router,
        prometheus_url=PROMETHEUS_URL,
    )

    # Act
    await controller._evaluate_rules()

    # Assert
    mock_inference_router.set_active_model.assert_awaited_once_with("yolov8n-light")

@pytest.mark.asyncio
@patch("prometheus_api_client.PrometheusConnect.async_custom_query")
async def test_controller_does_not_switch_if_no_threshold_breached(
    mock_async_query, mock_rules, mock_inference_router
):
    """
    Ensures no model change occurs if all metrics are within normal bounds.
    """
    # Arrange
    # First query for latency, then for CPU
    mock_async_query.side_effect = [
        mock_prom_query_result(0.2),
        mock_prom_query_result(50),
    ]
    controller = AdaptationController(
        rules=mock_rules,
        inference_router=mock_inference_router,
        prometheus_url=PROMETHEUS_URL,
    )

    # Act
    await controller._evaluate_rules()

    # Assert
    mock_inference_router.set_active_model.assert_not_awaited()
    assert mock_async_query.call_count == 2

@pytest.mark.asyncio
@patch("prometheus_api_client.PrometheusConnect.async_custom_query")
async def test_controller_respects_cooldown_period(
    mock_async_query, mock_rules, mock_inference_router
):
    """
    Ensures that if a change was made recently, another is not made.
    """
    # Arrange
    controller = AdaptationController(
        rules=mock_rules,
        inference_router=mock_inference_router,
        prometheus_url=PROMETHEUS_URL,
        cooldown_seconds=300,
    )
    controller.last_adaptation_time = time.time() - 10  # 10 seconds ago

    # Act
    await controller._evaluate_rules()

    # Assert
    mock_inference_router.set_active_model.assert_not_awaited()
    mock_async_query.assert_not_awaited() # Should not even query

@pytest.mark.asyncio
@patch("prometheus_api_client.PrometheusConnect.async_custom_query")
async def test_controller_adapts_after_cooldown_period(
    mock_async_query, mock_rules, mock_inference_router
):
    """
    Ensures a change is made if the cooldown has passed.
    """
    # Arrange
    mock_async_query.return_value = mock_prom_query_result(1.5) # Breaches CRITICAL
    controller = AdaptationController(
        rules=mock_rules,
        inference_router=mock_inference_router,
        prometheus_url=PROMETHEUS_URL,
        cooldown_seconds=60,
    )
    controller.last_adaptation_time = time.time() - 100

    # Act
    await controller._evaluate_rules()

    # Assert
    mock_inference_router.set_active_model.assert_awaited_once_with("yolov8n-tiny")