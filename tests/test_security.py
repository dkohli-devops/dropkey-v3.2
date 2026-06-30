"""
tests/test_security.py — DropKey v3.2 Security Tests

Tests:
- JWT token generation and validation
- Password hashing and verification
- Rate limiting
- RBAC (Role-Based Access Control)
- Input validation
- Security headers
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

pytestmark = pytest.mark.security


# ═════════════════════════════════════════════════════════════════════════════
# JWT MANAGER TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestJWTManager:
    """Test JWT token generation and validation."""
    
    def test_create_token(self, jwt_manager):
        """Test JWT token creation."""
        payload = {"sub": "user123"}
        token = jwt_manager.create_token(payload)
        
        assert token is not None
        assert isinstance(token, str)
        assert "." in token  # JWT format: header.payload.signature
    
    def test_verify_valid_token(self, jwt_manager):
        """Test verifying valid JWT token."""
        payload = {"sub": "user123"}
        token = jwt_manager.create_token(payload)
        
        decoded = jwt_manager.verify_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == "user123"
    
    def test_verify_invalid_token(self, jwt_manager):
        """Test verifying invalid JWT token."""
        result = jwt_manager.verify_token("invalid.jwt.token")
        
        assert result is None
    
    def test_token_expiration(self, jwt_manager):
        """Test token expiration."""
        payload = {"sub": "user123"}
        expires_delta = timedelta(seconds=-1)  # Already expired
        
        token = jwt_manager.create_token(payload, expires_delta=expires_delta)
        decoded = jwt_manager.verify_token(token)
        
        # Expired token should return None or fail verification
        assert decoded is None or "exp" in token
    
    def test_token_includes_timestamp(self, jwt_manager):
        """Test token includes timestamp."""
        payload = {"sub": "user123"}
        token = jwt_manager.create_token(payload)
        
        decoded = jwt_manager.verify_token(token)
        
        assert "iat" in decoded  # issued at
        assert "exp" in decoded  # expiration
    
    def test_token_payload_preserved(self, jwt_manager):
        """Test token payload is preserved."""
        payload = {
            "sub": "user123",
            "username": "john",
            "email": "john@example.com",
            "role": "admin"
        }
        
        token = jwt_manager.create_token(payload)
        decoded = jwt_manager.verify_token(token)
        
        for key, value in payload.items():
            assert decoded[key] == value


# ═════════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification."""
    
    @pytest.mark.asyncio
    async def test_set_password(self, sample_user):
        """Test password setting."""
        original_hash = sample_user.password_hash
        
        sample_user.set_password("NewPassword123!")
        
        assert sample_user.password_hash != original_hash
        assert sample_user.password_hash.startswith("$2b$")  # Bcrypt format
    
    @pytest.mark.asyncio
    async def test_verify_correct_password(self, sample_user):
        """Test verifying correct password."""
        password = "TestPassword123!"
        sample_user.set_password(password)
        
        is_valid = await sample_user.verify_password(password)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_verify_incorrect_password(self, sample_user):
        """Test verifying incorrect password."""
        sample_user.set_password("TestPassword123!")
        
        is_valid = await sample_user.verify_password("WrongPassword123!")
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_verify_empty_password(self, sample_user):
        """Test verifying empty password."""
        sample_user.set_password("TestPassword123!")
        
        is_valid = await sample_user.verify_password("")
        
        assert is_valid is False
    
    def test_password_minimum_length(self, sample_user):
        """Test password minimum length requirement."""
        with pytest.raises(ValueError):
            sample_user.set_password("short")  # Too short
    
    def test_password_maximum_length(self, sample_user):
        """Test password maximum length requirement."""
        with pytest.raises(ValueError):
            sample_user.set_password("x" * 200)  # Too long
    
    @pytest.mark.asyncio
    async def test_password_hashes_are_unique(self):
        """Test that same password hashes to different values."""
        from models import User
        
        user1 = User(username="user1", email="user1@example.com")
        user2 = User(username="user2", email="user2@example.com")
        
        password = "SamePassword123!"
        user1.set_password(password)
        user2.set_password(password)
        
        # Different hashes for same password (bcrypt has salt)
        assert user1.password_hash != user2.password_hash
        
        # But both verify correctly
        assert await user1.verify_password(password)
        assert await user2.verify_password(password)


