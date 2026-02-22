# E1-grep Raw Transcript

**Agent ID:** a26996f6e88a4fbda
**Tool:** grep (Grep, Glob, Read)
**Test:** E1 — Map all custom Django middleware classes
**Tool calls:** 13
**Tokens:** 36,162

## Final Answer

## Custom Django Middleware Map

All custom middleware lives under `/Users/albertgwo/Work/evvy/backend/app/middleware/`.

---

### Execution Order

From `/Users/albertgwo/Work/evvy/backend/app/settings.py` (lines 243-266), the full `MIDDLEWARE` list in order, with custom entries highlighted:

```
Position  Middleware
1         django.middleware.security.SecurityMiddleware
2         whitenoise.middleware.WhiteNoiseMiddleware
3         django.contrib.sessions.middleware.SessionMiddleware
4         corsheaders.middleware.CorsMiddleware
5         django.middleware.common.CommonMiddleware
6         django.middleware.csrf.CsrfViewMiddleware
7         django.contrib.auth.middleware.AuthenticationMiddleware
8         django.contrib.messages.middleware.MessageMiddleware
9         django.middleware.clickjacking.XFrameOptionsMiddleware
10        django_otp.middleware.OTPMiddleware
11        csp.middleware.CSPMiddleware
12        django_permissions_policy.PermissionsPolicyMiddleware
--- CUSTOM MIDDLEWARE BEGINS ---
13        app.middleware.ExceptionContextMiddleware         ← custom
14        app.middleware.RequestLoggingMiddleware           ← custom
15        app.middleware.ImpersonateMiddleware              ← custom
16        app.middleware.EvvyAuditLogMiddleware             ← custom
17        app.middleware.CheckoutMonitoringMiddleware       ← custom
```

In Django, `process_request` hooks run top-to-bottom (positions 1→17) and `process_response`/`process_exception` hooks run bottom-to-top (positions 17→1).

---

### 1. ExceptionContextMiddleware

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 8-15)

**Purpose:** On any unhandled exception, attaches the authenticated user's ID to the New Relic transaction as a custom parameter (`user_id`). Enables filtering New Relic error traces by user.

**Hook used:** `process_exception` only — runs last (bottom of stack) when exceptions bubble up.

**Conditional skip:** Yes — only calls `newrelic.agent.add_custom_parameter` if `request.user` exists and is authenticated. No-ops for anonymous requests.

```python
class ExceptionContextMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if request.user and request.user.is_authenticated:
            newrelic.agent.add_custom_parameter("user_id", request.user.id)
```

---

### 2. RequestLoggingMiddleware

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py` (lines 9-34)

**Purpose:** Logs every request/response cycle via the `evvy.request.logging` logger. The log line includes timestamp, user ID (or "none" for anonymous), client IP from the `True-Client-IP` header, HTTP method, response status code, and full path.

**Hook used:** `process_response` only — runs on every response including errors. The `process_request` method is present but commented out.

**Conditional skip:** Soft — if logging itself throws an exception, it logs a warning instead of propagating, so it never breaks the response chain. User ID gracefully degrades to "none" for anonymous or unauthenticated users.

```python
class RequestLoggingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        try:
            msg = "%s [user:%s] [ip:%s] %s %s %s" % (
                datetime.datetime.now(),
                request.user and request.user.is_authenticated and request.user.id or "none",
                request.headers.get("True-Client-IP", "none"),
                request.method,
                response.status_code,
                request.get_full_path(),
            )
            request_logger.debug(msg=msg, extra={})
        except Exception as e:
            request_logger.warning(msg=f"Failed to log request: {str(e)}")
        return response
```

---

### 3. ImpersonateMiddleware

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py` (lines 33-63)

**Purpose:** Allows staff users in the `user-impersonation` group to make requests on behalf of other users by passing `?__impersonate=<username>` as a query parameter. On the request side, it swaps the `HTTP_AUTHORIZATION` header to a freshly minted JWT for the target user. On the response side, it propagates the `__impersonate` parameter through redirects so multi-step flows (e.g., login redirects) stay impersonated.

**Hooks used:** Both `process_request` and `process_response`.

**Conditional skip:** Yes, heavily conditional:

