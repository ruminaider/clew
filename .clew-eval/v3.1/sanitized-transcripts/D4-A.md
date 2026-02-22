# Exploration Transcript: Tool A — D4

**Task:** Find all API endpoints that require authentication and identify which authentication method each uses (token auth, session auth, OAuth, API key, permission classes, etc.). Include decorator-based auth (`@login_required`, `@permission_classes`), middleware-based auth, and any custom auth backends. Also identify any endpoints that are explicitly exempted from authentication.

---

## Step 1: Initial Parallel Searches

I'll systematically investigate the authentication patterns in this codebase. Let me start with multiple search angles simultaneously.

**search("authentication middleware permission classes")**

Results (selected):
```json
[
    {
      "file_path": "backend/api/v1/views/provider_test_orders.py",
      "name": "IsVerified",
      "preview": "class IsVerified(permissions.BasePermission)"
    },
    {
      "file_path": "backend/partner_api/permissions.py",
      "name": "PartnerAPIKeyRequired",
      "preview": "class PartnerAPIKeyRequired(BasePermission)\nPermission that allows access if PartnerAPIKeyAuthentication succeeded.\n\n    Since partner authentication is service-to-service (not user-based),\n    we just check that authentication occurred (auth object is not None)."
    },
    {
      "file_path": "backend/api/v1/views/account.py",
      "name": "has_permission",
      "preview": "def has_permission(self, request, view)"
    },
    {
      "file_path": "backend/api/v1/permissions.py",
      "name": "CanAccessTest",
      "preview": "class CanAccessTest(permissions.BasePermission)\nPermission class to check if a user can access a test's data.\n\n    Authorization rules:\n    - Staff users can access any test"
    },
    {
      "file_path": "backend/app/settings.py",
      "preview": "\"\"\"Django settings for backend project..."
    },
    {
      "file_path": "backend/api/v1/views/account.py",
      "name": "IsProvider",
      "preview": "class IsProvider(permissions.BasePermission)"
    },
    {
      "file_path": "backend/partner_api/permissions.py",
      "name": "has_permission",
      "preview": "def has_permission(self, request, view)\nReturn True if authentication succeeded.\n\n        PartnerAPIKeyAuthentication returns (None, partner_or_api_key) on success,\n        so we check if request.auth is not None."
    },
    {
      "file_path": "backend/app/settings.py",
      "preview": "# App Core Configuration Architecture\n\nThe `app` Django app serves as the foundational configuration layer for the entire Evvy platform, managing Django settings, middleware stack, authentication backends, and core utilities..."
    }
]
```

**search("login required decorator API endpoint auth")**

Results (selected):
```json
[
    {
      "file_path": "backend/api/internal/views.py",
      "name": "evvy_logout_api_view",
      "preview": "def evvy_logout_api_view(*args, **kwargs)"
    },
    {
      "file_path": "backend/api/v1/views/views.py",
      "name": "decorator",
      "preview": "def decorator(view_func)"
    },
    {
      "file_path": "backend/api/v1/views/views.py",
      "name": "evvy_api_view",
      "preview": "def evvy_api_view(*args, **kwargs)"
    },
    {
      "file_path": "backend/partner_api/utils.py",
      "name": "wrapper",
      "preview": "def wrapper(self, request, *args, **kwargs)"
    },
    {
      "file_path": "backend/api/v1/views/auth.py",
      "preview": "# File: backend/api/v1/views/auth.py\n# Imports: from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView\n# Entities: class EvvyTokenObtainPairView(TokenObtainPairView), class EvvyTokenBlacklistView(APIView)"
    },
    {
      "file_path": "backend/api/v1/authentication.py",
      "name": "authenticate",
      "preview": "def authenticate(self, request)"
    }
]
```

**search("token authentication API key session auth backend")**

Results (selected):
```json
[
    {
      "file_path": "backend/partner_api/authentication.py",
      "name": "PartnerAPIKeyAuthentication",
      "preview": "class PartnerAPIKeyAuthentication(authentication.BaseAuthentication)\nBearer token authentication for partner integrations.\n\n    Clients should authenticate by passing the API key as a Bearer token\n    in the Authorization header: \"Authorization: Bearer <api_key>\""
    },
    {
      "file_path": "backend/partner_api/authentication.py",
      "name": "authenticate",
      "preview": "def authenticate(self, request)"
    },
    {
      "file_path": "backend/partner_api/authentication.py",
      "name": "authenticate",
      "preview": "def authenticate(self, request)"
    },
    {
      "file_path": "backend/partner_api/authentication.py",
      "name": "PartnerOnlyAPIKeyAuthentication",
      "preview": "class PartnerOnlyAPIKeyAuthentication(authentication.BaseAuthentication)\nBearer token authentication for partner integrations (distro module only).\n\n    Does NOT support legacy PARTNER_API_KEY setting."
    }
]
```

