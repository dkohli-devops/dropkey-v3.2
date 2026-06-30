"""
models/base.py — DropKey v3.2 Enterprise Base Model

FEATURES:
  [UUID] UUID primary keys instead of auto-increment integers
  [SOFT_DELETE] Soft delete support with deleted_at timestamp
  [TIMESTAMPS] Automatic created_at, updated_at timestamps
  [AUDIT] Change tracking and audit trail ready
  [MIXINS] Reusable model components (TimestampMixin, SoftDeleteMixin)
  [SERIALIZATION] Enhanced JSON serialization
  [INDEXING] Strategic indexes for performance
  [SCALABILITY] Designed for millions of records
  [EXTENSIBILITY] Easy to extend with custom fields and methods

DEPENDENCIES:
  pip install sqlalchemy uuid6

USAGE:
  from models.base import BaseModel, TimestampMixin, SoftDeleteMixin
  
  class User(BaseModel):
      __tablename__ = "users"
      
      username = Column(String(255), unique=True, nullable=False)
      email = Column(String(255), unique=True, nullable=False)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Boolean, Index, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, CHAR
import uuid6

# ═════════════════════════════════════════════════════════════════════════════
# CUSTOM TYPES
# ═════════════════════════════════════════════════════════════════════════════


class GUID(TypeDecorator):
    """
    Platform-independent GUID type using UUID6.
    
    Uses native UUID type on PostgreSQL, CHAR on others.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load dialect-specific implementation."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        """Convert UUID to database format."""
        if value is None:
            return value

        if dialect.name == "postgresql":
            return str(value)

        if not isinstance(value, uuid.UUID):
            return "%.32x" % uuid.UUID(value).int

        return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        """Convert from database format to UUID."""
        if value is None:
            return value

        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)

        return value


# ═════════════════════════════════════════════════════════════════════════════
# TIMESTAMP MIXIN
# ═════════════════════════════════════════════════════════════════════════════


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamps.
    
    Usage:
        class User(TimestampMixin, BaseModel):
            __tablename__ = "users"
            # ...
    """

    @declared_attr
    def created_at(cls):
        """Timestamp when record was created."""
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            nullable=False,
            index=True,
        )

    @declared_attr
    def updated_at(cls):
        """Timestamp when record was last updated."""
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
            index=True,
        )


# ═════════════════════════════════════════════════════════════════════════════
# SOFT DELETE MIXIN
# ═════════════════════════════════════════════════════════════════════════════


class SoftDeleteMixin:
    """
    Mixin that adds soft delete support via deleted_at timestamp.
    
    Soft deletes mark records as deleted without removing them from database.
    Useful for:
    - Audit trails
    - Data recovery
    - Referential integrity
    - Analytics on deleted data
    
    Usage:
        class User(SoftDeleteMixin, BaseModel):
            __tablename__ = "users"
            # ...
        
        user = await repo.get(user_id)
        await repo.soft_delete(user_id)  # User still in DB, deleted_at set
        
        # Query excludes soft-deleted by default
        users = await repo.list()  # Doesn't include deleted
        
        # Include soft-deleted
        users = await repo.list(include_deleted=True)
    """

    @declared_attr
    def deleted_at(cls):
        """Timestamp when record was soft deleted (None if not deleted)."""
        return Column(
            DateTime(timezone=True),
            nullable=True,
            index=True,
            default=None,
        )

    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None

    async def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT MIXIN
# ═════════════════════════════════════════════════════════════════════════════


class AuditMixin:
    """
    Mixin that adds audit information (created_by, updated_by).
    
    Tracks who created/modified records.
    
    Usage:
        class User(AuditMixin, BaseModel):
            __tablename__ = "users"
            # ...
        
        user = User(username="john", created_by_id=admin_id)
        await session.add(user)
    """

    @declared_attr
    def created_by_id(cls):
        """UUID of user who created this record."""
        return Column(GUID(), nullable=True, index=True)

    @declared_attr
    def updated_by_id(cls):
        """UUID of user who last updated this record."""
        return Column(GUID(), nullable=True, index=True)


# ═════════════════════════════════════════════════════════════════════════════
# BASE MODEL
# ═════════════════════════════════════════════════════════════════════════════

# Create declarative base
Base = declarative_base()


