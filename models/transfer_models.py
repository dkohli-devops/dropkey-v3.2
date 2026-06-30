# ═════════════════════════════════════════════════════════════════════════════
# models/transfer_session.py — Transfer Session Domain Model
#
# Represents a file transfer session (P2P encrypted transfer)
# Layer: Domain (Business Logic)
# ═════════════════════════════════════════════════════════════════════════════

from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid

from sqlalchemy import Column, String, DateTime, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pydantic import BaseModel, Field

from .base import Base


class TransferStatus(str, Enum):
    """Transfer session status."""
    PENDING = "pending"           # Waiting for peer
    CONNECTED = "connected"       # Peer connected
    IN_PROGRESS = "in_progress"   # Actively transferring
    COMPLETED = "completed"       # Transfer complete
    FAILED = "failed"             # Transfer failed
    CANCELLED = "cancelled"       # User cancelled
    EXPIRED = "expired"           # Session expired


class TransferSessionORM(Base):
    """
    ORM Model: Transfer Session
    
    Represents a P2P encrypted file transfer session.
    """
    
    __tablename__ = "transfer_sessions"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Session Info
    initiator_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Transfer Details
    status = Column(SQLEnum(TransferStatus), default=TransferStatus.PENDING, index=True)
    session_key = Column(String(256), nullable=False)  # ECDH public key
    transfer_mode = Column(String(50), default="p2p")  # p2p, relay, direct
    
    # File Metadata
    file_count = Column(Integer, default=0)
    total_size = Column(Integer, default=0)  # Bytes
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    # Encryption
    encryption_algorithm = Column(String(50), default="AES-256-GCM")
    key_derivation = Column(String(50), default="PBKDF2")
    
    # Additional Data
    metadata = Column(JSONB, default={})
    
    # Flags
    is_encrypted = Column(Boolean, default=True)
    allow_resume = Column(Boolean, default=True)
    verify_checksum = Column(Boolean, default=True)


class TransferSessionCreate(BaseModel):
    """Schema for creating transfer session."""
    initiator_id: str
    recipient_id: Optional[str] = None
    transfer_mode: str = "p2p"
    file_count: int = 0
    total_size: int = 0
    encryption_algorithm: str = "AES-256-GCM"


class TransferSessionUpdate(BaseModel):
    """Schema for updating transfer session."""
    status: Optional[TransferStatus] = None
    recipient_id: Optional[str] = None
    file_count: Optional[int] = None
    total_size: Optional[int] = None
    metadata: Optional[dict] = None


class TransferSessionResponse(BaseModel):
    """Schema for transfer session response."""
    id: str
    initiator_id: str
    recipient_id: Optional[str]
    status: TransferStatus
    session_key: str
    transfer_mode: str
    file_count: int
    total_size: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    expires_at: datetime
    encryption_algorithm: str
    metadata: dict
    
    class Config:
        from_attributes = True


# ═════════════════════════════════════════════════════════════════════════════
# models/transfer_file.py — Transfer File Domain Model
#
# Represents individual files within a transfer session
# Layer: Domain (Business Logic)
# ═════════════════════════════════════════════════════════════════════════════

class FileStatus(str, Enum):
    """Transfer file status."""
    PENDING = "pending"           # Waiting to transfer
    IN_PROGRESS = "in_progress"   # Currently transferring
    COMPLETED = "completed"       # Transfer complete
    FAILED = "failed"             # Transfer failed
    PAUSED = "paused"             # Transfer paused
    CANCELLED = "cancelled"       # User cancelled


class TransferFileORM(Base):
    """
    ORM Model: Transfer File
    
    Represents a single file within a transfer session.
    """
    
    __tablename__ = "transfer_files"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Key
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # File Info
    file_name = Column(String(512), nullable=False)
    file_path = Column(String(2048), nullable=False)
    file_size = Column(Integer, nullable=False)  # Bytes
    
    # Status
    status = Column(SQLEnum(FileStatus), default=FileStatus.PENDING, index=True)
    transferred_bytes = Column(Integer, default=0)
    
    # Checksums
    original_checksum = Column(String(128), nullable=True)  # SHA-256
    transferred_checksum = Column(String(128), nullable=True)
    checksum_verified = Column(Boolean, default=False)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Metadata
    mime_type = Column(String(100), nullable=True)
    compression_ratio = Column(Integer, default=0)  # Percentage
    metadata = Column(JSONB, default={})


class TransferFileCreate(BaseModel):
    """Schema for creating transfer file."""
    session_id: str
    file_name: str
    file_path: str
    file_size: int
    original_checksum: Optional[str] = None
    mime_type: Optional[str] = None


class TransferFileUpdate(BaseModel):
    """Schema for updating transfer file."""
    status: Optional[FileStatus] = None
    transferred_bytes: Optional[int] = None
    transferred_checksum: Optional[str] = None
    checksum_verified: Optional[bool] = None


class TransferFileResponse(BaseModel):
    """Schema for transfer file response."""
    id: str
    session_id: str
    file_name: str
    file_path: str
    file_size: int
    status: FileStatus
    transferred_bytes: int
    original_checksum: Optional[str]
    transferred_checksum: Optional[str]
    checksum_verified: bool
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    mime_type: Optional[str]
    compression_ratio: int
    
    class Config:
        from_attributes = True
