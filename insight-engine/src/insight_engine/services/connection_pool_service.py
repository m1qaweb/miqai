"""
Database connection pooling optimization service.

This module provides:
- Async connection pool management for databases
- Connection health monitoring and lifecycle management
- Pool size optimization based on load
- Connection pool metrics and performance tracking
- Integration with monitoring and health check services
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncContextManager, Callable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from enum import Enum
import weakref

from prometheus_client import Gauge, Histogram, Counter
from pydantic import BaseModel

from insight_engine.logging_config import get_logger
from insight_engine.exceptions import ConnectionPoolException

logger = get_logger(__name__)

# Connection pool metrics
CONNECTION_POOL_SIZE = Gauge(
    'connection_pool_size',
    'Connection pool size',
    ['pool_name', 'state']  # active, idle, total
)

CONNECTION_POOL_UTILIZATION = Gauge(
    'connection_pool_utilization_ratio',
    'Connection pool utilization ratio',
    ['pool_name']
)

CONNECTION_WAIT_TIME = Histogram(
    'connection_wait_time_seconds',
    'Time waiting for connection from pool',
    ['pool_name']
)

CONNECTION_LIFETIME = Histogram(
    'connection_lifetime_seconds',
    'Connection lifetime in seconds',
    ['pool_name']
)

CONNECTION_ERRORS_TOTAL = Counter(
    'connection_errors_total',
    'Total connection errors',
    ['pool_name', 'error_type']
)


class ConnectionState(Enum):
    """Connection state enumeration."""
    IDLE = "idle"
    ACTIVE = "active"
    STALE = "stale"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """Connection information and metadata."""
    connection_id: str
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    state: ConnectionState = ConnectionState.IDLE
    error_count: int = 0
    connection: Any = None


@dataclass
class PoolConfig:
    """Connection pool configuration."""
    name: str
    min_size: int = 5
    max_size: int = 20
    max_idle_time: float = 300.0  # 5 minutes
    max_lifetime: float = 3600.0  # 1 hour
    connection_timeout: float = 30.0
    health_check_interval: float = 60.0
    max_retries: int = 3
    retry_delay: float = 1.0


class ConnectionPool:
    """
    Generic async connection pool with health monitoring and optimization.
    
    Features:
    - Dynamic pool sizing based on load
    - Connection health monitoring
    - Automatic connection recycling
    - Comprehensive metrics collection
    - Connection lifecycle management
    """
    
    def __init__(
        self,
        config: PoolConfig,
        connection_factory: Callable[[], Any],
        connection_validator: Optional[Callable[[Any], bool]] = None,
        connection_closer: Optional[Callable[[Any], None]] = None
    ):
        self.config = config
        self.connection_factory = connection_factory
        self.connection_validator = connection_validator
        self.connection_closer = connection_closer or (lambda conn: None)
        
        self._connections: Dict[str, ConnectionInfo] = {}
        self._idle_connections: asyncio.Queue = asyncio.Queue()
        self._active_connections: weakref.WeakSet = weakref.WeakSet()
        self._lock = asyncio.Lock()
        self._shutdown = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._stats = {
            'total_created': 0,
            'total_closed': 0,
            'total_errors': 0,
            'current_size': 0,
            'peak_size': 0
        }
        
        logger.info(f"Connection pool '{config.name}' initialized")
    
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        try:
            # Create minimum number of connections
            for _ in range(self.config.min_size):
                await self._create_connection()
            
            # Start health check task
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )
            
            logger.info(
                f"Connection pool '{self.config.name}' initialized with "
                f"{len(self._connections)} connections"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize connection pool '{self.config.name}': {e}")
            raise ConnectionPoolException(f"Pool initialization failed: {e}")
    
    async def close(self) -> None:
        """Close the connection pool and all connections."""
        self._shutdown = True
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        async with self._lock:
            for conn_info in list(self._connections.values()):
                await self._close_connection(conn_info.connection_id)
        
        logger.info(f"Connection pool '{self.config.name}' closed")
    
    async def _create_connection(self) -> str:
        """Create a new connection and add it to the pool."""
        connection_id = f"{self.config.name}_{int(time.time() * 1000000)}"
        
        try:
            if asyncio.iscoroutinefunction(self.connection_factory):
                connection = await self.connection_factory()
            else:
                connection = self.connection_factory()
            
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow(),
                connection=connection
            )
            
            self._connections[connection_id] = conn_info
            await self._idle_connections.put(connection_id)
            
            self._stats['total_created'] += 1
            self._stats['current_size'] = len(self._connections)
            self._stats['peak_size'] = max(self._stats['peak_size'], self._stats['current_size'])
            
            # Update metrics
            self._update_pool_metrics()
            
            logger.debug(f"Created connection {connection_id} for pool '{self.config.name}'")
            return connection_id
            
        except Exception as e:
            self._stats['total_errors'] += 1
            CONNECTION_ERRORS_TOTAL.labels(
                pool_name=self.config.name,
                error_type='creation_error'
            ).inc()
            logger.error(f"Failed to create connection for pool '{self.config.name}': {e}")
            raise ConnectionPoolException(f"Connection creation failed: {e}")
    
    async def _close_connection(self, connection_id: str) -> None:
        """Close and remove a connection from the pool."""
        if connection_id not in self._connections:
            return
        
        conn_info = self._connections[connection_id]
        
        try:
            if asyncio.iscoroutinefunction(self.connection_closer):
                await self.connection_closer(conn_info.connection)
            else:
                self.connection_closer(conn_info.connection)
        except Exception as e:
            logger.warning(f"Error closing connection {connection_id}: {e}")
        
        del self._connections[connection_id]
        self._stats['total_closed'] += 1
        self._stats['current_size'] = len(self._connections)
        
        # Update metrics
        self._update_pool_metrics()
        
        logger.debug(f"Closed connection {connection_id} from pool '{self.config.name}'")
    
    async def _validate_connection(self, connection_id: str) -> bool:
        """Validate a connection's health."""
        if connection_id not in self._connections:
            return False
        
        conn_info = self._connections[connection_id]
        
        # Check connection age
        age = (datetime.utcnow() - conn_info.created_at).total_seconds()
        if age > self.config.max_lifetime:
            logger.debug(f"Connection {connection_id} exceeded max lifetime ({age}s)")
            return False
        
        # Check idle time
        idle_time = (datetime.utcnow() - conn_info.last_used).total_seconds()
        if idle_time > self.config.max_idle_time:
            logger.debug(f"Connection {connection_id} exceeded max idle time ({idle_time}s)")
            return False
        
        # Custom validation
        if self.connection_validator:
            try:
                if asyncio.iscoroutinefunction(self.connection_validator):
                    is_valid = await self.connection_validator(conn_info.connection)
                else:
                    is_valid = self.connection_validator(conn_info.connection)
                
                if not is_valid:
                    logger.debug(f"Connection {connection_id} failed custom validation")
                    return False
            except Exception as e:
                logger.warning(f"Connection validation error for {connection_id}: {e}")
                return False
        
        return True
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncContextManager[Any]:
        """Get a connection from the pool."""
        connection_id = None
        start_time = time.time()
        
        try:
            # Wait for available connection
            while True:
                try:
                    connection_id = await asyncio.wait_for(
                        self._idle_connections.get(),
                        timeout=self.config.connection_timeout
                    )
                    break
                except asyncio.TimeoutError:
                    # Try to create new connection if under max size
                    async with self._lock:
                        if len(self._connections) < self.config.max_size:
                            connection_id = await self._create_connection()
                            break
                    
                    # Pool is full and no connections available
                    CONNECTION_ERRORS_TOTAL.labels(
                        pool_name=self.config.name,
                        error_type='timeout'
                    ).inc()
                    raise ConnectionPoolException(
                        f"Connection timeout after {self.config.connection_timeout}s"
                    )
            
            # Validate connection
            if not await self._validate_connection(connection_id):
                # Connection is stale, close it and try again
                await self._close_connection(connection_id)
                async with self._lock:
                    if len(self._connections) < self.config.max_size:
                        connection_id = await self._create_connection()
                    else:
                        raise ConnectionPoolException("No valid connections available")
            
            # Mark connection as active
            conn_info = self._connections[connection_id]
            conn_info.state = ConnectionState.ACTIVE
            conn_info.last_used = datetime.utcnow()
            conn_info.use_count += 1
            
            wait_time = time.time() - start_time
            CONNECTION_WAIT_TIME.labels(pool_name=self.config.name).observe(wait_time)
            
            # Update metrics
            self._update_pool_metrics()
            
            yield conn_info.connection
            
        except Exception as e:
            CONNECTION_ERRORS_TOTAL.labels(
                pool_name=self.config.name,
                error_type='acquisition_error'
            ).inc()
            logger.error(f"Error acquiring connection from pool '{self.config.name}': {e}")
            raise
        
        finally:
            # Return connection to pool
            if connection_id and connection_id in self._connections:
                conn_info = self._connections[connection_id]
                conn_info.state = ConnectionState.IDLE
                conn_info.last_used = datetime.utcnow()
                
                # Check if connection should be recycled
                if await self._validate_connection(connection_id):
                    await self._idle_connections.put(connection_id)
                else:
                    await self._close_connection(connection_id)
                
                # Update metrics
                self._update_pool_metrics()
    
    async def _health_check_loop(self) -> None:
        """Background task for connection health checks and maintenance."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if self._shutdown:
                    break
                
                await self._perform_maintenance()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop for pool '{self.config.name}': {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _perform_maintenance(self) -> None:
        """Perform pool maintenance tasks."""
        async with self._lock:
            stale_connections = []
            
            # Check all connections for staleness
            for connection_id, conn_info in self._connections.items():
                if conn_info.state == ConnectionState.IDLE:
                    if not await self._validate_connection(connection_id):
                        stale_connections.append(connection_id)
            
            # Remove stale connections
            for connection_id in stale_connections:
                await self._close_connection(connection_id)
            
            # Ensure minimum pool size
            current_size = len(self._connections)
            if current_size < self.config.min_size:
                for _ in range(self.config.min_size - current_size):
                    try:
                        await self._create_connection()
                    except Exception as e:
                        logger.error(f"Failed to create connection during maintenance: {e}")
                        break
            
            logger.debug(
                f"Pool '{self.config.name}' maintenance: "
                f"removed {len(stale_connections)} stale connections, "
                f"current size: {len(self._connections)}"
            )
    
    def _update_pool_metrics(self) -> None:
        """Update Prometheus metrics for the pool."""
        active_count = sum(1 for conn in self._connections.values() 
                          if conn.state == ConnectionState.ACTIVE)
        idle_count = len(self._connections) - active_count
        total_count = len(self._connections)
        
        CONNECTION_POOL_SIZE.labels(
            pool_name=self.config.name, 
            state='active'
        ).set(active_count)
        
        CONNECTION_POOL_SIZE.labels(
            pool_name=self.config.name, 
            state='idle'
        ).set(idle_count)
        
        CONNECTION_POOL_SIZE.labels(
            pool_name=self.config.name, 
            state='total'
        ).set(total_count)
        
        utilization = active_count / self.config.max_size if self.config.max_size > 0 else 0
        CONNECTION_POOL_UTILIZATION.labels(
            pool_name=self.config.name
        ).set(utilization)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        active_count = sum(1 for conn in self._connections.values() 
                          if conn.state == ConnectionState.ACTIVE)
        idle_count = len(self._connections) - active_count
        
        return {
            'pool_name': self.config.name,
            'total_connections': len(self._connections),
            'active_connections': active_count,
            'idle_connections': idle_count,
            'utilization': active_count / self.config.max_size if self.config.max_size > 0 else 0,
            'config': {
                'min_size': self.config.min_size,
                'max_size': self.config.max_size,
                'max_idle_time': self.config.max_idle_time,
                'max_lifetime': self.config.max_lifetime
            },
            'stats': self._stats.copy()
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get pool health status."""
        stats = self.get_stats()
        
        # Determine health status
        utilization = stats['utilization']
        if utilization > 0.9:
            status = "degraded"
            message = f"High utilization: {utilization:.1%}"
        elif utilization > 0.95:
            status = "unhealthy"
            message = f"Critical utilization: {utilization:.1%}"
        else:
            status = "healthy"
            message = None
        
        return {
            'status': status,
            'message': message,
            'last_check': datetime.utcnow().isoformat(),
            'stats': stats
        }