Good initial results. Now let me dig into the key auth files.

---

## Step 2: Reading Core Auth Files

**read("backend/partner_api/authentication.py")**

```python
"""
Authentication for Partner API endpoints.
"""

from django.conf import settings
from rest_framework import authentication, exceptions

from partner_api.partner_config import get_partner_by_api_key


class PartnerAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Bearer token authentication for partner integrations.

    Clients should authenticate by passing the API key as a Bearer token
    in the Authorization header: "Authorization: Bearer <api_key>"

    Supports both:
    1. Partner-specific API keys via in-memory partner configuration
    2. Single API key via PARTNER_API_KEY setting (for backward compatibility with cx_automation)
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Bearer "):
            raise exceptions.AuthenticationFailed("Missing or invalid authorization header")

        api_key = auth_header[7:]

        if not api_key:
            raise exceptions.AuthenticationFailed("Missing authentication token")

        # First, try to find a Partner with this API key
        partner = get_partner_by_api_key(api_key)
        if partner:
            return (None, partner)

        # Fall back to legacy single API key for backward compatibility (cx_automation only)
        configured_key = getattr(settings, "PARTNER_API_KEY", None)
        if configured_key and api_key == configured_key:
            return (None, api_key)

        raise exceptions.AuthenticationFailed("Invalid API key")


class PartnerOnlyAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Bearer token authentication for partner integrations (distro module only).

    Only supports partner-specific API keys via in-memory partner configuration.
    Does NOT support legacy PARTNER_API_KEY setting.
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Bearer "):
            raise exceptions.AuthenticationFailed("Missing or invalid authorization header")

        api_key = auth_header[7:]

        if not api_key:
            raise exceptions.AuthenticationFailed("Missing authentication token")

        partner = get_partner_by_api_key(api_key)
        if partner:
            return (None, partner)

        raise exceptions.AuthenticationFailed("Invalid API key")
```

**read("backend/api/v1/authentication.py")**

```python
from django.core.cache import cache

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class EvvyJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        from api.v1.views.auth import ACCESS_TOKEN_PREFIX

        header = self.get_header(request)
        if header is None:
            return super().authenticate(request)

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return super().authenticate(request)

        validated_token = self.get_validated_token(raw_token)
        # Check for blacklisted Access tokens
        if cache.get(f"{ACCESS_TOKEN_PREFIX}{validated_token}"):
            raise InvalidToken("Invalid token")

        return super().authenticate(request)
```

**read("backend/partner_api/permissions.py")**

```python
"""
Permissions for Partner API endpoints.
"""

from rest_framework.permissions import BasePermission

from partner_api.partner_config import PartnerConfig


def get_client_ip(request) -> str:
    """
    Get the client IP address from the request.
    Uses Cloudflare's True-Client-IP header if available (as per Render support),
    otherwise falls back to REMOTE_ADDR.
    """
    ip = request.headers.get("True-Client-IP")
    if ip:
        return ip.strip()
    return request.META.get("REMOTE_ADDR", "").strip()


class PartnerAPIKeyRequired(BasePermission):
    """
    Permission that allows access if PartnerAPIKeyAuthentication succeeded.
    For PartnerConfig objects, also ensures the partner is active.
    """

    def has_permission(self, request, view):
        if request.auth is None:
            return False
        if isinstance(request.auth, PartnerConfig):
            return request.auth.is_active
        return True


class PartnerIPAllowlistRequired(BasePermission):
    """
    Permission that checks if the client IP address is in the partner's allowed IP list.
    Only applies to PartnerConfig objects.
    """

    def has_permission(self, request, view):
        if not isinstance(request.auth, PartnerConfig):
            return True
        partner: PartnerConfig = request.auth
        if not partner.allowed_ips:
            return True
        client_ip = get_client_ip(request)
        if not client_ip:
            return False
        return client_ip in partner.allowed_ips
```

---

## Step 3: Reading Settings and Base View Classes

