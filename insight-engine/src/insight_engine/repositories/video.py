"""Video and VideoClip repositories for video management operations."""

import uuid
from typing import Any, List, Optional

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from insight_engine.models.video import Video, VideoClip, ProcessingStatus
from insight_engine.exceptions import DatabaseException
from insight_engine.logging_config import get_logger
from .base import BaseRepository

logger = get_logger(__name__)


class VideoRepository(BaseRepository[Video]):
    """Repository for Video model operations."""
    
    def __init__(self):
        super().__init__(Video)
    
    async def get_by_field(
        self, 
        field_name: str, 
        field_value: Any,
        session: Optional[AsyncSession] = None
    ) -> Optional[Video]:
        """Get video by a specific field."""
        if field_name == "gcs_path":
            return await self.get_by_gcs_path(field_value, session)
        elif field_name == "filename":
            return await self.get_by_filename(field_value, session)
        else:
            return await super().get_by_field(field_name, field_value, session)
    
    async def get_by_gcs_path(
        self, 
        gcs_path: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[Video]:
        """
        Get video by GCS path.
        
        Args:
            gcs_path: Google Cloud Storage path
            session: Optional database session
            
        Returns:
            Video instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[Video]:
            try:
                stmt = select(Video).where(Video.gcs_path == gcs_path)
                result = await db_session.execute(stmt)
                video = result.scalar_one_or_none()
                
                if video:
                    logger.debug(f"Found video with GCS path: {gcs_path}")
                else:
                    logger.debug(f"Video not found with GCS path: {gcs_path}")
                
                return video
                
            except Exception as e:
                logger.error(f"Error getting video by GCS path {gcs_path}: {e}")
                raise DatabaseException(f"Failed to get video by GCS path: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_filename(
        self, 
        filename: str,
        user_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None
    ) -> Optional[Video]:
        """
        Get video by filename, optionally filtered by user.
        
        Args:
            filename: Video filename
            user_id: Optional user ID to filter by
            session: Optional database session
            
        Returns:
            Video instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[Video]:
            try:
                stmt = select(Video).where(Video.filename == filename)
                
                if user_id:
                    stmt = stmt.where(Video.user_id == user_id)
                
                result = await db_session.execute(stmt)
                video = result.scalar_one_or_none()
                
                if video:
                    logger.debug(f"Found video with filename: {filename}")
                else:
                    logger.debug(f"Video not found with filename: {filename}")
                
                return video
                
            except Exception as e:
                logger.error(f"Error getting video by filename {filename}: {e}")
                raise DatabaseException(f"Failed to get video by filename: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        status_filter: Optional[ProcessingStatus] = None,
        session: Optional[AsyncSession] = None
    ) -> List[Video]:
        """
        Get videos by user ID with optional filtering.
        
        Args:
            user_id: User ID to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            status_filter: Optional processing status filter
            session: Optional database session
            
        Returns:
            List of videos
        """
        async def _get_operation(db_session: AsyncSession) -> List[Video]:
            try:
                stmt = select(Video).where(Video.user_id == user_id)
                
                if status_filter:
                    stmt = stmt.where(Video.processing_status == status_filter)
                
                stmt = stmt.order_by(Video.created_at.desc())
                
                if offset:
                    stmt = stmt.offset(offset)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db_session.execute(stmt)
                videos = result.scalars().all()
                
                logger.debug(f"Found {len(videos)} videos for user {user_id}")
                return list(videos)
                
            except Exception as e:
                logger.error(f"Error getting videos for user {user_id}: {e}")
                raise DatabaseException(f"Failed to get videos for user: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_status(
        self,
        status: ProcessingStatus,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> List[Video]:
        """
        Get videos by processing status.
        
        Args:
            status: Processing status to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            session: Optional database session
            
        Returns:
            List of videos
        """
        async def _get_operation(db_session: AsyncSession) -> List[Video]:
            try:
                stmt = select(Video).where(Video.processing_status == status)
                stmt = stmt.order_by(Video.created_at.asc())  # Oldest first for processing
                
                if offset:
                    stmt = stmt.offset(offset)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db_session.execute(stmt)
                videos = result.scalars().all()
                
                logger.debug(f"Found {len(videos)} videos with status {status}")
                return list(videos)
                
            except Exception as e:
                logger.error(f"Error getting videos by status {status}: {e}")
                raise DatabaseException(f"Failed to get videos by status: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_with_clips(
        self,
        video_id: uuid.UUID,
        session: Optional[AsyncSession] = None
    ) -> Optional[Video]:
        """
        Get video with its clips loaded.
        
        Args:
            video_id: Video ID
            session: Optional database session
            
        Returns:
            Video instance with clips or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[Video]:
            try:
                stmt = select(Video).options(selectinload(Video.clips)).where(Video.id == video_id)
                result = await db_session.execute(stmt)
                video = result.scalar_one_or_none()
                
                if video:
                    logger.debug(f"Found video {video_id} with {len(video.clips)} clips")
                else:
                    logger.debug(f"Video not found: {video_id}")
                
                return video
                
            except Exception as e:
                logger.error(f"Error getting video with clips {video_id}: {e}")
                raise DatabaseException(f"Failed to get video with clips: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def update_processing_status(
        self,
        video_id: uuid.UUID,
        status: ProcessingStatus,
        error_message: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> Video:
        """
        Update video processing status with proper timestamp handling.
        
        Args:
            video_id: Video ID
            status: New processing status
            error_message: Optional error message if status is FAILED
            session: Optional database session
            
        Returns:
            Updated video instance
        """
        from datetime import datetime
        
        update_data = {"processing_status": status}
        
        if status == ProcessingStatus.PROCESSING:
            update_data["processing_started_at"] = datetime.utcnow()
            update_data["processing_error"] = None  # Clear any previous error
        elif status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
            update_data["processing_completed_at"] = datetime.utcnow()
            if error_message:
                update_data["processing_error"] = error_message
        
        return await self.update(video_id, update_data, session)
    
    async def count_by_user(
        self,
        user_id: uuid.UUID,
        status_filter: Optional[ProcessingStatus] = None,
        session: Optional[AsyncSession] = None
    ) -> int:
        """
        Count videos for a specific user.
        
        Args:
            user_id: User ID
            status_filter: Optional processing status filter
            session: Optional database session
            
        Returns:
            Video count
        """
        async def _count_operation(db_session: AsyncSession) -> int:
            try:
                stmt = select(func.count(Video.id)).where(Video.user_id == user_id)
                
                if status_filter:
                    stmt = stmt.where(Video.processing_status == status_filter)
                
                result = await db_session.execute(stmt)
                count = result.scalar() or 0
                
                logger.debug(f"Counted {count} videos for user {user_id}")
                return count
                
            except Exception as e:
                logger.error(f"Error counting videos for user {user_id}: {e}")
                raise DatabaseException(f"Failed to count videos for user: {str(e)}")
        
        if session:
            return await _count_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _count_operation(db_session)


class VideoClipRepository(BaseRepository[VideoClip]):
    """Repository for VideoClip model operations."""
    
    def __init__(self):
        super().__init__(VideoClip)
    
    async def get_by_field(
        self, 
        field_name: str, 
        field_value: Any,
        session: Optional[AsyncSession] = None
    ) -> Optional[VideoClip]:
        """Get video clip by a specific field."""
        if field_name == "gcs_path":
            return await self.get_by_gcs_path(field_value, session)
        else:
            return await super().get_by_field(field_name, field_value, session)
    
    async def get_by_gcs_path(
        self, 
        gcs_path: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[VideoClip]:
        """
        Get video clip by GCS path.
        
        Args:
            gcs_path: Google Cloud Storage path
            session: Optional database session
            
        Returns:
            VideoClip instance or None if not found
        """
        async def _get_operation(db_session: AsyncSession) -> Optional[VideoClip]:
            try:
                stmt = select(VideoClip).where(VideoClip.gcs_path == gcs_path)
                result = await db_session.execute(stmt)
                clip = result.scalar_one_or_none()
                
                if clip:
                    logger.debug(f"Found video clip with GCS path: {gcs_path}")
                else:
                    logger.debug(f"Video clip not found with GCS path: {gcs_path}")
                
                return clip
                
            except Exception as e:
                logger.error(f"Error getting video clip by GCS path {gcs_path}: {e}")
                raise DatabaseException(f"Failed to get video clip by GCS path: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_video_id(
        self,
        video_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        min_confidence: Optional[float] = None,
        session: Optional[AsyncSession] = None
    ) -> List[VideoClip]:
        """
        Get clips for a specific video.
        
        Args:
            video_id: Video ID
            limit: Maximum number of results
            offset: Number of results to skip
            min_confidence: Minimum confidence score filter
            session: Optional database session
            
        Returns:
            List of video clips
        """
        async def _get_operation(db_session: AsyncSession) -> List[VideoClip]:
            try:
                stmt = select(VideoClip).where(VideoClip.video_id == video_id)
                
                if min_confidence is not None:
                    stmt = stmt.where(VideoClip.confidence_score >= min_confidence)
                
                stmt = stmt.order_by(VideoClip.start_time.asc())
                
                if offset:
                    stmt = stmt.offset(offset)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db_session.execute(stmt)
                clips = result.scalars().all()
                
                logger.debug(f"Found {len(clips)} clips for video {video_id}")
                return list(clips)
                
            except Exception as e:
                logger.error(f"Error getting clips for video {video_id}: {e}")
                raise DatabaseException(f"Failed to get clips for video: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def get_by_query(
        self,
        query: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        min_confidence: Optional[float] = None,
        session: Optional[AsyncSession] = None
    ) -> List[VideoClip]:
        """
        Get clips that were extracted using a specific query.
        
        Args:
            query: Query string used for extraction
            limit: Maximum number of results
            offset: Number of results to skip
            min_confidence: Minimum confidence score filter
            session: Optional database session
            
        Returns:
            List of video clips
        """
        async def _get_operation(db_session: AsyncSession) -> List[VideoClip]:
            try:
                stmt = select(VideoClip).where(VideoClip.query_used == query)
                
                if min_confidence is not None:
                    stmt = stmt.where(VideoClip.confidence_score >= min_confidence)
                
                stmt = stmt.order_by(VideoClip.confidence_score.desc())
                
                if offset:
                    stmt = stmt.offset(offset)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await db_session.execute(stmt)
                clips = result.scalars().all()
                
                logger.debug(f"Found {len(clips)} clips for query: {query}")
                return list(clips)
                
            except Exception as e:
                logger.error(f"Error getting clips by query {query}: {e}")
                raise DatabaseException(f"Failed to get clips by query: {str(e)}")
        
        if session:
            return await _get_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _get_operation(db_session)
    
    async def count_by_video(
        self,
        video_id: uuid.UUID,
        min_confidence: Optional[float] = None,
        session: Optional[AsyncSession] = None
    ) -> int:
        """
        Count clips for a specific video.
        
        Args:
            video_id: Video ID
            min_confidence: Minimum confidence score filter
            session: Optional database session
            
        Returns:
            Clip count
        """
        async def _count_operation(db_session: AsyncSession) -> int:
            try:
                stmt = select(func.count(VideoClip.id)).where(VideoClip.video_id == video_id)
                
                if min_confidence is not None:
                    stmt = stmt.where(VideoClip.confidence_score >= min_confidence)
                
                result = await db_session.execute(stmt)
                count = result.scalar() or 0
                
                logger.debug(f"Counted {count} clips for video {video_id}")
                return count
                
            except Exception as e:
                logger.error(f"Error counting clips for video {video_id}: {e}")
                raise DatabaseException(f"Failed to count clips for video: {str(e)}")
        
        if session:
            return await _count_operation(session)
        else:
            async with get_database_session() as db_session:
                return await _count_operation(db_session)