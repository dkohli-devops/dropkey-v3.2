"""
tests/test_repository.py — DropKey v3.2 Repository Layer Tests

Tests:
- CRUD operations
- Filtering and sorting
- Pagination
- Error handling
- Custom queries
- Soft delete operations
"""

import pytest
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.integration


# ═════════════════════════════════════════════════════════════════════════════
# CREATE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCreate:
    """Test repository create operations."""
    
    async def test_create_user(self, user_repo):
        """Test creating a user."""
        user = await user_repo.create(
            username="newuser",
            email="new@example.com",
            password="TestPassword123!"
        )
        
        assert user is not None
        assert user.id is not None
        assert user.username == "newuser"
    
    async def test_create_user_with_all_fields(self, user_repo):
        """Test creating user with all fields."""
        user = await user_repo.create(
            username="fulluser",
            email="full@example.com",
            password="TestPassword123!",
            full_name="Full User",
            bio="Test bio",
            timezone="America/New_York",
            language="en"
        )
        
        assert user.full_name == "Full User"
        assert user.bio == "Test bio"
        assert user.timezone == "America/New_York"
    
    async def test_create_duplicate_username(self, user_repo, sample_user):
        """Test creating user with duplicate username."""
        from repository import DuplicateRecordError
        
        with pytest.raises(DuplicateRecordError):
            await user_repo.create(
                username=sample_user.username,
                email="different@example.com",
                password="TestPassword123!"
            )
    
    async def test_create_duplicate_email(self, user_repo, sample_user):
        """Test creating user with duplicate email."""
        from repository import DuplicateRecordError
        
        with pytest.raises(DuplicateRecordError):
            await user_repo.create(
                username="differentuser",
                email=sample_user.email,
                password="TestPassword123!"
            )
    
    async def test_bulk_create(self, user_repo):
        """Test bulk creating users."""
        items = [
            {
                "username": f"bulk{i}",
                "email": f"bulk{i}@example.com",
                "password": "TestPassword123!"
            }
            for i in range(3)
        ]
        
        users = await user_repo.bulk_create(items)
        
        assert len(users) == 3
        assert all(u.id is not None for u in users)


# ═════════════════════════════════════════════════════════════════════════════
# READ TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestRead:
    """Test repository read operations."""
    
    async def test_get_by_id(self, user_repo, sample_user):
        """Test getting user by ID."""
        user = await user_repo.get(sample_user.id)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.username == sample_user.username
    
    async def test_get_nonexistent(self, user_repo):
        """Test getting nonexistent user."""
        import uuid
        
        user = await user_repo.get(uuid.uuid4())
        
        assert user is None
    
    async def test_get_or_404(self, user_repo, sample_user):
        """Test get_or_404 with existing user."""
        user = await user_repo.get_or_404(sample_user.id)
        
        assert user.id == sample_user.id
    
    async def test_get_or_404_raises_error(self, user_repo):
        """Test get_or_404 raises error for missing user."""
        from repository import RecordNotFoundError
        import uuid
        
        with pytest.raises(RecordNotFoundError):
            await user_repo.get_or_404(uuid.uuid4())
    
    async def test_get_by_username(self, user_repo, sample_user):
        """Test getting user by username."""
        user = await user_repo.get_by_username(sample_user.username)
        
        assert user is not None
        assert user.username == sample_user.username
    
    async def test_get_by_email(self, user_repo, sample_user):
        """Test getting user by email."""
        user = await user_repo.get_by_email(sample_user.email)
        
        assert user is not None
        assert user.email == sample_user.email
    
    async def test_get_by_username_or_email_username(self, user_repo, sample_user):
        """Test getting user by username or email (username)."""
        user = await user_repo.get_by_username_or_email(sample_user.username)
        
        assert user is not None
        assert user.id == sample_user.id
    
    async def test_get_by_username_or_email_email(self, user_repo, sample_user):
        """Test getting user by username or email (email)."""
        user = await user_repo.get_by_username_or_email(sample_user.email)
        
        assert user is not None
        assert user.id == sample_user.id