**read("backend/app/settings.py")** (key sections)

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
    "app.middleware.ExceptionContextMiddleware",
    "app.middleware.RequestLoggingMiddleware",
    "app.middleware.ImpersonateMiddleware",
    "app.middleware.EvvyAuditLogMiddleware",
    "app.middleware.CheckoutMonitoringMiddleware",
]

AUTHENTICATION_BACKENDS = ("app.auth.EmailBackend",)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.v1.authentication.EvvyJWTAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "app.throttling.UserMinuteRateThrottle",
        "app.throttling.AnonMinuteRateThrottle",
        # ... (multiple throttle classes)
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user-minute": "120/min",
        "anon-minute": "60/min",
        "login-anon-minute": "10/min",
        "login-anon-hour": "50/hour",
        "token-refresh-anon-minute": "30/min",
        # ...
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=90),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# Only enforce 2FA in production
if get_environment() == "production":
    adminClass = OTPAdminSite
    adminClass.login_template = "login.html"
    admin.site.__class__ = adminClass
```

**read("backend/api/v1/views/views.py")**

```python
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ProviderProfile
from api.v1.authentication import EvvyJWTAuthentication


class EvvyUserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [EvvyJWTAuthentication]


class EvvyUserAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [EvvyJWTAuthentication]


def evvy_api_view(*args, **kwargs):
    def decorator(view_func):

        # Apply the permission_classes decorator
        view_func = permission_classes([permissions.IsAuthenticated])(view_func)

        # Apply the authentication_classes decorator
        view_func = authentication_classes([EvvyJWTAuthentication])(view_func)

        # Apply the api_view decorator last
        view_func = api_view(*args, **kwargs)(view_func)
        return view_func

    return decorator


class PublicProviderMagicLinkCheckout(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug: str):
        # ... (exchanges magic link slug for checkout URL)
```

---

## Step 4: Internal Views and URL Structure

**read("backend/api/internal/views.py")** (selected classes)

```python
from rest_framework.authentication import SessionAuthentication

class EvvyInternalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]


class EvvyInternalReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]


class EvvyInternalAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]


class ResultsManagerRequired(BasePermission):
    message = "Must be an Evvy Results Manager to access this resource."

    def has_permission(self, request, view):
        return request.user.groups.filter(name=GROUP_NAME_RESULTS_MANAGERS).exists()


class CoachUserAssignmentRequired(BasePermission):
    def has_permission(self, request, view):
        coach = request.user
        user_id = view.kwargs.get("pk")
        if not user_id:
            return True
        return has_coach_user_assignment(coach, user_id)


class ResultManagerViewSet(EvvyInternalViewSet):
    permission_classes = [ResultsManagerRequired, IsAuthenticated]


class UserSummaryViewSet(EvvyInternalReadOnlyViewSet):
    permission_classes = [IsAuthenticated, CoachUserAssignmentRequired]


class AIMessageViewSet(EvvyInternalViewSet):
    permission_classes = [IsAuthenticated, CoachUserAssignmentForAIRequired]
    # Additional in-method group check: GROUP_NAME_USER_SUMMARY_ASSISTANT_USERS

@evvy_logout_api_view()
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_200_OK, data={"message": "Successfully logged out."})
```

**find_files("backend/**/urls.py")**

Found:
- `backend/api/internal/urls.py`
- `backend/api/urls.py`
- `backend/api/v1/urls.py`
- `backend/partner_api/cx_automation/urls.py`
- `backend/partner_api/distro/urls.py`
- `backend/partner_api/urls.py`
- `backend/app/urls.py`

**read("backend/app/urls.py")**

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path(r"health/", views.health, name="health"),
    path(r"unhealthy/", views.unhealthy, name="unhealthy"),
    path(r"api/", include("api.urls"), name="api"),
]
```

**read("backend/api/urls.py")**

```python
urlpatterns = [
    path(r"v1/", include(("api.v1.urls", "v1"), namespace="v1")),
    path(r"internal/", include(("api.internal.urls", "admin"), namespace="internal")),
    path(r"partner/", include(("partner_api.urls", "partner_api"), namespace="partner")),
    # jwt auth endpoints
    path("token/", EvvyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", EvvyTokenRefreshView.as_view(), name="token_refresh"),
    path("token/logout/", EvvyTokenBlacklistView.as_view(), name="token_blacklist"),
]
```

**read("backend/api/v1/urls.py")** (selected)

