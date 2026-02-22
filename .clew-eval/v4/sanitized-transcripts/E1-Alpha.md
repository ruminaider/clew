# E1 Exploration Log

## Search 1: Locate all middleware files and settings
Searched for `**/middleware*.py` glob and `**/settings*.py` glob.

Findings:
- No custom middleware files existed at the top level; venv only had third-party middleware (Django, corsheaders, auditlog, django_otp, fastmcp).
- Found the main settings file at `/Users/albertgwo/Work/evvy/backend/app/settings.py`.

## Search 2: Find all classes named *Middleware across the codebase
Grep for `class.*Middleware` across all .py files (excluding venv via path scoping to `/Users/albertgwo/Work/evvy/backend`).

Findings — 6 source files matched:
- `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py`
- `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py`
- `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py`
- `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py`
- (plus two test files)

Also read `settings.py` fully. Found the MIDDLEWARE list at lines 243–266 showing 5 custom middleware entries:
```python
"app.middleware.ExceptionContextMiddleware",
"app.middleware.RequestLoggingMiddleware",
"app.middleware.ImpersonateMiddleware",
"app.middleware.EvvyAuditLogMiddleware",
"app.middleware.CheckoutMonitoringMiddleware",
```

## Search 3: Read auth.py middleware
Read `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py`.

Findings:
- `ImpersonateMiddleware` — uses `MiddlewareMixin`, has `process_request` and `process_response`.
- `process_request` conditionally skips entirely unless `__impersonate` is in `request.GET`.
- When active, verifies the requesting user via JWT, checks `is_user_allowed_to_impersonate()` (staff + "user-impersonation" group), then generates a new JWT for the target user and injects it as `HTTP_AUTHORIZATION`.
- `process_response` propagates the `__impersonate` query param on redirects if the user is allowed to impersonate.
- Helper `get_jwt_user()` delegates to `EvvyJWTAuthentication.authenticate()`.
- Helper `is_user_allowed_to_impersonate()` checks `user.is_staff` and group membership in `"user-impersonation"`.

## Search 4: Read logging.py middleware
Read `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py`.

Findings:
- `RequestLoggingMiddleware` — uses `MiddlewareMixin`, only `process_response`.
- Logs timestamp, user ID (or "none" for unauthenticated), `True-Client-IP` header, HTTP method, status code, and full path.
- No conditional skip logic; always logs (errors are caught and logged as warnings).

## Search 5: Read monitoring.py middleware
Read `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py`.

Findings:
- `ExceptionContextMiddleware` — `process_exception` only. Adds `user_id` to the New Relic transaction as a custom parameter. Conditionally skips if `request.user` is not authenticated.
- `CheckoutMonitoringMiddleware` — `process_exception` only. Sends metrics to New Relic for:
  - Any SSL/certificate errors anywhere (records `Custom/SSLError`).
  - Any exception on known checkout URL patterns (records `Custom/Checkout/Error` and `Custom/Checkout/Error/{ExceptionType}`).
  - Uses `fnmatch.fnmatch` with a hardcoded list of 6 checkout path patterns to determine if the request is a checkout. Conditionally skips metric recording unless at least one condition is true.

## Search 6: Read audit.py middleware
Read `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py`.

Findings:
- `EvvyAuditLogMiddleware` — subclasses `auditlog.middleware.AuditlogMiddleware` (from the `django-auditlog` third-party library).
- Overrides `__call__` to set the audit log actor to the current request user (lazy) and remote address, wrapping the entire request/response cycle in an `auditlog.context.set_actor` context manager.
- No conditional skip logic; always sets the actor context.

## Search 7: Read __init__.py to confirm exported names
Read `/Users/albertgwo/Work/evvy/backend/app/middleware/__init__.py`.

Confirmed all 5 middleware classes are exported from the package:
- `EvvyAuditLogMiddleware`
- `ImpersonateMiddleware`
- `RequestLoggingMiddleware`
- `CheckoutMonitoringMiddleware`
- `ExceptionContextMiddleware`

