# Exploration Transcript: Tool B — D4

**Task:** Find all API endpoints that require authentication and identify which authentication method each uses (token auth, session auth, OAuth, API key, permission classes, etc.). Include decorator-based auth (`@login_required`, `@permission_classes`), middleware-based auth, and any custom auth backends. Also identify any endpoints that are explicitly exempted from authentication.

---


I'll systematically explore the codebase to find all authentication methods and map them to endpoints.


**Step 1:** `ls .`
*List top-level directory structure*


```
backend
CLAUDE.md
docker
docker-compose-ci.yml
docker-compose.yml
docs
frontend
internal-frontend
makefile
pull_request_template.md
pyproject.toml
README.md
render.yaml
scripts
tools
```


**Step 2:** `ls backend`  
*List backend directory*


```
__pycache__
accounts
admin-interface
ai
analytics
api
app
associations
business_rules
cache.py
care
celery_entrypoint.sh
celerybeat-schedule
coaching
consults
cron_schedule.py
Dockerfile
docs
ecomm
entrypoint.sh
gunicorn_logging.conf
gunicorn.conf
health_history
manage.py
newrelic.ini
observability
partner_api
providers
README.md
requirements.in
requirements.txt
scripts
shipping
static
studies
subscriptions
support
surveys
test_results
transactional_email
utils
venv
wsgi.py
```


**Step 3:** `ls backend/api backend/partner_api backend/app`  
*List key API directories*


```
backend/api:
__init__.py
__pycache__
internal
tests
urls.py
v1

backend/app:
__init__.py
__pycache__
apps.py
auth.py
celery.py
management
middleware
scripts
settings_celery.py
settings.py
signals.py
static
tasks.py
templates
throttling.py
urls.py
utils.py
views.py
wsgi.py

backend/partner_api:
__init__.py
__pycache__
admin.py
apps.py
authentication.py
constants.py
cx_automation
distro
docs.py
exception_handler.py
migrations
models.py
partner_config.py
permissions.py
README.md
tests
urls.py
utils.py
```


**Step 4:** `search("AUTHENTICATION_BACKENDS|REST_FRAMEWORK|DEFAULT_AUTHENTICATION_CLASSES|DEFAULT_PERMISSION_CLASSES", path="backend", context=3)`


```
backend/app/settings.py-356-STATIC_ROOT = os.path.join(BASE_DIR, "static/")
backend/app/settings.py-357-
backend/app/settings.py-358-# authentication
backend/app/settings.py:359:AUTHENTICATION_BACKENDS = ("app.auth.EmailBackend",)
backend/app/settings.py-360-
backend/app/settings.py-361-# Partner API Integration
backend/app/settings.py-362-PARTNER_API_KEY = env("PARTNER_API_KEY", default=None)
--
backend/app/settings.py-370-
backend/app/settings.py-371-
backend/app/settings.py-372-# django rest framework
backend/app/settings.py:373:REST_FRAMEWORK = {
backend/app/settings.py:374:    "DEFAULT_AUTHENTICATION_CLASSES": [
backend/app/settings.py-375-        "api.v1.authentication.EvvyJWTAuthentication",
backend/app/settings.py-376-    ],
backend/app/settings.py-377-    "DEFAULT_THROTTLE_CLASSES": [
```


**Step 5:** `read("backend/app/settings.py", offset=358, limit=60)`


```
358→# authentication
   359→AUTHENTICATION_BACKENDS = ("app.auth.EmailBackend",)
   360→
   361→# Partner API Integration
   362→PARTNER_API_KEY = env("PARTNER_API_KEY", default=None)
   363→
   364→SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)
   365→CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None)
   366→CSRF_COOKIE_NAME = env("CSRF_COOKIE_NAME", default="csrftoken")
   367→
   368→# django admin session cookie age, 24 hours
   369→SESSION_COOKIE_AGE = 60 * 60 * 24
   370→
   371→
   372→# django rest framework
   373→REST_FRAMEWORK = {
   374→    "DEFAULT_AUTHENTICATION_CLASSES": [
   375→        "api.v1.authentication.EvvyJWTAuthentication",
   376→    ],
   377→    "DEFAULT_THROTTLE_CLASSES": [
   378→        "app.throttling.UserMinuteRateThrottle",
   379→        "app.throttling.AnonMinuteRateThrottle",
   380→        "app.throttling.UserHourRateThrottle",
   381→        "app.throttling.AnonHourRateThrottle",
   382→        "app.throttling.UserDayRateThrottle",
   383→        "app.throttling.AnonDayRateThrottle",
   384→    ],
   385→    "DEFAULT_THROTTLE_RATES": {
   386→        "user-minute": "120/min",
   387→        "anon-minute": "60/min",
   388→        "user-hour": "2000/hour",
   389→        "anon-hour": "1000/hour",
   390→        "user-day": "5000/day",
   391→        "anon-day": "2500/day",
   392→        # 10 login attempts per minute
   393→        "login-anon-minute": "10/min",
   394→        # 50 login attempts per hour
   395→        "login-anon-hour": "50/hour",
   396→        # Token refresh limits - more lenient than login since these are legitimate maintenance requests
   397→        "token-refresh-anon-minute": "30/min",
   398→        "token-refresh-anon-hour": "200/hour",
   399→        # Token logout limits - generous since it's a cleanup operation
   400→        "token-logout-anon-minute": "50/min",
   401→        "token-logout-anon-hour": "300/hour",
   402→    },
   403→    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
   404→    "EXCEPTION_HANDLER": "partner_api.exception_handler.partner_api_exception_handler",
   405→}
   406→
   407→# Controls whether throttling should be enforced or just logged and warned
   408→THROTTLE_MODE = env("THROTTLE_MODE", default="warn")
   409→
   410→
   411→# djangorestframework_simplejwt default config
   412→SIMPLE_JWT = {
   413→    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=90),
   414→    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
   415→    # 'ROTATE_REFRESH_TOKENS': False,
   416→    # 'BLACKLIST_AFTER_ROTATION': True,
   417→    # 'UPDATE_LAST_LOGIN': False,
```


**Step 6:** `find_files("**/authentication.py", path="backend")`


```
backend/api/v1/authentication.py
backend/partner_api/authentication.py
```


**Step 7:** `read("backend/api/v1/authentication.py")`


```
1→from django.core.cache import cache
     2→
     3→from rest_framework_simplejwt.authentication import JWTAuthentication
     4→from rest_framework_simplejwt.exceptions import InvalidToken
     5→
     6→
     7→class EvvyJWTAuthentication(JWTAuthentication):
     8→
     9→    def authenticate(self, request):
    10→        from api.v1.views.auth import ACCESS_TOKEN_PREFIX
    11→
    12→        header = self.get_header(request)
    13→        if header is None:
    14→            return super().authenticate(request)
    15→
    16→        raw_token = self.get_raw_token(header)
    17→        if raw_token is None:
    18→            return super().authenticate(request)
    19→
    20→        validated_token = self.get_validated_token(raw_token)
    21→        # Check for blacklisted Access tokens
    22→        if cache.get(f"{ACCESS_TOKEN_PREFIX}{validated_token}"):
    23→            raise InvalidToken("Invalid token")
    24→
    25→        return super().authenticate(request)
    26→
```


**Step 8:** `read("backend/partner_api/authentication.py")`


```
1→"""
     2→Authentication for Partner API endpoints.
     3→"""
     4→
     5→from django.conf import settings
     6→from rest_framework import authentication, exceptions
     7→
     8→from partner_api.partner_config import get_partner_by_api_key
     9→
    10→
    11→class PartnerAPIKeyAuthentication(authentication.BaseAuthentication):
    12→    """
    13→    Bearer token authentication for partner integrations.
    14→
    15→    Clients should authenticate by passing the API key as a Bearer token
    16→    in the Authorization header: "Authorization: Bearer <api_key>"
    17→
    18→    Supports both:
    19→    1. Partner-specific API keys via in-memory partner configuration
    20→    2. Single API key via PARTNER_API_KEY setting (for backward compatibility with cx_automation)
    21→    """
    22→
    23→    def authenticate(self, request):
    24→        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    25→
    26→        if not auth_header.startswith("Bearer "):
    27→            raise exceptions.AuthenticationFailed("Missing or invalid authorization header")
    28→
    29→        api_key = auth_header[7:]
    30→
    31→        if not api_key:
    32→            raise exceptions.AuthenticationFailed("Missing authentication token")
    33→
    34→        # First, try to find a Partner with this API key
    35→        partner = get_partner_by_api_key(api_key)
    36→        if partner:
    37→            return (None, partner)
    38→
    39→        # Fall back to legacy single API key for backward compatibility (cx_automation only)
    40→        configured_key = getattr(settings, "PARTNER_API_KEY", None)
    41→        if configured_key and api_key == configured_key:
    42→            return (None, api_key)
    43→
    44→        raise exceptions.AuthenticationFailed("Invalid API key")
    45→
    46→
    47→class PartnerOnlyAPIKeyAuthentication(authentication.BaseAuthentication):
    48→    """
    49→    Bearer token authentication for partner integrations (distro module only).
    50→
    51→    Clients should authenticate by passing the API key as a Bearer token
    52→    in the Authorization header: "Authorization: Bearer <api_key>"
    53→
    54→    Only supports partner-specific API keys via in-memory partner configuration.
    55→    Does NOT support legacy PARTNER_API_KEY setting.
    56→    """
    57→
    58→    def authenticate(self, request):
    59→        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    60→
    61→        if not auth_header.startswith("Bearer "):
    62→            raise exceptions.AuthenticationFailed("Missing or invalid authorization header")
    63→
    64→        api_key = auth_header[7:]
    65→
    66→        if not api_key:
    67→            raise exceptions.AuthenticationFailed("Missing authentication token")
    68→
    69→        # Only check for partner-specific API keys
    70→        partner = get_partner_by_api_key(api_key)
    71→        if partner:
    72→            return (None, partner)
    73→
    74→        raise exceptions.AuthenticationFailed("Invalid API key")
    75→
```


**Step 9:** `read("backend/app/auth.py")`


```
1→from django.contrib.auth.backends import ModelBackend, UserModel
     2→from django.contrib.auth.models import User
     3→from django.core.exceptions import MultipleObjectsReturned
     4→from django.forms import ValidationError
     5→
     6→
     7→class EmailBackend(ModelBackend):
     8→    """
     9→    Overwrites the auth backend so users can log in with email instead of username
    10→    """
    11→
    12→    def authenticate(self, request, username=None, password=None, **kwargs):
    13→        user = None
    14→        try:
    15→            # try to get user by username as username has indexes
    16→            user = UserModel.objects.get(username__iexact=username)
    17→        except UserModel.DoesNotExist:
    18→            try:
    19→                # if user not found by username, try to get user by email (this is an edge case)
    20→                # we should technically get rid of this
    21→                user = UserModel.objects.get(email__iexact=username)
    22→            except UserModel.DoesNotExist:
    23→                # User doesn't exist - hash password anyway to prevent timing attacks
    24→                # This makes "user doesn't exist" take similar time to "wrong password"
    25→                UserModel().set_password(password)
    26→                return None
    27→        except MultipleObjectsReturned:
    28→            # This shouldn't happen, but maybe username is not unique
    29→            user = User.objects.filter(username__iexact=username).order_by("id").first()
    30→
    31→        if user and user.check_password(password) and self.user_can_authenticate(user):
    32→            return user
    33→
    34→    def get_user(self, user_id):
    35→        try:
    36→            user = UserModel.objects.get(pk=user_id)
    37→        except UserModel.DoesNotExist:
    38→            return None
    39→
    40→        return user if self.user_can_authenticate(user) else None
    41→
    42→
    43→class MaximumLengthValidator:
    44→    def __init__(self, max_length=128):
    45→        self.max_length = max_length
    46→
    47→    def validate(self, password, user=None):
    48→        if len(password) > self.max_length:
    49→            raise ValidationError(
    50→                "This password is too long. It must contain at most %(max_length)d characters.",
    51→                code="password_too_long",
    52→                params={"max_length": self.max_length},
    53→            )
    54→
    55→    def get_help_text(self):
    56→        return "Your password must contain at most %(max_length)d characters." % {
    57→            "max_length": self.max_length
    58→        }
    59→
```


**Step 10:** `read("backend/app/urls.py")`


```
1→"""backend URL Configuration
     2→
     3→The `urlpatterns` list routes URLs to views. For more information please see:
     4→    https://docs.djangoproject.com/en/2.0/topics/http/urls/
     5→Examples:
     6→Function views
     7→    1. Add an import:  from my_app import views
     8→    2. Add a URL to urlpatterns:  path('', views.home, name='home')
     9→Class-based views
    10→    1. Add an import:  from other_app.views import Home
    11→    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
    12→Including another URLconf
    13→    1. Import the include() function: from django.urls import include, path
    14→    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
    15→"""
    16→
    17→from django.contrib import admin
    18→from django.urls import include, path
    19→
    20→from django_otp.admin import OTPAdminSite
    21→
    22→from app import views
    23→from app.utils import get_environment
    24→
    25→# from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    26→
    27→if get_environment() == "staging":
    28→    admin.site.site_header = "Staging Django Admin"
    29→    admin.site.site_title = "Staging Django Site Admin"
    30→
    31→if get_environment() == "preview":
    32→    admin.site.site_header = "Preview Django Admin"
    33→    admin.site.site_title = "Preview Django Site Admin"
    34→
    35→# Only enforce 2FA in production
    36→if get_environment() == "production":
    37→    adminClass = OTPAdminSite
    38→    adminClass.login_template = "login.html"
    39→    admin.site.__class__ = adminClass
    40→
    41→# Add custom login view to allow redirects to internal site
    42→admin.site.login = views.EvvyLoginView.as_view()
    43→
    44→urlpatterns = [
    45→    # django and installed apps
    46→    path("admin/", admin.site.urls),
    47→    # api endpoints
    48→    path(r"health/", views.health, name="health"),
    49→    path(r"unhealthy/", views.unhealthy, name="unhealthy"),  # just for testing
    50→    path(r"api/", include("api.urls"), name="api"),
    51→]
    52→
    53→# add static file patterns (for admin site)
    54→# urlpatterns += staticfiles_urlpatterns()
    55→
```


**Step 11:** `read("backend/api/urls.py")`


```
1→from django.urls import include, path
     2→
     3→from api.v1.views.auth import (
     4→    EvvyTokenBlacklistView,
     5→    EvvyTokenObtainPairView,
     6→    EvvyTokenRefreshView,
     7→)
     8→
     9→app_name = "api"
    10→urlpatterns = [
    11→    # most core functionality in here, apart from token auth and admin
    12→    path(r"v1/", include(("api.v1.urls", "v1"), namespace="v1")),
    13→    # internal endpoints
    14→    path(r"internal/", include(("api.internal.urls", "admin"), namespace="internal")),
    15→    # partner API endpoints
    16→    path(r"partner/", include(("partner_api.urls", "partner_api"), namespace="partner")),
    17→    # jwt auth endpoints
    18→    path("token/", EvvyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    19→    path("token/refresh/", EvvyTokenRefreshView.as_view(), name="token_refresh"),
    20→    path("token/logout/", EvvyTokenBlacklistView.as_view(), name="token_blacklist"),
    21→]
    22→
```


**Step 12:** `ls backend/api/v1/`  
*List v1 API directory*


```
__init__.py
__pycache__
authentication.py
pdf_data
permissions.py
serializers
tests
urls.py
utils
views
```


**Step 13:** `read("backend/api/internal/urls.py")`


```
1→from django.conf import settings
     2→from django.urls import path
     3→from rest_framework import routers
     4→
     5→from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
     6→
     7→from api.internal.views import (
     8→    AIMessageViewSet,
     9→    CurrentUserView,
    10→    PlanItemViewset,
    11→    PlanProfileViewSet,
    12→    ResultsViewSet,
    13→    UserSummaryViewSet,
    14→    logout_view,
    15→)
    16→
    17→router = routers.SimpleRouter()
    18→
    19→router.register(r"results", ResultsViewSet, basename="results")
    20→router.register(r"users", UserSummaryViewSet, basename="users")
    21→router.register(r"ai_sally/(?P<user_id>\d+)", AIMessageViewSet, basename="ai")
    22→router.register(r"plan_profiles", PlanProfileViewSet, basename="plan_profiles")
    23→router.register(r"plan_items", PlanItemViewset, basename="plan_items")
    24→urlpatterns = router.urls
    25→
    26→urlpatterns += [
    27→    path("auth/logout/", logout_view, name="logout"),
    28→    path("me/", CurrentUserView.as_view(), name="current-user"),
    29→]
    30→
    31→# Only enable API views in debug mode
    32→if settings.DEBUG:
    33→    urlpatterns += [
    34→        path(r"schema/", SpectacularAPIView.as_view(), name="schema"),
    35→        path(
    36→            r"swagger/",
    37→            SpectacularSwaggerView.as_view(url_name="api:admin:schema"),
    38→            name="swagger-ui",
    39→        ),
    40→    ]
    41→
```


**Step 14:** `read("backend/api/v1/urls.py")`


```
1→from django.urls import path, re_path
     2→from rest_framework import routers
     3→
     4→from api.v1.views.reset_password import (
     5→    EvvyResetPasswordConfirm,
     6→    EvvyResetPasswordRequestToken,
     7→    EvvyResetPasswordValidateToken,
     8→)
     9→
    10→from . import views
    11→from .views.views import PublicProviderMagicLinkCheckout
    12→
    13→
    14→# our model viewsets
    15→router = routers.SimpleRouter()
    16→router.register(r"user-tests", views.UserTestViewSet, basename="user-tests")
    17→router.register(r"health-context", views.HealthContextViewSet, basename="health-context")
    18→router.register(r"tasks", views.TasksViewSet, basename="tasks")
    19→router.register(r"cart", views.CartViewSet, basename="cart")
    20→router.register(r"consults", views.ConsultViewSet, basename="consults")
    21→router.register(r"consult-intake", views.ConsultIntakeViewSet, basename="consult-intake")
    22→router.register(r"lab-order-intake", views.LabOrderIntakeViewSet, basename="lab-order-intake")
    23→router.register(
    24→    r"treatment-interruption",
    25→    views.TreatmentPlanInterruptionViewSet,
    26→    basename="treatment-interruption",
    27→)
    28→router.register(r"products", views.ProductViewSet, basename="products")
    29→router.register(
    30→    r"provider-test-orders",
    31→    views.ProviderTestOrderViewSet,
    32→    basename="provider-test-orders",
    33→)
    34→router.register(
    35→    r"calendar-treatments",
    36→    views.CalendarTreatmentViewSet,
    37→    basename="calendar-treatments",
    38→)
    39→router.register(
    40→    r"pdp-configurations",
    41→    views.PDPConfigurationViewSet,
    42→    basename="pdp-configurations",
    43→)
    44→urlpatterns = router.urls
    45→
    46→# one-off views
    47→urlpatterns += [
    48→    # our view APIs
    49→    path(r"account/", views.UserAccountView.as_view(), name="account"),
    50→    path(r"compare/", views.CompareView.as_view(), name="compare"),
    51→    path(r"trends/", views.TrendsView.as_view(), name="trends"),
    52→    path(
    53→        r"email-verification/",
    54→        views.EmailVerificationView.as_view(),
    55→        name="email-verification",
    56→    ),
    57→    path(
    58→        r"email-verification-confirm/",
    59→        views.EmailVerificationConfirmView.as_view(),
    60→        name="email-verification-confirm",
    61→    ),
    62→    path(
    63→        r"order-transfer-verification/",
    64→        views.AccountOrderTransferVerification.as_view(),
    65→        name="order-transfer-verification",
    66→    ),
    67→    path(
    68→        r"order-transfer-verification-confirm/",
    69→        views.AccountOrderTransferConfirmVerification.as_view(),
    70→        name="order-transfer-verification-confirm",
    71→    ),
    72→    path(r"consent/", views.ConsentView.as_view(), name="consent"),
    73→    path(r"my-plan-old/", views.MyPlanOldView.as_view(), name="my-plan-old"),
    74→    path(r"my-plan/", views.MyPlanView.as_view(), name="my-plan"),
    75→    path(r"my-plan/feedback/", views.MyPlanFeedback.as_view(), name="my-plan-feedback"),
    76→    path(r"orders/", views.OrdersView.as_view(), name="orders"),
    77→    path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail"),
    78→    path(r"orders/process", views.OrdersView.as_view(), name="orders-process"),
    79→    path(r"register/", views.RegisterView.as_view(), name="register"),
    80→    path(r"user-config/", views.UserConfigView.as_view(), name="user-config"),
    81→    path(
    82→        r"male-partner-checkout/",
    83→        views.MalePartnerCheckoutView.as_view(),
    84→        name="male-partner-checkout",
    85→    ),
    86→    path(
    87→        r"ecomm-products/<str:sku>/",
    88→        views.EcommProductView.as_view(),
    89→        name="ecomm-products",
    90→    ),
    91→    path(
    92→        r"user-tests/<str:hash>/pdf-data/",
    93→        views.UserTestResultsView.as_view(),
    94→        name="user-tests-pdf-data",
    95→    ),
    96→    path(r"public-features/", views.PublicFeaturesView.as_view(), name="public-features"),
    97→    # Public magic link to exchange slug for checkout URL
    98→    re_path(
    99→        r"^provider-test/(?P<slug>[^/]+)/$",
   100→        PublicProviderMagicLinkCheckout.as_view(),
... [94 more lines truncated]
```


