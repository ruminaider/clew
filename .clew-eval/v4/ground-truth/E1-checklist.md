# E1 Ground Truth Checklist: Middleware Audit

Source: `/Users/albertgwo/Work/evvy/backend/`

## E1 Ground Truth Checklist

- [ ] Artifact 1: `ImpersonateMiddleware` (`backend/app/middleware/auth.py`) - Allows staff users in the "user-impersonation" group to act as another user. In `process_request`, checks for `__impersonate` query param, authenticates the requester via JWT, verifies impersonation permission, then overwrites `HTTP_AUTHORIZATION` with a fresh token for the target user. In `process_response`, appends `__impersonate` param to redirect `Location` headers to persist impersonation across redirects.
- [ ] Artifact 2: `RequestLoggingMiddleware` (`backend/app/middleware/logging.py`) - Logs every request at DEBUG level via the `evvy.request.logging` logger. Records timestamp, authenticated user ID (or "none"), `True-Client-IP` header, HTTP method, response status code, and full request path. Operates exclusively in `process_response`.
- [ ] Artifact 3: `EvvyAuditLogMiddleware` (`backend/app/middleware/audit.py`) - Extends the third-party `AuditlogMiddleware` (django-auditlog). In `__call__`, resolves the remote address and lazily binds the request user as the audit actor via `set_actor` context manager before delegating to the next middleware. Records all model changes (enabled by `AUDITLOG_INCLUDE_ALL_MODELS = True` in settings).
- [ ] Artifact 4: `ExceptionContextMiddleware` (`backend/app/middleware/monitoring.py`) - Attaches user context to New Relic transactions on unhandled exceptions. In `process_exception`, if the request user is authenticated, records `user_id` as a custom New Relic parameter to aid error diagnosis.
- [ ] Artifact 5: `CheckoutMonitoringMiddleware` (`backend/app/middleware/monitoring.py`) - Monitors checkout-path exceptions via New Relic. In `process_exception`, records a `Custom/Checkout/Error` metric and adds `checkout_path`, `exception_type`, and `exception_message` parameters if the request path matches a glob pattern against six checkout endpoints. Also records a `Custom/SSLError` metric if the exception message contains "ssl" or "certificate".

## Middleware Order (from `backend/app/settings.py`, lines 243-266)

1. `django.middleware.security.SecurityMiddleware` (standard)
2. `whitenoise.middleware.WhiteNoiseMiddleware` (third-party)
3. `django.contrib.sessions.middleware.SessionMiddleware` (standard)
4. `corsheaders.middleware.CorsMiddleware` (third-party)
5. `django.middleware.common.CommonMiddleware` (standard)
6. `django.middleware.csrf.CsrfViewMiddleware` (standard)
7. `django.contrib.auth.middleware.AuthenticationMiddleware` (standard)
8. `django.contrib.messages.middleware.MessageMiddleware` (standard)
9. `django.middleware.clickjacking.XFrameOptionsMiddleware` (standard)
10. `django_otp.middleware.OTPMiddleware` (third-party)
11. `csp.middleware.CSPMiddleware` (third-party)
12. `django_permissions_policy.PermissionsPolicyMiddleware` (third-party)
13. **`app.middleware.ExceptionContextMiddleware`** (custom)
14. **`app.middleware.RequestLoggingMiddleware`** (custom)
15. **`app.middleware.ImpersonateMiddleware`** (custom)
16. **`app.middleware.EvvyAuditLogMiddleware`** (custom)
17. **`app.middleware.CheckoutMonitoringMiddleware`** (custom)

## Conditional Skip Logic

- `ImpersonateMiddleware` skips in `process_request` when: `__impersonate` query parameter is absent from the request (no-op for normal requests). Also silently returns (no redirect injection) in `process_response` if the current `request.user` does not pass `is_user_allowed_to_impersonate`.
- `ImpersonateMiddleware` skips redirect injection in `process_response` when: the response is not an `HttpResponseRedirect`.
- `ExceptionContextMiddleware` skips adding user context when: `request.user` is unauthenticated or anonymous (only adds `user_id` parameter if `request.user.is_authenticated` is truthy).
- `CheckoutMonitoringMiddleware` skips recording checkout metrics when: the request path does not match any of the six checkout glob patterns (`/api/v1/carts/*/checkout`, `/api/v1/consults/*/checkout_url`, `/api/v1/consults/*/refill_checkout_url`, `/api/v1/consults/*/cross-sell-checkout-url`, `/api/v1/tests/*/checkout`, `/api/v1/tests/*/ungated-checkout`). SSL metrics are only recorded when the exception message contains "ssl" or "certificate" (case-insensitive).
- `RequestLoggingMiddleware` and `EvvyAuditLogMiddleware` have no conditional skip logic — they process every request unconditionally.

## Notes

- All five custom middleware classes live under `backend/app/middleware/` and are re-exported from `backend/app/middleware/__init__.py`.
- `EvvyAuditLogMiddleware` is the only custom class that uses the new-style `__call__` pattern (as it inherits from the third-party `AuditlogMiddleware`). The other four use the `MiddlewareMixin` + `process_*` hook pattern.
- The `ImpersonateMiddleware` depends on `AuthenticationMiddleware` having run first (position 7) to resolve `request.user` in `process_response`; it is placed at position 15, satisfying that dependency.
- `AUDITLOG_EXCLUDE_TRACKING_MODELS = ("sessions", "otp_static")` in settings limits what `EvvyAuditLogMiddleware` audits.