```python
router = routers.SimpleRouter()
router.register(r"user-tests", views.UserTestViewSet, basename="user-tests")
router.register(r"health-context", views.HealthContextViewSet, basename="health-context")
router.register(r"cart", views.CartViewSet, basename="cart")
router.register(r"consults", views.ConsultViewSet, basename="consults")
router.register(r"provider-test-orders", views.ProviderTestOrderViewSet, ...)
# ... more viewsets

urlpatterns += [
    path(r"account/", views.UserAccountView.as_view(), name="account"),
    path(r"register/", views.RegisterView.as_view(), name="register"),
    path(r"public-features/", views.PublicFeaturesView.as_view(), name="public-features"),
    re_path(r"^provider-test/(?P<slug>[^/]+)/$", PublicProviderMagicLinkCheckout.as_view(), ...),
    path(r"webhook/", views.webhook_view, name="webhook"),
    path(r"webhooks/shopify", views.shopify_webhook_view, ...),
    path(r"webhooks/wheel", views.wheel_webhook_view, ...),
    path(r"webhooks/berlin", views.berlin_webhook_view, ...),
    path(r"webhooks/microgen", views.microgen_webhook_view, ...),
    path(r"webhooks/junction", views.junction_webhook_view, ...),
    # ... more webhooks
    path(r"password_reset/", EvvyResetPasswordRequestToken.as_view(), ...),
]
```

---

## Step 5: Partner API Views

**read("backend/partner_api/cx_automation/views.py")** (selected)

```python
from partner_api.authentication import PartnerAPIKeyAuthentication
from partner_api.permissions import PartnerAPIKeyRequired

class TestLookupView(APIView):
    authentication_classes = [PartnerAPIKeyAuthentication]
    permission_classes = [PartnerAPIKeyRequired]
    # ...

class TestStatusView(APIView):
    authentication_classes = [PartnerAPIKeyAuthentication]
    permission_classes = [PartnerAPIKeyRequired]
    # ...

# All CX Automation views follow the same pattern:
# TestShippingView, TestCoachingView, TestHealthHistoryView,
# ConsultLookupView, ConsultStatusView, ConsultIntakeView, PrescriptionStatusView
```

**read("backend/partner_api/distro/views.py")** (selected)

```python
from partner_api.authentication import PartnerOnlyAPIKeyAuthentication
from partner_api.permissions import PartnerAPIKeyRequired, PartnerIPAllowlistRequired

class PartnerReportsView(BasePartnerDistroView):
    authentication_classes = [PartnerOnlyAPIKeyAuthentication]
    permission_classes = [PartnerAPIKeyRequired, PartnerIPAllowlistRequired]
    # ...

class PartnerTestStatusesView(BasePartnerDistroView):
    authentication_classes = [PartnerOnlyAPIKeyAuthentication]
    permission_classes = [PartnerAPIKeyRequired, PartnerIPAllowlistRequired]
    # ...
```

---

## Step 6: Auth Endpoints and Webhooks

**read("backend/api/v1/views/auth.py")**

```python
class EvvyTokenObtainPairView(TokenObtainPairView):
    """
    Custom login view with appropriate throttling for login attempts.
    """
    throttle_classes = [LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle]


class EvvyTokenBlacklistView(APIView):
    """
    Custom logout view with appropriate throttling for logout attempts.
    """
    throttle_classes = [TokenLogoutAnonMinuteRateThrottle, TokenLogoutAnonHourRateThrottle]

    def post(self, request, format=None):
        # Invalidate the JWT token by blacklisting it in Redis cache
        # ...


class EvvyTokenRefreshView(TokenRefreshView):
    throttle_classes = [TokenRefreshAnonMinuteRateThrottle, TokenRefreshAnonHourRateThrottle]

    def post(self, request, format=None):
        refresh = request.data.get("refresh")
        # Check for blacklisted refresh tokens
        if cache.get(f"{REFRESH_TOKEN_PREFIX}{refresh}"):
            raise InvalidToken("Invalid token")
        return super().post(request, format=format)
```

**read("backend/api/v1/views/webhooks.py")** (selected)

