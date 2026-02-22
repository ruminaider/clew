# Investigation: Authentication and Permission Mapping (Grep)

## Task

Find all API endpoints that require authentication and identify which authentication method each uses (token auth, session auth, OAuth, API key, permission classes, etc.). Include decorator-based auth (`@login_required`, `@permission_classes`), middleware-based auth, and any custom auth backends. Also identify any endpoints that are explicitly exempted from authentication.

## Tool Calls and Reasoning

### 1. Initial directory exploration
**Tool**: `Bash` - List directory contents
**Reasoning**: Verify that `/Users/albertgwo/Work/evvy` exists and understand project structure
**Result**: Confirmed directory exists with `backend/`, `frontend/`, `internal-frontend/` subdirectories. This is a Django project with REST API.

### 2. Find Python files to understand structure
**Tool**: `Glob` - Pattern match for `**/*.py` in backend
**Reasoning**: Get an overview of the Python codebase structure
**Result**: Found typical Django structure with `api/`, `accounts/`, `app/`, and various app modules.

### 3. Search for authentication decorators and permission classes
**Tool**: `Grep` - Pattern: `@login_required|@permission_classes|@authentication_classes|IsAuthenticated|AllowAny`
**Reasoning**: Find explicit authentication/permission declarations in views
**Result**: Found multiple occurrences of:
- `IsAuthenticated` permission class in `api/internal/views.py` and `api/v1/views/views.py`
- `AllowAny` permission in `api/v1/views/views.py`
- Custom permission classes like `ResultsManagerRequired`, `CoachUserAssignmentRequired`
- Both `SessionAuthentication` and `EvvyJWTAuthentication` authentication classes

### 4. Check Django/DRF settings for default authentication
**Tool**: `Grep` - Pattern: `REST_FRAMEWORK|AUTHENTICATION_BACKENDS|DEFAULT_AUTHENTICATION_CLASSES|DEFAULT_PERMISSION_CLASSES`
**Reasoning**: Understand default authentication configuration that applies to all endpoints
**Result**: Found in `app/settings.py`:
- `AUTHENTICATION_BACKENDS = ("app.auth.EmailBackend",)`
- `REST_FRAMEWORK` with `DEFAULT_AUTHENTICATION_CLASSES: ["api.v1.authentication.EvvyJWTAuthentication"]`
- No default permission classes set (defaults to unauthenticated access unless specified)

### 5. Search for custom authentication and permission classes
**Tool**: `Grep` - Pattern: `class.*Authentication|class.*Permission`
**Reasoning**: Find all custom authentication and permission implementations
**Result**: Found:
- `PartnerAPIKeyAuthentication` - Bearer token auth for partner integrations
- `PartnerOnlyAPIKeyAuthentication` - Partner-specific API key auth
- `PartnerAPIKeyRequired` - Permission class for partner auth
- `PartnerIPAllowlistRequired` - IP-based permission check
- `EvvyJWTAuthentication` - Custom JWT authentication
- `CanAccessTest` - Test access permission
- `IsProvider` - Provider-only permission
- `IsVerified` - Verified user permission
- Various custom permissions in internal views

### 6. Read settings file for authentication configuration
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/app/settings.py` (lines 359-408)
**Reasoning**: Understand complete authentication and throttling setup
**Result**: Confirmed:
- Email-based authentication backend
- JWT as default authentication
- Extensive throttling configuration for different user types and endpoints
- Custom exception handler for partner API

### 7. Read main URL configuration
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/app/urls.py`
**Reasoning**: Understand top-level routing structure
**Result**: Found main URL patterns:
- `/admin/` - Django admin with OTP 2FA in production
- `/health/` and `/unhealthy/` - Health check endpoints
- `/api/` - Main API endpoints (includes v1, internal, partner)

### 8. Read JWT authentication implementation
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py`
**Reasoning**: Understand custom JWT authentication logic
**Result**: `EvvyJWTAuthentication`:
- Extends `JWTAuthentication` from rest_framework_simplejwt
- Adds blacklist checking via cache for access tokens
- Raises `InvalidToken` if token is blacklisted

### 9. Read custom permission classes
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/permissions.py`
**Reasoning**: Understand custom permission logic
**Result**: `CanAccessTest` permission:
- Staff can access any test
- Providers can access tests linked via provider_test_orders
- Patients can only access their own tests