Also noted that `HttpResponseUnauthorized`, `get_jwt_user`, and `is_user_allowed_to_impersonate` helpers are exported.

## Search 8: Read test files
Read both test files to understand expected behaviors.

`test_middleware.py` tests `is_user_allowed_to_impersonate` with three cases: non-staff, staff without group, staff with "user-impersonation" group.

`test_checkout_middleware.py` tests `CheckoutMonitoringMiddleware` path matching and exception handling.

## Search 9: Check for any additional middleware references in settings
Grep for `app\.middleware\.` across all Python files to confirm exactly what's registered.

Result confirmed: exactly the 5 custom middleware entries found above are registered in settings.py. No other files reference these middleware classes (only the middleware package's own `__init__.py` and test files).

## Search 10: Read EvvyJWTAuthentication to understand auth chain
Read `/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py`.

Findings: `EvvyJWTAuthentication` extends `JWTAuthentication` (simplejwt). It adds a blacklist check: if the token's string representation is found in the cache under the `ACCESS_TOKEN_PREFIX` key, it raises `InvalidToken`. This is the same class used by `ImpersonateMiddleware.get_jwt_user()` to authenticate the requesting user before allowing impersonation.

---

## Final Answer

### Overview

The application has **5 custom middleware classes**, all located in `/Users/albertgwo/Work/evvy/backend/app/middleware/`. They are registered in `MIDDLEWARE` in `/Users/albertgwo/Work/evvy/backend/app/settings.py` (lines 243–266) and exported from the package `__init__.py`.

---

### Full MIDDLEWARE Order (settings.py lines 243–266)

```
Position 1:  django.middleware.security.SecurityMiddleware
Position 2:  whitenoise.middleware.WhiteNoiseMiddleware
Position 3:  django.contrib.sessions.middleware.SessionMiddleware
Position 4:  corsheaders.middleware.CorsMiddleware
Position 5:  django.middleware.common.CommonMiddleware
Position 6:  django.middleware.csrf.CsrfViewMiddleware
Position 7:  django.contrib.auth.middleware.AuthenticationMiddleware
Position 8:  django.contrib.messages.middleware.MessageMiddleware
Position 9:  django.middleware.clickjacking.XFrameOptionsMiddleware
Position 10: django_otp.middleware.OTPMiddleware
Position 11: csp.middleware.CSPMiddleware
Position 12: django_permissions_policy.PermissionsPolicyMiddleware
Position 13: app.middleware.ExceptionContextMiddleware        [CUSTOM]
Position 14: app.middleware.RequestLoggingMiddleware         [CUSTOM]
Position 15: app.middleware.ImpersonateMiddleware            [CUSTOM]
Position 16: app.middleware.EvvyAuditLogMiddleware           [CUSTOM]
Position 17: app.middleware.CheckoutMonitoringMiddleware     [CUSTOM]
```

All 5 custom middleware appear at the end of the stack (positions 13–17), after all standard Django and third-party middleware have run.

---

### Custom Middleware Detail

#### 1. ExceptionContextMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 8–15)
**Position in stack:** 13 (first custom middleware)
**Base class:** `MiddlewareMixin`
**Hook used:** `process_exception`

**Purpose:** Enriches New Relic error traces with the authenticated user ID when an unhandled exception occurs.

**Implementation:**
```python
class ExceptionContextMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if request.user and request.user.is_authenticated:
            newrelic.agent.add_custom_parameter("user_id", request.user.id)
```

**Conditional skip:** Yes — only adds the parameter if `request.user` is authenticated. Unauthenticated requests are silently skipped (no parameter is added).

---

#### 2. RequestLoggingMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py`
**Position in stack:** 14
**Base class:** `MiddlewareMixin`
**Hook used:** `process_response`

**Purpose:** Custom request/response logging that includes the authenticated user ID and the real client IP address (from `True-Client-IP` header) in every log entry. The comment notes this is specifically for "custom request logging with user ID."

**Implementation:**
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

**Conditional skip:** None. Every request is logged (exceptions during logging are caught and emit a warning instead).

---

#### 3. ImpersonateMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py`
**Position in stack:** 15
**Base class:** `MiddlewareMixin`
**Hooks used:** `process_request`, `process_response`

**Purpose:** Allows authorized staff users to impersonate another user by passing `?__impersonate=<username>` as a query parameter. It dynamically swaps the `Authorization` header to a JWT issued for the target user.

**Implementation:**
```python
class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if "__impersonate" in request.GET:
            try:
                user = get_jwt_user(request)
                if is_user_allowed_to_impersonate(user):
                    try:
                        impersonated_user = User.objects.get(username=request.GET["__impersonate"])
                    except User.DoesNotExist:
                        # logs warning, returns (skips impersonation)
                        return
                    refresh = RefreshToken.for_user(impersonated_user)
                    access_token = str(refresh.access_token)
                    request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
            except InvalidToken as e:
                return HttpResponseUnauthorized("invalid token")

    def process_response(self, request, response):
        if "__impersonate" in request.GET and is_user_allowed_to_impersonate(request.user):
            if isinstance(response, HttpResponseRedirect):
                # propagates __impersonate param through redirects
                ...
        return response
```

**Permission gate:** `is_user_allowed_to_impersonate(user)` — requires `user.is_staff == True` AND membership in the `"user-impersonation"` Django group.

**Conditional skip:** Yes — strongly conditional:
- Entire `process_request` logic is skipped unless `"__impersonate"` is in `request.GET`.
- Even when the param is present, impersonation is skipped if the requesting user lacks staff status or group membership.
- If the target username does not exist, impersonation is skipped (warning logged).
- If the JWT is invalid, returns `HttpResponseUnauthorized(401)` early.
- `process_response` only runs redirect parameter propagation if `__impersonate` is in GET and user is allowed.

**Interaction with other middleware:** This middleware runs after Django's `AuthenticationMiddleware` (position 7) has set `request.user`. It uses `EvvyJWTAuthentication` (the DRF authentication class) directly to re-authenticate from the JWT in the `Authorization` header, bypassing the session-based auth. The modified `HTTP_AUTHORIZATION` header then propagates to DRF view-level authentication for the remainder of the request cycle.

---

#### 4. EvvyAuditLogMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py`
**Position in stack:** 16
**Base class:** `auditlog.middleware.AuditlogMiddleware` (third-party `django-auditlog`)
**Hook used:** `__call__` (wraps full request/response cycle)

**Purpose:** Records all model changes to the audit log with the actor (current user) and remote address for every request. The application wraps the third-party `AuditlogMiddleware` to use the parent's `_get_remote_addr()` method while setting up its own actor context using a lazy `SimpleLazyObject` (so the user is not resolved until actually needed).

**Implementation:**
```python
class EvvyAuditLogMiddleware(AuditlogMiddleware):
    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)
        user = SimpleLazyObject(lambda: getattr(request, "user", None))
        context = set_actor(actor=user, remote_addr=remote_addr)
        with context:
            return self.get_response(request)
```

**Why override the parent?** The parent `AuditlogMiddleware` resolves the user eagerly; this override wraps it in `SimpleLazyObject` so the user is only resolved if the audit log actually needs it.

**Conditional skip:** None. Every request is wrapped in the actor context. If `request.user` is None (unauthenticated), the lazy object will return `None` as the actor, which the auditlog library handles gracefully.

**Setting:** `AUDITLOG_INCLUDE_ALL_MODELS = True` and `AUDITLOG_EXCLUDE_TRACKING_MODELS = ("sessions", "otp_static")` (settings.py lines 268–269).

---

#### 5. CheckoutMonitoringMiddleware
**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 18–53)
**Position in stack:** 17 (last custom middleware)
**Base class:** `MiddlewareMixin`
**Hook used:** `process_exception`

