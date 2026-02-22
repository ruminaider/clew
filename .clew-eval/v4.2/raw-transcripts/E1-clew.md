# Custom Django Middleware Map — Evvy Backend

## Source of Truth

All custom middleware lives in:
- **Directory:** `/Users/albertgwo/Work/evvy/backend/app/middleware/`
- **Files:** `auth.py`, `logging.py`, `audit.py`, `monitoring.py`, `__init__.py`

The MIDDLEWARE order is defined in `/Users/albertgwo/Work/evvy/backend/app/settings.py` lines 243–266.

---

## Execution Order (request phase, top to bottom)

Django processes middleware top-to-bottom on request, bottom-to-top on response. The full MIDDLEWARE list is:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",          # 1 — standard
    "whitenoise.middleware.WhiteNoiseMiddleware",              # 2 — standard
    "django.contrib.sessions.middleware.SessionMiddleware",   # 3 — standard
    "corsheaders.middleware.CorsMiddleware",                  # 4 — standard
    "django.middleware.common.CommonMiddleware",              # 5 — standard
    "django.middleware.csrf.CsrfViewMiddleware",              # 6 — standard
    "django.contrib.auth.middleware.AuthenticationMiddleware",# 7 — standard
    "django.contrib.messages.middleware.MessageMiddleware",   # 8 — standard
    "django.middleware.clickjacking.XFrameOptionsMiddleware", # 9 — standard
    "django_otp.middleware.OTPMiddleware",                    # 10 — third-party
    "csp.middleware.CSPMiddleware",                           # 11 — third-party
    "django_permissions_policy.PermissionsPolicyMiddleware",  # 12 — third-party

    # === CUSTOM APPLICATION MIDDLEWARE (positions 13–17) ===
    "app.middleware.ExceptionContextMiddleware",              # 13 — custom
    "app.middleware.RequestLoggingMiddleware",                # 14 — custom
    "app.middleware.ImpersonateMiddleware",                   # 15 — custom
    "app.middleware.EvvyAuditLogMiddleware",                  # 16 — custom
    "app.middleware.CheckoutMonitoringMiddleware",            # 17 — custom
]
```

The five custom middleware classes run after all standard Django and third-party middleware.

---

## Custom Middleware Classes (detailed)

### 1. ExceptionContextMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` lines 8–15
**Position:** 13 (first custom middleware)
**Base class:** `MiddlewareMixin` (from `django.utils.deprecation`)

**What it does:** On any unhandled exception, attaches the authenticated user's ID to the current New Relic transaction as a custom parameter. Enables correlating errors with specific users in APM.

**Key method:**
```python
def process_exception(self, request, exception):
    if request.user and request.user.is_authenticated:
        newrelic.agent.add_custom_parameter("user_id", request.user.id)
```

**Conditional skip:** Yes — silently does nothing if `request.user` is not authenticated. No New Relic call is made for anonymous requests.

---

### 2. RequestLoggingMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py` lines 9–34
**Position:** 14
**Base class:** `MiddlewareMixin`

**What it does:** Logs every completed request at DEBUG level to the `evvy.request.logging` logger. The log line includes timestamp, user ID (or "none" for anonymous), True-Client-IP header, HTTP method, response status code, and full path.

**Key method:**
```python
def process_response(self, request, response):
    msg = "%s [user:%s] [ip:%s] %s %s %s" % (
        datetime.datetime.now(),
        request.user and request.user.is_authenticated and request.user.id or "none",
        request.headers.get("True-Client-IP", "none"),
        request.method,
        response.status_code,
        request.get_full_path(),
    )
    request_logger.debug(msg=msg, extra={})
    return response
```

**Conditional skip:** No — runs for every request regardless of path or user. Failures are caught and logged as warnings rather than re-raised, so it never blocks a response.

**Note:** `process_request` is stubbed out with a comment (`# Could do stuff here to time the diff`). Only the response phase is active.

---

### 3. ImpersonateMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py` lines 33–63
**Position:** 15
**Base class:** `MiddlewareMixin`

**What it does:** Enables staff users in the `user-impersonation` group to act as another user. When `?__impersonate=<username>` is present in the query string, the middleware:
1. Authenticates the requesting user via JWT (`get_jwt_user`)
2. Checks they are staff AND in the `user-impersonation` group (`is_user_allowed_to_impersonate`)
3. Generates a fresh JWT access token for the target user
4. Overwrites `request.META["HTTP_AUTHORIZATION"]` with the impersonated user's Bearer token so all downstream auth sees the impersonated identity

On redirect responses (`process_response`), it propagates the `__impersonate` query parameter to preserve impersonation across redirects.

**Key helpers (module-level, exported from `__init__.py`):**
```python
def get_jwt_user(request):
    # Returns authenticated user from session or JWT token
    ...

def is_user_allowed_to_impersonate(user):
    return user.is_staff and user.groups.filter(name="user-impersonation").exists()
```

**Conditional skip:** Yes — both `process_request` and `process_response` are entirely skipped when `"__impersonate"` is not in `request.GET`. This is the most heavily conditional middleware.

**Error handling:** Returns `HttpResponseUnauthorized` (HTTP 401, defined in the same file) on `InvalidToken` exceptions; returns `None` (no-op) if the target username does not exist.

**Interaction with AuthenticationMiddleware (position 7):** `ImpersonateMiddleware` runs *after* `AuthenticationMiddleware`. It rewrites the Authorization header so that the *view's* DRF authentication sees the impersonated user, but the session-based `request.user` set by Django's own middleware remains the real staff user (used in `process_response` to check permissions for the redirect rewrite).

