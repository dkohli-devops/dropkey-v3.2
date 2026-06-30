"""
repository/user_repository.py — DropKey v3.2 Enterprise User Repository

FEATURES:
  [CUSTOM_QUERIES] User-specific queries
  [AUTHENTICATION] Username/email lookups for authentication
  [SEARCH] User search functionality
  [STATS] User statistics and analytics
  [FILTERING] Active/inactive user queries
  [VALIDATION] Username/email availability checks
  [BULK] Bulk user operations

DEPENDENCIES:
  pip install sqlalchemy

USAGE:
  from repository import UserRepository
  
  repo = UserRepository(session)
  user = await repo.get_by_username("john_doe")
  users = await repo.get_active_users()
  available = await repo.is_username_available("jane_doe")
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, or_, func, Text

from models import User, UserRole, UserStatus
from repository.base_repository import (
    BaseRepository,
    Filter,
    FilterOperator,
    RecordNotFoundError,
)

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """
    User repository with authentication and profile queries.

    Extends BaseRepository with User-specific operations:
    - Get by username/email
    - Search users
    - Get by role/status
    - User statistics
    - Availability checks
    """

    model = User

    # ════════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION QUERIES
    # ════════════════════════════════════════════════════════════════════════════

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username to search for

        Returns:
            User instance or None if not found
        """
        try:
            self.logger.debug(f"Getting user by username: {username}")

            stmt = select(self.model).where(self.model.username == username)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            self.logger.error(f"Failed to get user by username: {e}")
            return None

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: Email to search for

        Returns:
            User instance or None if not found
        """
        try:
            self.logger.debug(f"Getting user by email: {email}")

            stmt = select(self.model).where(self.model.email == email)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            self.logger.error(f"Failed to get user by email: {e}")
            return None

    async def get_by_username_or_email(self, identifier: str) -> Optional[User]:
        """
        Get user by username or email.

        Args:
            identifier: Username or email

        Returns:
            User instance or None if not found
        """
        try:
            stmt = select(self.model).where(
                or_(
                    self.model.username == identifier,
                    self.model.email == identifier,
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            self.logger.error(f"Failed to get user by identifier: {e}")
            return None

    # ════════════════════════════════════════════════════════════════════════════
    # STATUS QUERIES
    # ════════════════════════════════════════════════════════════════════════════

    async def get_active_users(
        self, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """
        Get all active verified users.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of active users
        """
        filters = [
            Filter("status", UserStatus.ACTIVE.value, FilterOperator.EQ),
            Filter("is_verified", True, FilterOperator.EQ),
        ]
        return await self.list(skip=skip, limit=limit, filters=filters)

    async def get_inactive_users(
        self, days: int = 30, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """
        Get users inactive for N days.

        Args:
            days: Days of inactivity
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of inactive users
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            stmt = select(self.model).where(
                and_(
                    self.model.last_login < cutoff_date,
                    self.model.status == UserStatus.ACTIVE.value,
                )
            )

            stmt = stmt.offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            self.logger.error(f"Failed to get inactive users: {e}")
            return []

    async def get_unverified_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get unverified users.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of unverified users
        """
        filters = [Filter("is_verified", False, FilterOperator.EQ)]
        return await self.list(skip=skip, limit=limit, filters=filters)

    async def get_suspended_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get suspended users.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of suspended users
        """
        filters = [Filter("status", UserStatus.SUSPENDED.value, FilterOperator.EQ)]
        return await self.list(skip=skip, limit=limit, filters=filters)

    async def get_banned_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get banned users.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of banned users
        """
        filters = [Filter("status", UserStatus.BANNED.value, FilterOperator.EQ)]
        return await self.list(skip=skip, limit=limit, filters=filters)

    # ════════════════════════════════════════════════════════════════════════════
    # ROLE QUERIES
    # ════════════════════════════════════════════════════════════════════════════

    async def get_admins(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all admin users.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of admin users
        """
        filters = [Filter("role", UserRole.ADMIN.value, FilterOperator.EQ)]
        return await self.list(skip=skip, limit=limit, filters=filters)

    async def get_moderators(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all moderator users.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of moderators
        """
        filters = [
            Filter(
                "role",
                [UserRole.MODERATOR.value, UserRole.ADMIN.value],
                FilterOperator.IN,
            )
        ]
        return await self.list(skip=skip, limit=limit, filters=filters)

    # ════════════════════════════════════════════════════════════════════════════
    # SEARCH
    # ════════════════════════════════════════════════════════════════════════════

    async def search(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
    ) -> List[User]:
        """
        Search users by username, email, or full name.

        Args:
            query: Search query
            skip: Number to skip
            limit: Maximum to return
            active_only: Only search active users

        Returns:
            List of matching users
        """
        try:
            self.logger.debug(f"Searching users: {query}")

            search_term = f"%{query}%"

            stmt = select(self.model).where(
                or_(
                    self.model.username.ilike(search_term),
                    self.model.email.ilike(search_term),
                    self.model.full_name.ilike(search_term),
                )
            )

            if active_only:
                stmt = stmt.where(
                    and_(
                        self.model.status == UserStatus.ACTIVE.value,
                        self.model.is_verified == True,
                    )
                )

            stmt = stmt.offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []

    # ════════════════════════════════════════════════════════════════════════════
    # AVAILABILITY CHECKS
    # ════════════════════════════════════════════════════════════════════════════

    async def is_username_available(self, username: str) -> bool:
        """
        Check if username is available.

        Args:
            username: Username to check

        Returns:
            True if available, False if taken
        """
        try:
            user = await self.get_by_username(username)
            return user is None

        except Exception as e:
            self.logger.error(f"Failed to check username availability: {e}")
            return False

    async def is_email_available(self, email: str) -> bool:
        """
        Check if email is available.

        Args:
            email: Email to check

        Returns:
            True if available, False if taken
        """
        try:
            user = await self.get_by_email(email)
            return user is None

        except Exception as e:
            self.logger.error(f"Failed to check email availability: {e}")
            return False

    # ════════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ════════════════════════════════════════════════════════════════════════════

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get user statistics.

        Returns:
            Dictionary with user statistics
        """
        try:
            # Total users
            total = await self.count()

            # Active users
            active = await self.count(
                filters=[Filter("status", UserStatus.ACTIVE.value, FilterOperator.EQ)]
            )

            # Verified users
            verified = await self.count(
                filters=[Filter("is_verified", True, FilterOperator.EQ)]
            )

            # Admin users
            stmt = select(func.count(self.model.id)).where(
                self.model.role == UserRole.ADMIN.value
            )
            result = await self.session.execute(stmt)
            admins = result.scalar() or 0

            # 2FA enabled
            stmt = select(func.count(self.model.id)).where(
                self.model.is_2fa_enabled == True
            )
            result = await self.session.execute(stmt)
            two_fa = result.scalar() or 0

            return {
                "total_users": total,
                "active_users": active,
                "verified_users": verified,
                "admin_users": admins,
                "two_fa_enabled": two_fa,
                "active_percentage": (active / total * 100) if total > 0 else 0,
                "verified_percentage": (verified / total * 100) if total > 0 else 0,
            }

        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}

    async def get_recent_signups(self, days: int = 7) -> List[User]:
        """
        Get users who signed up in last N days.

        Args:
            days: Number of days

        Returns:
            List of recently signed up users
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            stmt = (
                select(self.model)
                .where(self.model.created_at >= cutoff_date)
                .order_by(self.model.created_at.desc())
            )

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            self.logger.error(f"Failed to get recent signups: {e}")
            return []

    async def get_recently_active(self, minutes: int = 60) -> List[User]:
        """
        Get users active in last N minutes.

        Args:
            minutes: Number of minutes

        Returns:
            List of recently active users
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)

            stmt = (
                select(self.model)
                .where(self.model.last_activity >= cutoff_time)
                .order_by(self.model.last_activity.desc())
            )

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            self.logger.error(f"Failed to get recently active users: {e}")
            return []

    # ════════════════════════════════════════════════════════════════════════════
    # BULK OPERATIONS
    # ════════════════════════════════════════════════════════════════════════════

    async def activate_users(self, user_ids: List[Any]) -> int:
        """
        Activate multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            Number of activated users
        """
        return await self.bulk_update(
            user_ids, status=UserStatus.ACTIVE.value, is_verified=True
        )

    async def suspend_users(self, user_ids: List[Any]) -> int:
        """
        Suspend multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            Number of suspended users
        """
        return await self.bulk_update(user_ids, status=UserStatus.SUSPENDED.value)

    async def ban_users(self, user_ids: List[Any]) -> int:
        """
        Ban multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            Number of banned users
        """
        return await self.bulk_update(user_ids, status=UserStatus.BANNED.value)

    # ════════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION HELPERS
    # ════════════════════════════════════════════════════════════════════════════

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User instance if authenticated, None otherwise
        """
        try:
            self.logger.debug(f"Authenticating user: {username}")

            user = await self.get_by_username(username)
            if not user:
                self.logger.warning(f"User not found: {username}")
                return None

            if not user.is_active():
                self.logger.warning(f"User not active: {username}")
                return None

            if not await user.verify_password(password):
                self.logger.warning(f"Invalid password for user: {username}")
                return None

            # Record login
            await user.record_login()
            self.session.add(user)
            await self.session.flush()

            self.logger.info(f"User authenticated: {username}")
            return user

        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return None

    async def promote_to_admin(self, user_id: Any) -> Optional[User]:
        """
        Promote user to admin.

        Args:
            user_id: User ID

        Returns:
            Updated user or None if not found
        """
        return await self.update(user_id, role=UserRole.ADMIN.value)

    async def demote_from_admin(self, user_id: Any) -> Optional[User]:
        """
        Demote user from admin.

        Args:
            user_id: User ID

        Returns:
            Updated user or None if not found
        """
        return await self.update(user_id, role=UserRole.USER.value)
