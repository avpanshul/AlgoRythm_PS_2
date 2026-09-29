"""Tests for the web-hardening middleware (ULPF-master-prompt.md Part D8):
security response headers and per-client rate limiting."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_middleware import (
    rate_limit_middleware, security_headers_middleware, _buckets, _lock,
)


def _make_app():
    app = FastAPI()

    @app.get("/api/v1/whatever")
    def whatever():
        return {"ok": True}

    @app.get("/api/v1/auth/token")
    def token():
        return {"ok": True}

    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(security_headers_middleware)
    return app


class TestSecurityHeaders:
    def test_headers_present_on_normal_response(self):
        with _lock:
            _buckets.clear()
        client = TestClient(_make_app())
        resp = client.get("/api/v1/whatever")
        assert resp.status_code == 200
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert "default-src 'none'" in resp.headers["content-security-policy"]


class TestRateLimiting:
    def test_normal_endpoint_allows_up_to_the_default_limit(self):
        with _lock:
            _buckets.clear()
        client = TestClient(_make_app())
        for _ in range(120):
            resp = client.get("/api/v1/whatever")
            assert resp.status_code == 200
        resp = client.get("/api/v1/whatever")
        assert resp.status_code == 429
        assert "retry-after" in {k.lower() for k in resp.headers.keys()}

    def test_auth_endpoint_has_a_tighter_limit(self):
        with _lock:
            _buckets.clear()
        client = TestClient(_make_app())
        for _ in range(10):
            resp = client.get("/api/v1/auth/token")
            assert resp.status_code == 200
        resp = client.get("/api/v1/auth/token")
        assert resp.status_code == 429

    def test_rate_limited_response_still_has_security_headers(self):
        with _lock:
            _buckets.clear()
        client = TestClient(_make_app())
        for _ in range(10):
            client.get("/api/v1/auth/token")
        resp = client.get("/api/v1/auth/token")
        assert resp.status_code == 429
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_different_clients_are_tracked_independently(self):
        with _lock:
            _buckets.clear()
        client = TestClient(_make_app())
        for _ in range(10):
            resp = client.get("/api/v1/auth/token", headers={"x-forwarded-for": "1.1.1.1"})
            assert resp.status_code == 200
        # A different client's own budget is untouched by the first one's usage.
        resp = client.get("/api/v1/auth/token", headers={"x-forwarded-for": "2.2.2.2"})
        assert resp.status_code == 200
