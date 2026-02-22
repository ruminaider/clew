# E1 — Agent Beta

## Custom Django Middleware in the Evvy Backend

All custom middleware lives in `/Users/albertgwo/Work/evvy/backend/app/middleware/` and is exported from `/Users/albertgwo/Work/evvy/backend/app/middleware/__init__.py`.

---

### Middleware Execution Order

From `/Users/albertgwo/Work/evvy/backend/app/settings.py` (lines 243-266), Django processes middleware top-to-bottom on the request path and bottom-to-top on the response path. The five custom middleware classes appear at positions 11-15 in the stack (after all standard Django/third-party middleware):

```
1.  django.middleware.security.SecurityMiddleware
2.  whitenoise.middleware.WhiteNoiseMiddleware
3.  django.contrib.sessions.middleware.SessionMiddleware
4.  corsheaders.middleware.CorsMiddleware
5.  django.middleware.common.CommonMiddleware
6.  django.middleware.csrf.CsrfViewMiddleware
7.  django.contrib.auth.middleware.AuthenticationMiddleware      ← sets request.user
8.  django.contrib.messages.middleware.MessageMiddleware
9.  django.middleware.clickjacking.XFrameOptionsMiddleware
10. django_otp.middleware.OTPMiddleware
11. csp.middleware.CSPMiddleware
12. django_permissions_policy.PermissionsPolicyMiddleware
--- CUSTOM MIDDLEWARE ---
13. app.middleware.ExceptionContextMiddleware
14. app.middleware.RequestLoggingMiddleware
15. app.middleware.ImpersonateMiddleware
16. app.middleware.EvvyAuditLogMiddleware
17. app.middleware.CheckoutMonitoringMiddleware
```

---

### 1. `ExceptionContextMiddleware`

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 8-15)

**What it does:** Enriches New Relic transactions with user context when an unhandled exception occurs. If the request has an authenticated user, it attaches the `user_id` as a custom New Relic parameter before the exception propagates.

**Hooks used:** `process_exception(request, exception)`

**Conditional logic:** Skips adding the parameter if `request.user` is unauthenticated (anonymous). The check `request.user and request.user.is_authenticated` guards the New Relic call.

```python
class ExceptionContextMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if request.user and request.user.is_authenticated:
            newrelic.agent.add_custom_parameter("user_id", request.user.id)
```

---

### 2. `RequestLoggingMiddleware`

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/logging.py` (lines 9-34)

**What it does:** Logs a structured debug line for every HTTP response containing timestamp, user ID (or "none" for anonymous), client IP (from `True-Client-IP` header, i.e. Cloudflare/CDN), HTTP method, response status code, and full URL path.

**Hooks used:** `process_response(request, response)`

**Conditional logic:** Uses the expression `request.user and request.user.is_authenticated and request.user.id or "none"` to safely emit "none" for unauthenticated users. A broad `except Exception` catch prevents any logging failure from breaking the response. The `process_request` hook is explicitly commented out (was reserved for timing).

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

### 3. `ImpersonateMiddleware`

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/auth.py` (lines 33-63)

**What it does:** Allows staff members in the `user-impersonation` group to impersonate any other user by appending `?__impersonate=<username>` to any request URL. On the request side, it generates a short-lived JWT access token for the target user and injects it into `request.META["HTTP_AUTHORIZATION"]`, so all downstream authentication middleware and DRF views see the impersonated user. On the response side, it propagates the `__impersonate` query parameter through any `HttpResponseRedirect` so impersonation persists across redirects.

**Hooks used:** `process_request(request)` and `process_response(request, response)`

**Conditional logic (multiple gates):**
- `process_request` only activates if `"__impersonate" in request.GET` — all other requests pass through with zero cost.
- The impersonator must be authenticated via JWT (`get_jwt_user` validates the bearer token using `EvvyJWTAuthentication`).
- The impersonator must be a staff member AND in the `user-impersonation` group (`is_user_allowed_to_impersonate`).
- If the target username does not exist, a warning is logged and processing returns silently.
- If the JWT is invalid, it returns `HttpResponseUnauthorized` (401).
- `process_response` gate: only modifies redirects if `__impersonate` is in GET AND the current `request.user` (the impersonator, post-auth) is allowed to impersonate.