---

### 4. EvvyAuditLogMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py` lines 11–18
**Position:** 16
**Base class:** `AuditlogMiddleware` (from `auditlog.middleware`)

**What it does:** Wraps every request in an audit log context that associates all model-level changes (create/update/delete) with the requesting user and their remote IP address. Uses Python context managers via `auditlog.context.set_actor`.

The custom subclass overrides `__call__` to use a `SimpleLazyObject` for the user (deferred evaluation), which is important because `request.user` may not yet be resolved at middleware entry time for JWT-authenticated requests:

```python
def __call__(self, request):
    remote_addr = self._get_remote_addr(request)
    user = SimpleLazyObject(lambda: getattr(request, "user", None))
    context = set_actor(actor=user, remote_addr=remote_addr)
    with context:
        return self.get_response(request)
```

The base class `AuditlogMiddleware` (from the `django-auditlog` library) also handles X-Forwarded-For header parsing for remote address and sets a correlation ID via `set_cid`. The Evvy override drops `remote_port` tracking (present in base class) and uses lazy user resolution instead of eager.

**Conditional skip:** No — runs for all requests. The audit context is always established, but entries are only actually written by `django-auditlog`'s signals when models with audit tracking are saved.

**Settings interaction:**
```python
# settings.py
AUDITLOG_INCLUDE_ALL_MODELS = True
AUDITLOG_EXCLUDE_TRACKING_MODELS = ("sessions", "otp_static")
```

---

### 5. CheckoutMonitoringMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` lines 18–53
**Position:** 17 (last custom middleware)
**Base class:** `MiddlewareMixin`

**What it does:** Monitors checkout-related exceptions by recording custom New Relic metrics. It only fires on unhandled exceptions (`process_exception`), never on normal responses.

Two independent conditions each set a `send_error = True` flag:
1. **SSL errors:** If the exception message contains "ssl" or "certificate" (case-insensitive), records `Custom/SSLError` metric
2. **Checkout paths:** If `request.path` matches any of the six glob patterns below, records `Custom/Checkout/Error` metric

When either condition is true, a full context block is recorded: `Custom/Checkout/Error/<ExceptionType>`, `checkout_path`, `exception_type`, and `exception_message`.

**Monitored checkout paths (glob patterns):**
```python
CHECKOUT_PATHS = [
    "/api/v1/carts/*/checkout",
    "/api/v1/consults/*/checkout_url",
    "/api/v1/consults/*/refill_checkout_url",
    "/api/v1/consults/*/cross-sell-checkout-url",
    "/api/v1/tests/*/checkout",
    "/api/v1/tests/*/ungated-checkout",
]
```

**Conditional skip:** Yes — the most selective middleware. Does nothing if `send_error` is never set to `True`, which means no SSL keyword in the exception AND the path is not a checkout endpoint. Non-checkout API errors are completely ignored by this middleware.

---

## Interaction Map

```
Request → [Django security/session/auth chain] → ExceptionContextMiddleware
                                                      ↓
                                               RequestLoggingMiddleware (logs response only)
                                                      ↓
                                               ImpersonateMiddleware (may swap auth identity)
                                                      ↓
                                               EvvyAuditLogMiddleware (wraps remaining chain in audit context)
                                                      ↓
                                               CheckoutMonitoringMiddleware
                                                      ↓
                                                    [View]
```

**Key interactions:**

1. **ImpersonateMiddleware → EvvyAuditLogMiddleware:** ImpersonateMiddleware (position 15) overwrites the Authorization header before EvvyAuditLogMiddleware (position 16) evaluates the user. However, since `EvvyAuditLogMiddleware` uses `SimpleLazyObject(lambda: getattr(request, "user", None))`, the user is resolved lazily during the request body execution — after DRF authentication runs — so impersonation is correctly reflected in audit logs.

2. **ExceptionContextMiddleware vs CheckoutMonitoringMiddleware:** Both handle exceptions (both define `process_exception`). Django calls `process_exception` in reverse middleware order (bottom-up), so `CheckoutMonitoringMiddleware` fires first on exceptions, followed by `ExceptionContextMiddleware`. Neither returns a response from `process_exception`, so both always run on exceptions.

3. **RequestLoggingMiddleware:** Purely observational; does not modify request or response objects. Always runs last (in response order, it's the first to see the response after the view). Swallows its own exceptions silently.

4. **EvvyAuditLogMiddleware** is the only middleware using the new-style `__call__` interface rather than `MiddlewareMixin`'s `process_request`/`process_response` split. It wraps the entire remaining chain (positions 17 onward, plus the view) in a context manager.

---

## Summary Table

| Class | File | Position | Hook | Conditional Skip |
|---|---|---|---|---|
| `ExceptionContextMiddleware` | `monitoring.py` | 13 | `process_exception` | Yes — skips if user unauthenticated |
| `RequestLoggingMiddleware` | `logging.py` | 14 | `process_response` | No |
| `ImpersonateMiddleware` | `auth.py` | 15 | `process_request`, `process_response` | Yes — skips if `__impersonate` not in query string |
| `EvvyAuditLogMiddleware` | `audit.py` | 16 | `__call__` (wraps chain) | No — always establishes audit context |
| `CheckoutMonitoringMiddleware` | `monitoring.py` | 17 | `process_exception` | Yes — skips if not a checkout path AND not an SSL error |
