# Custom Django Middleware Map — Evvy Backend

## Source Files

All custom middleware is located in `/Users/albertgwo/Work/evvy/backend/app/middleware/`:

- `__init__.py` — package exports
- `audit.py` — `EvvyAuditLogMiddleware`
- `auth.py` — `ImpersonateMiddleware` (+ helpers)
- `logging.py` — `RequestLoggingMiddleware`
- `monitoring.py` — `ExceptionContextMiddleware`, `CheckoutMonitoringMiddleware`

---

## Middleware Registration and Order

Defined in `/Users/albertgwo/Work/evvy/backend/app/settings.py`, lines 243–266:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # first, besides security middleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "csp.middleware.CSPMiddleware",
    "django_permissions_policy.PermissionsPolicyMiddleware",
    # logs user ID in newrelic on exception
    "app.middleware.ExceptionContextMiddleware",
    # custom request logging with user ID
    "app.middleware.RequestLoggingMiddleware",
    # custom request middleware for impersonating other users
    "app.middleware.ImpersonateMiddleware",
    "app.middleware.EvvyAuditLogMiddleware",
    # checkout error monitoring for newrelic
    "app.middleware.CheckoutMonitoringMiddleware",
]
```

The five custom Evvy middleware classes run in positions 13–17 (0-indexed), after all standard Django and third-party middleware. In Django's middleware chain, request-phase hooks (`process_request`) run top-to-bottom and response-phase hooks (`process_response`) run bottom-to-top.

---

## Middleware Details

### 1. `ExceptionContextMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 8–15)
**Position:** 13th overall (first custom middleware)

**What it does:** On any unhandled exception, if the request has an authenticated user, attaches the user's ID to the current New Relic transaction as a custom parameter (`user_id`). This enriches error traces in New Relic with the affected user's identity.

```python
class ExceptionContextMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if request.user and request.user.is_authenticated:
            newrelic.agent.add_custom_parameter("user_id", request.user.id)
```

**Conditional skip:** Only adds the parameter if `request.user.is_authenticated` — skips anonymous requests entirely.

---

### 2. `RequestLoggingMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py` (lines 9–34)
**Position:** 14th overall

**What it does:** On every response, logs a structured line containing: timestamp, user ID (or "none" for anonymous), client IP (from `True-Client-IP` header), HTTP method, response status code, and full request path. Uses logger `evvy.request.logging` at DEBUG level. Catches and logs (at WARNING) any internal exception rather than propagating it.

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

**Conditional skip:** No explicit skipping — runs for every request. However, for anonymous users the user ID logs as "none" rather than a real ID.

---

### 3. `ImpersonateMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py` (lines 33–63)
**Position:** 15th overall

**What it does:** Allows authorized staff users to impersonate other users by adding `?__impersonate=<username>` to any request URL.

- **`process_request`:** If `__impersonate` is in the GET parameters, authenticates the requesting user via JWT. If the requester is staff AND a member of the `user-impersonation` group, fetches the target user by username and generates a fresh JWT access token for them. Replaces `request.META["HTTP_AUTHORIZATION"]` with a `Bearer <token>` for the impersonated user — so all downstream auth sees the impersonated user as the current user.
- **`process_response`:** If `__impersonate` was in the GET params and the user has impersonation rights, appends `__impersonate=<username>` to any redirect `Location` header, so the impersonation parameter is preserved across redirects.

```python
class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if "__impersonate" in request.GET:
            try:
                user = get_jwt_user(request)
                if is_user_allowed_to_impersonate(user):
                    impersonated_user = User.objects.get(username=request.GET["__impersonate"])
                    refresh = RefreshToken.for_user(impersonated_user)
                    access_token = str(refresh.access_token)
                    request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
            except InvalidToken as e:
                return HttpResponseUnauthorized("invalid token")

    def process_response(self, request, response):
        if "__impersonate" in request.GET and is_user_allowed_to_impersonate(request.user):
            if isinstance(response, HttpResponseRedirect):
                # append __impersonate param to redirect URL
                ...
        return response
```

**Conditional skip:** Entirely gated on `"__impersonate" in request.GET` — skips all processing if the query parameter is absent. Within the impersonation path, also skips if the user lacks staff status or `user-impersonation` group membership.

Helper functions in the same file:
- `get_jwt_user(request)`: returns the authenticated user from session or JWT token.
- `is_user_allowed_to_impersonate(user)`: returns `True` only if `user.is_staff` and user is in group `"user-impersonation"`.

---

### 4. `EvvyAuditLogMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py` (lines 11–18)
**Position:** 16th overall

**What it does:** Extends the third-party `auditlog.middleware.AuditlogMiddleware` to attach the current request's remote IP address and authenticated user to the audit log context for every model-level change made during this request (via `django-auditlog`'s `set_actor` context manager). This ensures that all database writes logged by auditlog include actor identity and IP.

```python
class EvvyAuditLogMiddleware(AuditlogMiddleware):
    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)
        user = SimpleLazyObject(lambda: getattr(request, "user", None))
        context = set_actor(actor=user, remote_addr=remote_addr)

        with context:
            return self.get_response(request)
```

Uses `SimpleLazyObject` so the user is not resolved until actually needed (avoids premature DB hits before auth middleware runs — though note auth middleware runs *before* this one, so the user should be available).