**Purpose:** Monitors checkout-related exceptions and SSL errors for New Relic. Records custom metrics and parameters to allow alerting and dashboards on checkout failure rates.

**Checkout paths monitored** (using `fnmatch` glob matching):
- `/api/v1/carts/*/checkout`
- `/api/v1/consults/*/checkout_url`
- `/api/v1/consults/*/refill_checkout_url`
- `/api/v1/consults/*/cross-sell-checkout-url`
- `/api/v1/tests/*/checkout`
- `/api/v1/tests/*/ungated-checkout`

**Implementation:**
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

**Metrics recorded:**
- `Custom/SSLError` — any SSL/certificate error on any path
- `Custom/Checkout/Error` — any exception on a checkout path
- `Custom/Checkout/Error/{ExceptionType}` — e.g. `Custom/Checkout/Error/ValueError`
- Custom parameters: `checkout_path`, `exception_type`, `exception_message`

**Conditional skip:** Yes — the most strongly conditional of all custom middleware. New Relic calls are only made if:
1. The exception message contains "ssl" or "certificate" (case-insensitive), OR
2. The request path matches one of the 6 checkout glob patterns.
If neither condition is true, the method does nothing.

---

### Interactions Between Custom Middleware

1. **ExceptionContextMiddleware → RequestLoggingMiddleware:** These run sequentially on exceptions. `ExceptionContextMiddleware` (position 13) handles exceptions by enriching New Relic with user context. `RequestLoggingMiddleware` (position 14) only has `process_response`, so it logs every completed response regardless. On exceptions that propagate to Django's exception handling, `RequestLoggingMiddleware.process_response` still fires (Django calls `process_response` even on error responses).