**Interaction with other middleware:** This middleware runs after `AuthenticationMiddleware` (#7), which has already set `request.user` from the session. However, `ImpersonateMiddleware` uses its own `get_jwt_user()` helper to re-authenticate from the `Authorization` bearer token (ignoring the session user), enabling API-level impersonation. It injects the impersonated user's token into `HTTP_AUTHORIZATION`, which downstream DRF views use via their own authentication layer.

```python
class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if "__impersonate" in request.GET:
            # ... validates impersonator, generates token for target user,
            # injects into request.META["HTTP_AUTHORIZATION"]

    def process_response(self, request, response):
        if "__impersonate" in request.GET and is_user_allowed_to_impersonate(request.user):
            if isinstance(response, HttpResponseRedirect):
                # appends __impersonate param to redirect Location header
```

---

### 4. `EvvyAuditLogMiddleware`

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/audit.py` (lines 11-18)

**What it does:** Extends the third-party `auditlog` library's `AuditlogMiddleware` to enable audit logging of model changes. It wraps every request in a context manager that sets the current "actor" (user + remote IP) for the `django-auditlog` library, so all model `save`/`delete` operations during that request are attributed to the correct user. The global setting `AUDITLOG_INCLUDE_ALL_MODELS = True` (settings.py line 268) means every model change is tracked; `sessions` and `otp_static` are excluded (line 269).

**Hooks used:** Implements `__call__` directly (new-style middleware), not `MiddlewareMixin`.

**Conditional logic:** Uses `SimpleLazyObject` so the `request.user` is not evaluated until the `auditlog` library actually needs it (deferred evaluation). The actor is set to `None`/anonymous if `request.user` is not present — the parent `_get_remote_addr()` handles IP extraction from standard headers.

**Interaction with other middleware:** Must run after `AuthenticationMiddleware` (#7) so `request.user` is populated. Running before `ImpersonateMiddleware` means audit logs attribute actions to the session user, not the impersonated user — this is an important ordering note.

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

### 5. `CheckoutMonitoringMiddleware`

**File:** `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` (lines 18-53)

**What it does:** Specialized New Relic monitoring for checkout-related endpoints. On any exception, it checks whether the request path matches a set of glob patterns covering all checkout URL paths, and/or whether the exception message contains SSL/certificate errors. If either condition matches, it records a custom New Relic metric and attaches detailed exception context (checkout path, exception type, exception message).

**Hooks used:** `process_exception(request, exception)`

**Conditional logic (path-based skip):** The middleware only sends telemetry if `send_error` is True, which requires at least one of:
1. The exception message contains `"ssl"` or `"certificate"` (case-insensitive) — records `Custom/SSLError`
2. The request path matches one of the `CHECKOUT_PATHS` glob patterns

Paths monitored:
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

All non-checkout, non-SSL errors pass through silently. The `fnmatch` module is used for glob-style path matching.

---

### Middleware Interactions Summary

| Middleware | Interacts With | Nature |
|---|---|---|
| `ExceptionContextMiddleware` | Django's `AuthenticationMiddleware` | Reads `request.user` set by Django auth |
| `RequestLoggingMiddleware` | Django's `AuthenticationMiddleware` | Reads `request.user` for log line |
| `ImpersonateMiddleware` | `EvvyAuditLogMiddleware` | **Ordering gap:** audit runs _before_ impersonation rewires the auth token; audit actor = session user, not target user |
| `ImpersonateMiddleware` | DRF views (downstream) | Injects impersonated JWT into `HTTP_AUTHORIZATION`; DRF's own auth layer picks it up |
| `EvvyAuditLogMiddleware` | `ImpersonateMiddleware` | See above — placement before impersonation middleware means audit context is set before the token swap |
| `CheckoutMonitoringMiddleware` | None | Fully self-contained; only reads `request.path` and exception |

### Key Architectural Note

`EvvyAuditLogMiddleware` (position 16) runs **before** `ImpersonateMiddleware` fully takes effect on the outbound side. Since `EvvyAuditLogMiddleware` uses new-style `__call__` middleware (not `MiddlewareMixin`), it wraps the entire remaining middleware stack including `CheckoutMonitoringMiddleware` in its audit context. However, it is positioned **after** `ImpersonateMiddleware` in the list, meaning on the inbound request path, impersonation happens first (position 15 `process_request` runs), but the audit context actor (`SimpleLazyObject`) is resolved lazily during the view execution, after impersonation has already rewritten `HTTP_AUTHORIZATION`. This means audit logs will capture the session user as actor, not the impersonated user — a subtle but important distinction for compliance purposes.