- `process_request`: Entirely skips unless `__impersonate` is in `request.GET`. Then checks that the requesting user is authenticated via JWT AND is a staff member in the `user-impersonation` group. Returns early (without modifying the request) if the impersonated username does not exist. Returns `HttpResponseUnauthorized(401)` if the JWT is invalid.
- `process_response`: Only modifies redirect `Location` headers if `__impersonate` is in `request.GET` AND the current request user is allowed to impersonate.

```python
class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if "__impersonate" in request.GET:
            # ... JWT auth check + group check + user lookup + token swap

    def process_response(self, request, response):
        if "__impersonate" in request.GET and is_user_allowed_to_impersonate(request.user):
            if isinstance(response, HttpResponseRedirect):
                # append __impersonate to redirect URL
```

Helper `is_user_allowed_to_impersonate(user)` requires `user.is_staff=True` AND membership in the `"user-impersonation"` Django group.

---

### 4. EvvyAuditLogMiddleware

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py` (lines 11-18)

**Purpose:** Wraps every request in a `django-auditlog` context that sets the acting user and their remote IP for all model change events during the request. This ensures all database mutations are attributed to the correct actor in the audit log, even when changes happen in background tasks triggered during the request.

**Hook used:** `__call__` (new-style middleware) — wraps the entire downstream middleware chain and view execution in a context manager.

**Extends:** `auditlog.middleware.AuditlogMiddleware` from the `django-auditlog` third-party package. The override customizes actor resolution to use `SimpleLazyObject` (lazy evaluation of `request.user`) rather than eagerly resolving it, which avoids forcing user resolution before `AuthenticationMiddleware` has run. However, since `EvvyAuditLogMiddleware` runs at position 16 (after `AuthenticationMiddleware` at position 7), `request.user` will already be set.

**Conditional skip:** None — wraps all requests unconditionally.

```python
class EvvyAuditLogMiddleware(AuditlogMiddleware):
    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)
        user = SimpleLazyObject(lambda: getattr(request, "user", None))
        context = set_actor(actor=user, remote_addr=remote_addr)
        with context:
            return self.get_response(request)
```

---

### 5. CheckoutMonitoringMiddleware

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 18-53)

**Purpose:** Tracks exceptions on checkout-related API endpoints in New Relic. When an exception occurs on a checkout path or contains SSL/certificate error text, it records custom metrics (`Custom/Checkout/Error`, `Custom/Checkout/Error/<ExceptionType>`, `Custom/SSLError`) and attaches parameters (path, exception type, message) to the New Relic transaction.

**Hook used:** `process_exception` only.

**Conditional skip:** Yes — the most conditional of all middlewares. It first checks if the exception message contains "ssl" or "certificate" (case-insensitive), then checks if the request path matches any of 6 checkout path glob patterns. Only sends data to New Relic if at least one condition is true. If neither condition triggers, it is a complete no-op.

Monitored paths (via `fnmatch` glob matching):
- `/api/v1/carts/*/checkout`
- `/api/v1/consults/*/checkout_url`
- `/api/v1/consults/*/refill_checkout_url`
- `/api/v1/consults/*/cross-sell-checkout-url`
- `/api/v1/tests/*/checkout`
- `/api/v1/tests/*/ungated-checkout`

```python
class CheckoutMonitoringMiddleware(MiddlewareMixin):
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

### Interaction Summary

The five custom middleware form two functional groups that run independently:

**Request authentication group (positions 13-16, tightly coupled):**
- `ImpersonateMiddleware` runs BEFORE `EvvyAuditLogMiddleware`. This matters: if impersonation swaps the auth token in `request.META`, subsequent code (including the audit log context) will see the impersonated user. The audit log entry will be attributed to the impersonated user's identity, not the staff member doing the impersonating. This is a subtle interaction — the real actor's identity is lost from the audit trail.

**Observability group (positions 13 and 17, independent):**
- `ExceptionContextMiddleware` and `CheckoutMonitoringMiddleware` both handle `process_exception` and both integrate with New Relic, but they operate on orthogonal concerns (user ID enrichment vs. checkout path error counting). They do not share state or call each other.
- `RequestLoggingMiddleware` (position 14) logs every response and is purely additive — it does not affect other middleware.

**No middleware short-circuits the chain:** None of these middlewares return early responses that would prevent the view from running (the one exception being `ImpersonateMiddleware.process_request` returning `HttpResponseUnauthorized(401)` on an invalid JWT token during an impersonation attempt).
