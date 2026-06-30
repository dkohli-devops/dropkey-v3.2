"""
models/user.py — DropKey v3.2 Enterprise User Model

FEATURES:
  [AUTH] Password hashing with bcrypt
  [PROFILE] User profile information
  [STATUS] Account status tracking
  [AUDIT] Creation/update tracking
  [VALIDATION] Email format validation
  [SOFT_DELETE] Soft delete support
  [RELATIONSHIPS] Ready for foreign keys
  [INDEXING] Strategic indexes for performance
  [SERIALIZATION] Custom JSON serialization

DEPENDENCIES:
  pip install bcrypt

USAGE:
  from models.user import User
  
  user = User(
      username="john",
      email="john@example.com",
      full_name="John Doe"
  )
  user.set_password("secure-password")
  
  # Verify password
  if await user.verify_password("secure-password"):
      user.last_login = datetime.now(timezone.utc)
"""

import re
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import Column, String, Boolean, DateTime, Text, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
import bcrypt
import enum

from models.base import BaseModel, SoftDeleteMixin, AuditMixin, GUID

# ═════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═════════════════════════════════════════════════════════════════════════════


class UserRole(str, enum.Enum):
    """User role enumeration."""

    USER = "user"
    """Regular user with standard permissions."""

    ADMIN = "admin"
    """Administrator with elevated permissions."""

    MODERATOR = "moderator"
    """Moderator with content management permissions."""

    SUPPORT = "support"
    """Support staff with customer assistance permissions."""


class UserStatus(str, enum.Enum):
    """User account status."""

    PENDING = "pending"
    """Account created but not verified."""

    ACTIVE = "active"
    """Account is active and verified."""

    SUSPENDED = "suspended"
    """Account temporarily suspended."""

    BANNED = "banned"
    """Account permanently banned."""

    ARCHIVED = "archived"
    """Account archived (soft deleted)."""


# ═════════════════════════════════════════════════════════════════════════════
# USER MODEL
# ═════════════════════════════════════════════════════════════════════════════


