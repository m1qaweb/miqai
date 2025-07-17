"""User repository for user management operations."""

import uuid
from typing import Any, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from insight_engine.models.user import User
from insight_engine.exceptions import DatabaseException
from insight_engine.logging_config import get_logger
from .base import BaseRepository

logger = get_logger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_by_field(
        self, 
        field_name: str, 
        field_value: Any,
        session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """Get user by a specific field."""
        if field_name == "username":
            return await self.get_by_username(field_value, session)
        elif field_name == "email":
            return await self.get_by_email(field_value, session)
        else:
            return await super().get_by_field(field_name, field_value, session)
    
    async def get_by_username(
        self, 
        username: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """
        Get user by username.
        
        Args:
            username: Username to search for
            session: Optional database session
            
        Returns:
            User instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[User]:
            try:
                stmt = select(User).where(User.username == username)
                result = await db_session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    logger.debug(f"Found user with username: {username}")
                else:
                    logger.debug(f"User not found with username: {username}")
                
                return user
                
            except Exception as e:
                logger.error(f"Error getting user by username {username}: {e}")
                raise DatabaseException(f"Failed to get user by username: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_email(
        self, 
        email: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """
        Get user by email address.
        
        Args:
            email: Email address to search for
            session: Optional database session
            
        Returns:
            User instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[User]:
            try:
                stmt = select(User).where(User.email == email)
                result = await db_session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    logger.debug(f"Found user with email: {email}")
                else:
                    logger.debug(f"User not found with email: {email}")
                
                return user
                
            except Exception as e:
                logger.error(f"Error getting user by email {email}: {e}")
                raise DatabaseException(f"Failed to get user by email: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_username_or_email(
        self, 
        identifier: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """
        Get user by username or email address.
        
        Args:
            identifier: Username or email to search for
            session: Optional database session
            
        Returns:
            User instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[User]:
            try:
                stmt = select(User).where(
                    or_(User.username == identifier, User.email == identifier)
                )
                result = await db_session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    logger.debug(f"Found user with identifier: {identifier}")
                else:
                    logger.debug(f"User not found with identifier: {identifier}")
                
                return user
                
            except Exception as e:
                logger.error(f"Error getting user by identifier {identifier}: {e}")
                raise DatabaseException(f"Failed to get user by identifier: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_active_users(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> List[User]:
        """
        Get all active users.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            session: Optional database session
            
        Returns:
            List of active users
        """
        async def _get_operation(db_session: AsyncSession) -> List[User]:
            try:
                stmt = select(User).where(User.is_active == True).order_by(User.created_at.desc())
                
                if offset:
                    stmt = stmt.offset(offset)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db_session.execute(stmt)
                users = result.scalars().all()
                
                logger.debug(f"Found {len(users)} active users")
                return list(users)
                
            except Exception as e:
                logger.error(f"Error getting active users: {e}")
                raise DatabaseException(f"Failed to get active users: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def username_exists(
        self, 
        username: str,
        exclude_user_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check if username already exists.
        
        Args:
            username: Username to check
            exclude_user_id: Optional user ID to exclude from check
            session: Optional database session
            
        Returns:
            True if username exists, False otherwise
        """
        async def _check_operation(db_session: AsyncSession) -> bool:
            try:
                stmt = select(User.id).where(User.username == username)
                
                if exclude_user_id:
                    stmt = stmt.where(User.id != exclude_user_id)
                
                result = await db_session.execute(stmt)
                exists = result.scalar_one_or_none() is not None
                
                logger.debug(f"Username '{username}' exists: {exists}")
                return exists
                
            except Exception as e:
                logger.error(f"Error checking username existence {username}: {e}")
                raise DatabaseException(f"Failed to check username existence: {str(e)}")
        
        if session:
            return await _check_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _check_operation(db_session)
    
    async def email_exists(
        self, 
        email: str,
        exclude_user_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check if email already exists.
        
        Args:
            email: Email to check
            exclude_user_id: Optional user ID to exclude from check
            session: Optional database session
            
        Returns:
            True if email exists, False otherwise
        """
        async def _check_operation(db_session: AsyncSession) -> bool:
            try:
                stmt = select(User.id).where(User.email == email)
                
                if exclude_user_id:
                    stmt = stmt.where(User.id != exclude_user_id)
                
                result = await db_session.execute(stmt)
                exists = result.scalar_one_or_none() is not None
                
                logger.debug(f"Email '{email}' exists: {exists}")
                return exists
                
            except Exception as e:
                logger.error(f"Error checking email existence {email}: {e}")
                raise DatabaseException(f"Failed to check email existence: {str(e)}")
        
        if session:
            return await _check_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _check_operation(db_session)
    
    async def deactivate_user(
        self, 
        user_id: uuid.UUID,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Deactivate a user account.
        
        Args:
            user_id: User ID to deactivate
            session: Optional database session
            
        Returns:
            True if deactivated, False if user not found
        """
        return await self.update(user_id, {"is_active": False}, session) is not None
    
    async def activate_user(
        self, 
        user_id: uuid.UUID,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Activate a user account.
        
        Args:
            user_id: User ID to activate
            session: Optional database session
            
        Returns:
            True if activated, False if user not found
        """
        return await self.update(user_id, {"is_active": True}, session) is not None