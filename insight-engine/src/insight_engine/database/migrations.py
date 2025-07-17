"""Database migration system for schema versioning."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from insight_engine.database.engine import get_database_session
from insight_engine.exceptions import DatabaseException
from insight_engine.logging_config import get_logger

logger = get_logger(__name__)

# Migration directory
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Migration:
    """Represents a single database migration."""
    
    def __init__(self, version: str, name: str, up_sql: str, down_sql: str):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.timestamp = datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"<Migration(version='{self.version}', name='{self.name}')>"


class MigrationManager:
    """Manages database migrations and schema versioning."""
    
    def __init__(self):
        self.migrations_dir = MIGRATIONS_DIR
        self.migrations_dir.mkdir(exist_ok=True)
    
    async def initialize_migration_table(self) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum VARCHAR(64)
        );
        """
        
        async with get_database_session() as session:
            await session.execute(text(create_table_sql))
            await session.commit()
        
        logger.info("Migration tracking table initialized")
    
    async def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        try:
            async with get_database_session() as session:
                result = await session.execute(
                    text("SELECT version FROM schema_migrations ORDER BY version")
                )
                return [row[0] for row in result.fetchall()]
        except Exception:
            # Table might not exist yet
            return []
    
    def get_available_migrations(self) -> List[Migration]:
        """Get list of available migration files."""
        migrations = []
        
        for migration_file in sorted(self.migrations_dir.glob("*.sql")):
            migration = self._parse_migration_file(migration_file)
            if migration:
                migrations.append(migration)
        
        return migrations
    
    def _parse_migration_file(self, file_path: Path) -> Optional[Migration]:
        """Parse a migration file and extract up/down SQL."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract version and name from filename
            # Format: YYYYMMDD_HHMMSS_migration_name.sql
            match = re.match(r'(\d{8}_\d{6})_(.+)\.sql$', file_path.name)
            if not match:
                logger.warning(f"Invalid migration filename format: {file_path.name}")
                return None
            
            version, name = match.groups()
            name = name.replace('_', ' ').title()
            
            # Split content into up and down sections
            sections = content.split('-- DOWN')
            if len(sections) != 2:
                logger.warning(f"Migration file must have UP and DOWN sections: {file_path.name}")
                return None
            
            up_sql = sections[0].replace('-- UP', '').strip()
            down_sql = sections[1].strip()
            
            return Migration(version, name, up_sql, down_sql)
            
        except Exception as e:
            logger.error(f"Failed to parse migration file {file_path}: {e}")
            return None
    
    async def run_migrations(self) -> None:
        """Run all pending migrations."""
        await self.initialize_migration_table()
        
        applied_migrations = await self.get_applied_migrations()
        available_migrations = self.get_available_migrations()
        
        pending_migrations = [
            m for m in available_migrations 
            if m.version not in applied_migrations
        ]
        
        if not pending_migrations:
            logger.info("No pending migrations to run")
            return
        
        logger.info(f"Running {len(pending_migrations)} pending migrations")
        
        for migration in pending_migrations:
            await self._apply_migration(migration)
        
        logger.info("All migrations completed successfully")
    
    async def _apply_migration(self, migration: Migration) -> None:
        """Apply a single migration."""
        logger.info(f"Applying migration {migration.version}: {migration.name}")
        
        async with get_database_session() as session:
            try:
                # Execute the migration SQL
                for statement in migration.up_sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await session.execute(text(statement))
                
                # Record the migration as applied
                await session.execute(
                    text("""
                        INSERT INTO schema_migrations (version, name, applied_at)
                        VALUES (:version, :name, :applied_at)
                    """),
                    {
                        "version": migration.version,
                        "name": migration.name,
                        "applied_at": datetime.utcnow()
                    }
                )
                
                await session.commit()
                logger.info(f"Migration {migration.version} applied successfully")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to apply migration {migration.version}: {e}")
                raise DatabaseException(f"Migration failed: {e}")
    
    async def rollback_migration(self, version: str) -> None:
        """Rollback a specific migration."""
        applied_migrations = await self.get_applied_migrations()
        
        if version not in applied_migrations:
            raise DatabaseException(f"Migration {version} is not applied")
        
        # Find the migration file
        migration_file = self.migrations_dir / f"{version}_*.sql"
        migration_files = list(self.migrations_dir.glob(f"{version}_*.sql"))
        
        if not migration_files:
            raise DatabaseException(f"Migration file for version {version} not found")
        
        migration = self._parse_migration_file(migration_files[0])
        if not migration:
            raise DatabaseException(f"Failed to parse migration file for version {version}")
        
        logger.info(f"Rolling back migration {version}: {migration.name}")
        
        async with get_database_session() as session:
            try:
                # Execute the rollback SQL
                for statement in migration.down_sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await session.execute(text(statement))
                
                # Remove the migration record
                await session.execute(
                    text("DELETE FROM schema_migrations WHERE version = :version"),
                    {"version": version}
                )
                
                await session.commit()
                logger.info(f"Migration {version} rolled back successfully")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to rollback migration {version}: {e}")
                raise DatabaseException(f"Migration rollback failed: {e}")
    
    def create_migration(self, name: str, up_sql: str, down_sql: str) -> str:
        """Create a new migration file."""
        # Generate version timestamp
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Clean up name for filename
        clean_name = re.sub(r'[^\w\s-]', '', name).strip()
        clean_name = re.sub(r'[-\s]+', '_', clean_name).lower()
        
        filename = f"{version}_{clean_name}.sql"
        file_path = self.migrations_dir / filename
        
        # Create migration file content
        content = f"""-- UP
{up_sql}

-- DOWN
{down_sql}
"""
        
        file_path.write_text(content, encoding='utf-8')
        logger.info(f"Created migration file: {filename}")
        
        return version


# Global migration manager instance
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """Get the global migration manager instance."""
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager()
    return _migration_manager


async def run_migrations() -> None:
    """Run all pending migrations."""
    manager = get_migration_manager()
    await manager.run_migrations()


async def rollback_migration(version: str) -> None:
    """Rollback a specific migration."""
    manager = get_migration_manager()
    await manager.rollback_migration(version)


def create_migration(name: str, up_sql: str, down_sql: str) -> str:
    """Create a new migration file."""
    manager = get_migration_manager()
    return manager.create_migration(name, up_sql, down_sql)