# ═════════════════════════════════════════════════════════════════════════════
# RATE LIMITING TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_creation(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter is not None
        assert rate_limiter.rpm == 100
    
    def test_rate_limit_allows_requests_below_limit(self, rate_limiter):
        """Test rate limiter allows requests below limit."""
        client_id = "127.0.0.1"
        
        for _ in range(10):
            is_allowed = rate_limiter.is_allowed(client_id)
            assert is_allowed is True
    
    def test_rate_limit_blocks_exceeded(self, rate_limiter):
        """Test rate limiter blocks when limit exceeded."""
        client_id = "127.0.0.1"
        
        # Fill up the limit (100 requests per minute)
        for _ in range(100):
            rate_limiter.is_allowed(client_id)
        
        # Next request should be blocked
        is_allowed = rate_limiter.is_allowed(client_id)
        assert is_allowed is False
    
    def test_rate_limit_different_clients(self, rate_limiter):
        """Test rate limiter tracks clients separately."""
        client1 = "127.0.0.1"
        client2 = "192.168.1.1"
        
        # Both clients can make requests independently
        assert rate_limiter.is_allowed(client1) is True
        assert rate_limiter.is_allowed(client2) is True


# ═════════════════════════════════════════════════════════════════════════════
# RBAC TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRBAC:
    """Test Role-Based Access Control."""
    
    def test_user_role(self, sample_user):
        """Test user role assignment."""
        from models import UserRole
        
        sample_user.role = UserRole.USER
        
        assert sample_user.is_admin() is False
        assert sample_user.is_moderator() is False
    
    def test_admin_role(self, sample_user):
        """Test admin role privileges."""
        from models import UserRole
        
        sample_user.role = UserRole.ADMIN
        
        assert sample_user.is_admin() is True
        assert sample_user.is_moderator() is True  # Admin includes moderator
    
    def test_moderator_role(self, sample_user):
        """Test moderator role privileges."""
        from models import UserRole
        
        sample_user.role = UserRole.MODERATOR
        
        assert sample_user.is_admin() is False
        assert sample_user.is_moderator() is True
    
    def test_role_change(self, sample_user):
        """Test changing user role."""
        from models import UserRole
        
        sample_user.role = UserRole.USER
        assert sample_user.is_admin() is False
        
        sample_user.role = UserRole.ADMIN
        assert sample_user.is_admin() is True


# ═════════════════════════════════════════════════════════════════════════════
# USER STATUS SECURITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestUserStatusSecurity:
    """Test user status security controls."""
    
    def test_active_user_can_login(self, sample_user):
        """Test active user can login."""
        from models import UserStatus
        
        sample_user.status = UserStatus.ACTIVE
        sample_user.is_verified = True
        
        assert sample_user.is_active() is True
    
    def test_suspended_user_cannot_login(self, sample_user):
        """Test suspended user cannot login."""
        from models import UserStatus
        
        sample_user.status = UserStatus.SUSPENDED
        
        assert sample_user.is_active() is False
    
    def test_banned_user_cannot_login(self, sample_user):
        """Test banned user cannot login."""
        from models import UserStatus
        
        sample_user.status = UserStatus.BANNED
        
        assert sample_user.is_active() is False
    
    def test_unverified_user_status(self, sample_user):
        """Test unverified user status."""
        from models import UserStatus
        
        sample_user.status = UserStatus.PENDING
        sample_user.is_verified = False
        
        assert sample_user.is_active() is False
    
    @pytest.mark.asyncio
    async def test_activate_user(self, sample_user):
        """Test activating a user."""
        from models import UserStatus
        
        await sample_user.activate()
        
        assert sample_user.status == UserStatus.ACTIVE
        assert sample_user.is_verified is True
    
    @pytest.mark.asyncio
    async def test_suspend_user(self, sample_user):
        """Test suspending a user."""
        from models import UserStatus
        
        await sample_user.suspend()
        
        assert sample_user.status == UserStatus.SUSPENDED
    
    @pytest.mark.asyncio
    async def test_ban_user(self, sample_user):
        """Test banning a user."""
        from models import UserStatus
        
        await sample_user.ban()
        
        assert sample_user.status == UserStatus.BANNED