2. **ImpersonateMiddleware (position 15) depends on AuthenticationMiddleware (position 7):** `ImpersonateMiddleware.process_request` reads `request.user` (set by Django's standard `AuthenticationMiddleware`) to call `is_user_allowed_to_impersonate()`. It then mutates `request.META["HTTP_AUTHORIZATION"]` to inject the impersonated user's JWT. This mutation happens before DRF's per-view authentication, so the DRF view sees the impersonated user's token.

3. **EvvyAuditLogMiddleware (position 16) uses request.user set by ImpersonateMiddleware:** Because `EvvyAuditLogMiddleware` wraps the entire request in a `with set_actor(user=...)` context (using a lazy object), and `ImpersonateMiddleware.process_request` runs first (position 15 < 16 on the inbound path but position 16 wraps the full call chain), the audit log actor will be the **original** requesting user (not the impersonated user), since `request.user` is not changed by `ImpersonateMiddleware` — only `HTTP_AUTHORIZATION` is changed, and DRF resolves the impersonated user at view time. The `set_actor` lazy object resolves `request.user` which is still the original session/JWT user at middleware level.

4. **CheckoutMonitoringMiddleware (position 17):** As the last middleware, it handles exceptions after all other custom middleware have had a chance to process them. Both `ExceptionContextMiddleware` and `CheckoutMonitoringMiddleware` implement `process_exception`, so both fire on every unhandled exception — Django calls `process_exception` on all middleware in reverse order. `CheckoutMonitoringMiddleware` is last in the list so its `process_exception` fires first (reverse order for exception handling), then `ExceptionContextMiddleware.process_exception` fires.

### Middleware Processing Order Summary

For a **normal request** (no exception):
- **Inbound (process_request):** ImpersonateMiddleware.process_request runs (if `__impersonate` in GET)
- **Wrapping:** EvvyAuditLogMiddleware wraps the full response cycle
- **Outbound (process_response, reverse order):** CheckoutMonitoringMiddleware → EvvyAuditLogMiddleware → ImpersonateMiddleware.process_response → RequestLoggingMiddleware.process_response → ExceptionContextMiddleware (no process_response, skipped)

For a request with an **exception**:
- **process_exception (reverse order):** CheckoutMonitoringMiddleware.process_exception → ExceptionContextMiddleware.process_exception
- **process_response (reverse order, after exception handler generates a response):** CheckoutMonitoringMiddleware → EvvyAuditLogMiddleware → ImpersonateMiddleware.process_response → RequestLoggingMiddleware.process_response