class User(SoftDeleteMixin, AuditMixin, BaseModel):
    """
    User model for authentication and profile management.
    
    Stores:
    - Authentication (username, email, password hash)
    - Profile information (full name, avatar, bio)
    - Account status (active, suspended, banned)
    - Account security (2FA, email verified)
    - Activity tracking (last login, IP address)
    - Preferences (timezone, language, notifications)
    
    Features:
    ✅ Password hashing with bcrypt
    ✅ Email validation
    ✅ Profile information
    ✅ Account status tracking
    ✅ Activity logging
    ✅ Soft delete support
    ✅ Audit trail (created_by, updated_by)
    ✅ Timestamps with timezone
    ✅ Strategic indexes
    
    Indexes:
    - username (unique)
    - email (unique)
    - created_at (for sorting)
    - status (for filtering)
    """

    __tablename__ = "users"

    # ════════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ════════════════════════════════════════════════════════════════════════════

    username = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    """Unique username for login and display."""

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    """Unique email address."""

    password_hash = Column(
        String(255),
        nullable=False,
    )
    """Bcrypt password hash (never plain text!)."""

    # ════════════════════════════════════════════════════════════════════════════
    # PROFILE
    # ════════════════════════════════════════════════════════════════════════════

    full_name = Column(
        String(255),
        nullable=True,
    )
    """Full name of user (optional)."""

    avatar_url = Column(
        String(500),
        nullable=True,
    )
    """URL to user's avatar image."""

    bio = Column(
        Text,
        nullable=True,
    )
    """User biography or description."""

    timezone = Column(
        String(50),
        default="UTC",
        nullable=False,
    )
    """User's timezone (e.g., "America/New_York")."""

    language = Column(
        String(10),
        default="en",
        nullable=False,
    )
    """User's preferred language (e.g., "en", "es", "fr")."""

    # ════════════════════════════════════════════════════════════════════════════
    # ACCOUNT STATUS
    # ════════════════════════════════════════════════════════════════════════════

    status = Column(
        SQLEnum(UserStatus),
        default=UserStatus.PENDING,
        nullable=False,
        index=True,
    )
    """Account status (pending, active, suspended, banned, archived)."""

    role = Column(
        SQLEnum(UserRole),
        default=UserRole.USER,
        nullable=False,
    )
    """User role (user, admin, moderator, support)."""

    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    """Whether email has been verified."""

    is_2fa_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    """Whether two-factor authentication is enabled."""

    # ════════════════════════════════════════════════════════════════════════════
    # ACTIVITY TRACKING
    # ════════════════════════════════════════════════════════════════════════════

    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    """Timestamp of last login."""

    last_login_ip = Column(
        String(45),
        nullable=True,
    )
    """IP address of last login (IPv4 or IPv6)."""

    last_activity = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    """Timestamp of last activity."""

    # ════════════════════════════════════════════════════════════════════════════
    # PREFERENCES
    # ════════════════════════════════════════════════════════════════════════════

    notifications_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
    )
    """Whether user wants email notifications."""

    newsletter_subscribed = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    """Whether user is subscribed to newsletter."""

    # ════════════════════════════════════════════════════════════════════════════
    # METADATA
    # ════════════────────────────────────────────────────────────────────────

    metadata_ = Column(
        Text,
        nullable=True,
    )
    """JSON metadata for custom fields."""

    # ════════════════════════════════════════════════════════════════════════════
    # INDEXES
    # ════════════════════════════════════════════════════════════════════════════

    __table_args__ = (
        # Index for listing active users
        Index("ix_users_status_created_at", "status", "created_at"),
        # Index for finding verified users
        Index("ix_users_is_verified_created_at", "is_verified", "created_at"),
        # Index for last login tracking
        Index("ix_users_last_login", "last_login"),
    )

    # ════════════════════════════════════════════════════════════════════════════
    # RELATIONSHIPS (for future use)
    # ════════════════════════════════════════════════════════════════════════════

    # transfer_sessions = relationship("TransferSession", back_populates="owner")
    # audit_logs = relationship("AuditLog", back_populates="user")

    # ════════════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ════════════════════════════════════════════════════════════════════════════

    def __init__(
        self,
        username: str,
        email: str,
        password: str = "",
        full_name: str = "",
        **kwargs,
    ):
        """
        Initialize user.
        
        Args:
            username: Unique username
            email: User email
            password: Plain text password (will be hashed)
            full_name: Full name
            **kwargs: Additional fields
        """
        super().__init__(**kwargs)

        self.username = username
        self.email = email
        self.full_name = full_name

        if password:
            self.set_password(password)

    def __repr__(self) -> str:
        """String representation."""
        return f"<User(username={self.username}, email={self.email}, status={self.status})>"

    # ════════════════════════════════════════════════════════════════════════════
    # PASSWORD MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    def set_password(self, password: str) -> None:
        """
        Hash and set password.
        
        Args:
            password: Plain text password (min 8 characters)
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        if len(password) > 128:
            raise ValueError("Password must be less than 128 characters")

        # Hash password with bcrypt (cost factor 12)
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    async def verify_password(self, password: str) -> bool:
        """
        Verify plain text password against hash.
        
        Args:
            password: Plain text password to verify
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                self.password_hash.encode("utf-8"),
            )
        except Exception:
            return False

    # ════════════════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════════════════

    def validate(self) -> List[str]:
        """
        Validate user model.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Username validation
        if not self.username:
            errors.append("Username is required")
        elif len(self.username) < 3:
            errors.append("Username must be at least 3 characters")
        elif len(self.username) > 255:
            errors.append("Username must be less than 255 characters")
        elif not re.match(r"^[a-zA-Z0-9_-]+$", self.username):
            errors.append("Username can only contain letters, numbers, _, -")

        # Email validation
        if not self.email:
            errors.append("Email is required")
        elif not self._is_valid_email(self.email):
            errors.append("Email is not valid")

        # Password validation (if set)
        if self.password_hash and len(self.password_hash) == 0:
            errors.append("Password hash is empty")

        # Full name validation
        if self.full_name and len(self.full_name) > 255:
            errors.append("Full name is too long")

        # Status validation
        try:
            if self.status and self.status not in [s.value for s in UserStatus]:
                errors.append(f"Invalid status: {self.status}")
        except Exception:
            errors.append("Status validation error")

        # Role validation
        try:
            if self.role and self.role not in [r.value for r in UserRole]:
                errors.append(f"Invalid role: {self.role}")
        except Exception:
            errors.append("Role validation error")

        return errors

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not email or len(email) > 255:
            return False

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    # ════════════════════════════════════════════════════════════════════════════
    # STATUS MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    def is_active(self) -> bool:
        """Check if user account is active."""
        return self.status == UserStatus.ACTIVE and not self.is_deleted()

    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == UserRole.ADMIN

    def is_moderator(self) -> bool:
        """Check if user is moderator."""
        return self.role in (UserRole.MODERATOR, UserRole.ADMIN)

    async def activate(self) -> None:
        """Activate user account."""
        self.status = UserStatus.ACTIVE
        self.is_verified = True

    async def suspend(self) -> None:
        """Suspend user account."""
        self.status = UserStatus.SUSPENDED

    async def ban(self) -> None:
        """Ban user account."""
        self.status = UserStatus.BANNED

    async def archive(self) -> None:
        """Archive user account (soft delete)."""
        self.status = UserStatus.ARCHIVED
        self.deleted_at = datetime.now(timezone.utc)

    # ════════════════════════════════════════════════════════════════════════════
    # ACTIVITY TRACKING
    # ════════════════════════════════════════════════════════════════════════════

    async def record_login(self, ip_address: str = "") -> None:
        """
        Record user login.
        
        Args:
            ip_address: IP address of login
        """
        self.last_login = datetime.now(timezone.utc)
        if ip_address:
            self.last_login_ip = ip_address

    async def record_activity(self) -> None:
        """Record user activity."""
        self.last_activity = datetime.now(timezone.utc)

    @property
    def days_since_login(self) -> Optional[float]:
        """Days since last login (or None if never logged in)."""
        if not self.last_login:
            return None
        return (datetime.now(timezone.utc) - self.last_login).days

    @property
    def is_inactive(self, days: int = 30) -> bool:
        """Check if user is inactive (no login for N days)."""
        if not self.last_login:
            return True
        return self.days_since_login >= days

    # ════════════════════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ════════════════════════════════════════════════════════════════════════════

    def to_dict(self, include_sensitive: bool = False, **kwargs) -> dict:
        """
        Convert user to dictionary.
        
        Args:
            include_sensitive: Include password_hash if True
            **kwargs: Additional arguments for parent to_dict()
            
        Returns:
            Dictionary representation of user
        """
        # Always exclude password hash unless explicitly requested
        exclude = kwargs.get("exclude", [])
        if not include_sensitive and "password_hash" not in exclude:
            exclude.append("password_hash")

        kwargs["exclude"] = exclude

        result = super().to_dict(**kwargs)

        # Add computed properties
        result["is_active"] = self.is_active()
        result["is_admin"] = self.is_admin()
        result["days_since_login"] = self.days_since_login

        # Convert enums to strings
        if "status" in result:
            result["status"] = result["status"].value if isinstance(result["status"], UserStatus) else result["status"]
        if "role" in result:
            result["role"] = result["role"].value if isinstance(result["role"], UserRole) else result["role"]

        return result

    def to_public_dict(self) -> dict:
        """
        Get public-safe user data (no sensitive info).
        
        Returns:
            Dictionary safe to send to other users
        """
        return self.to_dict(
            include=["id", "username", "full_name", "avatar_url", "bio", "created_at"],
            include_sensitive=False,
        )


# ═════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═════════════════════════════════════════════════════════════════════════════

"""
# Create user
user = User(
    username="john_doe",
    email="john@example.com",
    password="SecurePassword123!",
    full_name="John Doe"
)

# Validate
errors = user.validate()
if errors:
    raise ValueError(f"Invalid user: {errors}")

# Verify password
is_valid = await user.verify_password("SecurePassword123!")

# Record login
await user.record_login(ip_address="192.168.1.1")

# Check status
if user.is_active():
    print("User account is active")

# Soft delete
await user.archive()

# Serialize
user_dict = user.to_dict(include_sensitive=False)
public_dict = user.to_public_dict()
"""
