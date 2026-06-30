"""
tests/fixtures.py — DropKey v3.2 Test Data & Fixture Helpers

Provides:
- Test data factories
- Bulk data creation
- Data cleanup
- Fixture utilities
"""

from typing import List, Dict, Any
from datetime import datetime, timezone
from models import User, UserRole, UserStatus


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_user_data(
        username: str = "testuser",
        email: str = "test@example.com",
        password: str = "TestPassword123!",
        full_name: str = "Test User",
        **kwargs
    ) -> Dict[str, Any]:
        """Create user data dictionary."""
        data = {
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name,
        }
        data.update(kwargs)
        return data
    
    @staticmethod
    def create_users_data(count: int = 5) -> List[Dict[str, Any]]:
        """Create multiple user data dictionaries."""
        return [
            TestDataFactory.create_user_data(
                username=f"user{i}",
                email=f"user{i}@example.com",
                full_name=f"User {i}"
            )
            for i in range(count)
        ]
    
    @staticmethod
    def create_admin_user_data(**kwargs) -> Dict[str, Any]:
        """Create admin user data."""
        data = TestDataFactory.create_user_data(**kwargs)
        data["role"] = UserRole.ADMIN.value
        data["status"] = UserStatus.ACTIVE.value
        data["is_verified"] = True
        return data
    
    @staticmethod
    def create_suspended_user_data(**kwargs) -> Dict[str, Any]:
        """Create suspended user data."""
        data = TestDataFactory.create_user_data(**kwargs)
        data["status"] = UserStatus.SUSPENDED.value
        return data
    
    @staticmethod
    def create_inactive_user_data(**kwargs) -> Dict[str, Any]:
        """Create inactive user data."""
        data = TestDataFactory.create_user_data(**kwargs)
        data["status"] = UserStatus.PENDING.value
        data["is_verified"] = False
        return data
    
    @staticmethod
    def create_verified_user_data(**kwargs) -> Dict[str, Any]:
        """Create verified user data."""
        data = TestDataFactory.create_user_data(**kwargs)
        data["status"] = UserStatus.ACTIVE.value
        data["is_verified"] = True
        return data


class TestDataSeeder:
    """Seed test database with data."""
    
    @staticmethod
    async def seed_users(repo, count: int = 10) -> List[User]:
        """Seed database with test users."""
        users_data = TestDataFactory.create_users_data(count)
        return await repo.bulk_create(users_data)
    
    @staticmethod
    async def seed_admin_users(repo, count: int = 3) -> List[User]:
        """Seed database with admin users."""
        users = []
        for i in range(count):
            data = TestDataFactory.create_admin_user_data(
                username=f"admin{i}",
                email=f"admin{i}@example.com"
            )
            users.append(await repo.create(**data))
        return users
    
    @staticmethod
    async def seed_verified_users(repo, count: int = 5) -> List[User]:
        """Seed database with verified users."""
        users = []
        for i in range(count):
            data = TestDataFactory.create_verified_user_data(
                username=f"verified{i}",
                email=f"verified{i}@example.com"
            )
            users.append(await repo.create(**data))
        return users
    
    @staticmethod
    async def seed_suspended_users(repo, count: int = 2) -> List[User]:
        """Seed database with suspended users."""
        users = []
        for i in range(count):
            data = TestDataFactory.create_suspended_user_data(
                username=f"suspended{i}",
                email=f"suspended{i}@example.com"
            )
            users.append(await repo.create(**data))
        return users
    
    @staticmethod
    async def seed_full_dataset(repo) -> Dict[str, List[User]]:
        """Seed complete dataset for integration tests."""
        return {
            "regular_users": await TestDataSeeder.seed_users(repo, 10),
            "admins": await TestDataSeeder.seed_admin_users(repo, 3),
            "verified": await TestDataSeeder.seed_verified_users(repo, 5),
            "suspended": await TestDataSeeder.seed_suspended_users(repo, 2),
        }


class TestDataCleaner:
    """Clean up test data."""
    
    @staticmethod
    async def cleanup_all_users(repo) -> int:
        """Delete all users."""
        users = await repo.list(include_deleted=True)
        count = await repo.bulk_delete([u.id for u in users], soft=False)
        return count
    
    @staticmethod
    async def cleanup_soft_deleted(repo) -> int:
        """Permanently delete soft-deleted users."""
        users = await repo.list(include_deleted=True)
        soft_deleted = [u for u in users if u.is_deleted()]
        count = await repo.bulk_delete([u.id for u in soft_deleted], soft=False)
        return count


class AssertionHelpers:
    """Custom assertions for tests."""
    
    @staticmethod
    def assert_user_valid(user: User) -> None:
        """Assert user has valid structure."""
        assert user.id is not None
        assert user.username is not None
        assert user.email is not None
        assert user.password_hash is not None
        assert user.created_at is not None
        assert user.updated_at is not None
    
    @staticmethod
    def assert_user_active(user: User) -> None:
        """Assert user is active."""
        assert user.is_active() is True
        assert user.status == UserStatus.ACTIVE.value
    
    @staticmethod
    def assert_user_verified(user: User) -> None:
        """Assert user is verified."""
        assert user.is_verified is True
    
    @staticmethod
    def assert_user_admin(user: User) -> None:
        """Assert user is admin."""
        assert user.is_admin() is True
        assert user.role == UserRole.ADMIN.value
    
    @staticmethod
    def assert_user_deleted(user: User) -> None:
        """Assert user is soft deleted."""
        assert user.is_deleted() is True
        assert user.deleted_at is not None


# Pytest fixtures using factories

import pytest


@pytest.fixture
def user_factory():
    """Provide user factory."""
    return TestDataFactory()


@pytest.fixture
def seeder(user_repo):
    """Provide data seeder."""
    class Seeder:
        @staticmethod
        async def users(count: int = 5):
            return await TestDataSeeder.seed_users(user_repo, count)
        
        @staticmethod
        async def admins(count: int = 2):
            return await TestDataSeeder.seed_admin_users(user_repo, count)
        
        @staticmethod
        async def verified(count: int = 3):
            return await TestDataSeeder.seed_verified_users(user_repo, count)
        
        @staticmethod
        async def full():
            return await TestDataSeeder.seed_full_dataset(user_repo)
    
    return Seeder()


@pytest.fixture
def cleaner(user_repo):
    """Provide data cleaner."""
    class Cleaner:
        @staticmethod
        async def all_users():
            return await TestDataCleaner.cleanup_all_users(user_repo)
        
        @staticmethod
        async def soft_deleted():
            return await TestDataCleaner.cleanup_soft_deleted(user_repo)
    
    return Cleaner()


@pytest.fixture
def assertions():
    """Provide assertion helpers."""
    return AssertionHelpers()
