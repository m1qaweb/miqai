from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from insight_engine.api.v1.router import api_router
from insight_engine.config import settings
from insight_engine.config.validation import (
    validate_configuration_at_startup,
    get_configuration_summary
)
from insight_engine.handlers import register_exception_handlers
from insight_engine.logging_config import setup_logging, get_logger
from insight_engine.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    RequestContextMiddleware,
    RateLimitMiddleware,
)
from insight_engine.schemas.error import HealthCheckResponse, ServiceHealth
from insight_engine.services.performance_monitoring import (
    get_monitoring_service, 
    setup_monitoring, 
    shutdown_monitoring,
    MetricsMiddleware
)
from insight_engine.services.health_check_service import (
    get_health_check_service,
    HealthThresholds,
    ExternalServiceConfig
)
from insight_engine.services.cache_service import (
    get_cache_service,
    close_all_cache_services,
    CacheConfig
)
from insight_engine.services.connection_pool_service import (
    get_pool_manager,
    setup_connection_pools,
    shutdown_connection_pools
)

# Setup structured logging using configuration
setup_logging()

logger = get_logger(__name__)

# Application metadata
APP_VERSION = "0.1.0"
APP_START_TIME = datetime.utcnow()

app = FastAPI(
    title="Insight Engine API",
    description="AI-powered video analysis platform",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware using configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=settings.security.cors_credentials,
    allow_methods=settings.security.cors_methods,
    allow_headers=settings.security.cors_headers,
)

# Add custom middleware (order matters!)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestLoggingMiddleware, log_request_body=False)
app.add_middleware(
    RateLimitMiddleware, 
    requests_per_minute=settings.security.rate_limit_requests_per_minute
)

# Add performance monitoring middleware
monitoring_service = get_monitoring_service()
app.add_middleware(MetricsMiddleware, monitoring_service)

# Register exception handlers
register_exception_handlers(app)


@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint returning basic API information."""
    return {
        "name": "Insight Engine API",
        "version": APP_VERSION,
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Enhanced health check endpoint with comprehensive dependency monitoring.
    
    Returns the overall health status of the application and its dependencies
    using real health checks for Redis, Qdrant, system resources, and more.
    """
    try:
        # Get comprehensive health status from monitoring service
        health_status = await monitoring_service.get_comprehensive_health()
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "version": APP_VERSION
            }
        )


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """
    Prometheus metrics endpoint for monitoring.
    
    Returns metrics in Prometheus text format for scraping by monitoring systems.
    """
    try:
        prometheus_metrics = monitoring_service.get_prometheus_metrics()
        return PlainTextResponse(
            content=prometheus_metrics,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to generate metrics",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# Include API routes
app.include_router(api_router, prefix="/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize application services on startup."""
    global APP_START_TIME
    APP_START_TIME = datetime.utcnow()
    
    # Set up logging
    setup_logging()
    logger.info(f"Starting Insight Engine API v{APP_VERSION}")
    
    # Validate configuration
    try:
        validate_configuration_at_startup()
        config_summary = get_configuration_summary()
        logger.info(
            f"Configuration validated successfully",
            extra={"environment": config_summary["environment"]}
        )
    except Exception as e:
        logger.critical(f"Configuration validation failed: {e}")
        raise
    
    # Initialize enhanced cache service
    try:
        cache_config = CacheConfig(
            host=str(settings.REDIS_DSN).split('@')[-1].split('/')[0].split(':')[0],
            port=int(str(settings.REDIS_DSN).split('@')[-1].split('/')[0].split(':')[1]) if ':' in str(settings.REDIS_DSN).split('@')[-1].split('/')[0] else 6379,
            db=int(str(settings.REDIS_DSN).split('/')[-1]) if '/' in str(settings.REDIS_DSN) else 0,
            default_ttl=3600,  # Default TTL of 1 hour
            max_connections=20  # Default max connections
        )
        await get_cache_service("default", cache_config)
        logger.info("Cache service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize cache service: {e}")
        raise
    
    # Initialize connection pools
    try:
        await setup_connection_pools()
        logger.info("Connection pools initialized")
    except Exception as e:
        logger.error(f"Failed to initialize connection pools: {e}")
        raise
    
    # Initialize health check service
    try:
        health_service = get_health_check_service(
            thresholds=HealthThresholds(
                cpu_warning=80.0,
                cpu_critical=95.0,
                memory_warning=80.0,
                memory_critical=95.0
            )
        )
        
        # Register external services for health checks
        if settings.VIDEO_AI_SYSTEM_URL:
            health_service.register_external_service(
                ExternalServiceConfig(
                    name="video_ai_system",
                    url=f"{settings.VIDEO_AI_SYSTEM_URL}/health",
                    timeout=5.0
                )
            )
        
        # Register custom health checks
        health_service.register_custom_check(
            "database_connections", 
            health_service.check_database_connections
        )
        
        # Register health checks with monitoring service
        monitoring_service.register_health_check(
            "redis", health_service.check_redis_health
        )
        monitoring_service.register_health_check(
            "qdrant", health_service.check_qdrant_health
        )
        monitoring_service.register_health_check(
            "system_resources", health_service.check_system_resources
        )
        
        logger.info("Health check service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize health check service: {e}")
        raise
    
    # Start performance monitoring
    try:
        await setup_monitoring()
        logger.info("Performance monitoring started")
    except Exception as e:
        logger.error(f"Failed to start performance monitoring: {e}")
        raise
    
    logger.info(f"Insight Engine API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    shutdown_start = datetime.utcnow()
    
    logger.info(
        "Shutting down Insight Engine API",
        extra={
            "version": APP_VERSION,
            "uptime": (shutdown_start - APP_START_TIME).total_seconds(),
            "event": "application_shutdown"
        }
    )
    
    # Shutdown monitoring
    try:
        await shutdown_monitoring()
        logger.info("Performance monitoring stopped")
    except Exception as e:
        logger.error(f"Error stopping performance monitoring: {e}")
    
    # Close connection pools
    try:
        await shutdown_connection_pools()
        logger.info("Connection pools closed")
    except Exception as e:
        logger.error(f"Error closing connection pools: {e}")
    
    # Close cache services
    try:
        await close_all_cache_services()
        logger.info("Cache services closed")
    except Exception as e:
        logger.error(f"Error closing cache services: {e}")
    
    shutdown_duration = (datetime.utcnow() - shutdown_start).total_seconds()
    logger.info(
        "Insight Engine API shutdown complete",
        extra={
            "shutdown_duration": shutdown_duration,
            "event": "shutdown_complete"
        }
    )