**Conditional skip:** No explicit skipping — runs for all requests. The `set_actor` context simply may not find a user if the request is anonymous (the `SimpleLazyObject` would return `None`).

Configured globally in settings:
```python
AUDITLOG_INCLUDE_ALL_MODELS = True
AUDITLOG_EXCLUDE_TRACKING_MODELS = ("sessions", "otp_static")
```

---

### 5. `CheckoutMonitoringMiddleware`
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 18–53)
**Position:** 17th overall (last custom middleware)

**What it does:** On exceptions in checkout-related API endpoints, records structured custom metrics and parameters to New Relic. Additionally, records a metric for any SSL/certificate errors regardless of path.

Monitored paths (via `fnmatch` glob patterns):
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

When sending to New Relic, records: `Custom/Checkout/Error/<ErrorType>`, `checkout_path`, `exception_type`, `exception_message`.

**Conditional skip:** Only fires on exceptions (not normal responses). Within exception handling, only sends context if the path matches a checkout path OR if the error message contains "ssl"/"certificate". All other exceptions on non-checkout paths are silently ignored.

---

## Execution Order Summary

```
REQUEST PHASE (top to bottom):
  ...standard Django middleware...
  13. ExceptionContextMiddleware.process_request  — (no-op; only has process_exception)
  14. RequestLoggingMiddleware.process_request     — (no-op; only has process_response)
  15. ImpersonateMiddleware.process_request        — mutates HTTP_AUTHORIZATION if ?__impersonate= present
  16. EvvyAuditLogMiddleware.__call__              — sets audit actor context (wraps entire request)
  17. CheckoutMonitoringMiddleware.process_request — (no-op; only has process_exception)

  → VIEW EXECUTES

RESPONSE PHASE (bottom to top):
  17. CheckoutMonitoringMiddleware.process_response — (no-op)
  16. EvvyAuditLogMiddleware.__call__ context exits
  15. ImpersonateMiddleware.process_response        — appends ?__impersonate= to redirect Location if applicable
  14. RequestLoggingMiddleware.process_response     — logs request line with user/IP/method/status/path
  13. ExceptionContextMiddleware.process_response   — (no-op)
  ...standard Django middleware...

EXCEPTION PHASE (propagates upward):
  13. ExceptionContextMiddleware.process_exception  — adds user_id to New Relic (if authenticated)
  17. CheckoutMonitoringMiddleware.process_exception — records checkout/SSL errors to New Relic
```

Note: `EvvyAuditLogMiddleware` uses `__call__` (new-style middleware), not `process_request`/`process_response` hooks. It wraps the entire downstream call in a context manager, so its "response phase" is the `with context:` block exiting after `get_response(request)` returns.

---

## Interactions Between Middleware

1. **`ImpersonateMiddleware` → downstream auth:** `ImpersonateMiddleware` runs at position 15, *after* Django's `AuthenticationMiddleware` (position 7). It modifies `request.META["HTTP_AUTHORIZATION"]` for the current request, but Django's session-based auth has already run. The modified Authorization header is consumed by DRF's `EvvyJWTAuthentication` on each view, not by Django's middleware auth. This means impersonation works at the DRF layer, not the Django session layer.

2. **`ImpersonateMiddleware` → `EvvyAuditLogMiddleware`:** `ImpersonateMiddleware.process_request` runs before `EvvyAuditLogMiddleware.__call__` sets the audit actor. If impersonation succeeds, the `request.META["HTTP_AUTHORIZATION"]` is updated, but `request.user` at audit-log time is still the original session user (not the impersonated one), because the JWT is only decoded at the view/DRF layer. The audit log therefore records the real user as actor, not the impersonated user.

3. **`ExceptionContextMiddleware` and `CheckoutMonitoringMiddleware` — complementary New Relic instrumentation:** Both respond to exceptions. `ExceptionContextMiddleware` fires first (position 13 in the exception chain — exceptions propagate from inner to outer, so position 13 sees exceptions before position 17). It adds `user_id`. `CheckoutMonitoringMiddleware` (position 17) adds checkout-specific context. For a checkout exception on an authenticated request, both fire and New Relic receives both `user_id` and `checkout_path`/`exception_type` parameters.

4. **`RequestLoggingMiddleware` runs regardless of exception:** Since it uses `process_response`, it only fires if a response is actually returned. If an exception propagates all the way out unhandled, the response logging may not fire. The exception middleware (`ExceptionContextMiddleware`, `CheckoutMonitoringMiddleware`) would still fire in that case.

---

## Conditional Processing Summary

| Middleware | Condition for skipping |
|---|---|
| `ExceptionContextMiddleware` | Skips `add_custom_parameter` if `request.user` is not authenticated |
| `RequestLoggingMiddleware` | No skip — runs every request; logs "none" for unauthenticated users |
| `ImpersonateMiddleware` | Skips entirely if `__impersonate` not in `request.GET`; also skips if user lacks staff/group |
| `EvvyAuditLogMiddleware` | No skip — wraps all requests; actor may be `None` for anonymous requests |
| `CheckoutMonitoringMiddleware` | Only fires on exceptions; skips unless path matches checkout glob OR error is SSL-related |