**Step 15:** `read("backend/partner_api/urls.py")`


```
1→"""
     2→URL configuration for Partner API endpoints.
     3→"""
     4→
     5→from django.urls import include, path
     6→
     7→
     8→app_name = "partner_api"
     9→
    10→urlpatterns = [
    11→    path(
    12→        "cx-automation/",
    13→        include(("partner_api.cx_automation.urls", "cx_automation"), namespace="cx_automation"),
    14→    ),
    15→    path("", include("partner_api.docs")),
    16→    path("v1/distro/", include(("partner_api.distro.urls", "distro"), namespace="distro")),
    17→]
    18→
```


**Step 16:** `ls backend/api/v1/views/`  
*List views directory*


```
__init__.py
__pycache__
account_order_transfer_verification.py
account.py
announcements.py
auth.py
calendar_treatment.py
cart.py
compare.py
consent.py
consult.py
ecomm_products.py
email_verification.py
faqs.py
health_context.py
lab_orders.py
my_plan.py
orders.py
pdp_configuration.py
products.py
provider_test_orders.py
public_features.py
register.py
reset_password.py
subscription.py
surveys.py
tasks.py
treatment_interruption.py
trends.py
user_test_results.py
user_tests.py
userconfig.py
views.py
webhooks.py
```


**Step 17:** `read("backend/partner_api/cx_automation/urls.py")`


```
1→"""
     2→URL configuration for CX Automation API endpoints.
     3→"""
     4→
     5→from django.urls import path, register_converter
     6→
     7→from partner_api.utils import TestHashConverter
     8→
     9→from .views import (
    10→    ConsultIntakeView,
    11→    ConsultLookupView,
    12→    PrescriptionStatusView,
    13→    TestCoachingView,
    14→    TestHealthHistoryView,
    15→    TestLookupView,
    16→    TestShippingView,
    17→    TestStatusView,
    18→)
    19→
    20→
    21→# Register custom converter for automatic test hash normalization
    22→register_converter(TestHashConverter, "TestHash")
    23→
    24→
    25→urlpatterns = [
    26→    path("test/", TestLookupView.as_view(), name="test-lookup"),
    27→    path("test/<TestHash:test_hash>/status/", TestStatusView.as_view(), name="test-status"),
    28→    path(
    29→        "test/<TestHash:test_hash>/shipping-status/",
    30→        TestShippingView.as_view(),
    31→        name="test-shipping",
    32→    ),
    33→    path(
    34→        "test/<TestHash:test_hash>/coaching-info/", TestCoachingView.as_view(), name="test-coaching"
    35→    ),
    36→    path(
    37→        "test/<TestHash:test_hash>/health-history/",
    38→        TestHealthHistoryView.as_view(),
    39→        name="test-health-history",
    40→    ),
    41→    path(
    42→        "test/<TestHash:test_hash>/consult-lookup/",
    43→        ConsultLookupView.as_view(),
    44→        name="consult-lookup",
    45→    ),
    46→    path(
    47→        "consult/<str:consult_id>/prescription/",
    48→        PrescriptionStatusView.as_view(),
    49→        name="prescription-status",
    50→    ),
    51→    path("consult/<str:consult_id>/intake/", ConsultIntakeView.as_view(), name="consult-intake"),
    52→]
    53→
```


**Step 18:** `ls backend/partner_api/distro/`  
*List distro directory*


```
__init__.py
__pycache__
serializers.py
urls.py
utils.py
views.py
```


**Step 19:** `read("backend/api/v1/permissions.py")`


```
1→"""
     2→Custom permission classes for API views.
     3→"""
     4→
     5→from rest_framework import permissions
     6→
     7→from accounts.utils import is_provider
     8→from test_results.models.test import Test
     9→
    10→
    11→class CanAccessTest(permissions.BasePermission):
    12→    """
    13→    Permission class to check if a user can access a test's data.
    14→
    15→    Authorization rules:
    16→    - Staff users can access any test
    17→    - Providers can access tests linked via provider_test_orders
    18→    - Patients can only access their own tests
    19→    """
    20→
    21→    def has_object_permission(self, request, view, obj):
    22→        test = obj if isinstance(obj, Test) else getattr(obj, "test", None)
    23→        if not test:
    24→            return False
    25→
    26→        # Staff can access any test
    27→        if request.user.is_staff:
    28→            return True
    29→
    30→        # Providers can access tests linked via provider_test_orders
    31→        if is_provider(request.user):
    32→            return request.user.provider_test_orders.filter(test=test).exists()
    33→
    34→        # Patients can only access their own tests
    35→        return test.user == request.user
    36→
```


**Step 20:** `read("backend/partner_api/distro/urls.py")`


```
1→"""
     2→URL configuration for Partner API distro endpoints.
     3→"""
     4→
     5→from django.urls import path, register_converter
     6→
     7→from partner_api.distro.views import PartnerReportsView, PartnerTestStatusesView
     8→from partner_api.utils import TestHashConverter
     9→
    10→
    11→app_name = "distro_partner_api"
    12→
    13→# Register custom converter for automatic test hash normalization
    14→register_converter(TestHashConverter, "TestHash")
    15→
    16→urlpatterns = [
    17→    path("reports/<TestHash:test_hash>/", PartnerReportsView.as_view(), name="reports"),
    18→    path("tests/statuses/", PartnerTestStatusesView.as_view(), name="test-statuses"),
    19→]
    20→
```


**Step 21:** `read("backend/partner_api/permissions.py")`


```
1→"""
     2→Permissions for Partner API endpoints.
     3→"""
     4→
     5→from rest_framework.permissions import BasePermission
     6→
     7→from partner_api.partner_config import PartnerConfig
     8→
     9→
    10→def get_client_ip(request) -> str:
    11→    """
    12→    Get the client IP address from the request.
    13→
    14→    Uses Cloudflare's True-Client-IP header if available (as per Render support),
    15→    otherwise falls back to REMOTE_ADDR.
    16→
    17→    Args:
    18→        request: Django request object
    19→
    20→    Returns:
    21→        Client IP address as string, or empty string if not found
    22→    """
    23→    # Try True-Client-IP header first (used by Cloudflare/Render)
    24→    ip = request.headers.get("True-Client-IP")
    25→    if ip:
    26→        return ip.strip()
    27→
    28→    # Fall back to REMOTE_ADDR
    29→    return request.META.get("REMOTE_ADDR", "").strip()
    30→
    31→
    32→class PartnerAPIKeyRequired(BasePermission):
    33→    """
    34→    Permission that allows access if PartnerAPIKeyAuthentication succeeded.
    35→
    36→    Since partner authentication is service-to-service (not user-based),
    37→    we just check that authentication occurred (auth object is not None).
    38→
    39→    For PartnerConfig objects, also ensures the partner is active.
    40→    """
    41→
    42→    def has_permission(self, request, view):
    43→        """
    44→        Return True if authentication succeeded.
    45→
    46→        PartnerAPIKeyAuthentication returns (None, partner_or_api_key) on success,
    47→        so we check if request.auth is not None.
    48→        For PartnerConfig objects, also check that they are active.
    49→        """
    50→        if request.auth is None:
    51→            return False
    52→
    53→        # If it's a PartnerConfig object, ensure it's active
    54→        if isinstance(request.auth, PartnerConfig):
    55→            return request.auth.is_active
    56→
    57→        # Legacy API key (string) - allow access
    58→        return True
    59→
    60→
    61→class PartnerIPAllowlistRequired(BasePermission):
    62→    """
    63→    Permission that checks if the client IP address is in the partner's allowed IP list.
    64→
    65→    Only applies to PartnerConfig objects. If allowed_ips is None or empty,
    66→    no IP restriction is enforced.
    67→    """
    68→
    69→    def has_permission(self, request, view):
    70→        """
    71→        Return True if the client IP is in the partner's allowed IP list.
    72→
    73→        Args:
    74→            request: Django request object
    75→            view: View instance
    76→
    77→        Returns:
    78→            True if IP is allowed or no IP restriction is configured, False otherwise
    79→        """
    80→        # Only check IP for PartnerConfig objects
    81→        if not isinstance(request.auth, PartnerConfig):
    82→            return True
    83→
    84→        partner: PartnerConfig = request.auth
    85→
    86→        # If no IP restriction is configured, allow access
    87→        if not partner.allowed_ips:
    88→            return True
    89→
    90→        # Get client IP and check if it's in the allowed list
    91→        client_ip = get_client_ip(request)
    92→        if not client_ip:
    93→            return False
    94→
    95→        return client_ip in partner.allowed_ips
    96→
```


**Step 22:** `read("backend/partner_api/cx_automation/views.py")`


```
1→"""
     2→Views for CX Automation API endpoints.
     3→"""
     4→
     5→from rest_framework.response import Response
     6→from rest_framework.views import APIView
     7→
     8→from partner_api.authentication import PartnerAPIKeyAuthentication
     9→from partner_api.permissions import PartnerAPIKeyRequired
    10→from partner_api.utils import extract_query_params
    11→
    12→from utils.advanced_api_docs_helper import advanced_api_docs
    13→
    14→from .serializers import (
    15→    ConsultIntakeResponseSerializer,
    16→    ConsultLookupResponseSerializer,
    17→    ConsultStatusResponseSerializer,
    18→    PrescriptionStatusResponseSerializer,
    19→    TestCoachingResponseSerializer,
    20→    TestHealthHistoryResponseSerializer,
    21→    TestLookupResponseSerializer,
    22→    TestShippingResponseSerializer,
    23→    TestStatusResponseSerializer,
    24→)
    25→from .services import (
    26→    ConsultIntakeService,
    27→    ConsultLookupService,
    28→    ConsultStatusService,
    29→    PrescriptionStatusService,
    30→    TestCoachingService,
    31→    TestHealthHistoryService,
    32→    TestLookupService,
    33→    TestShippingService,
    34→    TestStatusService,
    35→)
    36→
    37→
    38→CX_AUTOMATION_TAG = "CX Automation"
    39→TESTS_TAG = f"{CX_AUTOMATION_TAG} - Tests"
    40→CONSULTS_TAG = f"{CX_AUTOMATION_TAG} - Consults"
    41→
    42→
    43→class TestLookupView(APIView):
    44→    """
    45→    API endpoint for looking up test IDs by user identifiers.
    46→
    47→    This endpoint allows customer experience automation platforms to retrieve
    48→    test IDs for users who have forgotten their test activation codes.
    49→    """
    50→
    51→    authentication_classes = [PartnerAPIKeyAuthentication]
    52→    permission_classes = [PartnerAPIKeyRequired]
    53→
    54→    @advanced_api_docs(tags=[TESTS_TAG])
    55→    @extract_query_params("order_number", "email")
    56→    def get(self, request, order_number: str, email: str | None = None) -> Response:
    57→        """
    58→        Look up test ID by order number.
    59→
    60→        Query parameters should contain 'order_number' and optionally 'email'.
    61→        If email is provided, it will be verified against the order's email.
    62→        Returns response with api_status, api_message, and payload structure.
    63→        """
    64→        result = TestLookupService.lookup_test_by_order_number(
    65→            order_number=order_number, email=email
    66→        )
    67→        response_serializer = TestLookupResponseSerializer(
    68→            result.model_dump(by_alias=True, mode="json")
    69→        )
    70→        return Response(response_serializer.data, status=result.http_status_code)
    71→
    72→
    73→class TestStatusView(APIView):
    74→    """
    75→    API endpoint for retrieving test status and status changes with timestamps.
    76→    """
    77→
    78→    authentication_classes = [PartnerAPIKeyAuthentication]
    79→    permission_classes = [PartnerAPIKeyRequired]
    80→
    81→    @advanced_api_docs(tags=[TESTS_TAG])
    82→    @extract_query_params("email")
    83→    def get(self, request, test_hash: str, email: str | None = None) -> Response:
    84→        """
    85→        Get current test status and all status changes with timestamps.
    86→
    87→        Path parameter contains test_hash.
    88→        Query parameter 'email' can be provided for optional verification.
    89→        Returns current status and chronological list of status changes.
    90→        """
    91→        result = TestStatusService.get_test_status_and_changes(test_hash=test_hash, email=email)
    92→        response_serializer = TestStatusResponseSerializer(
    93→            result.model_dump(by_alias=True, mode="json")
    94→        )
    95→        return Response(response_serializer.data, status=result.http_status_code)
    96→
    97→
    98→class TestShippingView(APIView):
    99→    """
   100→    API endpoint for retrieving shipping statuses for both kit and sample.
... [178 more lines truncated]
```


**Step 23:** `read("backend/partner_api/distro/views.py")`


```
1→"""
     2→Views for Partner API distro endpoints.
     3→"""
     4→
     5→import logging
     6→
     7→from django.conf import settings
     8→from django.http import HttpResponse
     9→from rest_framework import status
    10→from rest_framework.response import Response
    11→from rest_framework.views import APIView
    12→
    13→import boto3
    14→from drf_spectacular.utils import extend_schema
    15→from partner_api.authentication import PartnerOnlyAPIKeyAuthentication
    16→from partner_api.distro.serializers import TestStatus, TestStatusesResponseSerializer
    17→from partner_api.partner_config import PartnerConfig, partner_has_access_to_test
    18→from partner_api.permissions import PartnerAPIKeyRequired, PartnerIPAllowlistRequired
    19→
    20→from app.utils import is_local_env
    21→from studies.models import Cohort
    22→from test_results.models.test import Test
    23→from test_results.utils import get_microgen_results_bucket_name
    24→from utils.advanced_api_docs_helper import advanced_api_docs
    25→
    26→
    27→logger = logging.getLogger(__name__)
    28→
    29→
    30→DISTRO_TAG = "Partner API - Distro"
    31→REPORTS_TAG = f"{DISTRO_TAG} - Reports"
    32→TESTS_TAG = f"{DISTRO_TAG} - Tests"
    33→
    34→
    35→class BasePartnerDistroView(APIView):
    36→    """
    37→    Base view class with shared helper methods for partner distro endpoints.
    38→    """
    39→
    40→    def _get_partner(self, request) -> PartnerConfig | None:
    41→        """
    42→        Get the PartnerConfig object from request.auth.
    43→
    44→        For distro endpoints, a PartnerConfig is required. This method returns None
    45→        only if authentication failed to provide a partner config (should not happen
    46→        with PartnerOnlyAPIKeyAuthentication).
    47→
    48→        Returns:
    49→            PartnerConfig object or None if not found
    50→        """
    51→        auth = request.auth
    52→        if isinstance(auth, PartnerConfig):
    53→            return auth
    54→        return None
    55→
    56→    def _partner_has_access(self, partner: PartnerConfig | None, test: Test) -> bool:
    57→        """
    58→        Check if partner has access to the test.
    59→
    60→        Args:
    61→            partner: PartnerConfig object (required - None will return False)
    62→            test: Test object
    63→
    64→        Returns:
    65→            True if partner has access to the test via cohort membership, False otherwise
    66→        """
    67→        # Partner config is required - no fallback to legacy API key
    68→        if partner is None:
    69→            return False
    70→
    71→        # Check access using cohort-based access control
    72→        return partner_has_access_to_test(partner, test)
    73→
    74→
    75→class PartnerReportsView(BasePartnerDistroView):
    76→    """
    77→    API endpoint for retrieving test report PDFs.
    78→
    79→    Returns the PDF report for a given test hash from the Microgen S3 bucket.
    80→    The partner must have access to the order associated with the test.
    81→    """
    82→
    83→    authentication_classes = [PartnerOnlyAPIKeyAuthentication]
    84→    permission_classes = [PartnerAPIKeyRequired, PartnerIPAllowlistRequired]
    85→
    86→    @advanced_api_docs(tags=[REPORTS_TAG])
    87→    @extend_schema(
    88→        responses={
    89→            403: {
    90→                "type": "object",
    91→                "properties": {"error": {"type": "string"}},
    92→                "example": {"error": "Not authorized to access this resource"},
    93→            },
    94→            404: {
    95→                "type": "object",
    96→                "properties": {"error": {"type": "string"}},
    97→                "example": {"error": "Test not found"},
    98→            },
    99→            500: {
   100→                "type": "object",
... [204 more lines truncated]
```


Now let me look at the main v1 views for authentication patterns:


**Step 24:** `read("backend/api/v1/views/auth.py")`


```
1→import datetime
     2→import time
     3→
     4→from django.core.cache import cache
     5→from rest_framework.response import Response
     6→from rest_framework.views import APIView
     7→
     8→from rest_framework_simplejwt.exceptions import InvalidToken
     9→from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
    10→from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
    11→
    12→from app.throttling import (
    13→    LoginAnonHourRateThrottle,
    14→    LoginAnonMinuteRateThrottle,
    15→    TokenLogoutAnonHourRateThrottle,
    16→    TokenLogoutAnonMinuteRateThrottle,
    17→    TokenRefreshAnonHourRateThrottle,
    18→    TokenRefreshAnonMinuteRateThrottle,
    19→)
    20→
    21→ACCESS_TOKEN_PREFIX = "blacklist_access_"
    22→REFRESH_TOKEN_PREFIX = "blacklist_refresh_"
    23→
    24→
    25→class EvvyTokenObtainPairView(TokenObtainPairView):
    26→    """
    27→    Custom login view with appropriate throttling for login attempts.
    28→    """
    29→    throttle_classes = [LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle]
    30→
    31→
    32→class EvvyTokenBlacklistView(APIView):
    33→    """
    34→    Custom logout view with appropriate throttling for logout attempts.
    35→    More lenient than login since logout is a cleanup operation.
    36→    """
    37→    throttle_classes = [TokenLogoutAnonMinuteRateThrottle, TokenLogoutAnonHourRateThrottle]
    38→
    39→    def post(self, request, format=None):
    40→        # Invalidate the JWT token by blacklisting it
    41→        refresh_str = request.data.get("refresh")
    42→        access_str = request.data.get("access")
    43→
    44→        refresh = RefreshToken(refresh_str)
    45→        access = AccessToken(access_str)
    46→
    47→        access_exp = access.payload.get("exp")
    48→        access_timeout = access_exp - time.time()
    49→        refresh_exp = refresh.payload.get("exp")
    50→        refresh_timeout = refresh_exp - time.time()
    51→
    52→        # Set the cache to expire at the same time as the token
    53→        cache.set(f"{ACCESS_TOKEN_PREFIX}{access}", "true", access_timeout)
    54→        cache.set(f"{REFRESH_TOKEN_PREFIX}{refresh}", "true", refresh_timeout)
    55→
    56→        return Response({"success": "Successfully logged out"}, status=200)
    57→
    58→
    59→class EvvyTokenRefreshView(TokenRefreshView):
    60→
    61→    throttle_classes = [TokenRefreshAnonMinuteRateThrottle, TokenRefreshAnonHourRateThrottle]
    62→
    63→    def post(self, request, format=None):
    64→        refresh = request.data.get("refresh")
    65→        # Check for blacklisted refresh tokens
    66→        if cache.get(f"{REFRESH_TOKEN_PREFIX}{refresh}"):
    67→            raise InvalidToken("Invalid token")
    68→
    69→        return super().post(request, format=format)
    70→
```


**Step 25:** `search("permission_classes|authentication_classes|IsAuthenticated|AllowAny|IsAdminUser|login_required|IsStaff", path="backend/api/v1/views", context=2)`


```
backend/api/v1/views/account.py-148-    """
backend/api/v1/views/account.py-149-
backend/api/v1/views/account.py:150:    permission_classes = EvvyUserAPIView.permission_classes + [IsProvider]
backend/api/v1/views/account.py-151-
backend/api/v1/views/account.py-152-    def post(self, request):
--
backend/api/v1/views/views.py-1-from django.views.decorators.csrf import csrf_exempt
backend/api/v1/views/views.py-2-from rest_framework import permissions, status, viewsets
backend/api/v1/views/views.py:3:from rest_framework.decorators import api_view, authentication_classes, permission_classes
backend/api/v1/views/views.py-4-from rest_framework.response import Response
backend/api/v1/views/views.py-5-from rest_framework.views import APIView
--
backend/api/v1/views/views.py-10-
backend/api/v1/views/views.py-11-class EvvyUserViewSet(viewsets.ModelViewSet):
backend/api/v1/views/views.py:12:    permission_classes = [permissions.IsAuthenticated]
backend/api/v1/views/views.py:13:    authentication_classes = [EvvyJWTAuthentication]
backend/api/v1/views/views.py-14-
backend/api/v1/views/views.py-15-
backend/api/v1/views/views.py-16-class EvvyUserAPIView(APIView):
backend/api/v1/views/views.py:17:    permission_classes = [permissions.IsAuthenticated]
backend/api/v1/views/views.py:18:    authentication_classes = [EvvyJWTAuthentication]
backend/api/v1/views/views.py-19-
backend/api/v1/views/views.py-20-
--
backend/api/v1/views/views.py-22-    def decorator(view_func):
backend/api/v1/views/views.py-23-
backend/api/v1/views/views.py:24:        # Apply the permission_classes decorator
backend/api/v1/views/views.py:25:        view_func = permission_classes([permissions.IsAuthenticated])(view_func)
backend/api/v1/views/views.py-26-
backend/api/v1/views/views.py:27:        # Apply the authentication_classes decorator
backend/api/v1/views/views.py:28:        view_func = authentication_classes([EvvyJWTAuthentication])(view_func)
backend/api/v1/views/views.py-29-
backend/api/v1/views/views.py-30-        # Apply the api_view decorator last
--
backend/api/v1/views/views.py-36-
backend/api/v1/views/views.py-37-class PublicProviderMagicLinkCheckout(APIView):
backend/api/v1/views/views.py:38:    permission_classes = [permissions.AllowAny]
backend/api/v1/views/views.py:39:    authentication_classes = []
backend/api/v1/views/views.py-40-
backend/api/v1/views/views.py-41-    def get(self, request, slug: str):
--
backend/api/v1/views/email_verification.py-53-    """
backend/api/v1/views/email_verification.py-54-
backend/api/v1/views/email_verification.py:55:    # permission_classes = (permissions.IsAuthenticated,) # can be logged out (mobile browser vs webview)
backend/api/v1/views/email_verification.py-56-
backend/api/v1/views/email_verification.py-57-    def post(self, request, format=None):
--
backend/api/v1/views/provider_test_orders.py-53-
backend/api/v1/views/provider_test_orders.py-54-class ProviderTestOrderViewSet(EvvyUserViewSet):
backend/api/v1/views/provider_test_orders.py:55:    permission_classes = EvvyUserViewSet.permission_classes + [IsProvider, IsVerified]
backend/api/v1/views/provider_test_orders.py-56-    serializer_class = serializers.ProviderTestOrderSerializer
backend/api/v1/views/provider_test_orders.py-57-
--
backend/api/v1/views/user_test_results.py-38-    """
backend/api/v1/views/user_test_results.py-39-
backend/api/v1/views/user_test_results.py:40:    permission_classes = EvvyUserAPIView.permission_classes + [CanAccessTest]
backend/api/v1/views/user_test_results.py-41-
backend/api/v1/views/user_test_results.py-42-    def get(self, request, hash: str):
--
backend/api/v1/views/public_features.py-12-    """
backend/api/v1/views/public_features.py-13-
backend/api/v1/views/public_features.py:14:    authentication_classes = []  # No authentication required
backend/api/v1/views/public_features.py:15:    permission_classes = []  # No permissions required
backend/api/v1/views/public_features.py-16-
backend/api/v1/views/public_features.py-17-    def get(self, request, format=None):
```