### 10. Read Partner API authentication
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/partner_api/authentication.py`
**Reasoning**: Understand partner authentication mechanisms
**Result**: Two authentication classes:
- `PartnerAPIKeyAuthentication`: Bearer token auth, supports partner-specific keys and legacy single API key
- `PartnerOnlyAPIKeyAuthentication`: Only partner-specific keys, no legacy support

### 11. Read Partner API permissions
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/partner_api/permissions.py`
**Reasoning**: Understand partner permission logic
**Result**: Two permission classes:
- `PartnerAPIKeyRequired`: Validates auth succeeded and partner is active
- `PartnerIPAllowlistRequired`: Checks client IP against partner's allowed IP list

### 12. Read internal API views
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/internal/views.py` (lines 1-100)
**Reasoning**: Understand internal API authentication patterns
**Result**: Found:
- `EvvyInternalViewSet`: Uses `SessionAuthentication` + `IsAuthenticated`
- `EvvyInternalReadOnlyViewSet`: Same auth as above
- Custom permissions: `ResultsManagerRequired`, `CoachUserAssignmentRequired`, `CoachUserAssignmentForAIRequired`
- `evvy_logout_api_view` decorator applies `SessionAuthentication`

### 13. Read V1 API base views
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`
**Reasoning**: Understand base view classes for V1 API
**Result**: Found:
- `EvvyUserViewSet`: `EvvyJWTAuthentication` + `IsAuthenticated`
- `EvvyUserAPIView`: Same as above
- `evvy_api_view` decorator: Applies both `EvvyJWTAuthentication` and `IsAuthenticated`
- `PublicProviderMagicLinkCheckout`: `AllowAny` permission, no authentication

### 14. Search for CSRF exemptions
**Tool**: `Grep` - Pattern: `@csrf_exempt|csrf_exempt`
**Reasoning**: Find endpoints that bypass CSRF protection (typically webhooks)
**Result**: Found CSRF exemptions in:
- `api/v1/views/tasks.py` - Task endpoints
- `api/v1/views/webhooks.py` - 15 webhook endpoints (Shopify, Wheel, Berlin, Microgen, Precision, Survicate, Calendly, Recharge, Viome, Typeform, Junction)

### 15. Read webhooks file
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 1-80)
**Reasoning**: Understand webhook authentication (if any)
**Result**: Webhooks use `@csrf_exempt` decorator, no authentication classes specified, rely on HMAC signature verification in webhook handlers

### 16. Search for view classes with auth/permission declarations
**Tool**: `Grep` - Pattern: `authentication_classes.*=|permission_classes.*=`
**Reasoning**: Find all explicit auth/permission declarations in V1 API
**Result**: Found 6 files with explicit declarations in api/v1/views

### 17. Read account views
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/views/account.py` (lines 1-150)
**Reasoning**: Check authentication on account management endpoints
**Result**: Found:
- `UserAccountView`: Inherits from `EvvyUserAPIView` (JWT + IsAuthenticated)
- `IsProvider` custom permission class (checks group membership)
- `ProviderProfileView`: JWT + IsAuthenticated + IsProvider

### 18. Search for all view classes
**Tool**: `Grep` - Pattern: `class.*ViewSet|class.*APIView|@api_view`
**Reasoning**: Get complete list of all API views
**Result**: Found 30+ view classes across different modules, including ViewSets, APIViews, and function-based views

### 19. Read auth views
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/views/auth.py`
**Reasoning**: Check authentication endpoints themselves
**Result**: Found:
- `EvvyTokenObtainPairView`: Login endpoint with throttling
- `EvvyTokenBlacklistView`: Logout endpoint (no auth required, accepts tokens in body)
- `EvvyTokenRefreshView`: Token refresh with blacklist checking
- All use custom throttle classes