```python
@csrf_exempt
def webhook_view(request):
    """processes webhooks — S3 bucket upload; TODO: check that it's coming from s3 lambda event"""
    # No HMAC verification

@csrf_exempt
def shopify_webhook_view(request):
    # HMAC-SHA256 verification: X-Shopify-Hmac-SHA256 vs SHOPIFY_WEBHOOK_SECRET

@csrf_exempt
def shopify_webhook_graphql_view(request):
    # HMAC-SHA256 verification: X-Shopify-Hmac-SHA256 vs SHOPIFY_WEBHOOK_GRAPHQL_SECRET

@csrf_exempt
def shopify_fulfillment_webhook_view(request):
    # HMAC-SHA256 verification via _parse_shopify_webhook_payload()

@csrf_exempt
def wheel_webhook_view(request):
    # Static token: X-Wheel-Access-Token == settings.WHEEL_ACCESS_TOKEN

@csrf_exempt
def berlin_webhook_view(request):
    # Static token: X-Berlin-Access-Token == settings.BERLIN_ACCESS_TOKEN

@csrf_exempt
def microgen_webhook_view(request):
    # HMAC-SHA256: X-Microgen-Hmac-SHA256 vs MICROGEN_SECRET_KEY

@csrf_exempt
def microgen_batch_webhook_view(request):
    # HMAC-SHA256: X-Microgen-Hmac-SHA256 vs MICROGEN_SECRET_KEY

@csrf_exempt
def precision_pharmacy_webhook_view(request):
    # HMAC-SHA256: x-hmac-hash vs PRECISION_SECRET_KEY

@csrf_exempt
def survicate_survey_complete_webhook_view(request):
    # HMAC-SHA256: Hmac header (hex→base64) vs SURVICATE_SECRET_KEY

@csrf_exempt
def calendly_webhook_view(request):
    # HMAC-SHA256: Calendly-Webhook-Signature vs CALENDLY_SECRET_KEY

@csrf_exempt
def recharge_webhook_view(request):
    # HMAC-SHA256-hex: X-Recharge-Hmac-Sha256 vs RECHARGE_WEBHOOK_SECRET

@csrf_exempt
def viome_webhook_view(request):
    # Static token: X-Viome-Access-Token == VIOME_WEBHOOK_SECRET (note: Shopify Flow limitation)

@csrf_exempt
def junction_webhook_view(request):
    # Svix signature: svix-id, svix-timestamp, svix-signature vs JUNCTION_WEBHOOK_SECRET

@csrf_exempt
def typeform_webhook_view(request):
    # HMAC-SHA256 OPTIONAL: Typeform-Signature header if present vs TYPEFORM_WEBHOOK_SECRET
    # NOTE: verification is skipped if header is absent — not enforced
```

---

## Step 7: Pattern Scan Across All v1 Views

**search("permission_classes|authentication_classes|AllowAny|IsAuthenticated|csrf_exempt")**

Key findings across `backend/api/v1/views/`:
```
views.py:12:    permission_classes = [permissions.IsAuthenticated]
views.py:13:    authentication_classes = [EvvyJWTAuthentication]
views.py:17:    permission_classes = [permissions.IsAuthenticated]
views.py:18:    authentication_classes = [EvvyJWTAuthentication]
views.py:38:    permission_classes = [permissions.AllowAny]
views.py:39:    authentication_classes = []
webhooks.py:56:@csrf_exempt
webhooks.py:80:@csrf_exempt
(... 12 more @csrf_exempt occurrences in webhooks.py ...)
account.py:150:    permission_classes = EvvyUserAPIView.permission_classes + [IsProvider]
provider_test_orders.py:55:    permission_classes = EvvyUserViewSet.permission_classes + [IsProvider, IsVerified]
user_test_results.py:40:    permission_classes = EvvyUserAPIView.permission_classes + [CanAccessTest]
public_features.py:14:    authentication_classes = []  # No authentication required
public_features.py:15:    permission_classes = []  # No permissions required
email_verification.py:55:    # permission_classes = (permissions.IsAuthenticated,) # can be logged out
```

**read("backend/api/v1/views/public_features.py")**

```python
class PublicFeaturesView(APIView):
    """
    Public API endpoint that returns system-level feature flags
    for unauthenticated users (e.g., registration flows)
    """
    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required
```

**read("backend/api/v1/views/register.py")** — `RegisterView` and `RegisterProviderView` are plain `APIView` subclasses with no auth set (throttled only via `LoginAnonMinuteRateThrottle`, `LoginAnonHourRateThrottle`).

**read("backend/api/v1/views/account.py")** (lines 130–180):

```python
class IsProvider(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name=GROUP_NAME_PROVIDERS).exists()


class ProviderProfileView(EvvyUserAPIView):
    permission_classes = EvvyUserAPIView.permission_classes + [IsProvider]
```

---

## Step 8: Verify Inheritance Patterns for Remaining ViewSets

**search("class.*ViewSet|class.*APIView|permission_classes|authentication_classes")**