**Step 26:** `read("backend/api/v1/views/views.py")`


```
1→from django.views.decorators.csrf import csrf_exempt
     2→from rest_framework import permissions, status, viewsets
     3→from rest_framework.decorators import api_view, authentication_classes, permission_classes
     4→from rest_framework.response import Response
     5→from rest_framework.views import APIView
     6→
     7→from accounts.models import ProviderProfile
     8→from api.v1.authentication import EvvyJWTAuthentication
     9→
    10→
    11→class EvvyUserViewSet(viewsets.ModelViewSet):
    12→    permission_classes = [permissions.IsAuthenticated]
    13→    authentication_classes = [EvvyJWTAuthentication]
    14→
    15→
    16→class EvvyUserAPIView(APIView):
    17→    permission_classes = [permissions.IsAuthenticated]
    18→    authentication_classes = [EvvyJWTAuthentication]
    19→
    20→
    21→def evvy_api_view(*args, **kwargs):
    22→    def decorator(view_func):
    23→
    24→        # Apply the permission_classes decorator
    25→        view_func = permission_classes([permissions.IsAuthenticated])(view_func)
    26→
    27→        # Apply the authentication_classes decorator
    28→        view_func = authentication_classes([EvvyJWTAuthentication])(view_func)
    29→
    30→        # Apply the api_view decorator last
    31→        view_func = api_view(*args, **kwargs)(view_func)
    32→        return view_func
    33→
    34→    return decorator
    35→
    36→
    37→class PublicProviderMagicLinkCheckout(APIView):
    38→    permission_classes = [permissions.AllowAny]
    39→    authentication_classes = []
    40→
    41→    def get(self, request, slug: str):
    42→        profile = (
    43→            ProviderProfile.objects.filter(magic_link_slug=slug).select_related("provider").first()
    44→        )
    45→        if not profile:
    46→            return Response({"error": "invalid"}, status=status.HTTP_404_NOT_FOUND)
    47→
    48→        provider = profile.provider
    49→
    50→        try:
    51→            from providers.utils import get_provider_order_checkout_link
    52→
    53→            checkout_url = get_provider_order_checkout_link(
    54→                provider=provider,
    55→                patient_email="",
    56→                add_expanded_pcr=False,
    57→                provider_test_order_id=None,
    58→                provider_paid=False,
    59→                buyer_user=None,
    60→                checkout_origin="magic-link",
    61→            )
    62→            return Response({"checkout_url": checkout_url}, status=status.HTTP_200_OK)
    63→        except Exception:
    64→            # Fall back to static link selection is inside the helper, on unexpected errors, return 200 with empty URL
    65→            return Response({"checkout_url": ""}, status=status.HTTP_200_OK)
    66→
```


**Step 27:** `search("permission_classes|authentication_classes|IsAuthenticated|AllowAny|csrf_exempt|@login_required", path="backend/api/v1/views", glob="*.py", context=4)`


```
<persisted-output>
Output too large (23KB). Full output saved to: [tool-results-cache]

Preview (first 2KB):
backend/api/v1/views/account.py-146-    - clinic state
backend/api/v1/views/account.py-147-    - hdyhau
backend/api/v1/views/account.py-148-    """
backend/api/v1/views/account.py-149-
backend/api/v1/views/account.py:150:    permission_classes = EvvyUserAPIView.permission_classes + [IsProvider]
backend/api/v1/views/account.py-151-
backend/api/v1/views/account.py-152-    def post(self, request):
backend/api/v1/views/account.py-153-        data = request.data
backend/api/v1/views/account.py-154-        user = request.user
--
backend/api/v1/views/views.py:1:from django.views.decorators.csrf import csrf_exempt
backend/api/v1/views/views.py-2-from rest_framework import permissions, status, viewsets
backend/api/v1/views/views.py:3:from rest_framework.decorators import api_view, authentication_classes, permission_classes
backend/api/v1/views/views.py-4-from rest_framework.response import Response
backend/api/v1/views/views.py-5-from rest_framework.views import APIView
backend/api/v1/views/views.py-6-
backend/api/v1/views/views.py-7-from accounts.models import ProviderProfile
backend/api/v1/views/views.py-8-from api.v1.authentication import EvvyJWTAuthentication
backend/api/v1/views/views.py-9-
backend/api/v1/views/views.py-10-
backend/api/v1/views/views.py-11-class EvvyUserViewSet(viewsets.ModelViewSet):
backend/api/v1/views/views.py:12:    permission_classes = [permissions.IsAuthenticated]
...
</persisted-output>
```


**Step 28:** `read("[tool-results-cache]")`


```
1→backend/api/v1/views/account.py-146-    - clinic state
     2→backend/api/v1/views/account.py-147-    - hdyhau
     3→backend/api/v1/views/account.py-148-    """
     4→backend/api/v1/views/account.py-149-
     5→backend/api/v1/views/account.py:150:    permission_classes = EvvyUserAPIView.permission_classes + [IsProvider]
     6→backend/api/v1/views/account.py-151-
     7→backend/api/v1/views/account.py-152-    def post(self, request):
     8→backend/api/v1/views/account.py-153-        data = request.data
     9→backend/api/v1/views/account.py-154-        user = request.user
    10→--
    11→backend/api/v1/views/views.py:1:from django.views.decorators.csrf import csrf_exempt
    12→backend/api/v1/views/views.py-2-from rest_framework import permissions, status, viewsets
    13→backend/api/v1/views/views.py:3:from rest_framework.decorators import api_view, authentication_classes, permission_classes
    14→backend/api/v1/views/views.py-4-from rest_framework.response import Response
    15→backend/api/v1/views/views.py-5-from rest_framework.views import APIView
    16→backend/api/v1/views/views.py-6-
    17→backend/api/v1/views/views.py-7-from accounts.models import ProviderProfile
    18→backend/api/v1/views/views.py-8-from api.v1.authentication import EvvyJWTAuthentication
    19→backend/api/v1/views/views.py-9-
    20→backend/api/v1/views/views.py-10-
    21→backend/api/v1/views/views.py-11-class EvvyUserViewSet(viewsets.ModelViewSet):
    22→backend/api/v1/views/views.py:12:    permission_classes = [permissions.IsAuthenticated]
    23→backend/api/v1/views/views.py:13:    authentication_classes = [EvvyJWTAuthentication]
    24→backend/api/v1/views/views.py-14-
    25→backend/api/v1/views/views.py-15-
    26→backend/api/v1/views/views.py-16-class EvvyUserAPIView(APIView):
    27→backend/api/v1/views/views.py:17:    permission_classes = [permissions.IsAuthenticated]
    28→backend/api/v1/views/views.py:18:    authentication_classes = [EvvyJWTAuthentication]
    29→backend/api/v1/views/views.py-19-
    30→backend/api/v1/views/views.py-20-
    31→backend/api/v1/views/views.py-21-def evvy_api_view(*args, **kwargs):
    32→backend/api/v1/views/views.py-22-    def decorator(view_func):
    33→backend/api/v1/views/views.py-23-
    34→backend/api/v1/views/views.py:24:        # Apply the permission_classes decorator
    35→backend/api/v1/views/views.py:25:        view_func = permission_classes([permissions.IsAuthenticated])(view_func)
    36→backend/api/v1/views/views.py-26-
    37→backend/api/v1/views/views.py:27:        # Apply the authentication_classes decorator
    38→backend/api/v1/views/views.py:28:        view_func = authentication_classes([EvvyJWTAuthentication])(view_func)
    39→backend/api/v1/views/views.py-29-
    40→backend/api/v1/views/views.py-30-        # Apply the api_view decorator last
    41→backend/api/v1/views/views.py-31-        view_func = api_view(*args, **kwargs)(view_func)
    42→backend/api/v1/views/views.py-32-        return view_func
    43→--
    44→backend/api/v1/views/views.py-34-    return decorator
    45→backend/api/v1/views/views.py-35-
    46→backend/api/v1/views/views.py-36-
    47→backend/api/v1/views/views.py-37-class PublicProviderMagicLinkCheckout(APIView):
    48→backend/api/v1/views/views.py:38:    permission_classes = [permissions.AllowAny]
    49→backend/api/v1/views/views.py:39:    authentication_classes = []
    50→backend/api/v1/views/views.py-40-
    51→backend/api/v1/views/views.py-41-    def get(self, request, slug: str):
    52→backend/api/v1/views/views.py-42-        profile = (
    53→backend/api/v1/views/views.py-43-            ProviderProfile.objects.filter(magic_link_slug=slug).select_related("provider").first()
    54→--
    55→backend/api/v1/views/webhooks.py-6-import time
    56→backend/api/v1/views/webhooks.py-7-
    57→backend/api/v1/views/webhooks.py-8-from django.conf import settings
    58→backend/api/v1/views/webhooks.py-9-from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
    59→backend/api/v1/views/webhooks.py:10:from django.views.decorators.csrf import csrf_exempt
    60→backend/api/v1/views/webhooks.py-11-from rest_framework.decorators import action
    61→backend/api/v1/views/webhooks.py-12-
    62→backend/api/v1/views/webhooks.py-13-import newrelic.agent
    63→backend/api/v1/views/webhooks.py-14-
    64→--
    65→backend/api/v1/views/webhooks.py-52-
    66→backend/api/v1/views/webhooks.py-53-REPLACEMENT_TEST_SUFFIX = "RPL"
    67→backend/api/v1/views/webhooks.py-54-
    68→backend/api/v1/views/webhooks.py-55-
    69→backend/api/v1/views/webhooks.py:56:@csrf_exempt
    70→backend/api/v1/views/webhooks.py-57-def webhook_view(request):
    71→backend/api/v1/views/webhooks.py-58-    """
    72→backend/api/v1/views/webhooks.py-59-    processes webhooks
    73→backend/api/v1/views/webhooks.py-60-
    74→--
    75→backend/api/v1/views/webhooks.py-76-
    76→backend/api/v1/views/webhooks.py-77-    return HttpResponse(status=200)
    77→backend/api/v1/views/webhooks.py-78-
    78→backend/api/v1/views/webhooks.py-79-
    79→backend/api/v1/views/webhooks.py:80:@csrf_exempt
    80→backend/api/v1/views/webhooks.py-81-@action(methods=["post"], detail=False)
    81→backend/api/v1/views/webhooks.py-82-def shopify_webhook_view(request):
    82→backend/api/v1/views/webhooks.py-83-    shopify_topic = request.headers.get("X-Shopify-Topic", "")
    83→backend/api/v1/views/webhooks.py-84-    newrelic.agent.add_custom_attribute("webhook_topic", shopify_topic)
    84→--
    85→backend/api/v1/views/webhooks.py-144-
    86→backend/api/v1/views/webhooks.py-145-    return HttpResponse(status=200)
    87→backend/api/v1/views/webhooks.py-146-
    88→backend/api/v1/views/webhooks.py-147-
    89→backend/api/v1/views/webhooks.py:148:@csrf_exempt
    90→backend/api/v1/views/webhooks.py-149-@action(methods=["post"], detail=False)
    91→backend/api/v1/views/webhooks.py-150-def shopify_webhook_graphql_view(request):
    92→backend/api/v1/views/webhooks.py-151-    data = request.body
    93→backend/api/v1/views/webhooks.py-152-    verified = _verify_hmac_webhook(
    94→--
    95→backend/api/v1/views/webhooks.py-169-
    96→backend/api/v1/views/webhooks.py-170-    return HttpResponse(status=200)
    97→backend/api/v1/views/webhooks.py-171-
    98→backend/api/v1/views/webhooks.py-172-
    99→backend/api/v1/views/webhooks.py:173:@csrf_exempt
   100→backend/api/v1/views/webhooks.py-174-@action(methods=["post"], detail=False)
... [174 more lines truncated]
```


**Step 29:** `read("backend/api/v1/views/webhooks.py", offset=1, limit=100)`


```
1→import base64
     2→import hashlib
     3→import hmac
     4→import json
     5→import logging
     6→import time
     7→
     8→from django.conf import settings
     9→from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
    10→from django.views.decorators.csrf import csrf_exempt
    11→from rest_framework.decorators import action
    12→
    13→import newrelic.agent
    14→
    15→from analytics.braze.constants import BrazeEventName
    16→from analytics.braze.utils import braze_track_user_event
    17→from analytics.typeform.typeform import process_typeform_quiz_completion
    18→from coaching.utils import process_calendly_webhook
    19→from consults.wheel.utils_webhook import process_wheel_webhook_notification
    20→from ecomm.monitoring import OrderErrorCategory, OrderEventType, create_order_logger
    21→from ecomm.services.viome import ViomeOrderService
    22→from ecomm.utils import process_shopify_order, process_shopify_subscription_webhook
    23→from shipping.precision.tasks import process_precision_pharmacy_webhook
    24→from shipping.tasks import process_tracking_statuses
    25→from subscriptions.constants import (
    26→    TOPIC_CHARGE_UPCOMING,
    27→    TOPIC_SUBSCRIPTION_ACTIVATED,
    28→    TOPIC_SUBSCRIPTION_CANCELLED,
    29→    TOPIC_SUBSCRIPTION_CREATED,
    30→    TOPIC_SUBSCRIPTION_DELETED,
    31→    TOPIC_SUBSCRIPTION_PAUSED,
    32→    TOPIC_SUBSCRIPTION_SKIPPED,
    33→    TOPIC_SUBSCRIPTION_SWAPPED,
    34→    TOPIC_SUBSCRIPTION_UNSKIPPED,
    35→    TOPIC_SUBSCRIPTION_UPDATED,
    36→)
    37→from subscriptions.service import handle_charge_upcoming_webhook, handle_subscription_webhook
    38→from surveys.service import process_survicate_webhook
    39→from test_results import constants
    40→from test_results.lab_services.providers.junction.webhook_handler import JunctionWebhookHandler
    41→from test_results.microgen.tasks import process_lab_status_update, process_lab_status_update_batch
    42→from test_results.utils_processing import (
    43→    process_community_type_file_upload_from_s3,
    44→    process_results_file_upload_from_s3,
    45→)
    46→
    47→
    48→logger = logging.getLogger("evvy.webhooks")
    49→
    50→BERLIN_WEBHOOK_FEDEX_PROVIDER = "FEDEX"
    51→BERLIN_WEBHOOK_USPS_PROVIDER = "USPS"
    52→
    53→REPLACEMENT_TEST_SUFFIX = "RPL"
    54→
    55→
    56→@csrf_exempt
    57→def webhook_view(request):
    58→    """
    59→    processes webhooks
    60→
    61→    Right now just s3 bucket upload, abstract out others later
    62→    """
    63→    payload = json.loads(request.body)
    64→    if "source" not in payload:
    65→        raise Exception(f"no source in payload {payload}")
    66→    if "type" not in payload:
    67→        raise Exception(f"no type in payload {payload}")
    68→
    69→    # TODO: check that it's coming from s3 lambda event
    70→    if payload["source"] == "s3" and payload["type"] == constants.S3_FILE_TAXATABLE_RESULTS:
    71→        process_results_file_upload_from_s3(payload)
    72→    elif payload["source"] == "s3" and payload["type"] == constants.S3_FILE_COMMUNITY_TYPES:
    73→        process_community_type_file_upload_from_s3(payload)
    74→    else:
    75→        raise Exception(f"unknown webhook source {payload['source']}: {payload['type']}")
    76→
    77→    return HttpResponse(status=200)
    78→
    79→
    80→@csrf_exempt
    81→@action(methods=["post"], detail=False)
    82→def shopify_webhook_view(request):
    83→    shopify_topic = request.headers.get("X-Shopify-Topic", "")
    84→    newrelic.agent.add_custom_attribute("webhook_topic", shopify_topic)
    85→
    86→    order_logger = create_order_logger()
    87→    webhook_start_time = time.time()
    88→
    89→    data = request.body
    90→    verified = _verify_hmac_webhook(
    91→        data,
    92→        request.headers.get("X-Shopify-Hmac-SHA256", ""),
    93→        settings.SHOPIFY_WEBHOOK_SECRET,
    94→    )
    95→    if not verified:
    96→        order_logger.log_processing_error(
    97→            "Shopify webhook signature verification failed",
    98→            OrderErrorCategory.VALIDATION,
    99→            additional_attributes={
   100→                "webhook_topic": shopify_topic,
```


**Step 30:** `read("backend/api/v1/views/tasks.py")`


```
1→"""
     2→Views used for firing async tasks via cronjob
     3→"""
     4→
     5→from __future__ import absolute_import
     6→
     7→import os
     8→
     9→from django.conf import settings
    10→from django.utils.decorators import method_decorator
    11→from django.views.decorators.csrf import csrf_exempt
    12→from rest_framework import viewsets
    13→from rest_framework.decorators import action
    14→from rest_framework.response import Response
    15→
    16→
    17→class TasksViewSet(viewsets.ViewSet):
    18→    """
    19→    Viewset that is used to trigger various "tasks"
    20→    That are initialized from render cron.
    21→    Schedule is refined in cron_schedule.py
    22→    """
    23→
    24→    def _confirm_token(self, request):
    25→        """
    26→        Make sure the token adds up
    27→        """
    28→        token = request.data.get("token", None)
    29→        if settings.DEBUG:
    30→            return  # no need to check for local
    31→        if not token:
    32→            raise Exception("missing token")
    33→        if not token == os.environ.get("RENDER_GIT_COMMIT", None):
    34→            raise Exception("Invalid token")
    35→
    36→    @method_decorator(csrf_exempt)
    37→    @action(methods=["post"], detail=False)
    38→    def echo(self, request, *args, **kwargs):
    39→        """
    40→        Just a test endpoint
    41→        """
    42→        self._confirm_token(request)
    43→        return Response("Done")
    44→
```


**Step 31:** `read("backend/api/v1/views/webhooks.py", offset=200, limit=200)`