class BaseModel(Base):
    """
    Abstract base model for all database models.
    
    Provides:
    - id: UUID primary key (uuid6 for sortability)
    - created_at: Creation timestamp (auto)
    - updated_at: Last update timestamp (auto)
    - Soft delete support (override deleted_at property)
    - JSON serialization
    - Computed properties
    - Utility methods
    
    Features:
    ✅ UUID primary keys (not auto-increment integers)
    ✅ UTC timestamps with timezone awareness
    ✅ Soft delete support
    ✅ Extensible architecture
    ✅ Production-ready
    
    Usage:
        class User(BaseModel):
            __tablename__ = "users"
            
            username = Column(String(255), unique=True)
            email = Column(String(255), unique=True)
    """

    __abstract__ = True

    # Primary key: UUID v6 (sortable, time-based)
    id = Column(
        GUID(),
        primary_key=True,
        default=uuid6.uuid6,
        nullable=False,
        index=True,
    )
    """Unique identifier for this record (UUID v6)."""

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    """Timestamp when record was created (UTC)."""

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    """Timestamp when record was last updated (UTC)."""

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__}(id={self.id})>"

    # ════════════════════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ════════════════════════════════════════════════════════════════════════════

    def to_dict(self, include: Optional[List[str]] = None, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Args:
            include: List of fields to include (None = all)
            exclude: List of fields to exclude
        
        Returns:
            Dictionary representation of model
            
        Example:
            user.to_dict()  # All fields
            user.to_dict(exclude=["password_hash"])  # Exclude sensitive
            user.to_dict(include=["id", "username", "email"])  # Only these
        """
        result = {}

        for column in self.__table__.columns:
            name = column.name

            # Skip if in exclude list
            if exclude and name in exclude:
                continue

            # Skip if not in include list
            if include and name not in include:
                continue

            value = getattr(self, name)

            # Serialize based on type
            if isinstance(value, datetime):
                result[name] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                result[name] = str(value)
            elif isinstance(value, PyEnum):
                result[name] = value.value
            else:
                result[name] = value

        return result

    def to_json_dict(self) -> Dict[str, Any]:
        """
        Convert model to JSON-serializable dictionary.
        
        Automatically handles:
        - UUID → str
        - datetime → ISO format
        - Enum → value
        """
        return self.to_dict()

    # ════════════════════════════════════════════════════════════════════════════
    # COMPUTED PROPERTIES
    # ════════════════════════════════════════════════════════════════════════════

    @property
    def is_new(self) -> bool:
        """Check if model is newly created (not yet persisted)."""
        return self.id is None

    @property
    def age_seconds(self) -> float:
        """Get age of record in seconds since creation."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    @property
    def age_minutes(self) -> float:
        """Get age of record in minutes since creation."""
        return self.age_seconds / 60

    @property
    def age_hours(self) -> float:
        """Get age of record in hours since creation."""
        return self.age_minutes / 60

    @property
    def age_days(self) -> float:
        """Get age of record in days since creation."""
        return self.age_hours / 24

    @property
    def is_recently_updated(self, minutes: int = 5) -> bool:
        """Check if record was updated in last N minutes."""
        delta = datetime.now(timezone.utc) - self.updated_at
        return delta.total_seconds() < (minutes * 60)

    @property
    def time_since_created(self) -> str:
        """Get human-readable time since creation."""
        age = self.age_seconds

        if age < 60:
            return f"{int(age)}s ago"
        elif age < 3600:
            return f"{int(age / 60)}m ago"
        elif age < 86400:
            return f"{int(age / 3600)}h ago"
        else:
            return f"{int(age / 86400)}d ago"

    # ════════════════════════════════════════════════════════════════════════════
    # SOFT DELETE SUPPORT
    # ════════════════════════════════════════════════════════════════════════════

    @property
    def deleted_at(self) -> Optional[DateTime]:
        """
        Get deleted_at timestamp if model supports soft deletes.
        
        Override in subclass:
            deleted_at = Column(DateTime(timezone=True), nullable=True)
        """
        if hasattr(self, "_deleted_at"):
            return getattr(self, "_deleted_at")
        return None

    @deleted_at.setter
    def deleted_at(self, value):
        """Set deleted_at timestamp."""
        if hasattr(self.__class__, "deleted_at"):
            object.__setattr__(self, "_deleted_at", value)

    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        if not hasattr(self.__class__, "deleted_at"):
            return False
        return getattr(self, "deleted_at", None) is not None

    async def restore(self) -> None:
        """Restore a soft-deleted record."""
        if hasattr(self.__class__, "deleted_at"):
            self.deleted_at = None

    # ════════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ════════════════════════════════════════════════════════════════════════════

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Update model fields from dictionary.
        
        Args:
            data: Dictionary with field names as keys
            
        Example:
            user.update_from_dict({"username": "jane", "email": "jane@example.com"})
        """
        for key, value in data.items():
            if hasattr(self, key) and not key.startswith("_"):
                setattr(self, key, value)

    def merge_dict(self, data: Dict[str, Any]) -> None:
        """
        Merge dictionary into model (only non-null values).
        
        Args:
            data: Dictionary to merge
            
        Example:
            user.merge_dict({"email": "jane@example.com"})  # Only updates email
        """
        for key, value in data.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)

    def get_changed_fields(self, other: "BaseModel") -> List[str]:
        """
        Get list of fields that differ from another model instance.
        
        Args:
            other: Another instance of same model
            
        Returns:
            List of field names that differ
            
        Example:
            changed = user1.get_changed_fields(user2)
            # ["email", "username"]
        """
        changed = []

        for column in self.__table__.columns:
            name = column.name
            if getattr(self, name) != getattr(other, name):
                changed.append(name)

        return changed

    def validate(self) -> List[str]:
        """
        Validate model (can be overridden in subclasses).
        
        Returns:
            List of validation errors (empty if valid)
            
        Example:
            errors = user.validate()
            if errors:
                raise ModelValidationError(errors)
        """
        return []


# ═════════════════════════════════════════════════════════════════════════════
# EXAMPLE TIMESTAMP INDEX
# ═════════════════════════════════════════════════════════════════════════════

"""
For models with heavy date filtering, add composite indexes:

class User(BaseModel):
    __tablename__ = "users"
    
    username = Column(String(255))
    is_active = Column(Boolean)
    
    __table_args__ = (
        Index('ix_users_created_at_is_active', 'created_at', 'is_active'),
        Index('ix_users_updated_at_is_active', 'updated_at', 'is_active'),
    )
"""


if __name__ == "__main__":
    # Test UUID generation
    test_id = uuid6.uuid6()
    print(f"Generated UUID v6: {test_id}")
    print(f"UUID is sortable: {uuid6.uuid6() > test_id}")

    # Test GUID type
    guid = GUID()
    print(f"GUID type: {guid}")
