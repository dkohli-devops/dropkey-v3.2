# ═════════════════════════════════════════════════════════════════════════════
# repository/transfer_repository.py — Transfer Session/File Repository
#
# Data access layer for transfer operations
# Layer: Infrastructure (Data Persistence)
# ═════════════════════════════════════════════════════════════════════════════

from typing import List, Optional
from datetime import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from .base_repository import BaseRepository
from models.transfer_models import (
    TransferSessionORM,
    TransferFileORM,
    TransferStatus,
    FileStatus,
)


class TransferSessionRepository(BaseRepository[TransferSessionORM]):
    """
    Repository for transfer sessions.
    
    CRUD operations for P2P transfer sessions with advanced filtering.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        super().__init__(TransferSessionORM, db)
    
    async def get_by_initiator(self, initiator_id: str) -> List[TransferSessionORM]:
        """Get all sessions initiated by user."""
        stmt = select(self.model).where(
            self.model.initiator_id == uuid.UUID(initiator_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_by_recipient(self, recipient_id: str) -> List[TransferSessionORM]:
        """Get all sessions for recipient."""
        stmt = select(self.model).where(
            self.model.recipient_id == uuid.UUID(recipient_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_active_sessions(self, user_id: str) -> List[TransferSessionORM]:
        """Get active sessions for user (initiator or recipient)."""
        stmt = select(self.model).where(
            and_(
                self.model.status.in_([
                    TransferStatus.CONNECTED,
                    TransferStatus.IN_PROGRESS,
                ]),
                self.model.initiator_id == uuid.UUID(user_id) |
                self.model.recipient_id == uuid.UUID(user_id),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_pending_sessions(self) -> List[TransferSessionORM]:
        """Get all pending sessions."""
        stmt = select(self.model).where(
            self.model.status == TransferStatus.PENDING
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_expired_sessions(self) -> List[TransferSessionORM]:
        """Get expired sessions."""
        stmt = select(self.model).where(
            self.model.expires_at <= datetime.utcnow()
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update_status(
        self,
        session_id: str,
        status: TransferStatus,
    ) -> bool:
        """Update session status."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(session_id)
        ).values(status=status)
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def mark_started(self, session_id: str) -> bool:
        """Mark session as started."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(session_id)
        ).values(
            status=TransferStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def mark_completed(self, session_id: str) -> bool:
        """Mark session as completed."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(session_id)
        ).values(
            status=TransferStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0


class TransferFileRepository(BaseRepository[TransferFileORM]):
    """
    Repository for transfer files.
    
    CRUD operations for individual files within transfer sessions.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        super().__init__(TransferFileORM, db)
    
    async def get_by_session(self, session_id: str) -> List[TransferFileORM]:
        """Get all files in session."""
        stmt = select(self.model).where(
            self.model.session_id == uuid.UUID(session_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_by_status(
        self,
        session_id: str,
        status: FileStatus,
    ) -> List[TransferFileORM]:
        """Get files in session with specific status."""
        stmt = select(self.model).where(
            and_(
                self.model.session_id == uuid.UUID(session_id),
                self.model.status == status,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_pending(self, session_id: str) -> List[TransferFileORM]:
        """Get pending files in session."""
        return await self.get_by_status(session_id, FileStatus.PENDING)
    
    async def get_in_progress(self, session_id: str) -> List[TransferFileORM]:
        """Get in-progress files in session."""
        return await self.get_by_status(session_id, FileStatus.IN_PROGRESS)
    
    async def get_completed(self, session_id: str) -> List[TransferFileORM]:
        """Get completed files in session."""
        return await self.get_by_status(session_id, FileStatus.COMPLETED)
    
    async def update_status(
        self,
        file_id: str,
        status: FileStatus,
    ) -> bool:
        """Update file status."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(file_id)
        ).values(status=status)
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def update_progress(
        self,
        file_id: str,
        transferred_bytes: int,
    ) -> bool:
        """Update transfer progress."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(file_id)
        ).values(transferred_bytes=transferred_bytes)
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def verify_checksum(
        self,
        file_id: str,
        transferred_checksum: str,
    ) -> bool:
        """Verify file checksum."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(file_id)
        ).values(
            transferred_checksum=transferred_checksum,
            checksum_verified=True,
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def mark_completed(self, file_id: str) -> bool:
        """Mark file as completed."""
        stmt = update(self.model).where(
            self.model.id == uuid.UUID(file_id)
        ).values(
            status=FileStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def count_completed(self, session_id: str) -> int:
        """Count completed files in session."""
        stmt = select(self.model).where(
            and_(
                self.model.session_id == uuid.UUID(session_id),
                self.model.status == FileStatus.COMPLETED,
            )
        )
        result = await self.db.execute(stmt)
        return len(result.scalars().all())
    
    async def get_total_transferred(self, session_id: str) -> int:
        """Get total bytes transferred in session."""
        files = await self.get_by_session(session_id)
        return sum(f.transferred_bytes for f in files)