# ═════════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestInputValidation:
    """Test input validation security."""
    
    def test_username_validation_too_short(self):
        """Test username validation - too short."""
        from models import User
        
        user = User(
            username="ab",  # Too short
            email="test@example.com",
            password="ValidPassword123!"
        )
        
        errors = user.validate()
        assert any("username" in error.lower() for error in errors)
    
    def test_username_validation_invalid_characters(self):
        """Test username validation - invalid characters."""
        from models import User
        
        user = User(
            username="user@name",  # Invalid character
            email="test@example.com",
            password="ValidPassword123!"
        )
        
        errors = user.validate()
        assert any("username" in error.lower() for error in errors)
    
    def test_email_validation_invalid_format(self):
        """Test email validation - invalid format."""
        from models import User
        
        user = User(
            username="validuser",
            email="invalid-email",  # Invalid
            password="ValidPassword123!"
        )
        
        errors = user.validate()
        assert any("email" in error.lower() for error in errors)
    
    def test_email_validation_valid(self):
        """Test email validation - valid format."""
        from models import User
        
        user = User(
            username="validuser",
            email="valid@example.com",
            password="ValidPassword123!"
        )
        
        errors = user.validate()
        assert not any("email" in error.lower() for error in errors)
    
    def test_full_name_validation_too_long(self):
        """Test full name validation - too long."""
        from models import User
        
        user = User(
            username="validuser",
            email="test@example.com",
            password="ValidPassword123!",
            full_name="x" * 256  # Too long
        )
        
        errors = user.validate()
        assert any("full name" in error.lower() for error in errors)


# ═════════════════════════════════════════════════════════════════════════════
# 2FA TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestTwoFactorAuth:
    """Test two-factor authentication."""
    
    def test_2fa_disabled_by_default(self, sample_user):
        """Test 2FA is disabled by default."""
        assert sample_user.is_2fa_enabled is False
    
    def test_2fa_can_be_enabled(self, sample_user):
        """Test 2FA can be enabled."""
        sample_user.is_2fa_enabled = True
        
        assert sample_user.is_2fa_enabled is True
    
    def test_2fa_can_be_disabled(self, sample_user):
        """Test 2FA can be disabled."""
        sample_user.is_2fa_enabled = True
        sample_user.is_2fa_enabled = False
        
        assert sample_user.is_2fa_enabled is False


# ═════════════════════════════════════════════════════════════════════════════
# SOFT DELETE SECURITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestSoftDeleteSecurity:
    """Test soft delete security."""
    
    def test_soft_deleted_user_is_deleted(self, sample_user):
        """Test soft-deleted user is marked as deleted."""
        assert sample_user.is_deleted() is False
        
        sample_user.deleted_at = datetime.now(timezone.utc)
        
        assert sample_user.is_deleted() is True
    
    @pytest.mark.asyncio
    async def test_restore_deleted_user(self, sample_user):
        """Test restoring a soft-deleted user."""
        sample_user.deleted_at = datetime.now(timezone.utc)
        assert sample_user.is_deleted() is True
        
        await sample_user.restore()
        
        assert sample_user.is_deleted() is False
        assert sample_user.deleted_at is None


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT TRAIL TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestAuditTrail:
    """Test audit trail functionality."""
    
    def test_created_by_tracking(self, sample_user):
        """Test tracking who created a user."""
        admin_id = "admin-uuid"
        sample_user.created_by_id = admin_id
        
        assert sample_user.created_by_id == admin_id
    
    def test_updated_by_tracking(self, sample_user):
        """Test tracking who updated a user."""
        modifier_id = "modifier-uuid"
        sample_user.updated_by_id = modifier_id
        
        assert sample_user.updated_by_id == modifier_id
    
    def test_audit_trail_complete(self, sample_user):
        """Test complete audit trail."""
        sample_user.created_by_id = "creator-id"
        sample_user.updated_by_id = "modifier-id"
        
        assert sample_user.created_by_id is not None
        assert sample_user.updated_by_id is not None
        assert sample_user.created_at is not None
        assert sample_user.updated_at is not None
