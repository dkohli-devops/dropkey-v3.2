"""
models/__init__.py — DropKey v3.2 Models Package

Easy imports for all models, base classes, and enums.

Usage:
    from models import User, BaseModel, UserRole, UserStatus
    from models.base import BaseModel, SoftDeleteMixin, AuditMixin, GUID
"""

# Base classes and utilities
from models.base import (
    Base,
    BaseModel,
    TimestampMixin,
    SoftDeleteMixin,
    AuditMixin,
    GUID,
)

# Models
from models.user import User, UserRole, UserStatus

# Export all
__all__ = [
    # Base
    "Base",
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "GUID",
    # Models
    "User",
    # Enums
    "UserRole",
    "UserStatus",
]