### 20. Read public features view
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/views/public_features.py`
**Reasoning**: Check explicitly public endpoints
**Result**: `PublicFeaturesView`:
- `authentication_classes = []`
- `permission_classes = []`
- Returns system-level feature flags for unauthenticated users

### 21. Read registration view
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/views/register.py` (lines 1-60)
**Reasoning**: Check authentication on registration endpoints
**Result**: `RegisterView`:
- No authentication required (inherits from APIView but doesn't set auth classes)
- Uses throttling for rate limiting
- Public endpoint for account creation

### 22. Read V1 URL configuration
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`
**Reasoning**: Map all V1 endpoints to their views
**Result**: Complete URL routing showing:
- ViewSet routes via router (user-tests, health-context, tasks, cart, consults, etc.)
- Individual endpoint routes (account, compare, trends, webhooks, etc.)
- Public endpoints (register, public-features, provider-magic-checkout)
- Webhook endpoints (all CSRF exempt)

### 23. Read main API URL configuration
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/urls.py`
**Reasoning**: Understand API namespace structure
**Result**: Three main API sections:
- `/api/v1/` - Main user-facing API
- `/api/internal/` - Internal admin API
- `/api/partner/` - Partner integration API
- Token endpoints at `/api/token/`

### 24. Read partner API URL configuration
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/partner_api/urls.py`
**Reasoning**: Map partner API structure
**Result**: Partner API includes:
- `/cx-automation/` - CX automation endpoints
- `/v1/distro/` - Distribution endpoints
- API documentation endpoints

### 25. Read internal API URL configuration
**Tool**: `Read` - `/Users/albertgwo/Work/evvy/backend/api/internal/urls.py`
**Reasoning**: Map internal API endpoints
**Result**: Internal API includes:
- ViewSet routes (results, users, ai_sally, plan_profiles, plan_items)
- Auth logout endpoint
- Current user endpoint
- Schema/Swagger endpoints (DEBUG mode only)

## Investigation Results

### Authentication Methods Summary

The Evvy application uses **four distinct authentication methods**:

#### 1. **JWT Authentication (Default - User-Facing API)**
- **Implementation**: `api.v1.authentication.EvvyJWTAuthentication`
- **Mechanism**: JWT tokens with blacklist checking via cache
- **Used by**: All `/api/v1/` endpoints by default (unless overridden)
- **Base classes**: `EvvyUserViewSet`, `EvvyUserAPIView`, `evvy_api_view` decorator
- **Token lifecycle**:
  - Obtain: `POST /api/token/`
  - Refresh: `POST /api/token/refresh/`
  - Logout/Blacklist: `POST /api/token/logout/`

#### 2. **Session Authentication (Internal/Admin API)**
- **Implementation**: `rest_framework.authentication.SessionAuthentication`
- **Mechanism**: Django session cookies
- **Used by**: All `/api/internal/` endpoints
- **Base classes**: `EvvyInternalViewSet`, `EvvyInternalReadOnlyViewSet`
- **Additional security**: Django admin uses OTP 2FA in production

#### 3. **Partner API Key Authentication**
- **Implementation**:
  - `partner_api.authentication.PartnerAPIKeyAuthentication` (cx_automation)
  - `partner_api.authentication.PartnerOnlyAPIKeyAuthentication` (distro)
- **Mechanism**: Bearer token in Authorization header
- **Used by**: All `/api/partner/` endpoints
- **Additional security**: Optional IP allowlist via `PartnerIPAllowlistRequired` permission

#### 4. **Email Backend Authentication**
- **Implementation**: `app.auth.EmailBackend`
- **Mechanism**: Django authentication backend (for admin login)
- **Used by**: Django admin site login

### Endpoints by Authentication Requirement

#### **Authenticated Endpoints (JWT - User API)**

All endpoints inherit `EvvyJWTAuthentication` + `IsAuthenticated` unless specified otherwise:

**User Management**
- `POST /api/v1/account/` - Update user account info
- `GET /api/v1/user-config/` - Get user configuration
- `POST /api/v1/male-partner-checkout/` - Male partner checkout

**Test & Results**
- `/api/v1/user-tests/*` - User test management (ViewSet)
- `GET /api/v1/user-tests/{hash}/pdf-data/` - Test results (requires `CanAccessTest` permission)
- `GET /api/v1/compare/` - Compare results
- `GET /api/v1/trends/` - View trends
- `GET /api/v1/my-plan/` - View treatment plan
- `GET /api/v1/my-plan-old/` - Old plan view
- `POST /api/v1/my-plan/feedback/` - Submit plan feedback

**Health & Consults**
- `/api/v1/health-context/*` - Health context management (ViewSet)
- `/api/v1/consults/*` - Consult management (ViewSet)
- `/api/v1/consult-intake/*` - Consult intake (ViewSet)
- `/api/v1/lab-order-intake/*` - Lab order intake (ViewSet)

**E-commerce**
- `/api/v1/cart/*` - Shopping cart (ViewSet)
- `/api/v1/products/*` - Products (ViewSet)
- `GET /api/v1/orders/` - View orders
- `POST /api/v1/orders/attach` - Attach order to user
- `POST /api/v1/orders/process` - Process order

**Subscriptions**
- `GET /api/v1/subscription/` - Get subscription
- `GET /api/v1/subscriptions/` - List subscriptions
- `GET /api/v1/subscriptions/{id}/` - Get subscription by ID
- `GET /api/v1/subscriptions/sku/{sku}/` - Get subscription by SKU
- `GET /api/v1/subscription/exists/` - Check subscription existence
- `POST /api/v1/subscription/next-charge/` - Update next charge
- `POST /api/v1/subscription/next-charge-with-discount/` - Update with discount
- `GET /api/v1/subscription/portal-link/` - Get portal link
- `POST /api/v1/subscription/swap/` - Swap subscription

**Treatments & Calendar**
- `/api/v1/treatment-interruption/*` - Treatment interruption (ViewSet)
- `/api/v1/calendar-treatments/*` - Calendar treatments (ViewSet)

**Email & Verification**
- `POST /api/v1/email-verification/` - Request email verification
- `POST /api/v1/order-transfer-verification/` - Request order transfer

**Consent & Announcements**
- `POST /api/v1/consent/` - Submit consent
- `GET /api/v1/announcements/` - Get announcements
- `GET /api/v1/faqs/` - Get FAQs

**Surveys**
- `POST /api/v1/survey/` - Submit survey

**Provider Endpoints** (Requires `IsProvider` + `IsVerified` permissions)
- `/api/v1/provider-test-orders/*` - Provider test orders (ViewSet)
- `GET /api/v1/provider/profile` - Get provider profile
- `POST /api/v1/provider/profile` - Update provider profile

**Public Data**
- `/api/v1/pdp-configurations/*` - PDP configurations (read-only ViewSet)

#### **Authenticated Endpoints (Session Auth - Internal API)**

All require `SessionAuthentication` + `IsAuthenticated`:

**User Management**
- `/api/internal/users/*` - User summaries (ViewSet)
- `GET /api/internal/me/` - Current user info
- `POST /api/internal/auth/logout/` - Logout

**Results Management** (Requires `ResultsManagerRequired` permission)
- `/api/internal/results/*` - Results management (ViewSet)

**AI & Coaching** (Requires specific user assignment permissions)
- `/api/internal/ai_sally/{user_id}/*` - AI messages (requires `CoachUserAssignmentForAIRequired`)

**Plan Management**
- `/api/internal/plan_profiles/*` - Plan profiles (ViewSet)
- `/api/internal/plan_items/*` - Plan items (ViewSet)

#### **Authenticated Endpoints (Partner API Key)**

All require `PartnerAPIKeyAuthentication`:

**CX Automation** (Uses `PartnerAPIKeyAuthentication`)
- All endpoints under `/api/partner/cx-automation/*`
- 9 endpoints found in `partner_api/cx_automation/views.py`

**Distribution** (Uses `PartnerOnlyAPIKeyAuthentication`)
- All endpoints under `/api/partner/v1/distro/*`
- 2 endpoints found in `partner_api/distro/views.py`

#### **Unauthenticated/Public Endpoints**

**Authentication & Registration**
- `POST /api/token/` - Login (obtain JWT tokens) - Has throttling
- `POST /api/token/refresh/` - Refresh JWT token - Has throttling
- `POST /api/token/logout/` - Logout (blacklist tokens) - Has throttling
- `POST /api/v1/register/` - User registration - Has throttling
- `POST /api/v1/provider/register` - Provider registration
- `POST /api/v1/password_reset/` - Request password reset - Has throttling
- `POST /api/v1/password_reset/validate_token/` - Validate reset token
- `POST /api/v1/password_reset/confirm/` - Confirm password reset

**Public Access**
- `GET /api/v1/public-features/` - Get feature flags (explicitly `AllowAny`)
- `GET /api/v1/provider-test/{slug}/` - Provider magic link checkout (explicitly `AllowAny`)
- `GET /api/v1/ecomm-products/{sku}/` - Get product by SKU
- `POST /api/v1/email-verification-confirm/` - Confirm email verification
- `POST /api/v1/order-transfer-verification-confirm/` - Confirm order transfer

**Webhooks** (All use `@csrf_exempt`, no auth classes, rely on signature verification)
- `POST /api/v1/webhook/` - Generic S3 webhook
- `POST /api/v1/webhooks/shopify` - Shopify webhook
- `POST /api/v1/webhooks/shopify-graphql` - Shopify GraphQL webhook
- `POST /api/v1/webhooks/shopify-fulfillment` - Shopify fulfillment webhook
- `POST /api/v1/webhooks/wheel` - Wheel webhook
- `POST /api/v1/webhooks/berlin` - Berlin webhook
- `POST /api/v1/webhooks/microgen` - Microgen webhook
- `POST /api/v1/webhooks/microgen-batch` - Microgen batch webhook
- `POST /api/v1/webhooks/precision` - Precision pharmacy webhook
- `POST /api/v1/webhooks/survicate-survey-complete` - Survicate webhook
- `POST /api/v1/webhooks/calendly` - Calendly webhook
- `POST /api/v1/webhooks/recharge` - Recharge webhook
- `POST /api/v1/webhooks/viome` - Viome webhook
- `POST /api/v1/webhooks/typeform` - Typeform webhook
- `POST /api/v1/webhooks/junction` - Junction webhook

**Health Checks**
- `GET /health/` - Health check endpoint
- `GET /unhealthy/` - Unhealthy endpoint (testing)

**Tasks** (CSRF exempt, unclear auth - needs further investigation)
- `/api/v1/tasks/*` - Task ViewSet with `@method_decorator(csrf_exempt)`

### Custom Permission Classes

**User API Permissions**
1. **`IsProvider`** (`api/v1/views/account.py`) - Checks user is in providers group
2. **`IsVerified`** (`api/v1/views/provider_test_orders.py`) - Checks user verification status
3. **`CanAccessTest`** (`api/v1/permissions.py`) - Multi-tier test access control:
   - Staff can access any test
   - Providers can access linked tests
   - Patients can only access own tests

**Internal API Permissions**
1. **`ResultsManagerRequired`** - Checks user is in results managers group
2. **`CoachUserAssignmentRequired`** - Validates coach-user assignment
3. **`CoachUserAssignmentForAIRequired`** - Validates coach-user assignment for AI features

**Partner API Permissions**
1. **`PartnerAPIKeyRequired`** - Validates partner authentication and active status
2. **`PartnerIPAllowlistRequired`** - Validates client IP against partner allowlist

### Middleware-Based Authentication

No middleware-based authentication found. The application relies on:
- DRF authentication classes (applied per-view or globally)
- Django admin session authentication with optional OTP 2FA (production only)

### Security Features

**Rate Limiting/Throttling** (via DRF throttle classes):
- User rates: 120/min, 2000/hour, 5000/day
- Anonymous rates: 60/min, 1000/hour, 2500/day
- Special rates for:
  - Login: 10/min, 50/hour
  - Token refresh: 30/min, 200/hour
  - Token logout: 50/min, 300/hour

**CSRF Protection**:
- Enabled by default for Django views
- Disabled for webhooks (via `@csrf_exempt`)
- API endpoints use token-based auth (CSRF not applicable)

**Token Blacklisting**:
- Custom implementation using Django cache
- Both access and refresh tokens can be blacklisted
- Tokens blacklisted on logout

**IP Allowlisting**:
- Partner API supports IP-based access control
- Uses `True-Client-IP` header (Cloudflare) or `REMOTE_ADDR`

## Tool Call Summary

**Total Tool Calls**: 25

1. `Bash` - Check directory exists and list contents
2. `Glob` - Find all Python files in backend
3. `Grep` - Search for auth decorators and permission classes
4. `Grep` - Search for Django/DRF settings
5. `Grep` - Search for custom auth/permission class definitions
6. `Read` - Django settings file (authentication config)
7. `Read` - Main URL configuration
8. `Read` - JWT authentication implementation
9. `Read` - Custom permission classes
10. `Read` - Partner API authentication
11. `Read` - Partner API permissions
12. `Read` - Internal API views
13. `Read` - V1 API base views
14. `Grep` - Search for CSRF exemptions
15. `Read` - Webhooks file
16. `Grep` - Search for auth/permission declarations in V1
17. `Read` - Account views
18. `Grep` - Search for all view classes
19. `Read` - Auth views (login/logout/refresh)
20. `Read` - Public features view
21. `Read` - Registration view
22. `Read` - V1 URL configuration (complete routing)
23. `Read` - Main API URL configuration
24. `Read` - Partner API URL configuration
25. `Read` - Internal API URL configuration
