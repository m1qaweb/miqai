"""Monitoring and health check endpoints for resilience patterns."""

import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException

from .decorators import get_circuit_breaker_stats, reset_circuit_breaker
from .rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resilience", tags=["resilience"])


@router.get("/health")
async def get_resilience_health() -> Dict[str, Any]:
    """
    Get overall health status of resilience patterns.
    
    Returns:
        Dictionary containing health status and circuit breaker states
    """
    try:
        circuit_breaker_stats = get_circuit_breaker_stats()
        
        # Determine overall health based on circuit breaker states
        open_circuits = [
            name for name, stats in circuit_breaker_stats.items() 
            if stats.get("state") == "open"
        ]
        
        half_open_circuits = [
            name for name, stats in circuit_breaker_stats.items() 
            if stats.get("state") == "half_open"
        ]
        
        # Determine overall status
        if open_circuits:
            overall_status = "degraded"
        elif half_open_circuits:
            overall_status = "recovering"
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "circuit_breakers": {
                "total": len(circuit_breaker_stats),
                "open": len(open_circuits),
                "half_open": len(half_open_circuits),
                "closed": len(circuit_breaker_stats) - len(open_circuits) - len(half_open_circuits),
                "open_services": open_circuits,
                "recovering_services": half_open_circuits
            },
            "details": circuit_breaker_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting resilience health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resilience health status")


@router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    """
    Get detailed circuit breaker statistics.
    
    Returns:
        Dictionary containing all circuit breaker statistics
    """
    try:
        return {
            "timestamp": datetime.now().isoformat(),
            "circuit_breakers": get_circuit_breaker_stats()
        }
    except Exception as e:
        logger.error(f"Error getting circuit breaker stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get circuit breaker statistics")


@router.post("/circuit-breakers/{service_name}/reset")
async def reset_service_circuit_breaker(service_name: str) -> Dict[str, Any]:
    """
    Manually reset a circuit breaker to closed state.
    
    Args:
        service_name: Name of the service whose circuit breaker to reset
        
    Returns:
        Success message and updated circuit breaker status
    """
    try:
        success = reset_circuit_breaker(service_name)
        
        if not success:
            raise HTTPException(
                status_code=404, 
                detail=f"Circuit breaker for service '{service_name}' not found"
            )
        
        # Get updated stats
        updated_stats = get_circuit_breaker_stats()
        service_stats = updated_stats.get(service_name, {})
        
        return {
            "message": f"Circuit breaker for service '{service_name}' has been reset",
            "service_name": service_name,
            "timestamp": datetime.now().isoformat(),
            "current_state": service_stats.get("state", "unknown"),
            "stats": service_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breaker for {service_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to reset circuit breaker for service '{service_name}'"
        )


@router.get("/metrics")
async def get_resilience_metrics() -> Dict[str, Any]:
    """
    Get resilience metrics for monitoring and alerting.
    
    Returns:
        Dictionary containing key metrics for external monitoring systems
    """
    try:
        circuit_breaker_stats = get_circuit_breaker_stats()
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "circuit_breaker_count": len(circuit_breaker_stats),
            "open_circuit_count": sum(
                1 for stats in circuit_breaker_stats.values() 
                if stats.get("state") == "open"
            ),
            "half_open_circuit_count": sum(
                1 for stats in circuit_breaker_stats.values() 
                if stats.get("state") == "half_open"
            ),
            "total_failures": sum(
                stats.get("failure_count", 0) 
                for stats in circuit_breaker_stats.values()
            ),
            "services": {}
        }
        
        # Add per-service metrics
        for service_name, stats in circuit_breaker_stats.items():
            metrics["services"][service_name] = {
                "state": stats.get("state", "unknown"),
                "failure_count": stats.get("failure_count", 0),
                "success_count": stats.get("success_count", 0),
                "last_failure_time": stats.get("last_failure_time", 0),
                "state_change_time": stats.get("state_change_time", 0)
            }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting resilience metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resilience metrics")