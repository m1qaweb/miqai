"""
Comprehensive performance monitoring service with Prometheus metrics.

This module provides:
- System-wide metrics collection
- HTTP request/response monitoring
- Database and cache performance tracking
- Resource utilization monitoring
- Custom business metrics
- Health check aggregation
"""

import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from prometheus_client import (
    Counter, Histogram, Gauge, Info, Summary,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from insight_engine.logging_config import get_logger
from insight_engine.services.cache_service import get_cache_service
from insight_engine.exceptions import MonitoringException

logger = get_logger(__name__)

# System-wide Prometheus metrics
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

HTTP_REQUEST_SIZE = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint']
)

HTTP_RESPONSE_SIZE = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

# System resource metrics
SYSTEM_CPU_USAGE = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes',
    ['type']  # total, available, used, free
)

SYSTEM_DISK_USAGE = Gauge(
    'system_disk_usage_bytes',
    'System disk usage in bytes',
    ['device', 'type']  # total, used, free
)

SYSTEM_NETWORK_IO = Counter(
    'system_network_io_bytes_total',
    'System network I/O in bytes',
    ['direction']  # sent, received
)

# Database metrics
DATABASE_CONNECTIONS = Gauge(
    'database_connections',
    'Database connections',
    ['database', 'state']  # active, idle, total
)

DATABASE_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['database', 'operation']
)

DATABASE_QUERY_TOTAL = Counter(
    'database_queries_total',
    'Total database queries',
    ['database', 'operation', 'status']
)

# Application metrics
APPLICATION_INFO = Info(
    'application_info',
    'Application information'
)

APPLICATION_UPTIME = Gauge(
    'application_uptime_seconds',
    'Application uptime in seconds'
)

BACKGROUND_TASKS_TOTAL = Counter(
    'background_tasks_total',
    'Total background tasks',
    ['task_type', 'status']
)

BACKGROUND_TASK_DURATION = Histogram(
    'background_task_duration_seconds',
    'Background task duration in seconds',
    ['task_type']
)

# Business metrics
VIDEO_PROCESSING_TOTAL = Counter(
    'video_processing_total',
    'Total video processing operations',
    ['operation', 'status']
)

VIDEO_PROCESSING_DURATION = Histogram(
    'video_processing_duration_seconds',
    'Video processing duration in seconds',
    ['operation']
)

RAG_QUERIES_TOTAL = Counter(
    'rag_queries_total',
    'Total RAG queries',
    ['status']
)

RAG_QUERY_DURATION = Histogram(
    'rag_query_duration_seconds',
    'RAG query duration in seconds'
)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceHealth:
    """Service health information."""
    name: str
    status: HealthStatus
    response_time: float
    last_check: datetime
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_total: int
    memory_available: int
    memory_used: int
    memory_percent: float
    disk_usage: Dict[str, Dict[str, int]]
    network_sent: int
    network_received: int
    load_average: List[float]
    timestamp: datetime