# ═════════════════════════════════════════════════════════════════════════════
# LIST AND PAGINATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestListAndPagination:
    """Test repository list and pagination."""
    
    async def test_list_all(self, user_repo, sample_users):
        """Test listing all users."""
        users = await user_repo.list()
        
        assert len(users) >= len(sample_users)
    
    async def test_list_with_limit(self, user_repo, sample_users):
        """Test listing with limit."""
        users = await user_repo.list(limit=2)
        
        assert len(users) <= 2
    
    async def test_list_with_skip(self, user_repo, sample_users):
        """Test listing with skip."""
        all_users = await user_repo.list()
        skipped = await user_repo.list(skip=2, limit=10)
        
        # Skipped should have fewer or equal items
        assert len(skipped) <= len(all_users)
    
    async def test_list_with_sorting(self, user_repo, sample_users):
        """Test listing with sorting."""
        users_asc = await user_repo.list(sort_by="created_at", sort_order="asc")
        users_desc = await user_repo.list(sort_by="created_at", sort_order="desc")
        
        # Both should return results
        assert len(users_asc) > 0
        assert len(users_desc) > 0
    
    async def test_page_object(self, user_repo, sample_users):
        """Test page object with metadata."""
        page = await user_repo.page(skip=0, limit=10)
        
        assert page is not None
        assert page.items is not None
        assert page.total >= 0
        assert page.page_number >= 1
        assert page.page_count >= 1
        assert hasattr(page, 'has_next')
        assert hasattr(page, 'has_previous')
    
    async def test_page_next_previous(self, user_repo, sample_users):
        """Test page next/previous indicators."""
        page1 = await user_repo.page(skip=0, limit=2)
        
        if page1.total > 2:
            assert page1.has_next is True
            assert page1.has_previous is False
        
        page2 = await user_repo.page(skip=2, limit=2)
        
        if page2.total > 2:
            assert page2.has_previous is True


# ═════════════════════════════════════════════════════════════════════════════
# UPDATE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUpdate:
    """Test repository update operations."""
    
    async def test_update_user(self, user_repo, sample_user):
        """Test updating a user."""
        updated = await user_repo.update(
            sample_user.id,
            full_name="Updated Name"
        )
        
        assert updated is not None
        assert updated.full_name == "Updated Name"
    
    async def test_update_multiple_fields(self, user_repo, sample_user):
        """Test updating multiple fields."""
        updated = await user_repo.update(
            sample_user.id,
            full_name="New Name",
            bio="New bio",
            timezone="UTC"
        )
        
        assert updated.full_name == "New Name"
        assert updated.bio == "New bio"
        assert updated.timezone == "UTC"
    
    async def test_update_nonexistent(self, user_repo):
        """Test updating nonexistent user."""
        import uuid
        
        updated = await user_repo.update(uuid.uuid4(), full_name="New")
        
        assert updated is None
    
    async def test_bulk_update(self, user_repo, sample_users):
        """Test bulk updating users."""
        ids = [u.id for u in sample_users[:2]]
        
        count = await user_repo.bulk_update(ids, timezone="UTC")
        
        assert count >= 0


