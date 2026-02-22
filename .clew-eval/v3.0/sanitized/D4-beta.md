# D4 Authentication Inventory - Search Tool Evaluation

**Task:** Find all API endpoints that require authentication and identify which authentication method each uses (token auth, session auth, OAuth, API key, permission classes, etc.). Include decorator-based auth, middleware-based auth, and custom auth backends. Also identify endpoints explicitly exempted from authentication.

## Tool Calls and Exploration

### Initial Discovery
1. Listed directory structure - identified Django backend application
2. Found main settings file at `/Users/albertgwo/Work/evvy/backend/app/settings.py`
3. Located URL configuration files

### Settings Analysis
From `/Users/albertgwo/Work/evvy/backend/app/settings.py`:
- **DEFAULT_AUTHENTICATION_CLASSES**: `api.v1.authentication.EvvyJWTAuthentication` (JWT-based)
- **AUTHENTICATION_BACKENDS**: `app.auth.EmailBackend` (custom email-based authentication)
- **MIDDLEWARE**: Includes `SessionMiddleware`, `AuthenticationMiddleware`, `OTPMiddleware`
- **SESSION_COOKIE_AGE**: 24 hours (for Django admin)

### URL Structure Analysis
Main URL patterns from `/Users/albertgwo/Work/evvy/backend/app/urls.py`:
- `/admin/` - Django admin with 2FA in production (OTPAdminSite)
- `/health/` and `/unhealthy/` - Health check endpoints
- `/api/` - Main API endpoints

API sub-routes from `/Users/albertgwo/Work/evvy/backend/api/urls.py`:
- `/api/v1/` - Main v1 API endpoints
- `/api/internal/` - Internal portal endpoints
- `/api/partner/` - Partner API endpoints
- `/api/token/` - JWT token endpoints (obtain, refresh, logout)

### Authentication Classes Discovery

#### 1. EvvyJWTAuthentication (`/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py`)
- Extends `rest_framework_simplejwt.authentication.JWTAuthentication`
- Checks for blacklisted access tokens in cache
- Used as default for v1 API endpoints

#### 2. PartnerAPIKeyAuthentication (`/Users/albertgwo/Work/evvy/backend/partner_api/authentication.py`)
- Bearer token authentication for partner integrations
- Supports partner-specific API keys and legacy single API key
- Used for cx_automation endpoints

#### 3. PartnerOnlyAPIKeyAuthentication (`/Users/albertgwo/Work/evvy/backend/partner_api/authentication.py`)
- Partner-specific API keys only (no legacy key support)
- Used for distro module endpoints

#### 4. SessionAuthentication (Django REST Framework)
- Used for internal portal endpoints (`/api/internal/`)

### Permission Classes Discovery

#### Standard DRF Permissions
- `IsAuthenticated` - Requires authenticated user
- `AllowAny` - No authentication required

#### Custom Permission Classes

1. **CanAccessTest** (`/Users/albertgwo/Work/evvy/backend/api/v1/permissions.py`)
   - Staff can access any test
   - Providers can access tests linked via provider_test_orders
   - Patients can only access their own tests

2. **IsProvider** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/account.py`)
   - Checks if user is in GROUP_NAME_PROVIDERS group

3. **IsVerified** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py`)
   - Checks if provider profile is verified

4. **ResultsManagerRequired** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
   - Checks if user is in GROUP_NAME_RESULTS_MANAGERS group

5. **CoachUserAssignmentRequired** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
   - Checks if coach has assignment to user or is results manager

6. **CoachUserAssignmentForAIRequired** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
   - Similar to above but for AI endpoints

7. **PartnerAPIKeyRequired** (`/Users/albertgwo/Work/evvy/backend/partner_api/permissions.py`)
   - Ensures partner API key authentication succeeded
   - Checks partner is active for PartnerConfig objects