class PerformanceMonitoringService:
    """
    Comprehensive performance monitoring service.
    
    Provides:
    - Automatic metrics collection
    - Health check aggregation
    - System resource monitoring
    - Performance analytics
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.registry = CollectorRegistry()
        self._health_checks: Dict[str, Callable] = {}
        self._system_metrics_task: Optional[asyncio.Task] = None
        self._monitoring_enabled = True
        
        # Initialize application info
        APPLICATION_INFO.info({
            'version': '0.1.0',
            'environment': 'development',  # This should come from config
            'start_time': datetime.fromtimestamp(self.start_time).isoformat()
        })
        
        logger.info("Performance monitoring service initialized")
    
    async def start_monitoring(self) -> None:
        """Start background monitoring tasks."""
        if self._system_metrics_task is None:
            self._system_metrics_task = asyncio.create_task(
                self._collect_system_metrics()
            )
            logger.info("System metrics collection started")
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring tasks."""
        self._monitoring_enabled = False
        if self._system_metrics_task:
            self._system_metrics_task.cancel()
            try:
                await self._system_metrics_task
            except asyncio.CancelledError:
                pass
            self._system_metrics_task = None
        logger.info("System metrics collection stopped")
    
    async def _collect_system_metrics(self) -> None:
        """Collect system resource metrics periodically."""
        while self._monitoring_enabled:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                SYSTEM_CPU_USAGE.set(cpu_percent)
                
                # Memory usage
                memory = psutil.virtual_memory()
                SYSTEM_MEMORY_USAGE.labels(type='total').set(memory.total)
                SYSTEM_MEMORY_USAGE.labels(type='available').set(memory.available)
                SYSTEM_MEMORY_USAGE.labels(type='used').set(memory.used)
                SYSTEM_MEMORY_USAGE.labels(type='free').set(memory.free)
                
                # Disk usage
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        device = partition.device.replace(':', '').replace('\\', '_')
                        SYSTEM_DISK_USAGE.labels(device=device, type='total').set(usage.total)
                        SYSTEM_DISK_USAGE.labels(device=device, type='used').set(usage.used)
                        SYSTEM_DISK_USAGE.labels(device=device, type='free').set(usage.free)
                    except (PermissionError, OSError):
                        continue
                
                # Network I/O
                network = psutil.net_io_counters()
                if network:
                    SYSTEM_NETWORK_IO.labels(direction='sent')._value._value = network.bytes_sent
                    SYSTEM_NETWORK_IO.labels(direction='received')._value._value = network.bytes_recv
                
                # Application uptime
                APPLICATION_UPTIME.set(time.time() - self.start_time)
                
                await asyncio.sleep(30)  # Collect every 30 seconds
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def register_health_check(
        self, 
        name: str, 
        check_function: Callable[[], Any]
    ) -> None:
        """Register a health check function."""
        self._health_checks[name] = check_function
        logger.info(f"Registered health check: {name}")
    
    async def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    device = partition.device.replace(':', '').replace('\\', '_')
                    disk_usage[device] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free
                    }
                except (PermissionError, OSError):
                    continue
            
            network = psutil.net_io_counters()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_total=memory.total,
                memory_available=memory.available,
                memory_used=memory.used,
                memory_percent=memory.percent,
                disk_usage=disk_usage,
                network_sent=network.bytes_sent if network else 0,
                network_received=network.bytes_recv if network else 0,
                load_average=list(load_avg),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            raise MonitoringException(f"Failed to get system metrics: {e}")
    
    async def perform_health_checks(self) -> Dict[str, ServiceHealth]:
        """Perform all registered health checks."""
        health_results = {}
        
        for name, check_function in self._health_checks.items():
            start_time = time.time()
            try:
                if asyncio.iscoroutinefunction(check_function):
                    result = await check_function()
                else:
                    result = check_function()
                
                response_time = time.time() - start_time
                
                # Parse result
                if isinstance(result, dict):
                    status = HealthStatus(result.get('status', 'healthy'))
                    error_message = result.get('error')
                    metadata = result.get('metadata', {})
                else:
                    status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                    error_message = None if result else "Health check failed"
                    metadata = {}
                
                health_results[name] = ServiceHealth(
                    name=name,
                    status=status,
                    response_time=response_time,
                    last_check=datetime.utcnow(),
                    error_message=error_message,
                    metadata=metadata
                )
                
            except Exception as e:
                response_time = time.time() - start_time
                health_results[name] = ServiceHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    last_check=datetime.utcnow(),
                    error_message=str(e)
                )
                logger.error(f"Health check failed for {name}: {e}")
        
        return health_results
    
    async def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive health status including all dependencies."""
        health_checks = await self.perform_health_checks()
        system_metrics = await self.get_system_metrics()
        
        # Determine overall status
        overall_status = HealthStatus.HEALTHY
        for health in health_checks.values():
            if health.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
                break
            elif health.status == HealthStatus.DEGRADED:
                overall_status = HealthStatus.DEGRADED
        
        return {
            'status': overall_status.value,
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': time.time() - self.start_time,
            'version': '0.1.0',
            'services': {
                name: {
                    'status': health.status.value,
                    'response_time': health.response_time,
                    'last_check': health.last_check.isoformat(),
                    'error_message': health.error_message,
                    'metadata': health.metadata
                }
                for name, health in health_checks.items()
            },
            'system_metrics': {
                'cpu_percent': system_metrics.cpu_percent,
                'memory_percent': system_metrics.memory_percent,
                'memory_used_gb': system_metrics.memory_used / (1024**3),
                'memory_total_gb': system_metrics.memory_total / (1024**3),
                'disk_usage': system_metrics.disk_usage,
                'load_average': system_metrics.load_average
            }
        }
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest()
    
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0
    ) -> None:
        """Record HTTP request metrics."""
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        if request_size > 0:
            HTTP_REQUEST_SIZE.labels(
                method=method,
                endpoint=endpoint
            ).observe(request_size)
        
        if response_size > 0:
            HTTP_RESPONSE_SIZE.labels(
                method=method,
                endpoint=endpoint
            ).observe(response_size)
    
    def record_database_query(
        self,
        database: str,
        operation: str,
        duration: float,
        status: str = "success"
    ) -> None:
        """Record database query metrics."""
        DATABASE_QUERY_TOTAL.labels(
            database=database,
            operation=operation,
            status=status
        ).inc()
        
        DATABASE_QUERY_DURATION.labels(
            database=database,
            operation=operation
        ).observe(duration)
    
    def record_background_task(
        self,
        task_type: str,
        duration: float,
        status: str = "success"
    ) -> None:
        """Record background task metrics."""
        BACKGROUND_TASKS_TOTAL.labels(
            task_type=task_type,
            status=status
        ).inc()
        
        BACKGROUND_TASK_DURATION.labels(
            task_type=task_type
        ).observe(duration)
    
    def record_video_processing(
        self,
        operation: str,
        duration: float,
        status: str = "success"
    ) -> None:
        """Record video processing metrics."""
        VIDEO_PROCESSING_TOTAL.labels(
            operation=operation,
            status=status
        ).inc()
        
        VIDEO_PROCESSING_DURATION.labels(
            operation=operation
        ).observe(duration)
    
    def record_rag_query(self, duration: float, status: str = "success") -> None:
        """Record RAG query metrics."""
        RAG_QUERIES_TOTAL.labels(status=status).inc()
        RAG_QUERY_DURATION.observe(duration)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically collect HTTP request metrics."""
    
    def __init__(self, app, monitoring_service: PerformanceMonitoringService):
        super().__init__(app)
        self.monitoring_service = monitoring_service
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        # Get request size
        request_size = 0
        if hasattr(request, 'body'):
            try:
                body = await request.body()
                request_size = len(body) if body else 0
            except Exception:
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        duration = time.time() - start_time
        endpoint = self._get_endpoint_name(request)
        
        # Get response size
        response_size = 0
        if hasattr(response, 'body'):
            try:
                response_size = len(response.body) if response.body else 0
            except Exception:
                pass
        
        # Record metrics
        self.monitoring_service.record_http_request(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
            duration=duration,
            request_size=request_size,
            response_size=response_size
        )
        
        return response
    
    def _get_endpoint_name(self, request: Request) -> str:
        """Extract endpoint name from request."""
        path = request.url.path
        
        # Normalize common patterns
        if path.startswith('/v1/'):
            path = path[4:]  # Remove /v1/ prefix
        
        # Replace IDs with placeholders
        import re
        path = re.sub(r'/[0-9a-f-]{36}', '/{id}', path)  # UUIDs
        path = re.sub(r'/\d+', '/{id}', path)  # Numeric IDs
        
        return path or '/'


# Global monitoring service instance
_monitoring_service: Optional[PerformanceMonitoringService] = None


def get_monitoring_service() -> PerformanceMonitoringService:
    """Get the global monitoring service instance."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = PerformanceMonitoringService()
    return _monitoring_service


async def setup_monitoring() -> PerformanceMonitoringService:
    """Set up and start the monitoring service."""
    service = get_monitoring_service()
    await service.start_monitoring()
    return service


async def shutdown_monitoring() -> None:
    """Shutdown the monitoring service."""
    global _monitoring_service
    if _monitoring_service:
        await _monitoring_service.stop_monitoring()
        _monitoring_service = None