Key findings:
- `TreatmentPlanInterruptionViewSet(EvvyUserViewSet)` — inherits JWT + IsAuthenticated
- `HealthContextViewSet(EvvyUserViewSet)` — same

All remaining ViewSets confirmed to extend `EvvyUserViewSet` or `EvvyUserAPIView`.

---

## Final Answer: Comprehensive Authentication Mapping

### Authentication Infrastructure Overview

**Global Default Auth (DRF Settings — `settings.py`):**
- `DEFAULT_AUTHENTICATION_CLASSES`: `["api.v1.authentication.EvvyJWTAuthentication"]`
- No `DEFAULT_PERMISSION_CLASSES` set; every authenticated view base class hardcodes `IsAuthenticated`.

**Authentication Backends (Django):**
- `AUTHENTICATION_BACKENDS = ("app.auth.EmailBackend",)` — custom backend allowing email-as-username login.

---

### Auth Method Definitions

**1. JWT Authentication (`EvvyJWTAuthentication`)**
- Extends `rest_framework_simplejwt.authentication.JWTAuthentication`
- Adds Redis-based access token blacklist check (`blacklist_access_{token}` cache key)
- Bearer token in `Authorization` header: `Authorization: Bearer <jwt>`
- Token lifetime: Access = 90 minutes, Refresh = 1 day

**2. Session Authentication (`SessionAuthentication`)**
- Used only for the internal admin portal (`api/internal/`)
- Django session cookie-based (24 hour session age)

**3. Partner API Key Authentication (`PartnerAPIKeyAuthentication`)**
- Bearer token in `Authorization` header: `Authorization: Bearer <api_key>`
- Looks up key against in-memory `PartnerConfig` list first, then falls back to `settings.PARTNER_API_KEY` (legacy)

**4. Partner-Only API Key Authentication (`PartnerOnlyAPIKeyAuthentication`)**
- Same as above but no legacy fallback — only partner config keys accepted

**5. Custom Email Backend (`app.auth.EmailBackend`)**
- Used for Django admin and initial JWT token issuance
- Allows login with email address instead of username

**6. OTP/2FA (`django_otp.middleware.OTPMiddleware`)**
- Applied via middleware stack globally
- In production: Django admin uses `OTPAdminSite` requiring TOTP verification

---

### Endpoint Authentication Mapping

#### API v1 — JWT Auth Required (`EvvyJWTAuthentication` + `IsAuthenticated`)

All extend `EvvyUserViewSet`, `EvvyUserAPIView`, or use `evvy_api_view`, which hardcode:
```python
authentication_classes = [EvvyJWTAuthentication]
permission_classes = [permissions.IsAuthenticated]
```

| Endpoint | URL | Extra Permission |
|---|---|---|
| User account info | `POST /api/v1/account/` | None |
| Provider profile | `GET/POST /api/v1/provider/profile` | `IsProvider` |
| Compare tests | `/api/v1/compare/` | None |
| Trends | `/api/v1/trends/` | None |
| Email verification send | `/api/v1/email-verification/` | None |
| Order transfer initiation | `/api/v1/order-transfer-verification/` | None |
| Consent | `/api/v1/consent/` | None |
| My plan (old) | `/api/v1/my-plan-old/` | None |
| My plan | `/api/v1/my-plan/` | None |
| My plan feedback | `/api/v1/my-plan/feedback/` | None |
| Orders (GET/PUT) | `GET PUT /api/v1/orders/` | None |
| User config | `/api/v1/user-config/` | None |
| Male partner checkout | `/api/v1/male-partner-checkout/` | None |
| Announcements | `/api/v1/announcements/` | None |
| FAQs | `/api/v1/faqs/` | None |
| Survey | `/api/v1/survey/` | None |
| User test results PDF data | `GET /api/v1/user-tests/<hash>/pdf-data/` | `CanAccessTest` |

**ViewSets using `EvvyUserViewSet`:**

| Resource | URL prefix | Extra Permission |
|---|---|---|
| User tests | `/api/v1/user-tests/` | None |
| Health context | `/api/v1/health-context/` | None |
| Cart | `/api/v1/cart/` | None |
| Consults | `/api/v1/consults/` | None |
| Consult intake | `/api/v1/consult-intake/` | None |
| Lab order intake | `/api/v1/lab-order-intake/` | None |
| Treatment interruption | `/api/v1/treatment-interruption/` | None |
| Products | `/api/v1/products/` | None |
| Calendar treatments | `/api/v1/calendar-treatments/` | None |
| Provider test orders | `/api/v1/provider-test-orders/` | `IsProvider` + `IsVerified` |