```
200→    computed_hmac = base64.b64encode(digest)
   201→    return hmac.compare_digest(computed_hmac, hmac_header.encode("utf-8"))
   202→
   203→
   204→@csrf_exempt
   205→@action(methods="post", detail=False)
   206→def wheel_webhook_view(request):
   207→    data = request.body
   208→    verified = _verify_wheel_webhook(request.headers.get("X-Wheel-Access-Token", ""))
   209→    if not verified:
   210→        return HttpResponse("Not allowed", status=403)
   211→    if data:
   212→        data = json.loads(data)
   213→        process_wheel_webhook_notification(data)
   214→    return HttpResponse(status=200)
   215→
   216→
   217→def _verify_wheel_webhook(header_value):
   218→    return header_value == settings.WHEEL_ACCESS_TOKEN
   219→
   220→
   221→@csrf_exempt
   222→@action(methods="post", detail=False)
   223→def berlin_webhook_view(request):
   224→    data = request.body
   225→    verified = _verify_berlin_webhook(request.headers.get("X-Berlin-Access-Token", ""))
   226→    if not verified:
   227→        return HttpResponse("Not allowed", status=403)
   228→    if data:
   229→        logger.info(f"[process_tracking_statuses]: Received webhook {data}")
   230→        data = json.loads(data)
   231→        test_hash = data.get("test_id") if data.get("test_id") else ""
   232→        test_hash = test_hash.replace("-", "").strip().lower()
   233→
   234→        order_number = data.get("shopify_order_number") if data.get("shopify_order_number") else ""
   235→        order_number = order_number.replace("#", "").strip()
   236→
   237→        if REPLACEMENT_TEST_SUFFIX in order_number:
   238→            order_number = order_number.replace(REPLACEMENT_TEST_SUFFIX, "")
   239→            logger.info(
   240→                f"[process_tracking_statuses]: Processing replacement order {order_number} for test {test_hash}"
   241→            )
   242→
   243→        kit_tracking_number = (
   244→            data.get("outbound_tracking_number") if data.get("outbound_tracking_number") else ""
   245→        )
   246→        kit_tracking_number = kit_tracking_number.strip()
   247→
   248→        sample_tracking_number = (
   249→            data.get("return_tracking_number") if data.get("return_tracking_number") else ""
   250→        )
   251→        sample_tracking_number = sample_tracking_number.strip()
   252→
   253→        process_tracking_statuses.delay(
   254→            test_hash=test_hash,
   255→            order_number=order_number,
   256→            kit_tracking_number=kit_tracking_number,
   257→            sample_tracking_number=sample_tracking_number,
   258→        )
   259→    return HttpResponse(status=200)
   260→
   261→
   262→def _verify_berlin_webhook(header_value):
   263→    return header_value == settings.BERLIN_ACCESS_TOKEN
   264→
   265→
   266→@csrf_exempt
   267→@action(methods=["post"], detail=False)
   268→def microgen_webhook_view(request):
   269→    data = request.body
   270→    verified = _verify_hmac_webhook(
   271→        data,
   272→        request.headers.get("X-Microgen-Hmac-SHA256", ""),
   273→        settings.MICROGEN_SECRET_KEY,
   274→    )
   275→    if not verified:
   276→        return HttpResponse("invalid signature", status=403)
   277→    payload = json.loads(data)
   278→    logger.info(payload)
   279→    process_lab_status_update(payload)
   280→    return HttpResponse(status=200)
   281→
   282→
   283→@csrf_exempt
   284→@action(methods=["post"], detail=False)
   285→def microgen_batch_webhook_view(request):
   286→    data = request.body
   287→    verified = _verify_hmac_webhook(
   288→        data,
   289→        request.headers.get("X-Microgen-Hmac-SHA256", ""),
   290→        settings.MICROGEN_SECRET_KEY,
   291→    )
   292→    if not verified:
   293→        return HttpResponse("invalid signature", status=403)
   294→    payload = json.loads(data)
   295→    logger.info(payload)
   296→    process_lab_status_update_batch.delay(payload)
   297→    return HttpResponse(status=200)
   298→
   299→
... [100 more lines truncated]
```


**Step 32:** `read("backend/api/v1/views/account.py")`


```
1→"""
     2→User config API
     3→"""
     4→
     5→from django.contrib.auth.password_validation import validate_password
     6→from django.core.exceptions import ValidationError
     7→from django.utils import timezone
     8→from rest_framework import permissions, status
     9→from rest_framework.response import Response
    10→
    11→from accounts.enums import (
    12→    HowDidYouHearAboutUs,
    13→    PatientType,
    14→    PatientVolume,
    15→    PlatformAccess,
    16→    PlatformLeverage,
    17→    ProviderGoal,
    18→    ProviderType,
    19→)
    20→from accounts.models import GROUP_NAME_PROVIDERS
    21→from accounts.tasks import send_intake_completed_notifications
    22→from accounts.utils import (
    23→    check_email_already_exists,
    24→    check_name_field,
    25→    get_provider_profile,
    26→    get_user_profile,
    27→    get_validated_birth_date_from_string,
    28→    normalize_user_input_fields,
    29→    send_email_address_changed_email,
    30→    send_password_changed_email,
    31→)
    32→from analytics.braze.constants import PROVIDER_CLINIC_STATE
    33→from analytics.service import update_user_profile
    34→from api.v1.views.views import EvvyUserAPIView
    35→from consults.constants import (
    36→    CANADIAN_PROVINCE_CODES,
    37→    COUNTRIES,
    38→    COUNTRIES_PLUS_OTHER,
    39→    PROVINCES_PLUS_OTHER,
    40→    STATES,
    41→    STATES_PLUS_OTHER,
    42→)
    43→
    44→
    45→class UserAccountView(EvvyUserAPIView):
    46→    """
    47→    View used by user to modify their account information:
    48→    - first/last name
    49→    - email address
    50→    - password
    51→    """
    52→
    53→    def post(self, request, format=None):
    54→        data = request.data
    55→        user = request.user
    56→
    57→        first_name = data.get("first_name", None)
    58→        last_name = data.get("last_name", None)
    59→        email = data.get("email", None)
    60→        birthday = request.data.get("birthday", None)
    61→        phone_number = data.get("phone_number", None)
    62→        current_password = data.get("current_password", None)
    63→        new_password = data.get("new_password", None)
    64→        new_password_again = data.get("new_password_again", None)
    65→
    66→        if first_name or last_name or email:
    67→            first_name, last_name, email = normalize_user_input_fields(
    68→                first_name=first_name, last_name=last_name, email=email
    69→            )
    70→
    71→        if first_name:
    72→            if not check_name_field(first_name):
    73→                return Response(
    74→                    "First name must contain only letters, spaces, dashes, underscores, and apostrophes",
    75→                    status=status.HTTP_400_BAD_REQUEST,
    76→                )
    77→            user.first_name = first_name
    78→        if last_name:
    79→            if not check_name_field(last_name):
    80→                return Response(
    81→                    "Last name must contain only letters, spaces, dashes, underscores, and apostrophes",
    82→                    status=status.HTTP_400_BAD_REQUEST,
    83→                )
    84→            user.last_name = last_name
    85→        if birthday:
    86→            try:
    87→                birthday_date = get_validated_birth_date_from_string(birthday)
    88→            except ValidationError as e:
    89→                return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
    90→            profile = get_user_profile(user)
    91→            profile.birthday = birthday_date
    92→            profile.save()
    93→
    94→        if phone_number is not None:
    95→            profile = get_user_profile(user)
    96→            profile.phone_number = phone_number
    97→            profile.save()
    98→
    99→        if email and (not user.email or user.email.lower() != email):
   100→            if not current_password:
... [210 more lines truncated]
```


**Step 33:** `read("backend/api/v1/views/register.py")`


```
1→"""
     2→User config API
     3→"""
     4→
     5→import logging
     6→
     7→from django.contrib.auth.models import Group, User
     8→from django.contrib.auth.password_validation import validate_password
     9→from django.core.exceptions import ValidationError
    10→from rest_framework import status
    11→from rest_framework.response import Response
    12→from rest_framework.views import APIView
    13→
    14→from rest_framework_simplejwt.tokens import RefreshToken
    15→
    16→from accounts.models import GROUP_NAME_PROVIDERS
    17→from accounts.utils import (
    18→    check_email_already_exists,
    19→    check_name_field,
    20→    get_provider_profile,
    21→    get_user_profile,
    22→    get_validated_birth_date_from_string,
    23→    normalize_user_input_fields,
    24→)
    25→from analytics.braze.constants import (
    26→    IS_EVVY_ACCOUNT,
    27→    PROVIDER_REGISTRATION_STATUS,
    28→    BrazeEventName,
    29→    ProviderRegistrationStatus,
    30→)
    31→from analytics.service import identify_user, track_event, update_user_profile
    32→from analytics.tasks import send_provider_registered_event
    33→from api.v1.utils.male_partner import create_male_partner_consult_and_checkout_url
    34→from app.throttling import LoginAnonHourRateThrottle, LoginAnonMinuteRateThrottle
    35→from ecomm.models.order import Order
    36→from ecomm.services.cart import attach_order_to_user
    37→from ecomm.tasks import attach_unattached_orders_to_user
    38→
    39→
    40→logger = logging.getLogger("api.v1.views.register")
    41→
    42→
    43→class RegisterView(APIView):
    44→    """
    45→    Register user. Returns user's auth jwt tokens
    46→    """
    47→
    48→    throttle_classes = [LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle]
    49→
    50→    def post(self, request, format=None):
    51→        email = request.data.get("email", None)
    52→        password = request.data.get("password", None)
    53→        first_name = request.data.get("first_name", None)
    54→        last_name = request.data.get("last_name", None)
    55→        birthday = request.data.get("birthday", None)
    56→
    57→        # these 2 params are used for accounts created through the ungated RX flow
    58→        registration_route = request.data.get("registration_route", None)
    59→        checkout_id = request.data.get("checkout_id", None)
    60→        order_number = request.data.get("order_number", None)
    61→
    62→        # voucher code for male partner treatment flow
    63→        voucher_code = request.data.get("voucher_code", None)
    64→
    65→        # fetch the order if checkout ID is provided, if not just use the order number
    66→        if checkout_id and not order_number:
    67→            order = Order.objects.filter(checkout_id=checkout_id).first()
    68→            order_number = order.order_number if order else None
    69→
    70→        validation_fields = [email, password, first_name, last_name, birthday]
    71→
    72→        for field in validation_fields:
    73→            if not field:
    74→                return Response("Missing required fields", status=status.HTTP_400_BAD_REQUEST)
    75→
    76→        first_name, last_name, email = normalize_user_input_fields(
    77→            first_name=first_name, last_name=last_name, email=email
    78→        )
    79→
    80→        if not check_name_field(first_name) or not check_name_field(last_name):
    81→            return Response(
    82→                "First and last name must contain only letters, spaces, dashes, underscores, and apostrophes",
    83→                status=status.HTTP_400_BAD_REQUEST,
    84→            )
    85→
    86→        if check_email_already_exists(email):
    87→            return Response(
    88→                "Please enter a valid email address. If you already have an account, please log in below.",
    89→                status=status.HTTP_400_BAD_REQUEST,
    90→            )
    91→
    92→        try:
    93→            validate_password(password)
    94→        except ValidationError as e:
    95→            return Response("; ".join(e.messages), status=status.HTTP_400_BAD_REQUEST)
    96→
    97→        try:
    98→            birthday_date = get_validated_birth_date_from_string(birthday)
    99→        except ValidationError as e:
   100→            return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
... [150 more lines truncated]
```


**Step 34:** `read("backend/api/v1/views/email_verification.py")`


```
1→"""
     2→User config API
     3→"""
     4→
     5→from django.conf import settings
     6→from rest_framework import status
     7→from rest_framework.response import Response
     8→from rest_framework.views import APIView
     9→
    10→from accounts.models import VerificationEmail
    11→from accounts.utils import user_has_verified_email
    12→from api.v1.views.views import EvvyUserAPIView
    13→from app.throttling import LoginAnonHourRateThrottle, LoginAnonMinuteRateThrottle
    14→from transactional_email.constants import TEMPLATE_VERIFY_EMAIL
    15→from transactional_email.utils import get_email_context, send_templated_email
    16→
    17→
    18→class EmailVerificationView(EvvyUserAPIView):
    19→    """
    20→    Allows the user to send a verification email & create a VerificationEmail
    21→    """
    22→
    23→    throttle_classes = [LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle]
    24→
    25→    def post(self, request, format=None):
    26→        user = request.user
    27→
    28→        # make sure user has email and isn't already verified
    29→        if not user.email:
    30→            return Response("Missing email address", status=status.HTTP_400_BAD_REQUEST)
    31→        if user_has_verified_email(user):
    32→            return Response("Email already verified", status=status.HTTP_400_BAD_REQUEST)
    33→
    34→        # create the object
    35→        verification_email = VerificationEmail.objects.create(user=user, email=user.email)
    36→
    37→        # send an e-mail to the user
    38→        verify_url = "{}/verify-email-confirm/?hash={}".format(
    39→            settings.SITE_URL, verification_email.hash
    40→        )
    41→        context = get_email_context(user, {"verify_url": verify_url})
    42→
    43→        sent, error = send_templated_email(user.email, TEMPLATE_VERIFY_EMAIL, context=context)
    44→        if sent:
    45→            return Response("sent", status=status.HTTP_200_OK)
    46→        else:
    47→            return Response(error, status=status.HTTP_400_BAD_REQUEST)
    48→
    49→
    50→class EmailVerificationConfirmView(APIView):
    51→    """
    52→    Allows the user to confirm an VerificationEmail
    53→    """
    54→
    55→    # permission_classes = (permissions.IsAuthenticated,) # can be logged out (mobile browser vs webview)
    56→
    57→    def post(self, request, format=None):
    58→        verification_hash = request.data.get("hash", None)
    59→        if not verification_hash:
    60→            return Response("Missing hash", status=status.HTTP_400_BAD_REQUEST)
    61→
    62→        verification_email = VerificationEmail.objects.filter(hash=verification_hash).last()
    63→        if not verification_email:
    64→            return Response("Invalid hash", status=status.HTTP_400_BAD_REQUEST)
    65→
    66→        # TODO: expiring verification?
    67→
    68→        # confirm verification
    69→        verification_email.verified = True
    70→        verification_email.save()
    71→        return Response("verified", status=status.HTTP_200_OK)
    72→
```


**Step 35:** `read("backend/api/v1/views/reset_password.py")`


```
1→import hashlib
     2→import logging
     3→
     4→from django.contrib.auth.models import User
     5→from django.utils.decorators import method_decorator
     6→from django.views.decorators.cache import never_cache
     7→from rest_framework import status
     8→from rest_framework.response import Response
     9→from rest_framework.settings import api_settings
    10→
    11→from django_rest_passwordreset.models import ResetPasswordToken
    12→from django_rest_passwordreset.views import (
    13→    ResetPasswordConfirm,
    14→    ResetPasswordRequestToken,
    15→    ResetPasswordValidateToken,
    16→)
    17→
    18→from app.throttling import LoginAnonHourRateThrottle, LoginAnonMinuteRateThrottle
    19→
    20→
    21→logger = logging.getLogger("evvy.api.reset_password")
    22→
    23→
    24→def _get_token_fingerprint(token: str) -> str:
    25→    """Generate a secure SHA-256 fingerprint of the token for logging purposes."""
    26→    return hashlib.sha256(token.encode()).hexdigest()[:16]
    27→
    28→
    29→@method_decorator(never_cache, name="dispatch")
    30→class CustomResetPasswordRequestToken(ResetPasswordRequestToken):
    31→    def post(self, request, *args, **kwargs):
    32→        email = request.data.get("email")
    33→        if not email:
    34→            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
    35→
    36→        try:
    37→            user = User.objects.get(email=email)
    38→            logger.info(f"Password reset requested for user ID {user.id}")
    39→        except User.DoesNotExist:
    40→            user = None
    41→            logger.info("Password reset requested for non-existent user (lookup id unavailable)")
    42→
    43→        # Delete any existing active tokens for this user (if user exists)
    44→        if user:
    45→            ResetPasswordToken.objects.filter(user=user).delete()
    46→
    47→        # Truncate user agent to prevent database constraint violations
    48→        # The ResetPasswordToken.user_agent field has max_length=256
    49→        original_user_agent = request.META.get("HTTP_USER_AGENT", "")
    50→        if len(original_user_agent) > 256:
    51→            request.META["HTTP_USER_AGENT"] = original_user_agent[:256]
    52→            logger.warning(
    53→                f"Truncated user agent from {len(original_user_agent)} to 256 characters "
    54→                f"for password reset request. Original: {original_user_agent[:100]}..."
    55→            )
    56→
    57→        # Proceed with the default token generation
    58→        return super().post(request, *args, **kwargs)
    59→
    60→
    61→class EvvyResetPasswordRequestToken(CustomResetPasswordRequestToken):
    62→    throttle_classes = [LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle]
    63→
    64→    def post(self, request, *args, **kwargs):
    65→        email = request.data.get("email")
    66→        user_id = None
    67→
    68→        if email:
    69→            # Try to get user ID for logging without exposing email
    70→            try:
    71→                user = User.objects.get(email=email)
    72→                user_id = user.id
    73→                logger.info(f"Password reset request initiated for user ID {user_id}")
    74→            except User.DoesNotExist:
    75→                logger.info("Password reset request initiated for non-existent user")
    76→        else:
    77→            logger.warning("Password reset request attempted without email")
    78→
    79→        response = super().post(request, *args, **kwargs)
    80→
    81→        if response.status_code == 200:
    82→            if user_id:
    83→                logger.info(f"Password reset request successful for user ID {user_id}")
    84→            else:
    85→                logger.info("Password reset request successful")
    86→        elif response.status_code == 400:
    87→            error_data = response.data if hasattr(response, "data") else {}
    88→            user_context = f"for user ID {user_id} " if user_id else ""
    89→            logger.warning(
    90→                f"Password reset request failed {user_context}- Status: 400, Response data: {error_data}"
    91→            )
    92→        else:
    93→            user_context = f"for user ID {user_id} " if user_id else ""
    94→            logger.warning(
    95→                f"Password reset request unexpected response {user_context}- Status: {response.status_code}"
    96→            )
    97→
    98→        return response
    99→
   100→
... [85 more lines truncated]
```


**Step 36:** `read("backend/api/v1/views/subscription.py")`


```
1→"""
     2→API for accessing subscription services
     3→"""
     4→
     5→import logging
     6→
     7→from rest_framework import status
     8→from rest_framework.request import Request
     9→from rest_framework.response import Response
    10→
    11→from api.v1.views.views import evvy_api_view
    12→from ecomm.constants import RETEST_DISCOUNT_CODE
    13→from subscriptions.models import ProductType
    14→from subscriptions.subscription_service import SubscriptionService
    15→
    16→logger = logging.getLogger("evvy.subscription")
    17→
    18→
    19→@evvy_api_view(["GET"])
    20→def get_subscription(request: Request):
    21→    user = request.user
    22→    subscription_info = SubscriptionService(user).get_subscription()
    23→    if subscription_info:
    24→        return Response(subscription_info.model_dump(), status=status.HTTP_200_OK)
    25→    return Response("User does not have a subscription account", status=status.HTTP_404_NOT_FOUND)
    26→
    27→
    28→@evvy_api_view(["GET"])
    29→def get_active_subscription_by_product_sku(request: Request, sku: str):
    30→    user = request.user
    31→    subscription_response = SubscriptionService(user).get_all_subscriptions()
    32→    info = next((sub for sub in subscription_response.subscriptions if sub.sku == sku), None)
    33→    if info:
    34→        return Response(info.model_dump(), status=status.HTTP_200_OK)
    35→    return Response("User does not have a subscription account", status=status.HTTP_404_NOT_FOUND)
    36→
    37→
    38→@evvy_api_view(["GET"])
    39→def get_subscriptions(request: Request):
    40→    user = request.user
    41→    subscription_info = SubscriptionService(user).get_all_subscriptions_with_cache()
    42→    if subscription_info and subscription_info.subscriptions:
    43→        return Response(subscription_info.model_dump(), status=status.HTTP_200_OK)
    44→    return Response("User does not have any subscriptions", status=status.HTTP_404_NOT_FOUND)
    45→
    46→
    47→@evvy_api_view(["GET"])
    48→def get_subscription_by_id(request: Request, subscription_id: str):
    49→    user = request.user
    50→    subscription_info = SubscriptionService(user).get_subscription_by_id(subscription_id)
    51→    if subscription_info:
    52→        return Response(subscription_info.model_dump(), status=status.HTTP_200_OK)
    53→    return Response("Subscription not found", status=status.HTTP_404_NOT_FOUND)
    54→
    55→
    56→@evvy_api_view(["GET"])
    57→def subscription_exists(request):
    58→    user = request.user
    59→    has_subscription = SubscriptionService(user).has_subscription(ProductType.TEST)
    60→    return Response({"exists": has_subscription})
    61→
    62→
    63→@evvy_api_view(["PUT"])
    64→def swap_subscription(request):
    65→    user = request.user
    66→    subscription_type = request.data.get("subscription_type")
    67→    sub_info = SubscriptionService(user).swap_subscription(subscription_type)
    68→    if sub_info:
    69→        return Response(sub_info.model_dump(), status=status.HTTP_200_OK)
    70→    return Response("User does not have a subscription to update", status=status.HTTP_404_NOT_FOUND)
    71→
    72→
    73→@evvy_api_view(["GET"])
    74→def portal_link(request):
    75→    user = request.user
    76→    portal_link = SubscriptionService(user).get_subscription_portal_link()
    77→    if portal_link:
    78→        return Response({"url": portal_link})
    79→    else:
    80→        logger.warning(
    81→            f"Tried to get Recharge account login for user {user.id} without recharge account."
    82→        )
    83→        return Response(
    84→            "User does not have a subscription account",
    85→            status=status.HTTP_404_NOT_FOUND,
    86→        )
    87→
    88→
    89→@evvy_api_view(["PUT"])
    90→def update_next_subscription_charge(request, subscription_id: str | None = None):
    91→    user = request.user
    92→    success = SubscriptionService(user).move_next_order_to_today(subscription_id)
    93→    if success:
    94→        return Response({}, status=status.HTTP_200_OK)
    95→    else:
    96→        # either there is no recharge customer ID or subscription does not exist
    97→        return Response(
    98→            "User does not have a subscription to update",
    99→            status=status.HTTP_404_NOT_FOUND,
   100→        )
... [34 more lines truncated]
```


**Step 37:** `search("permission_classes|authentication_classes|AllowAny|IsAuthenticated|csrf_exempt|login_required", path="backend/api/v1/views", glob="*.py", context=1)`


```
No matches found

[Showing results with pagination = limit: 200, offset: 200]
```


**Step 38:** `read("backend/app/middleware")`


```
EISDIR: illegal operation on a directory, read 'backend/app/middleware'
```


**Step 39:** `ls backend/app/middleware/`


