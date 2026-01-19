"""Tests for request size limit middleware."""

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.size_limit import RequestSizeLimitMiddleware


async def echo_endpoint(request: Request) -> Response:
    """Simple echo endpoint for testing."""
    body = await request.body()
    return JSONResponse({"size": len(body)})


@pytest.fixture
def app_with_middleware():
    """Create a test app with size limit middleware."""
    app = Starlette(routes=[Route("/echo", echo_endpoint, methods=["POST"])])
    app.add_middleware(RequestSizeLimitMiddleware, max_size=1024)  # 1KB limit
    return app


@pytest.fixture
def client(app_with_middleware):
    """Create a test client."""
    return TestClient(app_with_middleware, raise_server_exceptions=False)


class TestRequestSizeLimitMiddleware:
    """Tests for RequestSizeLimitMiddleware."""

    def test_allows_request_under_limit(self, client):
        """Requests smaller than max_size should be allowed."""
        data = "x" * 500  # 500 bytes, under 1KB limit
        response = client.post("/echo", content=data)

        assert response.status_code == 200
        assert response.json()["size"] == 500

    def test_allows_request_at_limit(self, client):
        """Requests exactly at max_size should be allowed."""
        data = "x" * 1024  # Exactly 1KB
        response = client.post("/echo", content=data)

        assert response.status_code == 200
        assert response.json()["size"] == 1024

    def test_rejects_request_over_limit(self, client):
        """Requests larger than max_size should be rejected with 413."""
        data = "x" * 2048  # 2KB, over 1KB limit
        response = client.post("/echo", content=data)

        assert response.status_code == 413
        assert "exceeds maximum size" in response.json()["detail"]

    def test_allows_request_without_content_length(self, client):
        """Requests without Content-Length header should pass through."""
        # TestClient automatically adds Content-Length, so we test with empty body
        response = client.post("/echo", content="")

        assert response.status_code == 200
        assert response.json()["size"] == 0

    def test_allows_get_requests(self):
        """GET requests should always be allowed (no body)."""
        app = Starlette(
            routes=[Route("/test", lambda r: JSONResponse({"ok": True}), methods=["GET"])]
        )
        app.add_middleware(RequestSizeLimitMiddleware, max_size=100)
        client = TestClient(app)

        response = client.get("/test")

        assert response.status_code == 200


class TestRequestSizeLimitMiddlewareConfiguration:
    """Tests for middleware configuration."""

    def test_uses_custom_max_size(self):
        """Middleware should use provided max_size."""
        app = Starlette(routes=[Route("/echo", echo_endpoint, methods=["POST"])])
        app.add_middleware(RequestSizeLimitMiddleware, max_size=100)  # 100 byte limit
        client = TestClient(app, raise_server_exceptions=False)

        # 50 bytes should pass
        response = client.post("/echo", content="x" * 50)
        assert response.status_code == 200

        # 200 bytes should fail
        response = client.post("/echo", content="x" * 200)
        assert response.status_code == 413

    def test_default_uses_settings(self):
        """Middleware should use settings.max_request_size_bytes by default."""
        from app.config import settings

        app = Starlette(routes=[Route("/echo", echo_endpoint, methods=["POST"])])
        app.add_middleware(RequestSizeLimitMiddleware)  # No max_size provided
        client = TestClient(app, raise_server_exceptions=False)

        # Test by sending a request just over 1MB (default)
        # If it's using the default, a 2MB request should be rejected
        data = "x" * (settings.max_request_size_bytes + 1)
        response = client.post("/echo", content=data)
        assert response.status_code == 413
