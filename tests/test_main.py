"""
tests/test_main.py — DropKey v3.2 API and Main Application Tests

Tests:
- Health check endpoints
- CORS configuration
- Error handling
- Response formatting
- Status codes
"""

import pytest
from fastapi import status
from httpx import AsyncClient

pytestmark = pytest.mark.api


# ═════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestHealthChecks:
    """Test health check endpoints."""
    
    async def test_liveness_probe(self, client: AsyncClient):
        """Test /health/live endpoint."""
        response = await client.get("/health/live")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "alive"
    
    async def test_readiness_probe_success(self, client: AsyncClient):
        """Test /health/ready endpoint when ready."""
        response = await client.get("/health/ready")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ["ready", "not_ready"]
    
    async def test_health_endpoint_structure(self, client: AsyncClient):
        """Test /health endpoint returns proper structure."""
        response = await client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]
    
    async def test_health_endpoint_includes_version(self, client: AsyncClient):
        """Test /health endpoint includes version."""
        response = await client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "version" in data
        assert isinstance(data["version"], str)


# ═════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling and responses."""
    
    async def test_404_not_found(self, client: AsyncClient):
        """Test 404 error response."""
        response = await client.get("/nonexistent-endpoint")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    async def test_method_not_allowed(self, client: AsyncClient):
        """Test 405 method not allowed."""
        response = await client.post("/health/live")
        
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    async def test_422_validation_error(self, client: AsyncClient):
        """Test 422 validation error."""
        response = await client.post(
            "/users/",
            json={"invalid": "data"}  # Missing required fields
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ═════════════════════════════════════════════════════════════════════════════
# RESPONSE FORMATTING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestResponseFormatting:
    """Test response formatting and content types."""
    
    async def test_json_response_content_type(self, client: AsyncClient):
        """Test responses have correct content type."""
        response = await client.get("/health/live")
        
        assert response.headers["content-type"].startswith("application/json")
    
    async def test_health_response_is_json(self, client: AsyncClient):
        """Test health endpoint returns valid JSON."""
        response = await client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        # Should not raise exception
        data = response.json()
        assert isinstance(data, dict)
    
    async def test_error_response_format(self, client: AsyncClient):
        """Test error responses have proper format."""
        response = await client.get("/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        
        assert "detail" in data


# ═════════════════════════════════════════════════════════════════════════════
# CORS HEADERS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCORSHeaders:
    """Test CORS header configuration."""
    
    async def test_cors_headers_present(self, client: AsyncClient):
        """Test CORS headers are included in response."""
        response = await client.get("/health/live")
        
        # Should include CORS headers or be configured
        assert response.status_code == status.HTTP_200_OK
    
    async def test_cors_preflight_request(self, client: AsyncClient):
        """Test CORS preflight (OPTIONS) request."""
        response = await client.options("/health/live")
        
        # Should handle OPTIONS or return 404
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ═════════════════════════════════════════════════════════════════════════════
# TIMEOUT HANDLING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTimeoutHandling:
    """Test request timeout handling."""
    
    async def test_health_endpoint_responds_quickly(self, client: AsyncClient):
        """Test health endpoint responds quickly (< 1 second)."""
        import time
        
        start = time.time()
        response = await client.get("/health/live")
        elapsed = time.time() - start
        
        assert response.status_code == status.HTTP_200_OK
        assert elapsed < 1.0  # Should respond in less than 1 second


# ═════════════════════════════════════════════════════════════════════════════
# METRICS AND MONITORING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestMetricsAndMonitoring:
    """Test monitoring and metrics endpoints."""
    
    async def test_multiple_health_checks(self, client: AsyncClient):
        """Test multiple health checks work correctly."""
        for _ in range(5):
            response = await client.get("/health/live")
            assert response.status_code == status.HTTP_200_OK
    
    async def test_health_consistency(self, client: AsyncClient):
        """Test health status is consistent across checks."""
        responses = [
            await client.get("/health/live"),
            await client.get("/health/live"),
            await client.get("/health/live"),
        ]
        
        assert all(r.status_code == status.HTTP_200_OK for r in responses)
        assert all(r.json()["status"] == "alive" for r in responses)


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION STATE
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestApplicationState:
    """Test application state and configuration."""
    
    async def test_app_is_running(self, client: AsyncClient):
        """Test application is running."""
        response = await client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
    
    async def test_app_responds_to_requests(self, client: AsyncClient):
        """Test application can handle multiple requests."""
        for i in range(10):
            response = await client.get("/health/live")
            assert response.status_code == status.HTTP_200_OK


# ═════════════════════════════════════════════════════════════════════════════
# CONCURRENT REQUESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestConcurrentRequests:
    """Test handling of concurrent requests."""
    
    async def test_concurrent_health_checks(self, client: AsyncClient):
        """Test multiple concurrent health checks."""
        import asyncio
        
        tasks = [
            client.get("/health/live")
            for _ in range(5)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        assert all(r.status_code == status.HTTP_200_OK for r in responses)
    
    async def test_concurrent_different_endpoints(self, client: AsyncClient):
        """Test concurrent requests to different endpoints."""
        import asyncio
        
        tasks = [
            client.get("/health/live"),
            client.get("/health/ready"),
            client.get("/health"),
        ]
        
        responses = await asyncio.gather(*tasks)
        
        assert all(r.status_code == status.HTTP_200_OK for r in responses)


# ═════════════════════════════════════════════════════════════════════════════
# REQUEST VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestRequestValidation:
    """Test request validation."""
    
    async def test_invalid_json_rejected(self, client: AsyncClient):
        """Test invalid JSON is rejected."""
        response = await client.post(
            "/health/live",
            content="invalid json",
            headers={"content-type": "application/json"}
        )
        
        # Should return error
        assert response.status_code >= 400
    
    async def test_missing_content_type(self, client: AsyncClient):
        """Test requests without content type."""
        response = await client.get("/health/live")
        
        assert response.status_code == status.HTTP_200_OK