```
__init__.py
__pycache__
audit.py
auth.py
logging.py
monitoring.py
tests
```


**Step 40:** `read("backend/api/v1/views/user_tests.py")`


```
1→"""
     2→Views used for bulk exporting a user's data
     3→"""
     4→
     5→import datetime
     6→import logging
     7→from typing import Dict, List, Tuple, TypedDict
     8→
     9→from django.conf import settings
    10→from django.db.models import Q
    11→from django.db.models.functions import Coalesce
    12→from django.urls import reverse
    13→from rest_framework import status
    14→from rest_framework.decorators import action
    15→from rest_framework.exceptions import NotFound
    16→from rest_framework.request import Request
    17→from rest_framework.response import Response
    18→
    19→from accounts.utils import (
    20→    get_fertility_feature_enabled,
    21→    get_store_infection_state_enabled,
    22→    get_urine_test_enabled,
    23→)
    24→from analytics.braze.constants import BrazeEventName, BrazeEventProperties
    25→from analytics.service import track_event
    26→from analytics.tasks import (
    27→    send_additional_tests_checkout_created_event,
    28→    send_health_history_completed_klaviyo_event,
    29→)
    30→from api.v1 import serializers
    31→from api.v1.serializers.utils import get_expan_upsell_enabled
    32→from api.v1.utils.utils import get_normalized_bacteria_results_and_score_data
    33→from api.v1.views.views import EvvyUserViewSet
    34→from app.utils import is_production_env
    35→from associations.models import HealthAssociationLink
    36→from care.models import Product
    37→from care.service import (
    38→    filter_antibiotic_antifungal_treatments_if_previously_purchased,
    39→    get_all_available_treatments_for_a_la_care,
    40→    get_all_available_treatments_for_test,
    41→    get_all_available_treatments_for_user,
    42→    get_recommended_treatments_for_a_la_care_for_test,
    43→)
    44→from consults.service import get_additional_recommended_products
    45→from consults.utils import (
    46→    create_lab_order_with_consent_for_test,
    47→    submit_lab_order_for_test,
    48→)
    49→from ecomm.constants import (
    50→    EXPANDED_PCR_ADD_ON_VARIANT_ID,
    51→    MPT_VOUCHER_SKU,
    52→    RETEST_DISCOUNT_CODE,
    53→    SHOPIFY_VAGINAL_HEALTH_TEST_VARIANT_ID,
    54→)
    55→from ecomm.models.order import Order
    56→from ecomm.models.product import Product as EcommProduct
    57→from ecomm.shopify.shopify import ShopifyAPIClient
    58→from ecomm.tasks import (
    59→    add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult,
    60→)
    61→from health_history.models import HealthContext
    62→from health_history.utils import get_health_history_type
    63→from providers.utils import (
    64→    associate_patient_email_to_test_order_by_test,
    65→    associate_provider_test_order_to_test_by_email,
    66→)
    67→from test_results.constants import (
    68→    DISRUPTIVE_SCORE,
    69→    DISRUPTIVE_SCORE_DESCRIPTION,
    70→    DUPLICATE_TEST_HASHES_ALREADY_ACTIVATED,
    71→    DUPLICATE_TEST_HASHES_NOT_ACTIVATED,
    72→    PROTECTIVE_SCORE,
    73→    PROTECTIVE_SCORE_DESCRIPTION,
    74→    SHANNON_DIVERSITY_SCORE_SLUG,
    75→    VALENCIA_TYPE_DOMINANT_CATEGORIZATION,
    76→)
    77→from test_results.models.bacteria import Bacteria
    78→from test_results.models.infection_state import TestResultInfectionState
    79→from test_results.models.result_module import ResultModule
    80→from test_results.models.test import Test, UrineTest
    81→from test_results.post_processing_utils import (
    82→    get_or_create_recommended_treatment_program,
    83→)
    84→from test_results.service import (
    85→    get_user_current_test,
    86→    get_user_latest_ready_vaginal_test,
    87→)
    88→from test_results.utils import (
    89→    attach_user_to_test,
    90→    check_test_deactivated,
    91→    check_test_expired,
    92→    get_bacteria_association_conditions,
    93→    get_community_type_info_for_test,
    94→    get_current_test,
    95→    get_current_urine_test,
    96→    get_other_unactivated_tests_from_order,
    97→    get_pdf_report_presigned_url,
    98→    get_percent_tests_with_community_type,
    99→    get_score_range_category,
   100→    get_shannon_diversity_score_copy,
... [1467 more lines truncated]
```


Now let me look at the internal views and middleware:


**Step 41:** `read("backend/app/middleware/auth.py")`


```
1→import logging
     2→
     3→from django.contrib.auth.models import User
     4→from django.http import HttpResponse, HttpResponseRedirect
     5→from django.utils.deprecation import MiddlewareMixin
     6→
     7→from rest_framework_simplejwt.exceptions import InvalidToken
     8→from rest_framework_simplejwt.tokens import RefreshToken
     9→
    10→from api.v1.authentication import EvvyJWTAuthentication
    11→
    12→request_logger = logging.getLogger("evvy.request.auth")
    13→
    14→
    15→class HttpResponseUnauthorized(HttpResponse):
    16→    status_code = 401
    17→
    18→
    19→def get_jwt_user(request):
    20→    if request.user and request.user.is_authenticated:
    21→        return request.user
    22→    jwt_authentication = EvvyJWTAuthentication()
    23→    resp = jwt_authentication.authenticate(request)
    24→    if resp:
    25→        return resp[0]
    26→    return None
    27→
    28→
    29→def is_user_allowed_to_impersonate(user):
    30→    return user.is_staff and user.groups.filter(name="user-impersonation").exists()
    31→
    32→
    33→class ImpersonateMiddleware(MiddlewareMixin):
    34→    def process_request(self, request):
    35→        if "__impersonate" in request.GET:
    36→            try:
    37→                user = get_jwt_user(request)
    38→                if is_user_allowed_to_impersonate(user):
    39→                    try:
    40→                        impersonated_user = User.objects.get(username=request.GET["__impersonate"])
    41→                    except User.DoesNotExist:
    42→                        request_logger.warning(
    43→                            "Attempted impersonation for %s: User does not exist"
    44→                            % request.GET["__impersonate"]
    45→                        )
    46→                        return
    47→                    refresh = RefreshToken.for_user(impersonated_user)
    48→                    access_token = str(refresh.access_token)
    49→                    request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
    50→            except InvalidToken as e:
    51→                return HttpResponseUnauthorized("invalid token")
    52→
    53→    def process_response(self, request, response):
    54→        if "__impersonate" in request.GET and is_user_allowed_to_impersonate(request.user):
    55→            if isinstance(response, HttpResponseRedirect):
    56→                location = response["Location"]
    57→                if "?" in location:
    58→                    location += "&"
    59→                else:
    60→                    location += "?"
    61→                location += f"__impersonate={request.GET['__impersonate']}"
    62→                response["Location"] = location
    63→        return response
    64→
```


**Step 42:** `ls backend/api/internal/`


```
__init__.py
__pycache__
serializers
tests
urls.py
utils.py
views.py
```


**Step 43:** `read("backend/api/internal/views.py")`


```
1→import logging
     2→
     3→from django.contrib.auth import logout
     4→from django.contrib.auth.models import User
     5→from django.db.models import Q
     6→from django.http import Http404
     7→from django.utils import timezone
     8→from rest_framework import serializers, status, viewsets
     9→from rest_framework.authentication import SessionAuthentication
    10→from rest_framework.decorators import action, api_view, authentication_classes
    11→from rest_framework.pagination import PageNumberPagination
    12→from rest_framework.permissions import BasePermission, IsAuthenticated
    13→from rest_framework.response import Response
    14→from rest_framework.views import APIView
    15→
    16→from drf_spectacular.utils import (
    17→    OpenApiParameter,
    18→    OpenApiResponse,
    19→    OpenApiTypes,
    20→    PolymorphicProxySerializer,
    21→    extend_schema,
    22→    inline_serializer,
    23→)
    24→
    25→from accounts.models import (
    26→    GROUP_NAME_RESULTS_MANAGERS,
    27→    GROUP_NAME_USER_SUMMARY_ASSISTANT_USERS,
    28→)
    29→from ai.models import AISummary, AssistantThreadMessage
    30→from ai.service import (
    31→    ask_sally,
    32→    summarize_intercom_interactions_for_intercom_conversation_id,
    33→    summarize_survicate_response_for_survey_id,
    34→)
    35→from ai.utils import get_cost_from_openai_response
    36→from api.internal.serializers.ai import (
    37→    AISummarySerializer,
    38→    AssistantThreadMessageSerializer,
    39→)
    40→from api.internal.serializers.plan_profiles import (
    41→    PlanItemSerializer,
    42→    PlanProfileSerializer,
    43→)
    44→from api.internal.serializers.results import (
    45→    TestResultListSerializer,
    46→    TestResultSerializer,
    47→)
    48→from api.internal.serializers.timeline import (
    49→    CareEventSerializer,
    50→    SupportInteractionEventSerializer,
    51→    TestEventSerializer,
    52→    UrineTestEventSerializer,
    53→)
    54→from api.internal.serializers.timeline.coaching_call import CoachingCallEventSerializer
    55→from api.internal.serializers.users import (
    56→    InternalUserSerializer,
    57→    UserSummaryListSerializer,
    58→    UserSummarySerializer,
    59→)
    60→from api.internal.utils import (
    61→    create_summary_sally_thread_for_user_sync,
    62→    get_user_timeline,
    63→)
    64→from coaching.models import CoachUserAssignment
    65→from test_results.models.mngs import TestResult
    66→from test_results.models.plan import (
    67→    PlanItem,
    68→    PlanItemAddition,
    69→    PlanItemException,
    70→    PlanProfile,
    71→)
    72→from test_results.models.test import Test
    73→from test_results.tasks import create_test_result_tagset
    74→from test_results.utils import plan_items_for_test, release_test_results
    75→from utils.mixins import AIMessageMixin
    76→
    77→
    78→logger = logging.getLogger("evvy.api.internal.views")
    79→
    80→
    81→def evvy_logout_api_view(*args, **kwargs):
    82→    def decorator(view_func):
    83→        # Apply the authentication_classes decorator
    84→        view_func = authentication_classes([SessionAuthentication])(view_func)
    85→
    86→        # Apply the api_view decorator last
    87→        view_func = api_view(*args, **kwargs)(view_func)
    88→        return view_func
    89→
    90→    return decorator
    91→
    92→
    93→class EvvyInternalViewSet(viewsets.ModelViewSet):
    94→    permission_classes = [IsAuthenticated]
    95→    authentication_classes = [SessionAuthentication]
    96→
    97→
    98→class EvvyInternalReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    99→    permission_classes = [IsAuthenticated]
   100→    authentication_classes = [SessionAuthentication]
... [566 more lines truncated]
```


**Step 44:** `read("backend/app/views.py")`


```
1→# -*- coding: utf-8 -*-
     2→from django.conf import settings
     3→from django.contrib.auth.views import LoginView
     4→from django.http import HttpResponse
     5→from django.template.defaultfilters import safe
     6→from django.urls import reverse
     7→
     8→from django_otp.admin import OTPAdminAuthenticationForm
     9→
    10→from app.utils import is_production_env
    11→
    12→
    13→def health(request):
    14→    return HttpResponse("Healthy")
    15→
    16→
    17→def unhealthy(request):
    18→    raise Exception("raising an exception on purpose")
    19→
    20→
    21→class EvvyLoginView(LoginView):
    22→    template_name = "login.html" if is_production_env() else "admin/login.html"
    23→    authentication_form = OTPAdminAuthenticationForm if is_production_env() else None
    24→
    25→    extra_context = {"site_title": "Django site admin"}
    26→
    27→    def get_success_url(self):
    28→        redirect_to = self.request.GET.get("next", "")
    29→
    30→        if not redirect_to or not redirect_to.startswith("/"):
    31→            # Validate the URL before redirecting
    32→            if redirect_to.startswith(settings.INTERNAL_SITE_URL):
    33→                return safe(redirect_to)
    34→            return reverse("admin:index")
    35→        return redirect_to
    36→
```


Now let me check the remaining v1 views for auth patterns, and also look at the settings for MIDDLEWARE:


**Step 45:** `search("MIDDLEWARE", path="backend/app/settings.py", context=3)`


```
240-    "transactional_email",
241-]
242-
243:MIDDLEWARE = [
244-    "django.middleware.security.SecurityMiddleware",
245-    # first, besides security middleware
246-    "whitenoise.middleware.WhiteNoiseMiddleware",
```


**Step 46:** `read("backend/api/v1/views/orders.py", offset=1, limit=60)`


```
1→import logging
     2→
     3→from django.db.models import Q
     4→from rest_framework import status
     5→from rest_framework.response import Response
     6→
     7→from api.v1.serializers import OrderSerializer
     8→from api.v1.views.views import EvvyUserAPIView
     9→from consults.models import ConsultOrder
    10→from ecomm.models.order import Order, RelatedOrder
    11→from ecomm.services.cart import attach_order_to_user, get_is_order_open
    12→from ecomm.shopify.tasks import (
    13→    process_unprocessed_shopify_orders_by_checkout_token,
    14→    process_unprocessed_shopify_orders_by_email,
    15→)
    16→
    17→
    18→logger = logging.getLogger("evvy.orders")
    19→
    20→
    21→class OrdersView(EvvyUserAPIView):
    22→    def get_permissions(self):
    23→        if self.request.method == "POST":
    24→            return []  # No auth required for POST
    25→        return super().get_permissions()  # Auth required for GET/PUT
    26→
    27→    def get(self, request, format=None):
    28→        """
    29→        Returns all orders for requesting user
    30→        Right now just returns "open" orders which are defined
    31→        as test or ungated rx orders where the test has not yet been activated
    32→        and the ungated rx order has not yet been attached to a consult
    33→
    34→        Note: currently does NOT support pagination
    35→        """
    36→        user_orders = request.user.order_set.exclude(status=Order.STATUS_CANCELLED).order_by(
    37→            "-create_date"
    38→        )
    39→        filter_open = request.query_params.get("open", False)
    40→        if filter_open:
    41→            ungated_rx_or_test_orders = user_orders.filter(
    42→                Q(order_type=Order.ORDER_TYPE_UNGATED_RX)
    43→                | Q(business_verticals__contains=Order.VERTICAL_TEST)
    44→            )
    45→            # now filter ungated_rx_orders to only include ones which do not have ConsultOrder records
    46→            all_orders = []
    47→            for order in ungated_rx_or_test_orders:
    48→                if get_is_order_open(order):
    49→                    all_orders.append(order)
    50→        else:
    51→            # if not unattached, just return all orders but limit to 50 orders
    52→            limit = int(request.query_params.get("limit", 50))
    53→            all_orders = list(user_orders.all()[:limit])
    54→
    55→        resp_data = OrderSerializer(all_orders, many=True).data
    56→
    57→        return Response(resp_data, status=status.HTTP_200_OK)
    58→
    59→    def put(self, request, format=None):
    60→        """
```


**Step 47:** `read("backend/app/settings.py", offset=243, limit=30)`


```
243→MIDDLEWARE = [
   244→    "django.middleware.security.SecurityMiddleware",
   245→    # first, besides security middleware
   246→    "whitenoise.middleware.WhiteNoiseMiddleware",
   247→    "django.contrib.sessions.middleware.SessionMiddleware",
   248→    "corsheaders.middleware.CorsMiddleware",
   249→    "django.middleware.common.CommonMiddleware",
   250→    "django.middleware.csrf.CsrfViewMiddleware",
   251→    "django.contrib.auth.middleware.AuthenticationMiddleware",
   252→    "django.contrib.messages.middleware.MessageMiddleware",
   253→    "django.middleware.clickjacking.XFrameOptionsMiddleware",
   254→    "django_otp.middleware.OTPMiddleware",
   255→    "csp.middleware.CSPMiddleware",
   256→    "django_permissions_policy.PermissionsPolicyMiddleware",
   257→    # logs user ID in newrelic on exception
   258→    "app.middleware.ExceptionContextMiddleware",
   259→    # custom request logging with user ID
   260→    "app.middleware.RequestLoggingMiddleware",
   261→    # custom request middleware for impersonating other users
   262→    "app.middleware.ImpersonateMiddleware",
   263→    "app.middleware.EvvyAuditLogMiddleware",
   264→    # checkout error monitoring for newrelic
   265→    "app.middleware.CheckoutMonitoringMiddleware",
   266→]
   267→
   268→AUDITLOG_INCLUDE_ALL_MODELS = True
   269→AUDITLOG_EXCLUDE_TRACKING_MODELS = ("sessions", "otp_static")
   270→
   271→ROOT_URLCONF = "app.urls"
   272→
```


**Step 48:** `read("backend/api/v1/views/orders.py", offset=60, limit=60)`


```
60→        """
    61→        Attempts to attach an order to the current logged in user
    62→        """
    63→        checkout_id = request.data.get("checkout_id", None)
    64→        order_number = request.data.get("order_number", None)
    65→
    66→        if checkout_id:
    67→            order = Order.objects.filter(checkout_id=checkout_id).first()
    68→        elif order_number:
    69→            order = Order.objects.filter(order_number=order_number).first()
    70→
    71→        if not order:
    72→            return Response("Order not found", status=status.HTTP_404_NOT_FOUND)
    73→
    74→        # Attempt to attach the order to the user
    75→        attach_order_to_user(request.user, order.order_number)
    76→        order.refresh_from_db()
    77→
    78→        resp_data = OrderSerializer(order).data
    79→        return Response(resp_data, status=status.HTTP_200_OK)
    80→
    81→    def post(self, request, format=None):
    82→        """
    83→        Process the order synchronously if it hasn't been processed yet
    84→        Returns relevant order data to redirect the user to after the order is finished processing.
    85→        """
    86→        checkout_id = request.data.get("checkout_id", None)
    87→        checkout_token = request.data.get("checkout_token", None)
    88→        order_email = request.data.get("order_email", None)
    89→
    90→        # If the order does not exist yet in our system, process it synchronously
    91→        order = None
    92→        if checkout_id:
    93→            order = Order.objects.filter(checkout_id=checkout_id).first()
    94→        elif checkout_token:
    95→            order = Order.objects.filter(checkout_token=checkout_token).first()
    96→
    97→        if not order:
    98→            processed_orders = []
    99→            if checkout_token:
   100→                processed_orders = process_unprocessed_shopify_orders_by_checkout_token(
   101→                    checkout_token
   102→                )
   103→            elif checkout_id and order_email:
   104→                processed_orders = process_unprocessed_shopify_orders_by_email(order_email)
   105→
   106→            if len(processed_orders) > 0:
   107→                if len(processed_orders) > 1:
   108→                    processed_order_numbers = (", ").join(
   109→                        [po.order_number for po in processed_orders]
   110→                    )
   111→                    logger.warning(
   112→                        f"Multiple unprocessed orders {processed_order_numbers} found for {order_email}"
   113→                    )
   114→                order = processed_orders[0]
   115→
   116→                # Set the checkout token here because it is not available in the order object returned from Shopify's graphql order API
   117→                order.checkout_token = checkout_token
   118→                order.save()
   119→            else:
```


**Step 49:** `read("backend/api/v1/views/cart.py", offset=1, limit=60)`


```
1→import logging
     2→
     3→from rest_framework import status
     4→from rest_framework.decorators import action
     5→from rest_framework.response import Response
     6→
     7→from api.v1 import serializers
     8→from api.v1.views.views import EvvyUserViewSet
     9→from consults.models import Consult
    10→from ecomm.constants import CONSULT_UID, PURCHASE_TYPE
    11→from ecomm.models.cart import Cart
    12→from ecomm.monitoring import track_cart_creation
    13→from ecomm.services.cart import CartService
    14→from ecomm.utils import cart_requires_consult
    15→
    16→
    17→logger = logging.getLogger("evvy.api.cart")
    18→
    19→
    20→class CartViewSet(EvvyUserViewSet):
    21→    """
    22→    API view for ecommerce shenanigans. Get latest active cart for user, add to cart, checkout etc.
    23→    """
    24→
    25→    serializer_class = serializers.CartSerializer
    26→
    27→    def get_queryset(self):
    28→        # only gets active carts, ordered by most recently active
    29→        return self.request.user.cart_set.filter(status=Cart.STATUS_ACTIVE).order_by(
    30→            "-last_active_at"
    31→        )
    32→
    33→    def create(self, request, *args, **kwargs):
    34→        # try to get the latest active cart, if none exists, then create a new one
    35→        cart = self.get_queryset().first()
    36→        cart_was_created = False
    37→        if not cart or cart.status != Cart.STATUS_ACTIVE:
    38→            cart = Cart.objects.create(user=request.user, status=Cart.STATUS_ACTIVE)
    39→            cart_was_created = True
    40→
    41→        if cart_was_created:
    42→            session_id = request.headers.get("X-Session-ID") or request.META.get(
    43→                "HTTP_X_SESSION_ID"
    44→            )
    45→            track_cart_creation(cart, source="api", session_id=session_id)
    46→
    47→        data = self.serializer_class(cart).data
    48→        return Response(data, status=status.HTTP_201_CREATED)
    49→
    50→    def update(self, request, *args, **kwargs):
    51→        # unsupported
    52→        return Response("Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    53→
    54→    @action(methods=["post", "delete"], detail=True)
    55→    def items(self, request, *args, **kwargs):
    56→        """
    57→        Add items to specific cart or deletes specified items
    58→        """
    59→        cart = self.get_object()
    60→        data = request.data
```