# ═════════════════════════════════════════════════════════════════════════════
# DELETE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDelete:
    """Test repository delete operations."""
    
    async def test_soft_delete_user(self, user_repo, sample_user):
        """Test soft deleting a user."""
        deleted = await user_repo.soft_delete(sample_user.id)
        
        assert deleted is True
        
        # User should still exist
        user = await user_repo.get(sample_user.id)
        assert user.is_deleted() is True
    
    async def test_soft_delete_nonexistent(self, user_repo):
        """Test soft deleting nonexistent user."""
        import uuid
        
        deleted = await user_repo.soft_delete(uuid.uuid4())
        
        assert deleted is False
    
    async def test_restore_deleted_user(self, user_repo, sample_user):
        """Test restoring deleted user."""
        await user_repo.soft_delete(sample_user.id)
        restored = await user_repo.restore(sample_user.id)
        
        assert restored is True
        
        user = await user_repo.get(sample_user.id)
        assert user.is_deleted() is False
    
    async def test_bulk_delete(self, user_repo):
        """Test bulk deleting users."""
        # Create test users
        users = await user_repo.bulk_create([
            {"username": f"del{i}", "email": f"del{i}@example.com", "password": "Test123!"}
            for i in range(3)
        ])
        
        ids = [u.id for u in users]
        count = await user_repo.bulk_delete(ids, soft=True)
        
        assert count >= 0
    
    async def test_list_excludes_deleted_by_default(self, user_repo, sample_user):
        """Test list excludes soft-deleted users by default."""
        await user_repo.soft_delete(sample_user.id)
        
        users = await user_repo.list()
        user_ids = [u.id for u in users]
        
        assert sample_user.id not in user_ids
    
    async def test_list_includes_deleted_with_flag(self, user_repo, sample_user):
        """Test list includes deleted users with flag."""
        await user_repo.soft_delete(sample_user.id)
        
        users = await user_repo.list(include_deleted=True)
        user_ids = [u.id for u in users]
        
        assert sample_user.id in user_ids


# ═════════════════════════════════════════════════════════════════════════════
# FILTERING TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestFiltering:
    """Test repository filtering."""
    
    async def test_filter_by_status(self, user_repo, sample_user):
        """Test filtering by status."""
        from models import UserStatus
        from repository import Filter, FilterOperator
        
        sample_user.status = UserStatus.ACTIVE
        
        filters = [Filter("status", UserStatus.ACTIVE.value, FilterOperator.EQ)]
        users = await user_repo.list(filters=filters)
        
        assert len(users) > 0
    
    async def test_filter_by_verified(self, user_repo, sample_user):
        """Test filtering by verification status."""
        from repository import Filter, FilterOperator
        
        sample_user.is_verified = True
        
        filters = [Filter("is_verified", True, FilterOperator.EQ)]
        users = await user_repo.list(filters=filters)
        
        assert len(users) > 0
    
    async def test_multiple_filters(self, user_repo, sample_user):
        """Test multiple filters."""
        from models import UserStatus
        from repository import Filter, FilterOperator
        
        sample_user.status = UserStatus.ACTIVE
        sample_user.is_verified = True
        
        filters = [
            Filter("status", UserStatus.ACTIVE.value, FilterOperator.EQ),
            Filter("is_verified", True, FilterOperator.EQ),
        ]
        
        users = await user_repo.list(filters=filters)
        
        assert len(users) > 0


# ═════════════════════════════════════════════════════════════════════════════
# SEARCH AND QUERY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSearch:
    """Test repository search functionality."""
    
    async def test_search_by_username(self, user_repo, sample_user):
        """Test searching by username."""
        results = await user_repo.search(sample_user.username[:3])
        
        assert len(results) > 0
    
    async def test_search_by_email(self, user_repo, sample_user):
        """Test searching by email."""
        results = await user_repo.search(sample_user.email.split("@")[0])
        
        assert len(results) > 0
    
    async def test_search_returns_empty(self, user_repo):
        """Test search returns empty for no matches."""
        results = await user_repo.search("nonexistentquery")
        
        assert len(results) == 0
    
    async def test_is_username_available(self, user_repo, sample_user):
        """Test checking username availability."""
        taken = await user_repo.is_username_available(sample_user.username)
        available = await user_repo.is_username_available("definitely_unique_username")
        
        assert taken is False
        assert available is True
    
    async def test_is_email_available(self, user_repo, sample_user):
        """Test checking email availability."""
        taken = await user_repo.is_email_available(sample_user.email)
        available = await user_repo.is_email_available("unique@example.com")
        
        assert taken is False
        assert available is True


# ═════════════════════════════════════════════════════════════════════════════
# COUNT TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCount:
    """Test repository count operations."""
    
    async def test_count_all(self, user_repo, sample_users):
        """Test counting all users."""
        count = await user_repo.count()
        
        assert count >= len(sample_users)
    
    async def test_count_with_filter(self, user_repo, sample_user):
        """Test counting with filter."""
        from models import UserStatus
        from repository import Filter, FilterOperator
        
        sample_user.status = UserStatus.ACTIVE
        
        filters = [Filter("status", UserStatus.ACTIVE.value, FilterOperator.EQ)]
        count = await user_repo.count(filters=filters)
        
        assert count >= 0