**`evvy_api_view` decorated subscription endpoints:**

All subscription functions at `/api/v1/subscription/` and `/api/v1/subscriptions/` use JWT + `IsAuthenticated`.

---

#### Internal API — Session Auth Required

All views extend `EvvyInternalViewSet`, `EvvyInternalReadOnlyViewSet`, or `EvvyInternalAPIView`:
```python
authentication_classes = [SessionAuthentication]
permission_classes = [IsAuthenticated]
```

| Endpoint | Extra Permission |
|---|---|
| `GET/POST /api/internal/results/` | `ResultsManagerRequired` + `IsAuthenticated` |
| `GET /api/internal/users/` | `IsAuthenticated` + `CoachUserAssignmentRequired` |
| `GET /api/internal/users/<pk>/timeline/` | same |
| `GET/POST/PATCH /api/internal/ai_sally/<user_id>/` | `IsAuthenticated` + `CoachUserAssignmentForAIRequired` + group check |
| `GET /api/internal/plan_profiles/` | `ResultsManagerRequired` + `IsAuthenticated` |
| `GET /api/internal/plan_items/` | `IsAuthenticated` + `ResultsManagerRequired` |
| `POST /api/internal/auth/logout/` | `SessionAuthentication` only (no `IsAuthenticated` permission check) |
| `GET /api/internal/me/` | `IsAuthenticated` |

**JWT Auth Endpoints (anonymous — login/token management):**

| Endpoint | Notes |
|---|---|
| `POST /api/token/` | Login endpoint; throttled (10/min, 50/hr anon) |
| `POST /api/token/refresh/` | Throttled; checks refresh token blacklist |
| `POST /api/token/logout/` | Throttled; no auth required |

---

#### Partner CX Automation API — Partner API Key Auth

All views:
```python
authentication_classes = [PartnerAPIKeyAuthentication]
permission_classes = [PartnerAPIKeyRequired]
```
Supports partner config keys AND legacy `PARTNER_API_KEY` setting.

| Endpoint | URL |
|---|---|
| Test lookup | `GET /api/partner/cx-automation/test/` |
| Test status | `GET /api/partner/cx-automation/test/<hash>/status/` |
| Test shipping | `GET /api/partner/cx-automation/test/<hash>/shipping-status/` |
| Test coaching info | `GET /api/partner/cx-automation/test/<hash>/coaching-info/` |
| Test health history | `GET /api/partner/cx-automation/test/<hash>/health-history/` |
| Consult lookup | `GET /api/partner/cx-automation/test/<hash>/consult-lookup/` |
| Consult intake | `GET /api/partner/cx-automation/consult/<id>/intake/` |
| Prescription status | `GET /api/partner/cx-automation/consult/<id>/prescription/` |

#### Partner Distro API — Stricter Partner API Key + IP Allowlist

```python
authentication_classes = [PartnerOnlyAPIKeyAuthentication]
permission_classes = [PartnerAPIKeyRequired, PartnerIPAllowlistRequired]
```

| Endpoint | URL |
|---|---|
| Test report PDF | `GET /api/partner/v1/distro/reports/<hash>/` |
| Test statuses | `GET /api/partner/v1/distro/tests/statuses/` |

---

### Endpoints Explicitly Exempted from Authentication

All use `@csrf_exempt`, no DRF auth — plain Django function views authenticated via payload signature:

| Endpoint | URL | Auth Method |
|---|---|---|
| S3 webhook | `POST /api/v1/webhook/` | None — `@csrf_exempt`, no HMAC (TODO comment) |
| Shopify orders webhook | `POST /api/v1/webhooks/shopify` | `@csrf_exempt` + HMAC-SHA256 (`X-Shopify-Hmac-SHA256`) |
| Shopify graphql webhook | `POST /api/v1/webhooks/shopify-graphql` | `@csrf_exempt` + HMAC-SHA256 (graphql secret) |
| Shopify fulfillment webhook | `POST /api/v1/webhooks/shopify-fulfillment` | `@csrf_exempt` + HMAC-SHA256 |
| Wheel webhook | `POST /api/v1/webhooks/wheel` | `@csrf_exempt` + static token (`X-Wheel-Access-Token`) |
| Berlin tracking webhook | `POST /api/v1/webhooks/berlin` | `@csrf_exempt` + static token (`X-Berlin-Access-Token`) |
| Microgen lab status webhook | `POST /api/v1/webhooks/microgen` | `@csrf_exempt` + HMAC-SHA256 (`X-Microgen-Hmac-SHA256`) |
| Microgen batch webhook | `POST /api/v1/webhooks/microgen-batch` | `@csrf_exempt` + HMAC-SHA256 |
| Precision pharmacy webhook | `POST /api/v1/webhooks/precision` | `@csrf_exempt` + HMAC-SHA256 (`x-hmac-hash`) |
| Survicate webhook | `POST /api/v1/webhooks/survicate-survey-complete` | `@csrf_exempt` + HMAC-SHA256 (hex→base64) |
| Calendly webhook | `POST /api/v1/webhooks/calendly` | `@csrf_exempt` + HMAC-SHA256 (`Calendly-Webhook-Signature`) |
| ReCharge webhook | `POST /api/v1/webhooks/recharge` | `@csrf_exempt` + HMAC-SHA256-hex (`X-Recharge-Hmac-Sha256`) |
| Viome webhook | `POST /api/v1/webhooks/viome` | `@csrf_exempt` + static token (`X-Viome-Access-Token`) |
| Junction webhook | `POST /api/v1/webhooks/junction` | `@csrf_exempt` + Svix signature |
| Typeform webhook | `POST /api/v1/webhooks/typeform` | `@csrf_exempt` + HMAC-SHA256 **optional** — verification skipped if header absent |

---

### Endpoints Explicitly Public (No Auth Required)

| Endpoint | URL | Notes |
|---|---|---|
| Register user | `POST /api/v1/register/` | Plain `APIView`, throttled only |
| Register provider | `POST /api/v1/provider/register` | Plain `APIView`, throttled only |
| Public features flags | `GET /api/v1/public-features/` | `authentication_classes = []`, `permission_classes = []` |
| Provider magic link checkout | `GET /api/v1/provider-test/<slug>/` | `permission_classes = [AllowAny]`, `authentication_classes = []` |
| Email verification confirm | `POST /api/v1/email-verification-confirm/` | No auth (commented-out `IsAuthenticated`) |
| Order transfer confirm | `POST /api/v1/order-transfer-verification-confirm/` | Documented "user can be unauthenticated" |
| Orders POST (process order) | `POST /api/v1/orders/` | Overrides `get_permissions()` to return `[]` for POST only |
| Ecomm product by SKU | `GET /api/v1/ecomm-products/<sku>/` | Documented "Public endpoint - no authentication required" |
| PDP configurations | `/api/v1/pdp-configurations/` | No auth set |
| Password reset request | `POST /api/v1/password_reset/` | No auth, throttled |
| Password reset validate token | `POST /api/v1/password_reset/validate_token/` | No auth |
| Password reset confirm | `POST /api/v1/password_reset/confirm/` | No auth |
| Health check | `GET /health/` | Plain Django view |

---

### Middleware-Based Auth

| Middleware | Purpose |
|---|---|
| `SessionMiddleware` | Enables session-based auth for admin and internal portal |
| `AuthenticationMiddleware` | Sets `request.user` from session for Django admin |
| `OTPMiddleware` | Enforces OTP device check on admin in production |
| `ImpersonateMiddleware` | Allows staff users in `user-impersonation` group to inject a JWT access token for another user via `?__impersonate=<username>` query param |
| `CsrfViewMiddleware` | CSRF protection for session-authenticated views |

---

### Custom Permission Classes Summary

| Permission Class | Logic |
|---|---|
| `IsProvider` | User must be in `GROUP_NAME_PROVIDERS` group |
| `IsVerified` | Provider profile must have `verified=True` |
| `CanAccessTest` | Staff: any test; Provider: only linked via `provider_test_orders`; Patient: only own tests |
| `ResultsManagerRequired` | User must be in `GROUP_NAME_RESULTS_MANAGERS` group |
| `CoachUserAssignmentRequired` | Coach must have active `CoachUserAssignment` for the user, or be a results manager |
| `CoachUserAssignmentForAIRequired` | Same, applied to AI endpoints |
| `PartnerAPIKeyRequired` | `request.auth` must not be None; for `PartnerConfig` objects, must be `is_active=True` |
| `PartnerIPAllowlistRequired` | Client IP (Cloudflare `True-Client-IP` or `REMOTE_ADDR`) must be in `partner.allowed_ips` |