**Step 50:** `read("backend/api/v1/views/announcements.py")`


```
1→from django.utils import timezone
     2→from rest_framework import status
     3→from rest_framework.response import Response
     4→
     5→from api.v1.serializers import AnnouncementSerializer
     6→from api.v1.views.views import EvvyUserAPIView
     7→
     8→
     9→class AnnouncementsView(EvvyUserAPIView):
    10→    """
    11→    View that is called by the frontend to get the announcements per user
    12→    and to modify the viewed state of an announcement.
    13→    """
    14→
    15→    def get(self, request):
    16→        user = request.user
    17→        announcements = user.announcement_set.filter(published=True).order_by("-published_at")
    18→
    19→        serializer = AnnouncementSerializer(announcements, many=True)
    20→        return Response(serializer.data)
    21→
    22→    def post(self, request):
    23→        announcement_id = request.data.get("announcement_id")
    24→        user = request.user
    25→        announcement = user.announcement_set.get(id=announcement_id)
    26→        announcement.viewed_at = timezone.now()
    27→        announcement.save()
    28→
    29→        return Response(status=status.HTTP_200_OK)
    30→
```


**Step 51:** `read("backend/api/v1/views/userconfig.py", offset=1, limit=50)`


```
1→"""
     2→User config API
     3→"""
     4→
     5→import logging
     6→
     7→from django.conf import settings
     8→from django.contrib.auth.models import User
     9→from rest_framework import status
    10→from rest_framework.response import Response
    11→
    12→from drf_spectacular.utils import extend_schema
    13→
    14→from accounts.models import GROUP_NAME_PROVIDERS
    15→from accounts.utils import (
    16→    get_bv_subtypes_enabled,
    17→    get_fertility_feature_enabled,
    18→    get_male_partner_enabled,
    19→    get_new_pdp_enabled,
    20→    get_provider_profile,
    21→    get_shop_all_enabled,
    22→    get_urine_test_enabled,
    23→    get_user_profile,
    24→    is_symptom_relief_experiment,
    25→    user_has_answered_research_consent,
    26→    user_has_verified_email,
    27→)
    28→from analytics.braze.constants import BrazeEventName
    29→from analytics.service import identify_user, track_event
    30→from api.v1.serializers.userconfig import UserConfigSerializer
    31→from api.v1.utils.male_partner import create_male_partner_consult_and_checkout_url
    32→from api.v1.views.views import EvvyUserAPIView
    33→from app.utils import get_environment, is_production_env
    34→from care.service import can_user_purchase_vaginitis_care, get_user_eligible_for_any_vaginitis_care
    35→from care.utils import user_has_completed_vaginitis_care
    36→from consults.utils import user_has_unread_message
    37→from ecomm.models.order import PartnerRelationship
    38→from subscriptions.subscription_service import SubscriptionService
    39→from test_results.models.test import Test
    40→from test_results.utils import is_my_plan_v2_enabled
    41→from utils.time import get_current_time
    42→
    43→
    44→logger = logging.getLogger("evvy.user_config_api")
    45→
    46→
    47→def get_user_coaching_call_count(user) -> int:
    48→    """
    49→    Get total number of completed coaching calls for user across all tests.
    50→
```


**Step 52:** `read("backend/api/v1/views/consent.py")`


```
1→"""
     2→Consent API
     3→"""
     4→
     5→from rest_framework import status
     6→from rest_framework.response import Response
     7→
     8→from accounts.models import Consent
     9→from accounts.utils import user_has_answered_research_consent
    10→from api.v1.views.views import EvvyUserAPIView
    11→from utils.time import get_current_time
    12→
    13→
    14→class ConsentView(EvvyUserAPIView):
    15→    """
    16→    Allows user to accept/deny a consent
    17→    We started officially tracking consent on 2022-11-08
    18→    """
    19→
    20→    def post(self, request, format=None):
    21→        user = request.user
    22→
    23→        agreed = request.data.get("agreed", None)
    24→        if agreed is None or not isinstance(agreed, bool):
    25→            return Response("Invalid consent agreed response", status=status.HTTP_400_BAD_REQUEST)
    26→
    27→        # if user has already submitted their response, don't let them change it and just return successful
    28→        if user_has_answered_research_consent(user):
    29→            return Response("success", status=status.HTTP_201_CREATED)
    30→
    31→        # otherwise, create the object and store the response
    32→        consent = Consent.objects.create(
    33→            user=user,
    34→            consent_type=Consent.CONSENT_TYPE_RESEARCH,
    35→            agreed=agreed,
    36→            consent_submitted_at=get_current_time(),
    37→        )
    38→        return Response("success", status=status.HTTP_201_CREATED)
    39→
```


**Step 53:** `read("backend/api/v1/views/account_order_transfer_verification.py")`


```
1→from django.conf import settings
     2→from django.contrib.auth.models import User
     3→from rest_framework import status
     4→from rest_framework.response import Response
     5→from rest_framework.views import APIView
     6→
     7→from accounts.models import OrderTransferVerification
     8→from api.v1.serializers.order import OrderSerializer
     9→from api.v1.views.views import EvvyUserAPIView
    10→from ecomm.models.order import Order
    11→from ecomm.services.cart import remove_order_from_current_associated_consults
    12→from ecomm.tasks import add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult
    13→from transactional_email.constants import TEMPLATE_ACCOUNT_ORDER_TRANSFER
    14→from transactional_email.utils import get_email_context, send_templated_email
    15→
    16→
    17→class AccountOrderTransferVerification(EvvyUserAPIView):
    18→    """
    19→    For initiating order transfers between orders with an email that does not match their current evvy account email.
    20→    Currently, OrderTransferVerification emails are sent only for ungated RX customers.
    21→    """
    22→
    23→    def get(self, request, format=None):
    24→        """
    25→        Get open orders that have had transferred initiated by the user.
    26→        - Email is not yet verified by user
    27→        - Order is not yet attached to any user
    28→        - Order has not been cancelled
    29→        """
    30→        user = request.user
    31→        unverified_emails = OrderTransferVerification.objects.filter(user=user, verified=False)
    32→
    33→        orders = []
    34→        for transfer_email in unverified_emails:
    35→            order = transfer_email.ecomm_order
    36→            if order.status != Order.STATUS_CANCELLED and order not in orders:
    37→                has_verified_email = OrderTransferVerification.objects.filter(
    38→                    user=user, order_email=order.email, verified=True, ecomm_order=order
    39→                ).exists()
    40→                if not has_verified_email and order.order_type == Order.ORDER_TYPE_UNGATED_RX:
    41→                    orders.append(order)
    42→
    43→        serializer = OrderSerializer(orders, many=True)
    44→        return Response(serializer.data, status=status.HTTP_200_OK)
    45→
    46→    def post(self, request, format=None):
    47→        """
    48→        Send verification emails to the order email for each order passed in.
    49→        """
    50→        user = request.user
    51→        order_numbers = request.data.get("orders", [])
    52→        orders = Order.objects.filter(order_number__in=order_numbers)
    53→
    54→        for order in orders:
    55→            # create instead of get_or_create in case they click on a previous order email
    56→            account_transfer_verification_email = OrderTransferVerification.objects.create(
    57→                user=user,
    58→                ecomm_order=order,
    59→                order_email=order.email,
    60→                verified=False,
    61→            )
    62→
    63→            # send an e-mail to the user's order email for each order they need to verify
    64→            verify_url = "{}/order-transfer-confirm/?hash={}".format(
    65→                settings.SITE_URL, account_transfer_verification_email.hash
    66→            )
    67→
    68→            context = get_email_context(
    69→                user,
    70→                {
    71→                    "order_number": order.order_number,
    72→                    "order_transfer_email": user.email,
    73→                    "verify_url": verify_url,
    74→                },
    75→            )
    76→            success, error = send_templated_email(
    77→                order.email, TEMPLATE_ACCOUNT_ORDER_TRANSFER, context=context
    78→            )
    79→
    80→            if error:
    81→                return Response(error, status=status.HTTP_400_BAD_REQUEST)
    82→
    83→        return Response("Order transfer emails sent", status=status.HTTP_200_OK)
    84→
    85→
    86→class AccountOrderTransferConfirmVerification(APIView):
    87→    """
    88→    Allows the user to confirm an order transfer to their account.
    89→    User can be unauthenticated.
    90→    """
    91→
    92→    def post(self, request, format=None):
    93→        verification_hash = request.data.get("hash", None)
    94→        if not verification_hash:
    95→            return Response("Missing hash", status=status.HTTP_400_BAD_REQUEST)
    96→
    97→        # Get the verification email
    98→        verification_email = OrderTransferVerification.objects.filter(
    99→            hash=verification_hash
   100→        ).first()
... [51 more lines truncated]
```


**Step 54:** `read("backend/api/v1/views/webhooks.py", offset=465, limit=150)`


```
465→
   466→@csrf_exempt
   467→@action(methods=["post"], detail=False)
   468→def viome_webhook_view(request):
   469→    """Handle webhooks from Viome for order creation and cancellation."""
   470→    data = request.body
   471→
   472→    # Get the secret, but fail if not configured
   473→    viome_secret = getattr(settings, "VIOME_WEBHOOK_SECRET", None)
   474→    if not viome_secret:
   475→        logger.error("VIOME_WEBHOOK_SECRET not configured")
   476→        return HttpResponse("Configuration error", status=500)
   477→
   478→    access_token = request.headers.get("X-Viome-Access-Token", "")
   479→    verified = _verify_viome_webhook(access_token, viome_secret)
   480→
   481→    if not verified:
   482→        logger.error("Invalid access token for Viome webhook")
   483→        return HttpResponse("Invalid access token", status=403)
   484→
   485→    try:
   486→        payload = json.loads(data)
   487→    except json.JSONDecodeError:
   488→        logger.error("Invalid JSON in Viome webhook payload")
   489→        return HttpResponse("Invalid JSON payload", status=400)
   490→
   491→    # Determine event type based on payload structure
   492→    order_data = payload.get("order", {})
   493→    order_id = order_data.get("id", "N/A")
   494→
   495→    has_line_items = bool(order_data.get("line_items"))
   496→    has_shipping_address = bool(order_data.get("shipping_address"))
   497→    has_cancelled_at = bool(order_data.get("cancelledAt"))
   498→    has_cancel_reason = bool(order_data.get("cancelReason"))
   499→
   500→    if has_cancelled_at and has_cancel_reason:
   501→        event_type = "cancel"
   502→    elif has_line_items and has_shipping_address:
   503→        event_type = "create"
   504→    else:
   505→        event_type = "unknown"
   506→        logger.warning(
   507→            f"Unable to determine event type for Viome webhook. Order ID: {order_id}, Payload: {payload}"
   508→        )
   509→        return HttpResponse("Unable to determine event type", status=400)
   510→
   511→    logger.info(f"Received Viome webhook with event type '{event_type}' for order ID: {order_id}")
   512→
   513→    viome_service = ViomeOrderService()
   514→
   515→    if event_type == "cancel":
   516→        result = viome_service.process_viome_order_cancellation(payload)
   517→    else:
   518→        result = viome_service.process_viome_order(payload)
   519→
   520→    if result["success"]:
   521→        logger.info(f"Successfully processed Viome {event_type} event: {result}")
   522→        return HttpResponse(result["message"], status=200)
   523→    else:
   524→        logger.error(f"Failed to process Viome {event_type} event: {result}")
   525→        return HttpResponse(f"Order processing failed: {result['message']}", status=400)
   526→
   527→
   528→def _verify_viome_webhook(access_token: str, secret_key: str) -> bool:
   529→    """
   530→    Verify Viome webhook using static key verification.
   531→
   532→    Note: Viome is using Shopify Flow which doesn't have the capability of generating
   533→    HMAC signatures, so we use static key verification instead.
   534→    """
   535→    if not access_token or not secret_key:
   536→        return False
   537→
   538→    return hmac.compare_digest(access_token, secret_key)
   539→
   540→
   541→@csrf_exempt
   542→@action(methods=["post"], detail=False)
   543→def junction_webhook_view(request):
   544→    """
   545→    Handle webhooks from Junction for lab test status updates.
   546→
   547→    Junction sends webhooks for order status changes throughout the lab test lifecycle.
   548→    Reference: https://docs.junction.com/lab/workflow/lab-test-lifecycle
   549→
   550→    Webhook URL: /webhooks/junction/
   551→    Headers:
   552→        - svix-id: Message ID
   553→        - svix-timestamp: Message timestamp
   554→        - svix-signature: Message signature (for webhook verification using Svix)
   555→    """
   556→    config = {
   557→        "webhook_secret": settings.JUNCTION_WEBHOOK_SECRET,
   558→    }
   559→
   560→    return JunctionWebhookHandler(config).handle_webhook(request)
   561→
   562→
   563→def _verify_typeform_webhook(data: bytes, signature_header: str, secret_key: str) -> bool:
   564→    """
... [50 more lines truncated]
```


**Step 55:** `read("backend/api/v1/views/my_plan.py", offset=1, limit=60)`


```
1→"""
     2→My Plan API
     3→"""
     4→
     5→from rest_framework import status
     6→from rest_framework.response import Response
     7→
     8→from analytics.braze.constants import BrazeEventName
     9→from analytics.service import track_event
    10→from analytics.tasks import send_viewed_plan_klaviyo_event
    11→from api.v1 import serializers
    12→from api.v1.views.views import EvvyUserAPIView
    13→from subscriptions.subscription_service import SubscriptionService
    14→from test_results.models.mngs import TestResult
    15→from test_results.models.plan import PlanFeedback
    16→from test_results.models.test import Test
    17→from test_results.post_processing_utils import get_or_create_recommended_treatment_program
    18→from test_results.service import get_user_latest_ready_vaginal_test
    19→from test_results.utils import get_test_eligible_for_care, plan_items_for_test
    20→from test_results.utils_old import old_plan_items_for_test
    21→from utils.time import get_current_time
    22→
    23→
    24→class MyPlanView(EvvyUserAPIView):
    25→    """
    26→    View that returns the user's plan items for their latest completed test
    27→    """
    28→
    29→    def get(self, request, format=None):
    30→        test = get_user_latest_ready_vaginal_test(request.user)
    31→
    32→        if not test:
    33→            return Response("Results not ready", status=status.HTTP_404_NOT_FOUND)
    34→
    35→        test_result = test.testresult if hasattr(test, "testresult") else None
    36→        plan_profile = test_result.plan_profile if test_result else None
    37→        user_plan_items = plan_items_for_test(test)
    38→        plan_items_data = serializers.PlanItemSerializer(user_plan_items, many=True).data
    39→
    40→        # whether we should record the viewed plan timestamp
    41→        record_view = request.query_params.get("record_viewed_plan", False)
    42→        # if user is viewing plan for the first time, record it
    43→        if record_view and test_result and not test_result.plan_viewed_at:
    44→            test_result.plan_viewed_at = get_current_time()
    45→            test_result.save()
    46→            send_viewed_plan_klaviyo_event.delay(test.id)
    47→            track_event(
    48→                user=request.user,
    49→                alias_name=request.user.email,
    50→                event_name=BrazeEventName.TREATMENT_PLAN_VIEWED,
    51→                properties={
    52→                    "testHash": test.hash,
    53→                },
    54→            )
    55→
    56→        eligible_for_care = get_test_eligible_for_care(test)
    57→        price = None
    58→        treatment_pathway_slug = None
    59→        if eligible_for_care and test_result:
    60→            recommended_treatment_program = get_or_create_recommended_treatment_program(test_result)
```


**Step 56:** `read("backend/api/v1/views/male_partner_checkout.py")`


```
File does not exist.
```


**Step 57:** `search("class MalePartnerCheckoutView|MalePartnerCheckoutView", path="backend/api/v1", context=3)`


```
backend/api/v1/views/userconfig.py-206-        return Response(serializer.data)
backend/api/v1/views/userconfig.py-207-
backend/api/v1/views/userconfig.py-208-
backend/api/v1/views/userconfig.py:209:class MalePartnerCheckoutView(EvvyUserAPIView):
backend/api/v1/views/userconfig.py-210-    """
backend/api/v1/views/userconfig.py-211-    Generate checkout URL for male partner treatment
backend/api/v1/views/userconfig.py-212-    """
--
backend/api/v1/urls.py-80-    path(r"user-config/", views.UserConfigView.as_view(), name="user-config"),
backend/api/v1/urls.py-81-    path(
backend/api/v1/urls.py-82-        r"male-partner-checkout/",
backend/api/v1/urls.py:83:        views.MalePartnerCheckoutView.as_view(),
backend/api/v1/urls.py-84-        name="male-partner-checkout",
backend/api/v1/urls.py-85-    ),
backend/api/v1/urls.py-86-    path(
```


**Step 58:** `search("class EcommProductView|class CompareView|class TrendsView|class SurveyView|class FAQPageView", path="backend/api/v1", context=5)`


```
backend/api/v1/views/compare.py-25-cache_logger = logging.getLogger("evvy.cache")
backend/api/v1/views/compare.py-26-USE_CACHE = False
backend/api/v1/views/compare.py-27-CACHE_TIME = 60 * 60 * 6  # 6 hours (only used for community type requests)
backend/api/v1/views/compare.py-28-
backend/api/v1/views/compare.py-29-
backend/api/v1/views/compare.py:30:class CompareView(EvvyUserAPIView):
backend/api/v1/views/compare.py-31-    """
backend/api/v1/views/compare.py-32-    Allows comparison against a particular valencia type, or a previous result for the same user.
backend/api/v1/views/compare.py-33-
backend/api/v1/views/compare.py-34-    In all cases, it works the same:
backend/api/v1/views/compare.py-35-    - find the tests that match this comparison type
--
backend/api/v1/views/trends.py-4-from api.v1.serializers import TrendTestSerializer
backend/api/v1/views/trends.py-5-from api.v1.views.views import EvvyUserAPIView
backend/api/v1/views/trends.py-6-from test_results.models.test import Test
backend/api/v1/views/trends.py-7-
backend/api/v1/views/trends.py-8-
backend/api/v1/views/trends.py:9:class TrendsView(EvvyUserAPIView):
backend/api/v1/views/trends.py-10-    def get(self, request, format=None):
backend/api/v1/views/trends.py-11-        tests = request.user.test_set.filter(status=Test.STATUS_READY).order_by("activated_at")
backend/api/v1/views/trends.py-12-
backend/api/v1/views/trends.py-13-        return Response(
backend/api/v1/views/trends.py-14-            {
--
backend/api/v1/views/faqs.py-4-from api.v1.serializers.faq import FAQPageSerializer
backend/api/v1/views/faqs.py-5-from api.v1.views.views import EvvyUserAPIView
backend/api/v1/views/faqs.py-6-from care.models import FAQPage
backend/api/v1/views/faqs.py-7-
backend/api/v1/views/faqs.py-8-
backend/api/v1/views/faqs.py:9:class FAQPageView(EvvyUserAPIView):
backend/api/v1/views/faqs.py-10-    """
backend/api/v1/views/faqs.py-11-    FAQ Page View called by the frontend to get faqs per page
backend/api/v1/views/faqs.py-12-    """
backend/api/v1/views/faqs.py-13-
backend/api/v1/views/faqs.py-14-    def get(self, request):
--
backend/api/v1/views/surveys.py-8-from api.v1 import serializers
backend/api/v1/views/surveys.py-9-from api.v1.views.views import EvvyUserAPIView
backend/api/v1/views/surveys.py-10-from surveys.models import Survey
backend/api/v1/views/surveys.py-11-
backend/api/v1/views/surveys.py-12-
backend/api/v1/views/surveys.py:13:class SurveyView(EvvyUserAPIView):
backend/api/v1/views/surveys.py-14-
backend/api/v1/views/surveys.py-15-    # gets hdyhau survey response for user if exists
backend/api/v1/views/surveys.py-16-    # always returns the survey answer options as _options
backend/api/v1/views/surveys.py-17-    def get(self, request, format=None):
backend/api/v1/views/surveys.py-18-        survey_type = request.query_params.get("survey_type", None)
--
backend/api/v1/views/ecomm_products.py-12-from ecomm.models.product import Product as EcommProduct
backend/api/v1/views/ecomm_products.py-13-
backend/api/v1/views/ecomm_products.py-14-logger = logging.getLogger("api.v1.views.ecomm_products")
backend/api/v1/views/ecomm_products.py-15-
backend/api/v1/views/ecomm_products.py-16-
backend/api/v1/views/ecomm_products.py:17:class EcommProductView(APIView):
backend/api/v1/views/ecomm_products.py-18-    """
backend/api/v1/views/ecomm_products.py-19-    Get an EcommProduct by SKU
backend/api/v1/views/ecomm_products.py-20-    Public endpoint - no authentication required
backend/api/v1/views/ecomm_products.py-21-    """
backend/api/v1/views/ecomm_products.py-22-
```


**Step 59:** `read("backend/api/v1/views/ecomm_products.py")`