8. **PartnerIPAllowlistRequired** (`/Users/albertgwo/Work/evvy/backend/partner_api/permissions.py`)
   - Checks client IP is in partner's allowed IP list
   - Uses True-Client-IP header (Cloudflare) or REMOTE_ADDR

### Base View Classes

1. **EvvyUserViewSet** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`)
   - `permission_classes = [permissions.IsAuthenticated]`
   - `authentication_classes = [EvvyJWTAuthentication]`

2. **EvvyUserAPIView** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`)
   - `permission_classes = [permissions.IsAuthenticated]`
   - `authentication_classes = [EvvyJWTAuthentication]`

3. **evvy_api_view** decorator (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`)
   - Applies `permissions.IsAuthenticated` and `EvvyJWTAuthentication`

### Endpoints Analysis

#### Authenticated Endpoints (JWT - EvvyJWTAuthentication)

**ViewSets (all extend EvvyUserViewSet):**
- `/api/v1/user-tests/` - UserTestViewSet
- `/api/v1/health-context/` - HealthContextViewSet
- `/api/v1/tasks/` - TasksViewSet
- `/api/v1/cart/` - CartViewSet
- `/api/v1/consults/` - ConsultViewSet
- `/api/v1/consult-intake/` - ConsultIntakeViewSet
- `/api/v1/lab-order-intake/` - LabOrderIntakeViewSet
- `/api/v1/treatment-interruption/` - TreatmentPlanInterruptionViewSet
- `/api/v1/products/` - ProductViewSet
- `/api/v1/provider-test-orders/` - ProviderTestOrderViewSet (+ IsProvider, IsVerified)
- `/api/v1/calendar-treatments/` - CalendarTreatmentViewSet
- `/api/v1/pdp-configurations/` - PDPConfigurationViewSet

**APIViews (extend EvvyUserAPIView):**
- `/api/v1/account/` - UserAccountView
- `/api/v1/compare/` - CompareView
- `/api/v1/trends/` - TrendsView
- `/api/v1/email-verification/` - EmailVerificationView
- `/api/v1/order-transfer-verification/` - AccountOrderTransferVerification
- `/api/v1/consent/` - ConsentView
- `/api/v1/my-plan-old/` - MyPlanOldView
- `/api/v1/my-plan/` - MyPlanView
- `/api/v1/my-plan/feedback/` - MyPlanFeedback
- `/api/v1/orders/` - OrdersView
- `/api/v1/user-config/` - UserConfigView
- `/api/v1/male-partner-checkout/` - MalePartnerCheckoutView
- `/api/v1/user-tests/<hash>/pdf-data/` - UserTestResultsView (+ CanAccessTest)
- `/api/v1/announcements/` - AnnouncementsView
- `/api/v1/faqs/` - FAQPageView
- `/api/v1/provider/profile` - ProviderProfileView (+ IsProvider)
- `/api/v1/survey/` - SurveyView

**Function-based views (use @evvy_api_view decorator):**
- `/api/v1/subscription/` - get_subscription
- `/api/v1/subscriptions/` - get_subscriptions
- `/api/v1/subscriptions/<id>/` - get_subscription_by_id
- `/api/v1/subscriptions/sku/<sku>/` - get_active_subscription_by_product_sku
- `/api/v1/subscription/exists/` - subscription_exists
- `/api/v1/subscription/next-charge/` - update_next_subscription_charge
- `/api/v1/subscription/next-charge-with-discount/` - update_next_subscription_charge_with_discount
- `/api/v1/subscription/portal-link/` - portal_link
- `/api/v1/subscription/swap/` - swap_subscription

#### Unauthenticated Endpoints (AllowAny or no auth/permission classes)

**Token endpoints (throttled):**
- `/api/token/` - EvvyTokenObtainPairView (LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle)
- `/api/token/refresh/` - EvvyTokenRefreshView (TokenRefreshAnonMinuteRateThrottle, TokenRefreshAnonHourRateThrottle)
- `/api/token/logout/` - EvvyTokenBlacklistView (TokenLogoutAnonMinuteRateThrottle, TokenLogoutAnonHourRateThrottle)

**Registration/Password Reset (throttled):**
- `/api/v1/register/` - RegisterView (LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle)
- `/api/v1/provider/register` - RegisterProviderView (no explicit auth classes)
- `/api/v1/password_reset/` - EvvyResetPasswordRequestToken (LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle)
- `/api/v1/password_reset/validate_token/` - EvvyResetPasswordValidateToken (default throttle classes)
- `/api/v1/password_reset/confirm/` - EvvyResetPasswordConfirm (default throttle classes)

**Email verification (public confirm endpoint):**
- `/api/v1/email-verification-confirm/` - EmailVerificationConfirmView (APIView, no permission classes)

**Order transfer verification:**
- `/api/v1/order-transfer-verification-confirm/` - AccountOrderTransferConfirmVerification (APIView, no auth)

**Public endpoints:**
- `/api/v1/public-features/` - PublicFeaturesView (authentication_classes=[], permission_classes=[])
- `/api/v1/ecomm-products/<sku>/` - EcommProductView (no explicit auth classes)
- `/api/v1/provider-test/<slug>/` - PublicProviderMagicLinkCheckout (permission_classes=[AllowAny], authentication_classes=[])

**Webhooks (CSRF exempt, no DRF auth):**
- `/api/v1/webhook/` - webhook_view (@csrf_exempt)
- `/api/v1/webhooks/shopify` - shopify_webhook_view (@csrf_exempt, HMAC verification)
- `/api/v1/webhooks/shopify-graphql` - shopify_webhook_graphql_view (@csrf_exempt)
- `/api/v1/webhooks/shopify-fulfillment` - shopify_fulfillment_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/wheel` - wheel_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/berlin` - berlin_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/microgen` - microgen_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/microgen-batch` - microgen_batch_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/precision` - precision_pharmacy_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/survicate-survey-complete` - survicate_survey_complete_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/calendly` - calendly_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/recharge` - recharge_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/viome` - viome_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/typeform` - typeform_webhook_view (@csrf_exempt)
- `/api/v1/webhooks/junction` - junction_webhook_view (@csrf_exempt)

**Health checks:**
- `/health/` - health view
- `/unhealthy/` - unhealthy view

#### Internal API Endpoints (Session Authentication)

All endpoints use:
- `authentication_classes = [SessionAuthentication]`
- `permission_classes = [IsAuthenticated]` + additional custom permissions

**ViewSets:**
- `/api/internal/results/` - ResultsViewSet (IsAuthenticated, ResultsManagerRequired)
- `/api/internal/users/` - UserSummaryViewSet (IsAuthenticated, CoachUserAssignmentRequired)
- `/api/internal/ai_sally/<user_id>/` - AIMessageViewSet (IsAuthenticated, CoachUserAssignmentForAIRequired)
- `/api/internal/plan_profiles/` - PlanProfileViewSet (IsAuthenticated)
- `/api/internal/plan_items/` - PlanItemViewset (IsAuthenticated, ResultsManagerRequired)

**APIViews:**
- `/api/internal/me/` - CurrentUserView (IsAuthenticated)

**Function-based views:**
- `/api/internal/auth/logout/` - logout_view (SessionAuthentication, IsAuthenticated)

#### Partner API Endpoints (API Key Authentication)

**CX Automation endpoints (PartnerAPIKeyAuthentication + PartnerAPIKeyRequired):**
- `/api/partner/cx-automation/` endpoints (9 views total, all require PartnerAPIKeyAuthentication + PartnerAPIKeyRequired)

**Distro endpoints (PartnerOnlyAPIKeyAuthentication + PartnerAPIKeyRequired + PartnerIPAllowlistRequired):**
- `/api/partner/v1/distro/` endpoints (PartnerOnlyAPIKeyAuthentication, PartnerAPIKeyRequired, PartnerIPAllowlistRequired)

#### Django Admin (Session + 2FA in Production)
- `/admin/` - Django admin site
  - Production: OTPAdminSite (2FA required)
  - Non-production: Regular admin site
  - Custom login view: EvvyLoginView

### Middleware-Based Authentication
From settings.py MIDDLEWARE list:
1. `SessionMiddleware` - Manages sessions
2. `AuthenticationMiddleware` - Associates users with requests
3. `OTPMiddleware` - One-time password middleware (django_otp)
4. `ImpersonateMiddleware` - Custom middleware for user impersonation
5. `EvvyAuditLogMiddleware` - Audit logging middleware

## Complete Authentication Inventory

### Authentication Methods Summary

1. **JWT Authentication (EvvyJWTAuthentication)**
   - Used by: Main v1 API endpoints
   - Token lifetime: 90 minutes (access), 1 day (refresh)
   - Blacklist support via cache
   - Endpoints: Most `/api/v1/` endpoints

2. **Session Authentication (SessionAuthentication)**
   - Used by: Internal portal API (`/api/internal/`)
   - Cookie age: 24 hours
   - Django session-based authentication

3. **Partner API Key Authentication**
   - Type A: PartnerAPIKeyAuthentication (cx_automation)
     - Supports partner-specific keys + legacy single key
   - Type B: PartnerOnlyAPIKeyAuthentication (distro)
     - Partner-specific keys only
     - Additional IP allowlist check
   - Bearer token format: "Authorization: Bearer <api_key>"

4. **Django Admin Authentication**
   - Session-based with custom EmailBackend
   - 2FA required in production (OTP)
   - Custom login view with redirect support

5. **Webhook Authentication**
   - CSRF exempt
   - Custom verification (e.g., HMAC for Shopify)
   - No DRF authentication

### Endpoints by Authentication Type

#### JWT Required (EvvyJWTAuthentication)
- All ViewSets in `/api/v1/` (12 total)
- Most APIViews in `/api/v1/` (19 total)
- Function-based views with @evvy_api_view (9 total)
- **Additional permissions:**
  - IsProvider + IsVerified: provider-test-orders
  - CanAccessTest: user-tests/<hash>/pdf-data/
  - IsProvider: provider/profile

#### Session Required (SessionAuthentication)
- All `/api/internal/` endpoints
- **Additional permissions:**
  - ResultsManagerRequired: results, plan_items
  - CoachUserAssignmentRequired: users
  - CoachUserAssignmentForAIRequired: ai_sally

#### API Key Required
- Partner API endpoints (`/api/partner/`)
  - cx_automation: PartnerAPIKeyAuthentication + PartnerAPIKeyRequired
  - distro: PartnerOnlyAPIKeyAuthentication + PartnerAPIKeyRequired + PartnerIPAllowlistRequired

#### No Authentication Required
1. **Token endpoints** (3 endpoints, throttled)
2. **Registration/Password Reset** (5 endpoints, throttled)
3. **Public endpoints** (3 endpoints)
4. **Email/Order verification confirm** (2 endpoints)
5. **Webhooks** (14 endpoints, CSRF exempt with custom verification)
6. **Health checks** (2 endpoints)
7. **EcommProduct lookup** (1 endpoint)

### Custom Authentication Backends
- `app.auth.EmailBackend` - Email-based authentication (used for Django admin)

### Throttling Configuration
Default throttle rates from settings.py:
- user-minute: 120/min
- anon-minute: 60/min
- user-hour: 2000/hour
- anon-hour: 1000/hour
- user-day: 5000/day
- anon-day: 2500/day
- login-anon-minute: 10/min
- login-anon-hour: 50/hour
- token-refresh-anon-minute: 30/min
- token-refresh-anon-hour: 200/hour
- token-logout-anon-minute: 50/min
- token-logout-anon-hour: 300/hour

Mode: Configurable via THROTTLE_MODE env var (default: "warn")
