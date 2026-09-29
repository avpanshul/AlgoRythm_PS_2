"""Web hardening middleware (ULPF-master-prompt.md Part D8): security
response headers, rate limiting, and CSRF defense-in-depth.

Rate limiting is Redis-backed when Redis is reachable (settings.REDIS_URL --
already in the compose/k8s stack for other features), using a fixed-window
INCR+EXPIRE counter shared by every backend replica: the k8s worker
deployment runs replicas: 2 (see deploy/k8s/07-worker.yaml), and a
per-process in-memory bucket would let each replica hand out its own
separate quota to the same attacker, silently multiplying the real limit by
the replica count. Falls back to the old per-process in-memory bucket
(logged once, not silently) if Redis is unreachable, so a demo/air-gapped
instance with no Redis running still starts and still gets *some* rate
limiting rather than none -- honest about the fallback's own limit (resets
on restart, not shared across replicas), same as before.
"""
import time
import threading
import warnings
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

# requests-per-window, per client IP, per rate-limit "bucket" (path prefix).
# Auth endpoints get a much tighter limit -- the thing D8 rate limiting
# exists to slow down is credential brute-forcing, not the dashboard's
# normal polling traffic.
_DEFAULT_LIMIT = (120, 60)   # 120 requests / 60s
_AUTH_LIMIT = (10, 60)       # 10 requests / 60s on /auth/*

# In-memory fallback bucket (used only if Redis is unreachable).
_buckets: dict = defaultdict(list)
_lock = threading.Lock()

_redis_client = None
_redis_warned = False
_redis_last_failure = 0.0
_REDIS_RETRY_COOLDOWN_SECONDS = 30


def _get_redis():
    """Lazily connects (and caches) a Redis client. Returns None -- rather
    than raising -- on any connection problem, so callers always have a
    clean fallback path instead of a try/except at every call site.

    Real bug found live (2026-09-29): this used to attempt a fresh
    connection (with its own 0.5s socket timeout) on *every single call*
    whenever Redis was unreachable -- it cached a success but never cached
    a failure. In practice each attempt actually took ~1-1.3s (connect
    timeout plus real OS-level connection-refused overhead on this
    network), so with Redis down, 121 requests spent over two minutes just
    retrying Redis before ever finishing -- comfortably longer than the
    in-memory limiter's own 60s window, so its sliding-window pruning
    evicted early timestamps before the request count could ever reach the
    configured limit. Net effect: with no Redis reachable (the exact
    demo/air-gapped scenario this fallback exists for, per this module's
    own docstring), rate limiting silently never triggered at all -- not a
    test-only issue, a real gap in exactly the deployment shape it was
    supposed to protect. Fixed by caching the failure too, with a cooldown
    before the next real retry, so a down Redis costs one slow attempt
    every 30s, not one on every request."""
    global _redis_client, _redis_warned, _redis_last_failure
    if _redis_client is not None:
        return _redis_client
    if _redis_last_failure and (time.monotonic() - _redis_last_failure) < _REDIS_RETRY_COOLDOWN_SECONDS:
        return None
    try:
        import redis as redis_lib
        client = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        _redis_last_failure = time.monotonic()
        if not _redis_warned:
            warnings.warn(
                "Rate limiting: Redis is unreachable -- falling back to a per-process, "
                "non-shared in-memory limiter. Multiple backend replicas will each get "
                "their own separate quota until Redis is available. Set REDIS_URL / start "
                "the redis service to fix this.",
                stacklevel=2,
            )
            _redis_warned = True
        return None


def _client_key(request: Request) -> str:
    # X-Forwarded-For is attacker-controlled unless a trusted reverse proxy
    # strips/sets it -- fine for this single-hop deployment (nginx sets it in
    # docker-compose.prod.yml); take the first hop's address as the
    # rate-limit identity, not a claimed chain.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit_for(path: str):
    if path.startswith("/api/v1/auth"):
        return _AUTH_LIMIT
    return _DEFAULT_LIMIT


def _check_redis(client, key: str, limit: int, window: int):
    """Fixed-window counter: INCR the window's counter key, set its TTL only
    on the first hit in that window (so it actually expires after `window`
    seconds rather than being perpetually refreshed), and compare against
    `limit`. Returns (allowed: bool, retry_after: int)."""
    pipe = client.pipeline()
    pipe.incr(key, 1)
    pipe.ttl(key)
    count, ttl = pipe.execute()
    if ttl is None or ttl < 0:
        client.expire(key, window)
        ttl = window
    if count > limit:
        return False, max(1, ttl)
    return True, 0


def _check_memory(key, limit: int, window: int):
    now = time.monotonic()
    with _lock:
        timestamps = _buckets[key]
        cutoff = now - window
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= limit:
            retry_after = max(1, int(window - (now - timestamps[0])))
            return False, retry_after
        timestamps.append(now)
        return True, 0


async def rate_limit_middleware(request: Request, call_next):
    limit, window = _limit_for(request.url.path)
    bucket = request.url.path.split("/")[:4].__str__()
    client_id = _client_key(request)

    redis_client = _get_redis()
    if redis_client is not None:
        try:
            redis_key = f"ulpf:ratelimit:{client_id}:{bucket}:{int(time.time()) // window}"
            allowed, retry_after = _check_redis(redis_client, redis_key, limit, window)
        except Exception:
            # Redis started reachable but a call failed mid-request (e.g. it
            # went down) -- degrade to the in-memory fallback for this
            # request rather than failing it outright.
            allowed, retry_after = _check_memory((client_id, bucket), limit, window)
    else:
        allowed, retry_after = _check_memory((client_id, bucket), limit, window)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded, try again later."},
            headers={"Retry-After": str(retry_after)},
        )

    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # A strict-by-default CSP for an API server (no HTML templates rendered
    # here -- the frontend is a separate origin/build); frame-ancestors and
    # no-sniff matter regardless of content type.
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# ─── CSRF defense-in-depth (Part D1) ──────────────────────────────────
#
# This API's real auth is a bearer token sent in an Authorization header
# (app/core/deps.py) -- never an ambient cookie the browser attaches
# automatically -- which is why classic CSRF (a third-party page silently
# riding the victim's cookie into a state-changing request) doesn't apply to
# it today: a forged cross-site request simply has no Authorization header
# and gets 401'd by get_current_user before this ever matters, no CSRF token
# required. This middleware exists as a real, working double-submit-cookie
# check anyway, so this stays true if a cookie-based session is ever added
# later (or for any client that does choose to use a cookie transport): if a
# request arrives with a `ulpf_csrf` cookie (i.e. it's using cookie-based
# auth), a state-changing method must also carry a matching X-CSRF-Token
# header -- a cross-site page can trigger the cookie to be sent, but per
# browser same-origin rules it cannot read the cookie's value to also set
# the header. Requests with no `ulpf_csrf` cookie at all (today's normal
# bearer-token traffic) are left untouched.
_CSRF_COOKIE = "ulpf_csrf"
_CSRF_HEADER = "x-csrf-token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


async def csrf_middleware(request: Request, call_next):
    cookie_token = request.cookies.get(_CSRF_COOKIE)
    if cookie_token and request.method.upper() not in _SAFE_METHODS:
        header_token = request.headers.get(_CSRF_HEADER)
        if not header_token or header_token != cookie_token:
            return JSONResponse(status_code=403, content={"detail": "Missing or invalid CSRF token"})
    return await call_next(request)
