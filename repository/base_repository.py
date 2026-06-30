"""
repository/base_repository.py — DropKey v3.2 Enterprise Base Repository

FEATURES:
  [CRUD] Complete CRUD operations (Create, Read, Update, Delete)
  [GENERIC] Generic T-parameterized base class for all models
  [PAGINATION] Offset/limit pagination support
  [FILTERING] WHERE clause filtering with operators
  [SORTING] Ascending/descending sort support
  [TRANSACTIONS] Context manager for transactions
  [BULK] Bulk insert/update operations
  [ERRORS] Custom error handling and logging
  [LOGGING] Comprehensive operation logging
  [VALIDATION] Input validation
  [SCALABILITY] Designed for millions of records

DEPENDENCIES:
  pip install sqlalchemy

USAGE:
  from repository import BaseRepository
  from models import User
  
  class UserRepository(BaseRepository):
      model = User
  
  repo = UserRepository(session)
  user = await repo.get(user_id)
  users = await repo.list(skip=0, limit=10)
  user = await repo.create(username="john", email="john@example.com")
"""

import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any, Type, Callable, Tuple
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_, func, desc, asc, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models.base import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for models
T = TypeVar("T", bound=BaseModel)

# ═════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═════════════════════════════════════════════════════════════════════════════


class RepositoryException(Exception):
    """Base exception for repository operations."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class RecordNotFoundError(RepositoryException):
    """Raised when record is not found."""

    pass


class DuplicateRecordError(RepositoryException):
    """Raised when trying to create duplicate record."""

    pass


class RecordAlreadyDeletedError(RepositoryException):
    """Raised when trying to delete already deleted record."""

    pass


class InvalidFilterError(RepositoryException):
    """Raised when filter is invalid."""

    pass


class OperationNotAllowedError(RepositoryException):
    """Raised when operation is not allowed."""

    pass


# ═════════════════════════════════════════════════════════════════════════════
# FILTER OPERATORS
# ═════════════════════════════════════════════════════════════════════════════


class FilterOperator:
    """Filter operators for querying."""

    EQ = "eq"  # Equal
    NE = "ne"  # Not equal
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    IN = "in"  # In list
    NOT_IN = "not_in"  # Not in list
    LIKE = "like"  # SQL LIKE
    ILIKE = "ilike"  # Case-insensitive LIKE
    IS_NULL = "is_null"  # IS NULL
    IS_NOT_NULL = "is_not_null"  # IS NOT NULL


class Filter:
    """Single filter condition."""

    def __init__(
        self,
        field: str,
        value: Any,
        operator: str = FilterOperator.EQ,
    ):
        """
        Initialize filter.

        Args:
            field: Field name to filter on
            value: Value to compare
            operator: Comparison operator
        """
        self.field = field
        self.value = value
        self.operator = operator

    def __repr__(self) -> str:
        return f"<Filter(field={self.field}, op={self.operator}, value={self.value})>"


# ═════════════════════════════════════════════════════════════════════════════
# PAGINATION
# ═════════════════════════════════════════════════════════════════════════════


class Page:
    """Page of results with metadata."""

    def __init__(
        self,
        items: List[T],
        total: int,
        skip: int,
        limit: int,
    ):
        """Initialize page."""
        self.items = items
        self.total = total
        self.skip = skip
        self.limit = limit

    @property
    def page_number(self) -> int:
        """Get current page number (1-indexed)."""
        return (self.skip // self.limit) + 1 if self.limit > 0 else 1

    @property
    def page_count(self) -> int:
        """Get total number of pages."""
        if self.limit == 0:
            return 1
        return (self.total + self.limit - 1) // self.limit

    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.skip + self.limit < self.total

    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.skip > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "skip": self.skip,
            "limit": self.limit,
            "page": self.page_number,
            "page_count": self.page_count,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
        }


# ═════════════════════════════════════════════════════════════════════════════
# BASE REPOSITORY
# ═════════════════════════════════════════════════════════════════════════════


class BaseRepository(ABC, Generic[T]):
    """
    Generic base repository providing CRUD operations.

    Provides:
    - Create, Read, Update, Delete operations
    - Pagination with offset/limit
    - Filtering with operators
    - Sorting ascending/descending
    - Soft delete support
    - Bulk operations
    - Transaction management
    - Comprehensive error handling
    - Operation logging

    Subclass and set model:
        class UserRepository(BaseRepository):
            model = User

    Usage:
        repo = UserRepository(session)
        user = await repo.get(user_id)
        users = await repo.list(limit=10)
        user = await repo.create(username="john", email="john@example.com")
    """

    model: Type[T]  # Must be set in subclass

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.logger = logger.getChild(self.__class__.__name__)

    # ════════════════════════════════════════════════════════════════════════════
    # CREATE
    # ════════════════════════════════════════════════════════════════════════════

    async def create(self, **kwargs) -> T:
        """
        Create new record.

        Args:
            **kwargs: Field values

        Returns:
            Created model instance

        Raises:
            DuplicateRecordError: If unique constraint violated
            RepositoryException: On other errors
        """
        try:
            self.logger.debug(f"Creating {self.model.__name__} with {kwargs}")

            instance = self.model(**kwargs)

            # Validate if model has validate method
            if hasattr(instance, "validate"):
                errors = instance.validate()
                if errors:
                    raise ValueError(f"Validation failed: {errors}")

            self.session.add(instance)
            await self.session.flush()

            self.logger.info(f"Created {self.model.__name__}(id={instance.id})")
            return instance

        except IntegrityError as e:
            await self.session.rollback()
            self.logger.warning(f"Duplicate record: {e.orig}")
            raise DuplicateRecordError(
                f"Duplicate record for {self.model.__name__}: {str(e.orig)}"
            )
        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to create {self.model.__name__}: {e}", exc_info=True)
            raise RepositoryException(f"Failed to create record: {e}")

    async def bulk_create(self, items: List[Dict[str, Any]]) -> List[T]:
        """
        Create multiple records.

        Args:
            items: List of field dictionaries

        Returns:
            List of created instances
        """
        try:
            self.logger.debug(f"Bulk creating {len(items)} {self.model.__name__} records")

            instances = [self.model(**item) for item in items]

            # Validate all
            for instance in instances:
                if hasattr(instance, "validate"):
                    errors = instance.validate()
                    if errors:
                        raise ValueError(f"Validation failed: {errors}")

            self.session.add_all(instances)
            await self.session.flush()

            self.logger.info(f"Bulk created {len(instances)} {self.model.__name__} records")
            return instances

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Bulk create failed: {e}", exc_info=True)
            raise RepositoryException(f"Bulk create failed: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # READ
    # ════════════════════════════════════════════════════════════════════════════

    async def get(self, id: Any) -> Optional[T]:
        """
        Get record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        try:
            self.logger.debug(f"Getting {self.model.__name__}(id={id})")

            stmt = select(self.model).where(self.model.id == id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            self.logger.error(f"Failed to get {self.model.__name__}(id={id}): {e}")
            raise RepositoryException(f"Failed to get record: {e}")

    async def get_or_404(self, id: Any) -> T:
        """
        Get record by ID, raise if not found.

        Args:
            id: Record ID

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If not found
        """
        instance = await self.get(id)
        if not instance:
            raise RecordNotFoundError(f"{self.model.__name__}(id={id}) not found")
        return instance

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        filters: Optional[List[Filter]] = None,
        include_deleted: bool = False,
    ) -> List[T]:
        """
        List records with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            sort_by: Field to sort by
            sort_order: 'asc' or 'desc'
            filters: List of Filter objects
            include_deleted: Include soft-deleted records

        Returns:
            List of model instances
        """
        try:
            self.logger.debug(
                f"Listing {self.model.__name__} skip={skip} limit={limit} filters={filters}"
            )

            stmt = select(self.model)

            # Apply filters
            if filters:
                for filter_ in filters:
                    stmt = self._apply_filter(stmt, filter_)

            # Exclude soft-deleted by default
            if not include_deleted and hasattr(self.model, "deleted_at"):
                stmt = stmt.where(self.model.deleted_at.is_(None))

            # Apply sorting
            if sort_by:
                sort_field = getattr(self.model, sort_by)
                if sort_order.lower() == "desc":
                    stmt = stmt.order_by(desc(sort_field))
                else:
                    stmt = stmt.order_by(asc(sort_field))

            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            self.logger.error(f"Failed to list {self.model.__name__}: {e}", exc_info=True)
            raise RepositoryException(f"Failed to list records: {e}")

    async def page(
        self,
        skip: int = 0,
        limit: int = 10,
        **kwargs,
    ) -> Page[T]:
        """
        Get paginated results.

        Args:
            skip: Number of records to skip
            limit: Records per page
            **kwargs: Additional arguments for list()

        Returns:
            Page object with items and metadata
        """
        items = await self.list(skip=skip, limit=limit, **kwargs)
        total = await self.count(**kwargs)

        return Page(items=items, total=total, skip=skip, limit=limit)

    async def count(
        self,
        filters: Optional[List[Filter]] = None,
        include_deleted: bool = False,
    ) -> int:
        """
        Count matching records.

        Args:
            filters: List of Filter objects
            include_deleted: Include soft-deleted records

        Returns:
            Number of matching records
        """
        try:
            stmt = select(func.count(self.model.id))

            # Apply filters
            if filters:
                for filter_ in filters:
                    stmt = self._apply_filter(stmt, filter_)

            # Exclude soft-deleted by default
            if not include_deleted and hasattr(self.model, "deleted_at"):
                stmt = stmt.where(self.model.deleted_at.is_(None))

            result = await self.session.execute(stmt)
            return result.scalar() or 0

        except Exception as e:
            self.logger.error(f"Failed to count {self.model.__name__}: {e}")
            raise RepositoryException(f"Failed to count records: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # UPDATE
    # ════════════════════════════════════════════════════════════════════════════

    async def update(self, id: Any, **kwargs) -> Optional[T]:
        """
        Update record.

        Args:
            id: Record ID
            **kwargs: Fields to update

        Returns:
            Updated instance or None if not found
        """
        try:
            self.logger.debug(f"Updating {self.model.__name__}(id={id}) with {kwargs}")

            instance = await self.get(id)
            if not instance:
                return None

            # Update fields
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            # Validate if model has validate method
            if hasattr(instance, "validate"):
                errors = instance.validate()
                if errors:
                    raise ValueError(f"Validation failed: {errors}")

            self.session.add(instance)
            await self.session.flush()

            self.logger.info(f"Updated {self.model.__name__}(id={id})")
            return instance

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to update {self.model.__name__}(id={id}): {e}")
            raise RepositoryException(f"Failed to update record: {e}")

    async def bulk_update(self, ids: List[Any], **kwargs) -> int:
        """
        Update multiple records.

        Args:
            ids: List of record IDs
            **kwargs: Fields to update

        Returns:
            Number of updated records
        """
        try:
            self.logger.debug(f"Bulk updating {len(ids)} {self.model.__name__} records")

            stmt = update(self.model).where(self.model.id.in_(ids)).values(**kwargs)

            result = await self.session.execute(stmt)
            await self.session.flush()

            self.logger.info(f"Bulk updated {result.rowcount} {self.model.__name__} records")
            return result.rowcount

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Bulk update failed: {e}")
            raise RepositoryException(f"Bulk update failed: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # DELETE
    # ════════════════════════════════════════════════════════════════════════════

    async def delete(self, id: Any) -> bool:
        """
        Delete record (physical delete).

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        try:
            self.logger.debug(f"Deleting {self.model.__name__}(id={id})")

            instance = await self.get(id)
            if not instance:
                return False

            await self.session.delete(instance)
            await self.session.flush()

            self.logger.info(f"Deleted {self.model.__name__}(id={id})")
            return True

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to delete {self.model.__name__}(id={id}): {e}")
            raise RepositoryException(f"Failed to delete record: {e}")

    async def soft_delete(self, id: Any) -> bool:
        """
        Soft delete record (mark as deleted).

        Args:
            id: Record ID

        Returns:
            True if soft deleted, False if not found

        Raises:
            OperationNotAllowedError: If model doesn't support soft delete
        """
        if not hasattr(self.model, "deleted_at"):
            raise OperationNotAllowedError(
                f"{self.model.__name__} does not support soft delete"
            )

        try:
            self.logger.debug(f"Soft deleting {self.model.__name__}(id={id})")

            instance = await self.get(id)
            if not instance:
                return False

            instance.deleted_at = datetime.now(timezone.utc)
            self.session.add(instance)
            await self.session.flush()

            self.logger.info(f"Soft deleted {self.model.__name__}(id={id})")
            return True

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to soft delete {self.model.__name__}(id={id}): {e}")
            raise RepositoryException(f"Failed to soft delete record: {e}")

    async def bulk_delete(self, ids: List[Any], soft: bool = False) -> int:
        """
        Delete multiple records.

        Args:
            ids: List of record IDs
            soft: Soft delete if True

        Returns:
            Number of deleted records
        """
        try:
            self.logger.debug(f"Bulk deleting {len(ids)} {self.model.__name__} records")

            if soft and hasattr(self.model, "deleted_at"):
                count = await self.bulk_update(
                    ids, deleted_at=datetime.now(timezone.utc)
                )
            else:
                stmt = delete(self.model).where(self.model.id.in_(ids))
                result = await self.session.execute(stmt)
                await self.session.flush()
                count = result.rowcount

            self.logger.info(f"Bulk deleted {count} {self.model.__name__} records")
            return count

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Bulk delete failed: {e}")
            raise RepositoryException(f"Bulk delete failed: {e}")

    async def restore(self, id: Any) -> bool:
        """
        Restore soft-deleted record.

        Args:
            id: Record ID

        Returns:
            True if restored, False if not found

        Raises:
            OperationNotAllowedError: If model doesn't support soft delete
        """
        if not hasattr(self.model, "deleted_at"):
            raise OperationNotAllowedError(
                f"{self.model.__name__} does not support soft delete"
            )

        try:
            self.logger.debug(f"Restoring {self.model.__name__}(id={id})")

            instance = await self.get(id)
            if not instance:
                return False

            instance.deleted_at = None
            self.session.add(instance)
            await self.session.flush()

            self.logger.info(f"Restored {self.model.__name__}(id={id})")
            return True

        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to restore {self.model.__name__}(id={id}): {e}")
            raise RepositoryException(f"Failed to restore record: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════════════════════

    def _apply_filter(self, stmt, filter_: Filter):
        """Apply single filter to statement."""
        field = getattr(self.model, filter_.field, None)
        if field is None:
            raise InvalidFilterError(
                f"Field '{filter_.field}' not found on {self.model.__name__}"
            )

        if filter_.operator == FilterOperator.EQ:
            return stmt.where(field == filter_.value)
        elif filter_.operator == FilterOperator.NE:
            return stmt.where(field != filter_.value)
        elif filter_.operator == FilterOperator.GT:
            return stmt.where(field > filter_.value)
        elif filter_.operator == FilterOperator.GTE:
            return stmt.where(field >= filter_.value)
        elif filter_.operator == FilterOperator.LT:
            return stmt.where(field < filter_.value)
        elif filter_.operator == FilterOperator.LTE:
            return stmt.where(field <= filter_.value)
        elif filter_.operator == FilterOperator.IN:
            return stmt.where(field.in_(filter_.value))
        elif filter_.operator == FilterOperator.NOT_IN:
            return stmt.where(~field.in_(filter_.value))
        elif filter_.operator == FilterOperator.LIKE:
            return stmt.where(field.like(filter_.value))
        elif filter_.operator == FilterOperator.ILIKE:
            return stmt.where(field.ilike(filter_.value))
        elif filter_.operator == FilterOperator.IS_NULL:
            return stmt.where(field.is_(None))
        elif filter_.operator == FilterOperator.IS_NOT_NULL:
            return stmt.where(field.isnot(None))
        else:
            raise InvalidFilterError(f"Unknown operator: {filter_.operator}")

    async def exists(self, id: Any) -> bool:
        """Check if record exists."""
        instance = await self.get(id)
        return instance is not None

    async def find_one(self, filters: List[Filter]) -> Optional[T]:
        """Find first record matching filters."""
        items = await self.list(limit=1, filters=filters)
        return items[0] if items else None

    async def transaction(self, func: Callable) -> Any:
        """
        Execute function in transaction.

        Args:
            func: Async function to execute

        Returns:
            Function return value
        """
        try:
            result = await func()
            await self.session.commit()
            return result
        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Transaction failed: {e}")
            raise
