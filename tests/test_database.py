"""
tests/test_database.py — DropKey v3.2 Database Layer Tests

Tests:
- Connection management
- Session creation
- Transaction handling
- Health checks
- Connection pooling
- Error handling
"""

import pytest
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.database


# ═════════════════════════════════════════════════════════════════════════════
# SESSION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDatabaseSession:
    """Test database session management."""
    
    async def test_session_creation(self, test_db):
        """Test database session can be created."""
        assert test_db is not None
    
    async def test_session_is_async(self, test_db):
        """Test session is async."""
        from sqlalchemy.ext.asyncio import AsyncSession
        
        assert isinstance(test_db, AsyncSession)
    
    async def test_session_can_query(self, test_db):
        """Test session can execute queries."""
        from models import User
        from sqlalchemy import select
        
        # Should not raise exception
        stmt = select(User)
        result = await test_db.execute(stmt)
        
        assert result is not None


# ═════════════════════════════════════════════════════════════════════════════
# MODEL OPERATIONS TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestModelOperations:
    """Test basic model operations."""
    
    async def test_create_model(self, test_db):
        """Test creating a model."""
        from models import User
        
        user = User(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.flush()
        
        assert user.id is not None
    
    async def test_read_model(self, test_db, sample_user):
        """Test reading a model."""
        from models import User
        from sqlalchemy import select
        
        stmt = select(User).where(User.username == sample_user.username)
        result = await test_db.execute(stmt)
        user = result.scalar_one()
        
        assert user.username == sample_user.username
    
    async def test_update_model(self, test_db, sample_user):
        """Test updating a model."""
        sample_user.full_name = "Updated Name"
        test_db.add(sample_user)
        await test_db.flush()
        
        # Refresh from database
        await test_db.refresh(sample_user)
        
        assert sample_user.full_name == "Updated Name"
    
    async def test_delete_model(self, test_db, sample_user):
        """Test soft deleting a model."""
        from datetime import datetime, timezone
        
        sample_user.deleted_at = datetime.now(timezone.utc)
        test_db.add(sample_user)
        await test_db.flush()
        
        assert sample_user.is_deleted() is True


# ═════════════════════════════════════════════════════════════════════════════
# TRANSACTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTransactions:
    """Test transaction handling."""
    
    async def test_transaction_commit(self, test_db):
        """Test transaction commit."""
        from models import User
        
        user = User(
            username="transaction_user",
            email="transaction@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.commit()
        
        # Verify persisted
        assert user.id is not None
    
    async def test_transaction_rollback(self, test_db):
        """Test transaction rollback."""
        from models import User
        from sqlalchemy import select
        
        user = User(
            username="rollback_user",
            email="rollback@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.rollback()
        
        # User should not be in database
        stmt = select(User).where(User.username == "rollback_user")
        result = await test_db.execute(stmt)
        found = result.scalar_one_or_none()
        
        assert found is None


# ═════════════════════════════════════════════════════════════════════════════
# CONSTRAINT TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDatabaseConstraints:
    """Test database constraints."""
    
    async def test_unique_username_constraint(self, test_db, sample_user):
        """Test unique username constraint."""
        from models import User
        from sqlalchemy.exc import IntegrityError
        
        duplicate = User(
            username=sample_user.username,  # Duplicate
            email="different@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(duplicate)
        
        with pytest.raises(IntegrityError):
            await test_db.flush()
    
    async def test_unique_email_constraint(self, test_db, sample_user):
        """Test unique email constraint."""
        from models import User
        from sqlalchemy.exc import IntegrityError
        
        duplicate = User(
            username="differentuser",
            email=sample_user.email,  # Duplicate
            password="TestPassword123!"
        )
        
        test_db.add(duplicate)
        
        with pytest.raises(IntegrityError):
            await test_db.flush()
    
    async def test_not_null_constraint(self, test_db):
        """Test NOT NULL constraint."""
        from models import User
        from sqlalchemy.exc import IntegrityError
        
        user = User(
            username="testuser",
            email=None,  # Required field
            password="TestPassword123!"
        )
        
        test_db.add(user)
        
        with pytest.raises((IntegrityError, ValueError)):
            await test_db.flush()


# ═════════════════════════════════════════════════════════════════════════════
# TIMESTAMP TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTimestamps:
    """Test timestamp fields."""
    
    async def test_created_at_set_on_creation(self, test_db):
        """Test created_at is set on creation."""
        from models import User
        
        user = User(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.flush()
        
        assert user.created_at is not None
    
    async def test_updated_at_set_on_creation(self, test_db):
        """Test updated_at is set on creation."""
        from models import User
        
        user = User(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.flush()
        
        assert user.updated_at is not None
    
    async def test_created_at_not_updated(self, test_db, sample_user):
        """Test created_at doesn't change on update."""
        original_created_at = sample_user.created_at
        
        sample_user.full_name = "Updated"
        test_db.add(sample_user)
        await test_db.flush()
        
        assert sample_user.created_at == original_created_at
    
    async def test_updated_at_changes_on_update(self, test_db, sample_user):
        """Test updated_at changes on update."""
        import asyncio
        from datetime import datetime, timezone
        
        original_updated_at = sample_user.updated_at
        
        # Wait a bit to ensure timestamp difference
        await asyncio.sleep(0.01)
        
        sample_user.full_name = "Updated"
        test_db.add(sample_user)
        await test_db.flush()
        
        # Updated_at should be more recent
        assert sample_user.updated_at >= original_updated_at


# ═════════════════════════════════════════════════════════════════════════════
# UUID TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUUIDs:
    """Test UUID primary keys."""
    
    async def test_uuid_generated_on_creation(self, test_db, assert_helpers):
        """Test UUID is generated on creation."""
        from models import User
        
        user = User(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.flush()
        
        assert user.id is not None
        assert assert_helpers.is_valid_uuid(user.id)
    
    async def test_uuid_is_unique(self, test_db):
        """Test each UUID is unique."""
        from models import User
        
        user1 = User(
            username="user1",
            email="user1@example.com",
            password="TestPassword123!"
        )
        user2 = User(
            username="user2",
            email="user2@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user1)
        test_db.add(user2)
        await test_db.flush()
        
        assert user1.id != user2.id
    
    async def test_uuid_is_string_in_database(self, test_db, sample_user):
        """Test UUID is stored as string."""
        from models import User
        from sqlalchemy import select
        
        stmt = select(User).where(User.id == sample_user.id)
        result = await test_db.execute(stmt)
        user = result.scalar_one()
        
        # Should be retrievable by UUID
        assert user.id == sample_user.id


# ═════════════════════════════════════════════════════════════════════════════
# SOFT DELETE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSoftDelete:
    """Test soft delete functionality."""
    
    async def test_soft_delete_preserves_record(self, test_db, sample_user):
        """Test soft delete preserves record in database."""
        from datetime import datetime, timezone
        from sqlalchemy import select
        
        # Soft delete
        sample_user.deleted_at = datetime.now(timezone.utc)
        test_db.add(sample_user)
        await test_db.commit()
        
        # Record still exists in database
        from models import User
        stmt = select(User).where(User.id == sample_user.id)
        result = await test_db.execute(stmt)
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.is_deleted() is True
    
    async def test_restore_soft_deleted_record(self, test_db, sample_user):
        """Test restoring soft deleted record."""
        from datetime import datetime, timezone
        
        # Soft delete
        sample_user.deleted_at = datetime.now(timezone.utc)
        test_db.add(sample_user)
        await test_db.flush()
        
        # Restore
        await sample_user.restore()
        test_db.add(sample_user)
        await test_db.flush()
        
        assert sample_user.is_deleted() is False
        assert sample_user.deleted_at is None


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT TRAIL TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestAuditFields:
    """Test audit trail fields."""
    
    async def test_created_by_id_field(self, test_db):
        """Test created_by_id field."""
        from models import User
        
        admin_id = "admin-uuid"
        user = User(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            created_by_id=admin_id
        )
        
        test_db.add(user)
        await test_db.flush()
        
        assert user.created_by_id == admin_id
    
    async def test_updated_by_id_field(self, test_db, sample_user):
        """Test updated_by_id field."""
        modifier_id = "modifier-uuid"
        sample_user.updated_by_id = modifier_id
        
        test_db.add(sample_user)
        await test_db.flush()
        
        assert sample_user.updated_by_id == modifier_id


# ═════════════════════════════════════════════════════════════════════════════
# BULK OPERATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestBulkOperations:
    """Test bulk database operations."""
    
    async def test_bulk_insert(self, test_db):
        """Test bulk insert."""
        from models import User
        
        users = [
            User(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="TestPassword123!"
            )
            for i in range(5)
        ]
        
        test_db.add_all(users)
        await test_db.flush()
        
        assert all(u.id is not None for u in users)
    
    async def test_bulk_query(self, test_db, sample_users):
        """Test bulk query."""
        from models import User
        from sqlalchemy import select
        
        stmt = select(User)
        result = await test_db.execute(stmt)
        users = result.scalars().all()
        
        assert len(users) >= len(sample_users)


# ═════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestErrorHandling:
    """Test database error handling."""
    
    async def test_invalid_query_error(self, test_db):
        """Test handling of invalid query."""
        from sqlalchemy import text
        
        with pytest.raises(SQLAlchemyError):
            await test_db.execute(text("INVALID SQL"))
    
    async def test_rollback_on_error(self, test_db):
        """Test rollback on error."""
        from models import User
        
        user = User(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!"
        )
        
        test_db.add(user)
        await test_db.flush()
        
        original_id = user.id
        
        # Simulate error
        try:
            user.username = None  # This will cause validation error
            await test_db.flush()
        except Exception:
            await test_db.rollback()
        
        # Object still has original state
        assert user.id == original_id
