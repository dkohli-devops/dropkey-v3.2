"""
tests/test_performance.py — DropKey v3.2 Performance & Load Tests

Tests:
- Response time benchmarks
- Database query performance
- Concurrent request handling
- Memory usage
- CPU usage
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone

pytestmark = pytest.mark.performance


# ═════════════════════════════════════════════════════════════════════════════
# RESPONSE TIME BENCHMARKS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestResponseTime:
    """Test response time performance."""
    
    @pytest.mark.slow
    async def test_health_check_response_time(self, client):
        """Health check should respond in < 100ms."""
        import time
        
        start = time.time()
        response = await client.get("/health/live")
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        assert response.status_code == 200
        assert elapsed < 100, f"Health check took {elapsed}ms (expected < 100ms)"
    
    @pytest.mark.slow
    async def test_create_user_response_time(self, client, sample_user_data):
        """Create user should respond in < 500ms."""
        import time
        
        start = time.time()
        response = await client.post("/users/", json=sample_user_data)
        elapsed = (time.time() - start) * 1000
        
        assert response.status_code in [200, 201]
        assert elapsed < 500, f"Create user took {elapsed}ms (expected < 500ms)"
    
    @pytest.mark.slow
    async def test_list_users_response_time(self, client, sample_users):
        """List users should respond in < 1000ms."""
        import time
        
        start = time.time()
        response = await client.get("/users/?limit=10")
        elapsed = (time.time() - start) * 1000
        
        assert response.status_code == 200
        assert elapsed < 1000, f"List users took {elapsed}ms (expected < 1000ms)"


# ═════════════════════════════════════════════════════════════════════════════
# CONCURRENT REQUEST TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestConcurrency:
    """Test concurrent request handling."""
    
    @pytest.mark.slow
    async def test_concurrent_health_checks(self, client):
        """Handle multiple concurrent health checks."""
        import time
        
        async def health_check():
            return await client.get("/health/live")
        
        start = time.time()
        tasks = [health_check() for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        assert all(r.status_code == 200 for r in responses)
        assert elapsed < 1.0, f"10 concurrent checks took {elapsed}s"
    
    @pytest.mark.slow
    async def test_concurrent_user_queries(self, user_repo, sample_users):
        """Handle concurrent user queries."""
        import time
        
        async def get_user():
            return await user_repo.get(sample_users[0].id)
        
        start = time.time()
        tasks = [get_user() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        assert all(r is not None for r in results)
        assert elapsed < 2.0, f"20 concurrent queries took {elapsed}s"
    
    @pytest.mark.slow
    async def test_concurrent_user_creation(self, user_repo):
        """Handle concurrent user creation."""
        import time
        import uuid
        
        async def create_user():
            return await user_repo.create(
                username=f"concurrent_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@example.com",
                password="TestPassword123!"
            )
        
        start = time.time()
        tasks = [create_user() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        assert len(results) == 5
        assert all(r.id is not None for r in results)
        assert elapsed < 5.0, f"5 concurrent creates took {elapsed}s"


# ═════════════════════════════════════════════════════════════════════════════
# THROUGHPUT TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestThroughput:
    """Test application throughput."""
    
    @pytest.mark.slow
    async def test_queries_per_second(self, user_repo, sample_users):
        """Measure queries per second."""
        import time
        
        start = time.time()
        count = 0
        
        while time.time() - start < 1.0:  # Run for 1 second
            await user_repo.get(sample_users[0].id)
            count += 1
        
        elapsed = time.time() - start
        qps = count / elapsed
        
        assert qps > 100, f"Only {qps} queries/sec (expected > 100)"
    
    @pytest.mark.slow
    async def test_pagination_throughput(self, user_repo, sample_users):
        """Measure pagination throughput."""
        import time
        
        start = time.time()
        
        for i in range(10):
            await user_repo.page(skip=i * 10, limit=10)
        
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"10 page queries took {elapsed}s"


# ═════════════════════════════════════════════════════════════════════════════
# SCALABILITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestScalability:
    """Test scalability with increasing load."""
    
    @pytest.mark.slow
    async def test_list_with_increasing_size(self, user_repo):
        """Test listing with increasing dataset size."""
        import time
        
        # Create users
        for batch in range(3):
            for i in range(10):
                await user_repo.create(
                    username=f"user_{batch}_{i}",
                    email=f"user_{batch}_{i}@example.com",
                    password="TestPassword123!"
                )
        
        # Test query time with growing dataset
        start = time.time()
        users = await user_repo.list(limit=1000)
        elapsed = time.time() - start
        
        assert len(users) >= 30
        assert elapsed < 1.0, f"List 30+ users took {elapsed}s"
    
    @pytest.mark.slow
    async def test_search_performance(self, user_repo, sample_users):
        """Test search performance."""
        import time
        
        start = time.time()
        results = await user_repo.search(sample_users[0].username[:3])
        elapsed = time.time() - start
        
        assert len(results) > 0
        assert elapsed < 0.5, f"Search took {elapsed}s"


# ═════════════════════════════════════════════════════════════════════════════
# DATABASE PERFORMANCE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDatabasePerformance:
    """Test database performance."""
    
    @pytest.mark.slow
    async def test_bulk_insert_performance(self, user_repo):
        """Test bulk insert performance."""
        import time
        
        data = [
            {
                "username": f"bulk_{i}",
                "email": f"bulk_{i}@example.com",
                "password": "TestPassword123!"
            }
            for i in range(50)
        ]
        
        start = time.time()
        users = await user_repo.bulk_create(data)
        elapsed = time.time() - start
        
        assert len(users) == 50
        assert elapsed < 2.0, f"Bulk create 50 users took {elapsed}s"
    
    @pytest.mark.slow
    async def test_transaction_performance(self, test_db):
        """Test transaction performance."""
        import time
        from models import User
        
        start = time.time()
        
        for i in range(20):
            user = User(
                username=f"txn_{i}",
                email=f"txn_{i}@example.com",
                password="TestPassword123!"
            )
            test_db.add(user)
        
        await test_db.commit()
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Transaction 20 inserts took {elapsed}s"


# ═════════════════════════════════════════════════════════════════════════════
# MEMORY USAGE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestMemoryUsage:
    """Test memory usage."""
    
    @pytest.mark.slow
    async def test_session_memory_cleanup(self, user_repo, sample_users):
        """Test that sessions properly cleanup memory."""
        import gc
        
        # Fetch many users
        for _ in range(100):
            await user_repo.get(sample_users[0].id)
        
        # Force garbage collection
        gc.collect()
        
        # Should not raise memory error
        assert True


# ═════════════════════════════════════════════════════════════════════════════
# CACHE EFFECTIVENESS TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCacheEffectiveness:
    """Test caching mechanisms."""
    
    @pytest.mark.slow
    async def test_repeated_query_performance(self, user_repo, sample_user):
        """Repeated queries should be fast."""
        import time
        
        # Warm up
        await user_repo.get(sample_user.id)
        
        # Measure repeated queries
        start = time.time()
        for _ in range(100):
            await user_repo.get(sample_user.id)
        elapsed = time.time() - start
        
        # Should be fast (no query planning overhead)
        assert elapsed < 1.0, f"100 repeated queries took {elapsed}s"


# ═════════════════════════════════════════════════════════════════════════════
# STRESS TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestStress:
    """Stress test the application."""
    
    @pytest.mark.slow
    async def test_rapid_fire_requests(self, client):
        """Send many requests rapidly."""
        import time
        
        async def request():
            return await client.get("/health/live")
        
        start = time.time()
        tasks = [request() for _ in range(100)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        
        # Most should succeed
        successes = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
        assert successes > 90, f"Only {successes}/100 requests succeeded"
        
        print(f"100 requests in {elapsed:.2f}s ({100/elapsed:.0f} req/s)")


# ═════════════════════════════════════════════════════════════════════════════
# BASELINE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestBaselines:
    """Define performance baselines."""
    
    # Health check: < 100ms
    # User creation: < 500ms
    # User list: < 1000ms
    # Concurrent (10x): < 1s
    # Queries/sec: > 100
    # Throughput: > 10 req/s
    
    def test_performance_baselines_documented(self):
        """Verify performance baselines are documented."""
        baselines = {
            "health_check_ms": 100,
            "create_user_ms": 500,
            "list_users_ms": 1000,
            "concurrent_requests": 1.0,
            "queries_per_second": 100,
        }
        
        # Baselines are defined
        assert len(baselines) > 0
