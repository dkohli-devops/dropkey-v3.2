"""
repository/__init__.py — DropKey v3.2 Repository Package

Easy imports for all repositories and base classes.

Usage:
    from repository import BaseRepository, UserRepository, Filter, FilterOperator
    from repository import Page, RecordNotFoundError
"""

# Base classes
from repository.base_repository import (
    BaseRepository,
    Filter,
    FilterOperator,
    Page,
)

# Exceptions
from repository.base_repository import (
    RepositoryException,
    RecordNotFoundError,
    DuplicateRecordError,
    RecordAlreadyDeletedError,
    InvalidFilterError,
    OperationNotAllowedError,
)

# Repositories
from repository.user_repository import UserRepository

# Export all
__all__ = [
    # Base
    "BaseRepository",
    "Filter",
    "FilterOperator",
    "Page",
    # Exceptions
    "RepositoryException",
    "RecordNotFoundError",
    "DuplicateRecordError",
    "RecordAlreadyDeletedError",
    "InvalidFilterError",
    "OperationNotAllowedError",
    # Repositories
    "UserRepository",
]
