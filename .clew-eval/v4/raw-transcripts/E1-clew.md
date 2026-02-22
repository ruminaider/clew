# E1 Exploration Log

## Search 1: Custom middleware classes (process_request)
Searched: `clew search "custom middleware class process_request" --project-root /Users/albertgwo/Work/evvy --json`

Found the middleware package at `/Users/albertgwo/Work/evvy/backend/app/middleware/` with four source files:
- `auth.py` — contains `ImpersonateMiddleware`
- `audit.py` — contains `EvvyAuditLogMiddleware`
- `logging.py` — contains `RequestLoggingMiddleware`
- `monitoring.py` — contains `ExceptionContextMiddleware` and `CheckoutMonitoringMiddleware`

Also confirmed the settings file at `/Users/albertgwo/Work/evvy/backend/app/settings.py` references the middleware stack.

## Search 2: List middleware directory
Used `ls` to confirm the exact files in the middleware package:
- `__init__.py`, `audit.py`, `auth.py`, `logging.py`, `monitoring.py`, `tests/`

## Search 3: Read all four middleware source files in parallel
Read `auth.py`, `audit.py`, `logging.py`, and `monitoring.py` simultaneously to get the full source of every custom middleware class.

Key findings:
- `ImpersonateMiddleware` — uses `MiddlewareMixin`, implements both `process_request` and `process_response`. Conditionally skips all processing unless `__impersonate` is in `request.GET`.
- `EvvyAuditLogMiddleware` — subclasses third-party `AuditlogMiddleware`, overrides `__call__` to use lazy user resolution.
- `RequestLoggingMiddleware` — uses `MiddlewareMixin`, only `process_response` is active (`process_request` is commented out).
- `ExceptionContextMiddleware` — uses `MiddlewareMixin`, only `process_exception`. Conditionally skips if user is not authenticated.
- `CheckoutMonitoringMiddleware` — uses `MiddlewareMixin`, only `process_exception`. Conditionally skips based on path pattern matching and error string content.

## Search 4: MIDDLEWARE ordering in settings.py
Searched: `clew search "MIDDLEWARE settings django" --project-root /Users/albertgwo/Work/evvy --json`

Confirmed the settings file path and that it contains the `MIDDLEWARE` list.

## Search 5: Read MIDDLEWARE list from settings.py
Read lines 243–266 of `/Users/albertgwo/Work/evvy/backend/app/settings.py`.

Found the complete ordered list of middleware (16 entries total, 5 custom).

## Search 6: Read __init__.py of middleware package
Read `/Users/albertgwo/Work/evvy/backend/app/middleware/__init__.py` to confirm the public API and all exported symbols.

## Search 7: Conditional skipping patterns
Searched: `clew search "middleware conditional skip request path" --project-root /Users/albertgwo/Work/evvy --json`

Confirmed that `CheckoutMonitoringMiddleware.is_checkout_path()` does glob-based path filtering, and `ImpersonateMiddleware` checks `__impersonate` in query params. No additional conditional middleware was discovered.

## Search 8: JWT authentication used by impersonate middleware
Searched: `clew search "EvvyJWTAuthentication authenticate impersonate" --project-root /Users/albertgwo/Work/evvy --json`

Confirmed that `ImpersonateMiddleware` delegates to `EvvyJWTAuthentication` (from `api/v1/authentication.py`) via the `get_jwt_user()` helper function rather than relying on Django's session-based `request.user`.

## Search 9: Verify no other custom middleware files exist
Used `find` to check all of `backend/` (excluding venv) for any `middleware.py` files or `middleware/` directories.

Confirmed that the only application-level middleware directory is `/Users/albertgwo/Work/evvy/backend/app/middleware/`. All other hits were inside `venv/` (third-party packages).

---

## Final Answer

### Custom Middleware Overview

All custom application middleware lives in `/Users/albertgwo/Work/evvy/backend/app/middleware/`. There are **5 custom middleware classes** across 4 source files.

---

### Execution Order (from `settings.py` lines 243–266)

The full `MIDDLEWARE` list, in Django's top-to-bottom (request) / bottom-to-top (response) execution order:

```
Position  Class
1         django.middleware.security.SecurityMiddleware
2         whitenoise.middleware.WhiteNoiseMiddleware
3         django.contrib.sessions.middleware.SessionMiddleware
4         corsheaders.middleware.CorsMiddleware
5         django.middleware.common.CommonMiddleware
6         django.middleware.csrf.CsrfViewMiddleware
7         django.contrib.auth.middleware.AuthenticationMiddleware  ← sets request.user
8         django.contrib.messages.middleware.MessageMiddleware
9         django.middleware.clickjacking.XFrameOptionsMiddleware
10        django_otp.middleware.OTPMiddleware
11        csp.middleware.CSPMiddleware
12        django_permissions_policy.PermissionsPolicyMiddleware
13  [CUSTOM] app.middleware.ExceptionContextMiddleware
14  [CUSTOM] app.middleware.RequestLoggingMiddleware
15  [CUSTOM] app.middleware.ImpersonateMiddleware
16  [CUSTOM] app.middleware.EvvyAuditLogMiddleware
17  [CUSTOM] app.middleware.CheckoutMonitoringMiddleware
```

All 5 custom middleware run after Django's `AuthenticationMiddleware` (position 7), meaning `request.user` is already populated when they execute.

---

### Class-by-Class Reference

#### 1. `ExceptionContextMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py`
**Position:** 13 (first custom middleware)
**Base:** `MiddlewareMixin`
**Hook:** `process_exception` only

**What it does:** On any unhandled exception, attaches the authenticated user's ID as a custom parameter to the active New Relic transaction. Enables correlating error traces to specific users in the APM dashboard.

**Conditional skipping:** Yes — explicitly skips if the user is not authenticated:
```python
def process_exception(self, request, exception):
    if request.user and request.user.is_authenticated:
        newrelic.agent.add_custom_parameter("user_id", request.user.id)
```
If the user is anonymous, no New Relic parameter is added and the method does nothing.

---

#### 2. `RequestLoggingMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py`
**Position:** 14
**Base:** `MiddlewareMixin`
**Hook:** `process_response` only (`process_request` exists but is entirely commented out)

**What it does:** After every request completes, logs a single debug line to the `evvy.request.logging` logger containing: timestamp, user ID (or "none" for anonymous), client IP from the `True-Client-IP` header (Cloudflare/Render), HTTP method, response status code, and full request path.

```python
msg = "%s [user:%s] [ip:%s] %s %s %s" % (
    datetime.datetime.now(),
    request.user and request.user.is_authenticated and request.user.id or "none",
    request.headers.get("True-Client-IP", "none"),
    request.method,
    response.status_code,
    request.get_full_path(),
)
```

**Conditional skipping:** No — runs on every response. Failures are caught and logged as warnings rather than propagated.

---

#### 3. `ImpersonateMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py`
**Position:** 15
**Base:** `MiddlewareMixin`
**Hooks:** `process_request` AND `process_response`

**What it does:** Allows authorized staff members to impersonate another user by appending `?__impersonate=<username>` to any URL.

- **`process_request`:** If `__impersonate` is present in query params, authenticates the *requesting* user via JWT (using `EvvyJWTAuthentication` from `api/v1/authentication.py`). If the requester is staff AND a member of the `"user-impersonation"` group, it looks up the target username, mints a new JWT access token for that user, and injects it into `request.META["HTTP_AUTHORIZATION"]`. This makes all downstream authentication see the impersonated user.

- **`process_response`:** If `__impersonate` was in the query params AND the current `request.user` is allowed to impersonate, propagates the `__impersonate` parameter through any redirect `Location` header so session continuity is maintained across redirects.

**Conditional skipping:** Yes — both hooks check `"__impersonate" in request.GET` as their first condition. If the parameter is absent, both methods are no-ops.

**Interaction note:** Runs before `EvvyAuditLogMiddleware` (position 16). This means audit log entries for impersonated requests will record the *impersonated user* as the actor (since the JWT swap happens at the HTTP_AUTHORIZATION level, before the lazy user is resolved for audit context).

**Authorization guard:**
```python
def is_user_allowed_to_impersonate(user):
    return user.is_staff and user.groups.filter(name="user-impersonation").exists()
```

---

#### 4. `EvvyAuditLogMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py`
**Position:** 16
**Base:** `AuditlogMiddleware` (from the `django-auditlog` package)
**Hook:** `__call__` (new-style middleware, wraps the entire request/response cycle)

**What it does:** Wraps every request in an audit logging context. Resolves the remote IP address and the current user (lazily, using `SimpleLazyObject`) and calls `set_actor()` which sets thread-local state consumed by django-auditlog's model signal handlers. This ensures every model change made during a request is attributed to the correct user and IP address in the audit log.

