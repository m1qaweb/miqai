"""Base repository with common CRUD operations and transaction management."""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound

from insight_engine.database.engine import get_database_session
from insight_engine.exceptions import (
    DatabaseException,
    DataNotFoundException,
    ValidationException,
)
from insight_engine.logging_config import get_logger
from insight_engine.models.base import Base

logger = get_logger(__name__)

# Type variable for model classes
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType], ABC):
    """
    Base repository class providing common CRUD operations.
    
    Implements the Repository pattern with proper transaction management,
    error handling, and logging.
    """
    
    def __init__(self, model_class: Type[ModelType]):
        self.model_class = model_class
        self.model_name = model_class.__name__
    
    async def create(
        self, 
        obj_data: Dict[str, Any], 
        session: Optional[AsyncSession] = None
    ) -> ModelType:
        """
        Create a new model instance.
        
        Args:
            obj_data: Dictionary of model data
            session: Optional database session (creates new one if not provided)
            
        Returns:
            Created model instance
            
        Raises:
            ValidationException: If data validation fails
            DatabaseException: If database operation fails
        """
        async def _create_operation(db_session: AsyncSession) -> ModelType:
            try:
                # Create model instance
                obj = self.model_class(**obj_data)
                
                # Add to session and flush to get ID
                db_session.add(obj)
                await db_session.flush()
                await db_session.refresh(obj)
                
                logger.info(f"Created {self.model_name} with ID: {obj.id}")
                return obj
                
            except IntegrityError as e:
                logger.error(f"Integrity error creating {self.model_name}: {e}")
                raise ValidationException(f"Data integrity violation: {str(e)}")
            except Exception as e:
                logger.error(f"Error creating {self.model_name}: {e}")
                raise DatabaseException(f"Failed to create {self.model_name}: {str(e)}")
        
        if session:
            return await _create_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _create_operation(db_session)
    
    async def get_by_id(
        self, 
        obj_id: Union[str, uuid.UUID], 
        session: Optional[AsyncSession] = None
    ) -> Optional[ModelType]:
        """
        Get model instance by ID.
        
        Args:
            obj_id: Model ID
            session: Optional database session
            
        Returns:
            Model instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[ModelType]:
            try:
                stmt = select(self.model_class).where(self.model_class.id == obj_id)
                result = await db_session.execute(stmt)
                obj = result.scalar_one_or_none()
                
                if obj:
                    logger.debug(f"Found {self.model_name} with ID: {obj_id}")
                else:
                    logger.debug(f"{self.model_name} not found with ID: {obj_id}")
                
                return obj
                
            except Exception as e:
                logger.error(f"Error getting {self.model_name} by ID {obj_id}: {e}")
                raise DatabaseException(f"Failed to get {self.model_name}: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_id_or_raise(
        self, 
        obj_id: Union[str, uuid.UUID], 
        session: Optional[AsyncSession] = None
    ) -> ModelType:
        """
        Get model instance by ID or raise exception if not found.
        
        Args:
            obj_id: Model ID
            session: Optional database session
            
        Returns:
            Model instance
            
        Raises:
            DataNotFoundException: If model not found
        """
        obj = await self.get_by_id(obj_id, session)
        if not obj:
            raise DataNotFoundException(self.model_name, str(obj_id))
        return obj
    
    async def update(
        self, 
        obj_id: Union[str, uuid.UUID], 
        update_data: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> ModelType:
        """
        Update model instance.
        
        Args:
            obj_id: Model ID
            update_data: Dictionary of fields to update
            session: Optional database session
            
        Returns:
            Updated model instance
            
        Raises:
            DataNotFoundException: If model not found
            ValidationException: If data validation fails
            DatabaseException: If database operation fails
        """
        async def _update_operation(db_session: AsyncSession) -> ModelType:
            try:
                # Get existing object
                obj = await self.get_by_id_or_raise(obj_id, db_session)
                
                # Update fields
                for field, value in update_data.items():
                    if hasattr(obj, field):
                        setattr(obj, field, value)
                    else:
                        logger.warning(f"Attempted to update non-existent field '{field}' on {self.model_name}")
                
                # Flush changes
                await db_session.flush()
                await db_session.refresh(obj)
                
                logger.info(f"Updated {self.model_name} with ID: {obj_id}")
                return obj
                
            except DataNotFoundException:
                raise
            except IntegrityError as e:
                logger.error(f"Integrity error updating {self.model_name}: {e}")
                raise ValidationException(f"Data integrity violation: {str(e)}")
            except Exception as e:
                logger.error(f"Error updating {self.model_name} {obj_id}: {e}")
                raise DatabaseException(f"Failed to update {self.model_name}: {str(e)}")
        
        if session:
            return await _update_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _update_operation(db_session)
    
    async def delete(
        self, 
        obj_id: Union[str, uuid.UUID],
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Delete model instance.
        
        Args:
            obj_id: Model ID
            session: Optional database session
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            DatabaseException: If database operation fails
        """
        async def _delete_operation(db_session: AsyncSession) -> bool:
            try:
                stmt = delete(self.model_class).where(self.model_class.id == obj_id)
                result = await db_session.execute(stmt)
                
                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"Deleted {self.model_name} with ID: {obj_id}")
                else:
                    logger.debug(f"{self.model_name} not found for deletion: {obj_id}")
                
                return deleted
                
            except Exception as e:
                logger.error(f"Error deleting {self.model_name} {obj_id}: {e}")
                raise DatabaseException(f"Failed to delete {self.model_name}: {str(e)}")
        
        if session:
            return await _delete_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _delete_operation(db_session)
    
    async def list_all(
        self, 
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> List[ModelType]:
        """
        List all model instances with optional pagination.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            session: Optional database session
            
        Returns:
            List of model instances
        """
        async def _list_operation(db_session: AsyncSession) -> List[ModelType]:
            try:
                stmt = select(self.model_class).order_by(self.model_class.created_at.desc())
                
                if offset:
                    stmt = stmt.offset(offset)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db_session.execute(stmt)
                objects = result.scalars().all()
                
                logger.debug(f"Listed {len(objects)} {self.model_name} instances")
                return list(objects)
                
            except Exception as e:
                logger.error(f"Error listing {self.model_name} instances: {e}")
                raise DatabaseException(f"Failed to list {self.model_name} instances: {str(e)}")
        
        if session:
            return await _list_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _list_operation(db_session)
    
    async def count(self, session: Optional[AsyncSession] = None) -> int:
        """
        Count total number of model instances.
        
        Args:
            session: Optional database session
            
        Returns:
            Total count
        """
        async def _count_operation(db_session: AsyncSession) -> int:
            try:
                stmt = select(func.count(self.model_class.id))
                result = await db_session.execute(stmt)
                count = result.scalar() or 0
                
                logger.debug(f"Counted {count} {self.model_name} instances")
                return count
                
            except Exception as e:
                logger.error(f"Error counting {self.model_name} instances: {e}")
                raise DatabaseException(f"Failed to count {self.model_name} instances: {str(e)}")
        
        if session:
            return await _count_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _count_operation(db_session)
    
    async def exists(
        self, 
        obj_id: Union[str, uuid.UUID],
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check if model instance exists.
        
        Args:
            obj_id: Model ID
            session: Optional database session
            
        Returns:
            True if exists, False otherwise
        """
        obj = await self.get_by_id(obj_id, session)
        return obj is not None
    
    @abstractmethod
    async def get_by_field(
        self, 
        field_name: str, 
        field_value: Any,
        session: Optional[AsyncSession] = None
    ) -> Optional[ModelType]:
        """
        Get model instance by a specific field.
        
        This method should be implemented by subclasses to provide
        field-specific queries.
        """
        pass