# ═════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestAuthentication:
    """Test repository authentication methods."""
    
    async def test_authenticate_valid(self, user_repo, sample_user):
        """Test authenticating with valid credentials."""
        password = "TestPassword123!"
        sample_user.set_password(password)
        
        user = await user_repo.authenticate(sample_user.username, password)
        
        assert user is not None
        assert user.id == sample_user.id
    
    async def test_authenticate_invalid_password(self, user_repo, sample_user):
        """Test authenticating with invalid password."""
        sample_user.set_password("TestPassword123!")
        
        user = await user_repo.authenticate(sample_user.username, "WrongPassword")
        
        assert user is None
    
    async def test_authenticate_nonexistent(self, user_repo):
        """Test authenticating nonexistent user."""
        user = await user_repo.authenticate("nonexistent", "password")
        
        assert user is None


# ═════════════════════════════════════════════════════════════════════════════
# STATUS QUERY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestStatusQueries:
    """Test repository status-specific queries."""
    
    async def test_get_active_users(self, user_repo, sample_user):
        """Test getting active users."""
        from models import UserStatus
        
        sample_user.status = UserStatus.ACTIVE
        sample_user.is_verified = True
        
        users = await user_repo.get_active_users()
        
        assert len(users) > 0
    
    async def test_get_unverified_users(self, user_repo, sample_user):
        """Test getting unverified users."""
        sample_user.is_verified = False
        
        users = await user_repo.get_unverified_users()
        
        assert len(users) > 0
    
    async def test_get_suspended_users(self, user_repo, sample_user):
        """Test getting suspended users."""
        from models import UserStatus
        
        sample_user.status = UserStatus.SUSPENDED
        
        users = await user_repo.get_suspended_users()
        
        assert len(users) > 0
    
    async def test_get_admins(self, user_repo, sample_user):
        """Test getting admin users."""
        from models import UserRole
        
        sample_user.role = UserRole.ADMIN
        
        users = await user_repo.get_admins()
        
        assert len(users) > 0


# ═════════════════════════════════════════════════════════════════════════════
# STATISTICS TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestStatistics:
    """Test repository statistics."""
    
    async def test_get_statistics(self, user_repo, sample_users):
        """Test getting user statistics."""
        stats = await user_repo.get_statistics()
        
        assert "total_users" in stats
        assert "active_users" in stats
        assert "verified_users" in stats
        assert stats["total_users"] > 0
    
    async def test_get_recent_signups(self, user_repo, sample_users):
        """Test getting recent signups."""
        users = await user_repo.get_recent_signups(days=7)
        
        assert isinstance(users, list)
    
    async def test_get_recently_active(self, user_repo, sample_user):
        """Test getting recently active users."""
        sample_user.last_activity = datetime.now(timezone.utc)
        
        users = await user_repo.get_recently_active(minutes=60)
        
        assert isinstance(users, list)


# ═════════════════════════════════════════════════════════════════════════════
# EXISTENCE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestExistence:
    """Test repository existence checks."""
    
    async def test_exists_returns_true(self, user_repo, sample_user):
        """Test exists returns true for existing user."""
        exists = await user_repo.exists(sample_user.id)
        
        assert exists is True
    
    async def test_exists_returns_false(self, user_repo):
        """Test exists returns false for nonexistent user."""
        import uuid
        
        exists = await user_repo.exists(uuid.uuid4())
        
        assert exists is False


# ═════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestErrorHandling:
    """Test repository error handling."""
    
    async def test_invalid_filter_raises_error(self, user_repo):
        """Test invalid filter raises error."""
        from repository import Filter, FilterOperator, InvalidFilterError
        
        invalid_filter = [Filter("nonexistent_field", "value", FilterOperator.EQ)]
        
        with pytest.raises(InvalidFilterError):
            await user_repo.list(filters=invalid_filter)