```python
def __call__(self, request):
    remote_addr = self._get_remote_addr(request)
    user = SimpleLazyObject(lambda: getattr(request, "user", None))
    context = set_actor(actor=user, remote_addr=remote_addr)
    with context:
        return self.get_response(request)
```

**Why a custom subclass:** The parent `AuditlogMiddleware` resolves `request.user` eagerly. The `SimpleLazyObject` wrapper defers resolution until the user is actually accessed, which is necessary to correctly capture impersonated users (since `ImpersonateMiddleware` at position 15 may still be modifying `request.META["HTTP_AUTHORIZATION"]` before auth backends run). The `with context:` block ensures the actor context is cleaned up even if the view raises an exception.

**Conditional skipping:** No — runs unconditionally on every request.

**Global settings** (from `settings.py`):
```python
AUDITLOG_INCLUDE_ALL_MODELS = True
AUDITLOG_EXCLUDE_TRACKING_MODELS = ("sessions", "otp_static")
```

---

#### 5. `CheckoutMonitoringMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py`
**Position:** 17 (last custom middleware)
**Base:** `MiddlewareMixin`
**Hook:** `process_exception` only

**What it does:** On exceptions in checkout-related paths or SSL/certificate errors, records custom New Relic metrics and adds structured context parameters to the transaction. Provides granular error tracking for the payment and consultation checkout flows.

Monitored paths (glob patterns):
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

**Conditional skipping:** Yes, two independent conditions:
1. **SSL/certificate errors** — activates regardless of path if `"ssl"` or `"certificate"` appears in the lowercased exception message.
2. **Checkout path** — activates for any exception on a checkout URL (matched via `fnmatch.fnmatch`).

If neither condition matches, `send_error` stays `False` and no New Relic calls are made.

```python
def process_exception(self, request, exception):
    send_error = False
    error_str = str(exception).lower()
    if "ssl" in error_str or "certificate" in error_str:
        newrelic.agent.record_custom_metric("Custom/SSLError", 1)
        send_error = True
    if self.is_checkout_path(request.path):
        newrelic.agent.record_custom_metric("Custom/Checkout/Error", 1)
        send_error = True
    if send_error:
        self._add_exception_context(request, exception)
```

---

### Middleware Interaction Map

```
Request Phase (top → bottom):
  [13] ExceptionContextMiddleware  — registers process_exception handler
  [14] RequestLoggingMiddleware    — no-op on request (process_request commented out)
  [15] ImpersonateMiddleware       — may swap HTTP_AUTHORIZATION header in request.META
  [16] EvvyAuditLogMiddleware      — opens set_actor context (lazy user resolution)
  [17] CheckoutMonitoringMiddleware — registers process_exception handler

  → VIEW EXECUTES

Response Phase (bottom → top):
  [17] CheckoutMonitoringMiddleware — no-op on response
  [16] EvvyAuditLogMiddleware       — closes set_actor context
  [15] ImpersonateMiddleware        — may propagate __impersonate param in redirect Location
  [14] RequestLoggingMiddleware     — logs final user ID, IP, method, status, path
  [13] ExceptionContextMiddleware   — no-op on response

Exception Phase (if view raises):
  [13] ExceptionContextMiddleware  — adds user_id to New Relic (if authenticated)
  [17] CheckoutMonitoringMiddleware — records checkout/SSL error metrics (conditionally)
```

### Key Interactions

1. **`ImpersonateMiddleware` → `EvvyAuditLogMiddleware`:** The impersonation token swap (position 15) happens before the audit context actor is resolved (position 16 uses `SimpleLazyObject`). The lazy evaluation means the audit log actor is captured after the swap completes, recording the impersonated user's actions correctly.

2. **`AuthenticationMiddleware` (position 7) → All custom middleware:** Django's built-in auth middleware sets `request.user` before any custom middleware runs. `ImpersonateMiddleware` overrides this at the HTTP header level; downstream DRF views will re-authenticate from the injected Bearer token.

3. **`ExceptionContextMiddleware` vs `CheckoutMonitoringMiddleware`:** Both handle exceptions but are non-overlapping in responsibility. `ExceptionContextMiddleware` attaches user identity; `CheckoutMonitoringMiddleware` attaches business-domain error classification. Both can fire on the same exception without conflict.

4. **`RequestLoggingMiddleware` commenting:** The `process_request` hook is present but commented out with a note ("Could do stuff here to time the diff in request/response"), indicating request-timing instrumentation was considered but not implemented.