```
1→"""
     2→EcommProduct API views
     3→"""
     4→
     5→import logging
     6→
     7→from rest_framework import status
     8→from rest_framework.response import Response
     9→from rest_framework.views import APIView
    10→
    11→from api.v1.serializers.product import EcommProductSerializer
    12→from ecomm.models.product import Product as EcommProduct
    13→
    14→logger = logging.getLogger("api.v1.views.ecomm_products")
    15→
    16→
    17→class EcommProductView(APIView):
    18→    """
    19→    Get an EcommProduct by SKU
    20→    Public endpoint - no authentication required
    21→    """
    22→
    23→    def get(self, request, sku: str, format=None):
    24→        try:
    25→            product = EcommProduct.objects.filter(sku=sku).first()
    26→            if product:
    27→                serializer = EcommProductSerializer(product)
    28→                return Response(serializer.data, status=status.HTTP_200_OK)
    29→            else:
    30→                return Response(
    31→                    {"error": f"Product with SKU '{sku}' not found"}, 
    32→                    status=status.HTTP_404_NOT_FOUND
    33→                )
    34→        except Exception as e:
    35→            logger.exception(f"Error fetching product with SKU '{sku}': {e}")
    36→            return Response(
    37→                {"error": "Failed to fetch product"}, 
    38→                status=status.HTTP_500_INTERNAL_SERVER_ERROR
    39→            )
    40→
```


**Step 60:** `read("backend/api/v1/views/public_features.py")`


```
1→from rest_framework.response import Response
     2→from rest_framework.views import APIView
     3→
     4→from accounts.utils import get_male_partner_enabled
     5→from app.utils import is_production_env
     6→
     7→
     8→class PublicFeaturesView(APIView):
     9→    """
    10→    Public API endpoint that returns system-level feature flags
    11→    for unauthenticated users (e.g., registration flows)
    12→    """
    13→
    14→    authentication_classes = []  # No authentication required
    15→    permission_classes = []  # No permissions required
    16→
    17→    def get(self, request, format=None):
    18→        # Create a dummy user object for feature flag functions that expect a user
    19→        # but actually only check system-level settings
    20→        class DummyUser:
    21→            is_staff = False
    22→
    23→        dummy_user = DummyUser()
    24→
    25→        features = {
    26→            "male_partner_enabled": get_male_partner_enabled(dummy_user),
    27→        }
    28→
    29→        return Response(features)
    30→
```


**Step 61:** `read("backend/api/v1/views/health_context.py", offset=1, limit=60)`


```
1→"""
     2→Views used for bulk exporting a user's data
     3→"""
     4→
     5→import datetime
     6→
     7→from rest_framework import status
     8→from rest_framework.decorators import action
     9→from rest_framework.exceptions import NotFound, ValidationError
    10→from rest_framework.response import Response
    11→
    12→from api.v1 import serializers
    13→from api.v1.views.views import EvvyUserViewSet
    14→from health_history.models import (
    15→    HealthContext,
    16→    HealthContextExtraData,
    17→    HealthContextRelatedDiagnoses,
    18→)
    19→from test_results.models.test import Test
    20→from test_results.utils import get_test_by_hash
    21→
    22→
    23→class HealthContextViewSet(EvvyUserViewSet):
    24→    """
    25→    API for users to see create/see/update health context questions.
    26→
    27→    allows GET, CREATE, UPDATE
    28→    """
    29→
    30→    serializer_class = serializers.HealthContextSerializer
    31→
    32→    lookup_field = "test__hash"  # look up by test hash
    33→    # lookup_value_regex = "[^/]+"
    34→
    35→    def get_object(self):
    36→        """
    37→        Override to support lookup by both test__hash and urine_test__hash
    38→        since HealthContext can be associated with either a vaginal test or urine test.
    39→
    40→        Optimized to avoid unnecessary joins by:
    41→        1. Looking up the test by hash first (indexed lookup)
    42→        2. Verifying the test belongs to the requesting user
    43→        3. Filtering HealthContext by test ID directly (no joins needed)
    44→        """
    45→        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
    46→        test_hash = self.kwargs.get(lookup_url_kwarg)
    47→
    48→        if not test_hash:
    49→            raise ValidationError("Test hash is required")
    50→
    51→        # Look up the test first (efficient hash lookup, avoids joins)
    52→        test = get_test_by_hash(test_hash)
    53→        if not test:
    54→            raise NotFound("Test not found for hash %s" % test_hash)
    55→
    56→        # Verify ownership - return 404 instead of 403 to avoid leaking information
    57→        if test.user != self.request.user:
    58→            raise NotFound("Test %s does not belong to user %s" % (test_hash, self.request.user.id))
    59→
    60→        if test.is_urine_test:
```


**Step 62:** `read("backend/api/v1/views/consult.py", offset=1, limit=60)`


```
1→"""
     2→Views for getting user's consultation data
     3→"""
     4→
     5→from datetime import datetime
     6→import json
     7→import logging
     8→import os
     9→
    10→from django.core.cache import cache
    11→from django.core.exceptions import ValidationError
    12→from rest_framework import status
    13→from rest_framework.decorators import action
    14→from rest_framework.response import Response
    15→
    16→from accounts.models import GROUP_NAME_PROVIDERS
    17→from accounts.utils import get_shop_all_enabled
    18→from analytics.braze.constants import BrazeEventName
    19→from analytics.service import track_event
    20→from analytics.tasks import (
    21→    BRAZE,
    22→    _send_consult_event_with_uti_support,
    23→    send_care_checkout_created_event,
    24→    send_consult_intake_started_klaviyo_event,
    25→    send_updated_treatment_start_date_event,
    26→)
    27→from api.v1 import serializers
    28→from api.v1.utils.male_partner import get_or_create_male_partner_consult
    29→from api.v1.views.views import EvvyUserViewSet
    30→from care.constants import VAGINAL_ESTROGEN_FORMULARY
    31→from care.models import CommonDrug, Product, TreatmentPathway, TreatmentPlan
    32→from care.tasks import create_or_reset_calendar_treatments, update_treatment_end_date
    33→from care.utils import get_treatment_calendar_data, get_treatment_end_date
    34→from consults.constants import ALL_BORIC_ACID_SLUGS, SOOTHE_FOR_ITCHY_SLUG
    35→from consults.models import Consult, ConsultIntake, ConsultOrder
    36→from consults.service import (
    37→    get_additional_recommended_products,
    38→    get_first_consult_prescription_fill,
    39→    pre_populate_intake_address_from_lab_order,
    40→)
    41→from consults.utils import (
    42→    _set_address_info_from_order_shipping_address,
    43→    clean_state_code,
    44→    get_consult_messages,
    45→    mark_consult_message_as_read,
    46→    pre_populate_intake_id_selfie_images_from_past_consult,
    47→    refer_out_based_on_consult_intake,
    48→    send_consult_message,
    49→)
    50→from consults.wheel.tasks import resubmit_consult_photo_id_info_to_wheel, submit_async_consult
    51→from consults.wheel.utils import (
    52→    get_recommended_products_for_consult,
    53→    replace_products_for_allergies,
    54→)
    55→from consults.wheel.wheel import WheelAPIClient
    56→from ecomm.constants import (
    57→    SHOPIFY_CARE_HIGH_PRICE_VARIANT_ID,
    58→    SHOPIFY_CARE_LOW_PRICE_VARIANT_ID,
    59→    SHOPIFY_CARE_STI_TREAMENT_PRICE_VARIANT_ID,
    60→    SHOPIFY_CARE_UTI_TREAMENT_PRICE_VARIANT_ID,
```


Now I have enough data to build a comprehensive auth mapping. Let me do a few more targeted checks:


**Step 63:** `search("class TasksViewSet|TasksViewSet|permission_classes|authentication_classes", path="backend/api/v1/views/tasks.py")`


```
17:class TasksViewSet(viewsets.ViewSet):
```


**Step 64:** `search("class ProductViewSet|class PDPConfigurationViewSet|class CalendarTreatmentViewSet|class TreatmentPlanInterruptionViewSet|class LabOrderIntakeViewSet|class ConsultIntakeViewSet|class ConsultViewSet", path="backend/api/v1/views", context=4)`


```
backend/api/v1/views/pdp_configuration.py-9-)
backend/api/v1/views/pdp_configuration.py-10-from ecomm.models import PDPConfiguration
backend/api/v1/views/pdp_configuration.py-11-
backend/api/v1/views/pdp_configuration.py-12-
backend/api/v1/views/pdp_configuration.py:13:class PDPConfigurationViewSet(ReadOnlyModelViewSet):
backend/api/v1/views/pdp_configuration.py-14-    """
backend/api/v1/views/pdp_configuration.py-15-    ViewSet for PDP configurations
backend/api/v1/views/pdp_configuration.py-16-    """
backend/api/v1/views/pdp_configuration.py-17-
--
backend/api/v1/views/treatment_interruption.py-11-from care.models import TreatmentPlan, TreatmentPlanInterruption
backend/api/v1/views/treatment_interruption.py-12-from utils.time import get_validated_date_from_string
backend/api/v1/views/treatment_interruption.py-13-
backend/api/v1/views/treatment_interruption.py-14-
backend/api/v1/views/treatment_interruption.py:15:class TreatmentPlanInterruptionViewSet(EvvyUserViewSet):
backend/api/v1/views/treatment_interruption.py-16-    serializer_class = TreatmentPlanInterruptionSerializer
backend/api/v1/views/treatment_interruption.py-17-
backend/api/v1/views/treatment_interruption.py-18-    def get_queryset(self):
backend/api/v1/views/treatment_interruption.py-19-        user = self.request.user
--
backend/api/v1/views/calendar_treatment.py-14-from care.models import CalendarTreatment, CalendarTreatmentAdjustment
backend/api/v1/views/calendar_treatment.py-15-from care.service import update_calendar_treatment
backend/api/v1/views/calendar_treatment.py-16-
backend/api/v1/views/calendar_treatment.py-17-
backend/api/v1/views/calendar_treatment.py:18:class CalendarTreatmentViewSet(EvvyUserViewSet):
backend/api/v1/views/calendar_treatment.py-19-    serializer_class = CalendarTreatmentSerializer
backend/api/v1/views/calendar_treatment.py-20-
backend/api/v1/views/calendar_treatment.py-21-    def get_queryset(self):
backend/api/v1/views/calendar_treatment.py-22-        user = self.request.user
--
backend/api/v1/views/products.py-18-)
backend/api/v1/views/products.py-19-from ecomm.models.product import Product as EcommProduct
backend/api/v1/views/products.py-20-
backend/api/v1/views/products.py-21-
backend/api/v1/views/products.py:22:class ProductViewSet(EvvyUserViewSet):
backend/api/v1/views/products.py-23-    """
backend/api/v1/views/products.py-24-    Model view set for getting all care products (aka treatments available)
backend/api/v1/views/products.py-25-    """
backend/api/v1/views/products.py-26-
--
backend/api/v1/views/consult.py-72-
backend/api/v1/views/consult.py-73-logger = logging.getLogger("evvy.consult_api")
backend/api/v1/views/consult.py-74-
backend/api/v1/views/consult.py-75-
backend/api/v1/views/consult.py:76:class ConsultViewSet(EvvyUserViewSet):
backend/api/v1/views/consult.py-77-    serializer_class = serializers.ConsultSerializer
backend/api/v1/views/consult.py-78-
backend/api/v1/views/consult.py-79-    lookup_field = "uid"  # look up by uid and not id
backend/api/v1/views/consult.py-80-
--
backend/api/v1/views/consult.py-624-        mark_consult_message_as_read(consult, message_id)
backend/api/v1/views/consult.py-625-        return Response({}, status=status.HTTP_200_OK)
backend/api/v1/views/consult.py-626-
backend/api/v1/views/consult.py-627-
backend/api/v1/views/consult.py:628:class ConsultIntakeViewSet(EvvyUserViewSet):
backend/api/v1/views/consult.py-629-    """
backend/api/v1/views/consult.py-630-    API for users to see create/see/update health context questions.
backend/api/v1/views/consult.py-631-
backend/api/v1/views/consult.py-632-    allows GET, CREATE, UPDATE
--
backend/api/v1/views/lab_orders.py-19-
backend/api/v1/views/lab_orders.py-20-logger = logging.getLogger("api.v1.views.lab_orders")
backend/api/v1/views/lab_orders.py-21-
backend/api/v1/views/lab_orders.py-22-
backend/api/v1/views/lab_orders.py:23:class LabOrderIntakeViewSet(EvvyUserViewSet):
backend/api/v1/views/lab_orders.py-24-    serializer_class = serializers.LabOrderIntakeSerializer
backend/api/v1/views/lab_orders.py-25-
backend/api/v1/views/lab_orders.py-26-    lookup_field = "test_hash"  # custom lookup field
backend/api/v1/views/lab_orders.py-27-
```


**Step 65:** `read("backend/api/v1/views/pdp_configuration.py")`


```
1→from rest_framework import status
     2→from rest_framework.decorators import action
     3→from rest_framework.response import Response
     4→from rest_framework.viewsets import ReadOnlyModelViewSet
     5→
     6→from api.v1.serializers.pdp_configuration import (
     7→    PDPConfigurationListSerializer,
     8→    PDPConfigurationSerializer,
     9→)
    10→from ecomm.models import PDPConfiguration
    11→
    12→
    13→class PDPConfigurationViewSet(ReadOnlyModelViewSet):
    14→    """
    15→    ViewSet for PDP configurations
    16→    """
    17→
    18→    queryset = PDPConfiguration.objects.filter(is_active=True)
    19→    serializer_class = PDPConfigurationSerializer
    20→
    21→    def get_serializer_class(self):
    22→        if self.action == "list":
    23→            return PDPConfigurationListSerializer
    24→        return PDPConfigurationSerializer
    25→
    26→    def get_queryset(self):
    27→        queryset = super().get_queryset()
    28→        # Filter by slug if provided
    29→        slug = self.request.query_params.get("slug", None)
    30→        if slug:
    31→            queryset = queryset.filter(slug=slug)
    32→
    33→        # Filter by care product if provided
    34→        care_product_slug = self.request.query_params.get("care_product_slug", None)
    35→        if care_product_slug:
    36→            queryset = queryset.filter(care_product__slug=care_product_slug)
    37→
    38→        # Filter by ecomm product if provided
    39→        ecomm_product_sku = self.request.query_params.get("ecomm_product_sku", None)
    40→        if ecomm_product_sku:
    41→            queryset = queryset.filter(ecomm_product__sku=ecomm_product_sku)
    42→
    43→        return queryset.order_by("-is_featured", "name")
    44→
    45→    @action(detail=False, methods=["get"], url_path="by-care-product/(?P<care_product_slug>[^/.]+)")
    46→    def by_care_product(self, request, care_product_slug=None):
    47→        """
    48→        Get PDP configuration by care product slug
    49→        """
    50→        try:
    51→            pdp_config = self.get_queryset().filter(care_product__slug=care_product_slug).first()
    52→            if pdp_config:
    53→                serializer = PDPConfigurationSerializer(pdp_config)
    54→                return Response(serializer.data, status=status.HTTP_200_OK)
    55→            else:
    56→                return Response(
    57→                    {"error": "No PDP configuration found for this care product"},
    58→                    status=status.HTTP_404_NOT_FOUND,
    59→                )
    60→        except Exception:
    61→            return Response(
    62→                {"error": "Error fetching PDP configuration"},
    63→                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    64→            )
    65→
    66→    @action(
    67→        detail=False, methods=["get"], url_path="by-ecomm-product/(?P<ecomm_product_sku>[^/.]+)"
    68→    )
    69→    def by_ecomm_product(self, request, ecomm_product_sku=None):
    70→        """
    71→        Get PDP configuration by ecomm product SKU
    72→        """
    73→        try:
    74→            pdp_config = self.get_queryset().filter(ecomm_product__sku=ecomm_product_sku).first()
    75→            if pdp_config:
    76→                serializer = PDPConfigurationSerializer(pdp_config)
    77→                return Response(serializer.data, status=status.HTTP_200_OK)
    78→            else:
    79→                return Response(
    80→                    {"error": "No PDP configuration found for this ecomm product"},
    81→                    status=status.HTTP_404_NOT_FOUND,
    82→                )
    83→        except Exception:
    84→            return Response(
    85→                {"error": "Error fetching PDP configuration"},
    86→                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    87→            )
    88→
    89→    @action(detail=False, methods=["get"], url_path="by-slug/(?P<slug>[^/.]+)")
    90→    def by_slug(self, request, slug=None):
    91→        """
    92→        Get PDP configuration by slug
    93→        """
    94→        try:
    95→            pdp_config = self.get_queryset().get(slug=slug)
    96→            if pdp_config:
    97→                serializer = self.get_serializer(pdp_config)
    98→                return Response(serializer.data, status=status.HTTP_200_OK)
    99→            else:
   100→                return Response(
... [18 more lines truncated]
```


**Step 66:** `read("backend/api/v1/views/provider_test_orders.py")`


```
1→import logging
     2→import uuid
     3→
     4→from django.db import transaction
     5→from django.db.models import Q
     6→from rest_framework import permissions, status
     7→from rest_framework.decorators import action
     8→from rest_framework.response import Response
     9→
    10→from accounts.utils import get_provider_profile
    11→from analytics.braze.constants import (
    12→    LATEST_TEST_ORDER_SOURCE,
    13→    BrazeEventName,
    14→    TestOrderSource,
    15→)
    16→from analytics.service import track_event, update_user_profile
    17→from analytics.tasks import (
    18→    send_provider_ordered_test_klaviyo_event,
    19→    send_provider_reminded_patient_klaviyo_event,
    20→)
    21→from api.v1 import serializers
    22→from api.v1.views.account import IsProvider
    23→from api.v1.views.views import EvvyUserViewSet
    24→from ecomm.constants import (
    25→    BULK_TIER_THRESHOLDS,
    26→    MAX_BULK_ORDER_SIZE,
    27→    PROVIDER_BULK_DISCOUNT_CODES,
    28→    SHOPIFY_PROVIDER_BILLED_CANADA_VHT_VARIANT_ID,
    29→    SHOPIFY_PROVIDER_BILLED_EXPAN_VARIANT_ID,
    30→    SHOPIFY_PROVIDER_BILLED_VHT_VARIANT_ID,
    31→)
    32→from ecomm.models.order import Order
    33→from providers.models import ProviderTestOrder
    34→from providers.tasks import (
    35→    send_provider_bulk_ordered_tests_notification,
    36→    send_provider_ordered_single_test_notifications,
    37→)
    38→from test_results.utils import plan_items_for_test
    39→from utils.random import create_random_hash
    40→
    41→
    42→logger = logging.getLogger(__name__)
    43→
    44→MAX_NUM_RECORDS = 500
    45→
    46→
    47→class IsVerified(permissions.BasePermission):
    48→    def has_permission(self, request, view):
    49→        user = request.user
    50→        profile = get_provider_profile(user)
    51→        return profile.verified
    52→
    53→
    54→class ProviderTestOrderViewSet(EvvyUserViewSet):
    55→    permission_classes = EvvyUserViewSet.permission_classes + [IsProvider, IsVerified]
    56→    serializer_class = serializers.ProviderTestOrderSerializer
    57→
    58→    def get_queryset(self):
    59→        return self.request.user.provider_test_orders.order_by("-create_date").all()
    60→
    61→    def list(self, request):
    62→        provider_test_orders = self.get_queryset().filter(
    63→            Q(patient_email__isnull=False) | Q(test__isnull=False)
    64→        )[:MAX_NUM_RECORDS]
    65→        serializer = self.serializer_class(
    66→            provider_test_orders, many=True, context={"request": request}
    67→        )
    68→        return Response(serializer.data)
    69→
    70→    @action(detail=False, methods=["get"], url_path="magic-link")
    71→    def magic_link(self, request):
    72→        """
    73→        Returns the provider's magic link slug. If none exists, generate and save one.
    74→        """
    75→        provider = request.user
    76→        profile = get_provider_profile(provider)
    77→        if not profile.magic_link_slug:
    78→            profile.magic_link_slug = create_random_hash(24)
    79→            profile.save(update_fields=["magic_link_slug"])
    80→        return Response({"slug": profile.magic_link_slug}, status=status.HTTP_200_OK)
    81→
    82→    def create(self, request):
    83→        provider = request.user
    84→        patient_email = request.data.get("patient_email")
    85→        payer = request.data.get("payer")
    86→        add_expanded_pcr = request.data.get("add_expanded_pcr", False)
    87→
    88→        if not patient_email:
    89→            return Response("Missing patient email field", status=status.HTTP_400_BAD_REQUEST)
    90→
    91→        provider_test_order = ProviderTestOrder.objects.create(
    92→            provider=provider,
    93→            patient_email=patient_email,
    94→            order_method=(
    95→                ProviderTestOrder.PATIENT_PAID
    96→                if payer == "patient"
    97→                else ProviderTestOrder.PROVIDER_PAID
    98→            ),
    99→            add_expanded_pcr=add_expanded_pcr,
   100→        )
... [284 more lines truncated]
```


Now I have enough information to compile the comprehensive authentication mapping. Let me also verify the `PDPConfigurationViewSet` auth (it uses `ReadOnlyModelViewSet` directly, not EvvyUserViewSet) and check the `TasksViewSet`:


**Step 67:** `search("OTPAdminSite|OTPMiddleware|OTPAdminAuthenticationForm", path="backend", glob="*.py", context=2)`