class ConnectionPoolManager:
    """
    Manager for multiple connection pools.
    
    Provides centralized management of connection pools for different
    databases and services with unified monitoring and health checks.
    """
    
    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self._configs: Dict[str, PoolConfig] = {}
        
        logger.info("Connection pool manager initialized")
    
    def register_pool(
        self,
        config: PoolConfig,
        connection_factory: Callable[[], Any],
        connection_validator: Optional[Callable[[Any], bool]] = None,
        connection_closer: Optional[Callable[[Any], None]] = None
    ) -> None:
        """Register a new connection pool."""
        if config.name in self._pools:
            raise ConnectionPoolException(f"Pool '{config.name}' already registered")
        
        pool = ConnectionPool(
            config=config,
            connection_factory=connection_factory,
            connection_validator=connection_validator,
            connection_closer=connection_closer
        )
        
        self._pools[config.name] = pool
        self._configs[config.name] = config
        
        logger.info(f"Registered connection pool: {config.name}")
    
    async def initialize_all_pools(self) -> None:
        """Initialize all registered pools."""
        for pool_name, pool in self._pools.items():
            try:
                await pool.initialize()
                logger.info(f"Initialized pool: {pool_name}")
            except Exception as e:
                logger.error(f"Failed to initialize pool '{pool_name}': {e}")
                raise
    
    async def close_all_pools(self) -> None:
        """Close all connection pools."""
        for pool_name, pool in self._pools.items():
            try:
                await pool.close()
                logger.info(f"Closed pool: {pool_name}")
            except Exception as e:
                logger.error(f"Error closing pool '{pool_name}': {e}")
        
        self._pools.clear()
        self._configs.clear()
    
    def get_pool(self, pool_name: str) -> ConnectionPool:
        """Get a connection pool by name."""
        if pool_name not in self._pools:
            raise ConnectionPoolException(f"Pool '{pool_name}' not found")
        return self._pools[pool_name]
    
    async def get_connection(self, pool_name: str) -> AsyncContextManager[Any]:
        """Get a connection from a specific pool."""
        pool = self.get_pool(pool_name)
        return pool.get_connection()
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all pools."""
        return {
            pool_name: pool.get_stats()
            for pool_name, pool in self._pools.items()
        }
    
    async def get_all_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all pools."""
        health_status = {}
        
        for pool_name, pool in self._pools.items():
            try:
                health_status[pool_name] = await pool.get_health_status()
            except Exception as e:
                health_status[pool_name] = {
                    'status': 'unhealthy',
                    'message': str(e),
                    'last_check': datetime.utcnow().isoformat()
                }
        
        return health_status


# Global connection pool manager
_pool_manager: Optional[ConnectionPoolManager] = None


def get_pool_manager() -> ConnectionPoolManager:
    """Get the global connection pool manager."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = ConnectionPoolManager()
    return _pool_manager


async def setup_connection_pools() -> ConnectionPoolManager:
    """Set up and initialize connection pools."""
    manager = get_pool_manager()
    
    # Example: Register Redis connection pool (if not using the cache service)
    # This would be configured based on application needs
    
    await manager.initialize_all_pools()
    return manager


async def shutdown_connection_pools() -> None:
    """Shutdown all connection pools."""
    global _pool_manager
    if _pool_manager:
        await _pool_manager.close_all_pools()
        _pool_manager = None