```
backend/app/views.py-6-from django.urls import reverse
backend/app/views.py-7-
backend/app/views.py:8:from django_otp.admin import OTPAdminAuthenticationForm
backend/app/views.py-9-
backend/app/views.py-10-from app.utils import is_production_env
--
backend/app/views.py-21-class EvvyLoginView(LoginView):
backend/app/views.py-22-    template_name = "login.html" if is_production_env() else "admin/login.html"
backend/app/views.py:23:    authentication_form = OTPAdminAuthenticationForm if is_production_env() else None
backend/app/views.py-24-
backend/app/views.py-25-    extra_context = {"site_title": "Django site admin"}
--
backend/app/urls.py-18-from django.urls import include, path
backend/app/urls.py-19-
backend/app/urls.py:20:from django_otp.admin import OTPAdminSite
backend/app/urls.py-21-
backend/app/urls.py-22-from app import views
--
backend/app/urls.py-35-# Only enforce 2FA in production
backend/app/urls.py-36-if get_environment() == "production":
backend/app/urls.py:37:    adminClass = OTPAdminSite
backend/app/urls.py-38-    adminClass.login_template = "login.html"
backend/app/urls.py-39-    admin.site.__class__ = adminClass
--
backend/app/settings.py-252-    "django.contrib.messages.middleware.MessageMiddleware",
backend/app/settings.py-253-    "django.middleware.clickjacking.XFrameOptionsMiddleware",
backend/app/settings.py:254:    "django_otp.middleware.OTPMiddleware",
backend/app/settings.py-255-    "csp.middleware.CSPMiddleware",
backend/app/settings.py-256-    "django_permissions_policy.PermissionsPolicyMiddleware",
```


Now I have a comprehensive picture. Here is the complete authentication mapping:

---

## Authentication Mapping for the Evvy Backend

### Authentication Infrastructure Overview

**Authentication Backends (Django `AUTHENTICATION_BACKENDS`)**
- File: `backend/app/auth.py`
- Class: `EmailBackend` — extends Django's `ModelBackend` to allow email-based login (username or email lookup)

**Default DRF Authentication (REST_FRAMEWORK settings)**
- File: `backend/app/settings.py` lines 373-376
- `DEFAULT_AUTHENTICATION_CLASSES`: `["api.v1.authentication.EvvyJWTAuthentication"]`
- No `DEFAULT_PERMISSION_CLASSES` set, meaning DRF defaults to `AllowAny` unless overridden per-view

---

### Authentication Classes

| Class | File | Description |
|---|---|---|
| `EvvyJWTAuthentication` | `backend/api/v1/authentication.py` | Extends `JWTAuthentication` from `rest_framework_simplejwt`. Checks Redis cache for blacklisted access tokens. Used globally for all user-facing API (v1) endpoints. |
| `PartnerAPIKeyAuthentication` | `backend/partner_api/authentication.py` | Bearer token auth for CX Automation. Supports partner-specific API keys (via `partner_config`) and legacy single `PARTNER_API_KEY` setting. |
| `PartnerOnlyAPIKeyAuthentication` | `backend/partner_api/authentication.py` | Bearer token auth for Distro endpoints only. Only supports partner-specific API keys — no legacy fallback. |
| `SessionAuthentication` | DRF built-in | Used by all Internal API endpoints (admin-facing tools). |
| `EmailBackend` (Django backend) | `backend/app/auth.py` | Backend that resolves email or username for `authenticate()` calls (used for login form / JWT token obtain flow). |

---

### Base View Classes and Their Auth

| Class | Auth | Permission | File |
|---|---|---|---|
| `EvvyUserViewSet` | `EvvyJWTAuthentication` | `IsAuthenticated` | `backend/api/v1/views/views.py` |
| `EvvyUserAPIView` | `EvvyJWTAuthentication` | `IsAuthenticated` | `backend/api/v1/views/views.py` |
| `evvy_api_view` decorator | `EvvyJWTAuthentication` | `IsAuthenticated` | `backend/api/v1/views/views.py` |
| `EvvyInternalViewSet` | `SessionAuthentication` | `IsAuthenticated` | `backend/api/internal/views.py` |
| `EvvyInternalReadOnlyViewSet` | `SessionAuthentication` | `IsAuthenticated` | `backend/api/internal/views.py` |
| `EvvyInternalAPIView` | `SessionAuthentication` | `IsAuthenticated` | `backend/api/internal/views.py` |

---

### API v1 Endpoints — JWT Authentication (`EvvyJWTAuthentication` + `IsAuthenticated`)

All endpoints in this section use JWT Bearer token auth unless otherwise noted. The base URL prefix is `/api/v1/`.

#### JWT Token Endpoints (no user auth required — these obtain/refresh/revoke tokens)

| URL | View | Auth Note |
|---|---|---|
| `POST /api/token/` | `EvvyTokenObtainPairView` | No auth — credential-based login. Throttled (10/min, 50/hour). Ultimately uses `EmailBackend` |
| `POST /api/token/refresh/` | `EvvyTokenRefreshView` | No auth — presents refresh token. Checks Redis for blacklisted refresh tokens. Throttled (30/min, 200/hour) |
| `POST /api/token/logout/` | `EvvyTokenBlacklistView` | No auth required by class — tokens blacklisted via Redis. Throttled (50/min, 300/hour) |

File: `backend/api/v1/views/auth.py`

#### Registration Endpoints (no auth — public registration)

| URL | View | Auth Note |
|---|---|---|
| `POST /api/v1/register/` | `RegisterView` | No auth — `APIView` with no `permission_classes` set. Throttled (login throttle rates) |
| `POST /api/v1/provider/register` | `RegisterProviderView` | No auth — `APIView` with no `permission_classes` set. Throttled (login throttle rates) |

File: `backend/api/v1/views/register.py`

#### Password Reset Endpoints (no auth — unauthenticated flow)

| URL | View | Auth Note |
|---|---|---|
| `POST /api/v1/password_reset/` | `EvvyResetPasswordRequestToken` | No auth (inherits from `django_rest_passwordreset`). Throttled |
| `POST /api/v1/password_reset/validate_token/` | `EvvyResetPasswordValidateToken` | No auth (token-based validation) |
| `POST /api/v1/password_reset/confirm/` | `EvvyResetPasswordConfirm` | No auth (token-based confirmation) |

File: `backend/api/v1/views/reset_password.py`

#### Authenticated User Endpoints — JWT Required

All the following extend `EvvyUserAPIView` or `EvvyUserViewSet` and require `EvvyJWTAuthentication` + `IsAuthenticated`:

| URL | View Class | Extra Permissions |
|---|---|---|
| `GET/POST /api/v1/account/` | `UserAccountView` | None (IsAuthenticated) |
| `GET/POST /api/v1/provider/profile` | `ProviderProfileView` | `IsProvider` (must be in providers group) |
| `GET/POST /api/v1/user-config/` | `UserConfigView` | None |
| `POST /api/v1/male-partner-checkout/` | `MalePartnerCheckoutView` | None |
| `GET/POST /api/v1/compare/` | `CompareView` | None |
| `GET /api/v1/trends/` | `TrendsView` | None |
| `GET /api/v1/my-plan/` | `MyPlanView` | None |
| `GET /api/v1/my-plan-old/` | `MyPlanOldView` | None |
| `GET/POST /api/v1/my-plan/feedback/` | `MyPlanFeedback` | None |
| `GET/POST /api/v1/consent/` | `ConsentView` | None |
| `GET/POST /api/v1/announcements/` | `AnnouncementsView` | None |
| `GET /api/v1/faqs/` | `FAQPageView` | None |
| `GET/POST /api/v1/survey/` | `SurveyView` | None |
| `GET/PUT /api/v1/orders/` | `OrdersView (GET/PUT)` | None |
| `GET/POST /api/v1/email-verification/` | `EmailVerificationView` | None (also throttled) |
| `GET/POST /api/v1/order-transfer-verification/` | `AccountOrderTransferVerification` | None |
| `GET /api/v1/subscription/` | `get_subscription` | None (`@evvy_api_view`) |
| `GET /api/v1/subscriptions/` | `get_subscriptions` | None (`@evvy_api_view`) |
| `GET /api/v1/subscriptions/<id>/` | `get_subscription_by_id` | None (`@evvy_api_view`) |
| `GET /api/v1/subscriptions/sku/<sku>/` | `get_active_subscription_by_product_sku` | None (`@evvy_api_view`) |
| `GET /api/v1/subscription/exists/` | `subscription_exists` | None (`@evvy_api_view`) |
| `PUT /api/v1/subscription/next-charge/` | `update_next_subscription_charge` | None (`@evvy_api_view`) |
| `PUT /api/v1/subscription/next-charge-with-discount/` | `update_next_subscription_charge_with_discount` | None (`@evvy_api_view`) |
| `GET /api/v1/subscription/portal-link/` | `portal_link` | None (`@evvy_api_view`) |
| `PUT /api/v1/subscription/swap/` | `swap_subscription` | None (`@evvy_api_view`) |

**ViewSets (JWT + IsAuthenticated):**

| URL prefix | ViewSet | Extra Permissions |
|---|---|---|
| `/api/v1/user-tests/` | `UserTestViewSet` (extends `EvvyUserViewSet`) | None — but `get_object()` enforces user ownership (returns 404 if not owner) |
| `/api/v1/health-context/` | `HealthContextViewSet` | None — ownership enforced in `get_object()` |
| `/api/v1/cart/` | `CartViewSet` | None |
| `/api/v1/consults/` | `ConsultViewSet` | None |
| `/api/v1/consult-intake/` | `ConsultIntakeViewSet` | None |
| `/api/v1/lab-order-intake/` | `LabOrderIntakeViewSet` | None |
| `/api/v1/treatment-interruption/` | `TreatmentPlanInterruptionViewSet` | None |
| `/api/v1/products/` | `ProductViewSet` | None |
| `/api/v1/calendar-treatments/` | `CalendarTreatmentViewSet` | None |
| `/api/v1/provider-test-orders/` | `ProviderTestOrderViewSet` | `IsProvider` + `IsVerified` (must be in providers group AND have verified profile) |

Special: `GET /api/v1/user-tests/<hash>/pdf-data/` → `UserTestResultsView`
- Auth: `EvvyUserAPIView.permission_classes` + `CanAccessTest`
- `CanAccessTest` permission: Staff = any test, Provider = only tests linked via `provider_test_orders`, Patient = own tests only

Files: `backend/api/v1/views/user_test_results.py`, `backend/api/v1/permissions.py`

---

### Endpoints Exempted from Authentication (Explicitly Public)

| URL | View | How Auth is Bypassed |
|---|---|---|
| `GET /api/v1/public-features/` | `PublicFeaturesView` | `authentication_classes = []`, `permission_classes = []` |
| `GET /api/v1/ecomm-products/<sku>/` | `EcommProductView` | Plain `APIView` — inherits DRF default `EvvyJWTAuthentication` but no `permission_classes`, so effectively no auth enforced. Documented as "public endpoint" |
| `GET /api/v1/pdp-configurations/` + actions | `PDPConfigurationViewSet` | Plain `ReadOnlyModelViewSet` — inherits DRF default auth but no `permission_classes` set. Effectively public |
| `GET /api/v1/announcements/` (reading public feature flags) | `PublicFeaturesView` | Same as above |
| `GET /api/v1/provider-test/<slug>/` | `PublicProviderMagicLinkCheckout` | `permission_classes = [AllowAny]`, `authentication_classes = []` |
| `POST /api/v1/email-verification-confirm/` | `EmailVerificationConfirmView` | Uses bare `APIView`, no permission_classes — hash-based verification. Comment in code: "can be logged out (mobile browser vs webview)" |
| `POST /api/v1/order-transfer-verification-confirm/` | `AccountOrderTransferConfirmVerification` | Uses bare `APIView`, no permission_classes — hash-based confirmation. Comment: "User can be unauthenticated." |
| `POST /api/v1/orders/` (POST only) | `OrdersView.post` | Overrides `get_permissions()` to return `[]` for POST. GET/PUT require auth. |
| `GET /health/` | `health` view | Django function view — no auth |
| `GET /unhealthy/` | `unhealthy` view | Django function view — no auth (testing only) |

Files:
- `backend/api/v1/views/public_features.py`
- `backend/api/v1/views/ecomm_products.py`
- `backend/api/v1/views/pdp_configuration.py`
- `backend/api/v1/views/views.py`
- `backend/api/v1/views/email_verification.py`
- `backend/api/v1/views/account_order_transfer_verification.py`
- `backend/api/v1/views/orders.py`

---

### Webhook Endpoints — CSRF-Exempt with Custom Signature Verification

All webhooks are CSRF-exempt (`@csrf_exempt`) and use no DRF authentication. They implement their own request verification. URL prefix: `/api/v1/webhooks/`.

| URL | View | Verification Method |
|---|---|---|
| `POST /api/v1/webhook/` | `webhook_view` | No verification — trusts source/type fields in payload. TODO comment noting verification needed. |
| `POST /api/v1/webhooks/shopify` | `shopify_webhook_view` | HMAC-SHA256 (`X-Shopify-Hmac-SHA256` header vs `SHOPIFY_WEBHOOK_SECRET`) |
| `POST /api/v1/webhooks/shopify-graphql` | `shopify_webhook_graphql_view` | HMAC-SHA256 (same Shopify mechanism) |
| `POST /api/v1/webhooks/shopify-fulfillment` | `shopify_fulfillment_webhook_view` | HMAC-SHA256 (same Shopify mechanism) |
| `POST /api/v1/webhooks/wheel` | `wheel_webhook_view` | Static token (`X-Wheel-Access-Token` header vs `WHEEL_ACCESS_TOKEN`) |
| `POST /api/v1/webhooks/berlin` | `berlin_webhook_view` | Static token (`X-Berlin-Access-Token` header vs `BERLIN_ACCESS_TOKEN`) |
| `POST /api/v1/webhooks/microgen` | `microgen_webhook_view` | HMAC-SHA256 (`X-Microgen-Hmac-SHA256` header vs `MICROGEN_SECRET_KEY`) |
| `POST /api/v1/webhooks/microgen-batch` | `microgen_batch_webhook_view` | HMAC-SHA256 (`X-Microgen-Hmac-SHA256` header vs `MICROGEN_SECRET_KEY`) |
| `POST /api/v1/webhooks/precision` | `precision_pharmacy_webhook_view` | HMAC-SHA256 (`x-hmac-hash` header vs `PRECISION_SECRET_KEY`) |
| `POST /api/v1/webhooks/survicate-survey-complete` | `survicate_survey_complete_webhook_view` | HMAC-SHA256 (`Hmac` header, hex→base64 conversion, vs `SURVICATE_SECRET_KEY`) |
| `POST /api/v1/webhooks/calendly` | `calendly_webhook_view` | HMAC-SHA256 with timestamp (`Calendly-Webhook-Signature` header vs `CALENDLY_SECRET_KEY`) |
| `POST /api/v1/webhooks/recharge` | `recharge_webhook_view` | HMAC-SHA256 hex (`X-Recharge-Hmac-Sha256` header vs `RECHARGE_WEBHOOK_SECRET`) |
| `POST /api/v1/webhooks/viome` | `viome_webhook_view` | Static token comparison (`X-Viome-Access-Token` header vs `VIOME_WEBHOOK_SECRET`) |
| `POST /api/v1/webhooks/junction` | `junction_webhook_view` | Svix signature (`svix-id`, `svix-timestamp`, `svix-signature` headers, `JunctionWebhookHandler`) |
| `POST /api/v1/webhooks/typeform` | `typeform_webhook_view` | HMAC-SHA256 (optional — `Typeform-Signature` header, if absent falls through) |

File: `backend/api/v1/views/webhooks.py`

---

### TasksViewSet — Custom Token Verification

| URL | Action | Auth Note |
|---|---|---|
| `POST /api/v1/tasks/echo/` | `TasksViewSet.echo` | CSRF-exempt (`@method_decorator(csrf_exempt)`). Custom `_confirm_token()` checks `token` body field equals `RENDER_GIT_COMMIT` env var. Skipped in `DEBUG` mode. No DRF permission class — uses plain `ViewSet`. |

File: `backend/api/v1/views/tasks.py`

---

### Internal API Endpoints — Session Authentication

URL prefix: `/api/internal/`. All use `SessionAuthentication` + `IsAuthenticated`.

| URL | View | Extra Permissions |
|---|---|---|
| `GET/POST/PUT/DELETE /api/internal/results/` | `ResultsViewSet` | `ResultsManagerRequired` (must be in `results_managers` group) + `IsAuthenticated` |
| `GET /api/internal/results/<hash>/plan_items/` | `ResultsViewSet.plan_items` | Same |
| `POST /api/internal/results/<hash>/release/` | `ResultsViewSet.release` | Same |
| `GET /api/internal/users/` | `UserSummaryViewSet` | `IsAuthenticated` + `CoachUserAssignmentRequired` (must have assignment to user, or be results manager) |
| `GET /api/internal/users/<id>/timeline/` | `UserSummaryViewSet.timeline` | Same |
| `GET/POST/PATCH /api/internal/ai_sally/<user_id>/` | `AIMessageViewSet` | `IsAuthenticated` + `CoachUserAssignmentForAIRequired` + group check for `user_summary_assistant_users` on certain actions |
| `GET /api/internal/plan_profiles/` | `PlanProfileViewSet` | `ResultsManagerRequired` + `IsAuthenticated` |
| `GET /api/internal/plan_items/` | `PlanItemViewset` | `IsAuthenticated` + `ResultsManagerRequired` |
| `POST /api/internal/auth/logout/` | `logout_view` | `SessionAuthentication` only (no permission check beyond being authenticated) |
| `GET /api/internal/me/` | `CurrentUserView` | `IsAuthenticated` (session) |

File: `backend/api/internal/views.py`

---

### Partner API Endpoints — Bearer API Key Authentication

URL prefix: `/api/partner/`. All use partner API key authentication, not user JWT.

#### CX Automation (`/api/partner/cx-automation/`)

All views: `authentication_classes = [PartnerAPIKeyAuthentication]`, `permission_classes = [PartnerAPIKeyRequired]`

| URL | View |
|---|---|
| `GET /api/partner/cx-automation/test/` | `TestLookupView` |
| `GET /api/partner/cx-automation/test/<hash>/status/` | `TestStatusView` |
| `GET /api/partner/cx-automation/test/<hash>/shipping-status/` | `TestShippingView` |
| `GET /api/partner/cx-automation/test/<hash>/coaching-info/` | `TestCoachingView` |
| `GET /api/partner/cx-automation/test/<hash>/health-history/` | `TestHealthHistoryView` |
| `GET /api/partner/cx-automation/test/<hash>/consult-lookup/` | `ConsultLookupView` |
| `GET /api/partner/cx-automation/consult/<id>/prescription/` | `PrescriptionStatusView` |
| `GET /api/partner/cx-automation/consult/<id>/intake/` | `ConsultIntakeView` |

File: `backend/partner_api/cx_automation/views.py`

#### Distro (`/api/partner/v1/distro/`)

All views: `authentication_classes = [PartnerOnlyAPIKeyAuthentication]`, `permission_classes = [PartnerAPIKeyRequired, PartnerIPAllowlistRequired]`

Additional IP allowlist enforcement (`PartnerIPAllowlistRequired`) — checks `True-Client-IP` (Cloudflare header) or `REMOTE_ADDR` against per-partner configured IP list.

| URL | View |
|---|---|
| `GET /api/partner/v1/distro/reports/<hash>/` | `PartnerReportsView` |
| `GET /api/partner/v1/distro/tests/statuses/` | `PartnerTestStatusesView` |

File: `backend/partner_api/distro/views.py`

---

### Admin Interface

| URL | Auth Method |
|---|---|
| `GET/POST /admin/` | Django admin session auth. In **production**: `OTPAdminSite` enforces TOTP 2FA (via `django-otp`). Login form uses `OTPAdminAuthenticationForm`. In non-production: standard session auth. |

Files: `backend/app/urls.py`, `backend/app/views.py`

---

### Middleware-Based Auth

| Middleware | File | Effect |
|---|---|---|
| `django.contrib.auth.middleware.AuthenticationMiddleware` | Django built-in | Associates session-authenticated user with `request.user` |
| `django_otp.middleware.OTPMiddleware` | Third-party | Marks whether `request.user` has completed OTP verification (used by admin 2FA) |
| `ImpersonateMiddleware` | `backend/app/middleware/auth.py` | If `__impersonate` query param is present AND authenticated user is staff + in `user-impersonation` group, swaps the JWT `Authorization` header to impersonate the target user. Uses `EvvyJWTAuthentication` for the impersonator check. |

---

### Custom Permission Classes Summary

| Permission Class | File | Logic |
|---|---|---|
| `IsProvider` | `backend/api/v1/views/account.py` | User must be in `GROUP_NAME_PROVIDERS` Django group |
| `IsVerified` | `backend/api/v1/views/provider_test_orders.py` | Provider profile `verified` field must be True |
| `CanAccessTest` | `backend/api/v1/permissions.py` | Staff: any test; Provider: only via `provider_test_orders`; Patient: own tests only |
| `ResultsManagerRequired` | `backend/api/internal/views.py` | Must be in `results_managers` group |
| `CoachUserAssignmentRequired` | `backend/api/internal/views.py` | Must have a non-expired `CoachUserAssignment` for the requested user, OR be a results manager |
| `CoachUserAssignmentForAIRequired` | `backend/api/internal/views.py` | Same as above but for AI endpoints (uses `user_id` kwarg) |
| `PartnerAPIKeyRequired` | `backend/partner_api/permissions.py` | `request.auth` must be non-None; if `PartnerConfig` object, must be `is_active` |
| `PartnerIPAllowlistRequired` | `backend/partner_api/permissions.py` | If partner has `allowed_ips` configured, client IP must be in the list; uses `True-Client-IP` (Cloudflare) or `REMOTE_ADDR` |
