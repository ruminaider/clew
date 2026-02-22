# D4 Beta Evaluation Transcript

**Task:** Find all API endpoints that require authentication and identify which authentication method each uses (token auth, session auth, OAuth, API key, permission classes, etc.). Include decorator-based auth, middleware-based auth, and any custom auth backends. Also identify any endpoints that are explicitly exempted from authentication.

**Date:** 2026-02-19

## Tool Calls

### 1. Check search modes
```
search_help()
```
Result: Confirmed 3 search modes available: semantic, keyword, exhaustive

### 2. Search for authentication decorators
```
search("authentication decorator login_required permission_classes")
```
Found key files:
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py` - EvvyUserViewSet, EvvyUserAPIView
- `/Users/albertgwo/Work/evvy/backend/api/internal/views.py` - Internal API views
- `/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py` - EvvyJWTAuthentication
- `/Users/albertgwo/Work/evvy/backend/partner_api/permissions.py` - PartnerAPIKeyRequired

### 3. Search for DRF permission classes
```
search("IsAuthenticated AllowAny authentication_classes")
```
Found:
- EvvyInternalAPIView, EvvyInternalViewSet with SessionAuthentication
- EvvyUserAPIView, EvvyUserViewSet with EvvyJWTAuthentication
- Various permission classes: IsProvider, IsVerified, etc.

### 4. Search for APIView viewsets
```
search("APIView viewset API endpoint authentication")
```
Found additional ViewSets and APIView classes

### 5. Read core authentication files
Read files:
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`
- `/Users/albertgwo/Work/evvy/backend/api/internal/views.py`
- `/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/authentication.py`

### 6. Read URL configurations
Read files:
- `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`
- `/Users/albertgwo/Work/evvy/backend/api/internal/urls.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/urls.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/cx_automation/urls.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/distro/urls.py`

### 7. Search for public/unauthenticated endpoints
```
search("csrf_exempt AllowAny unauthenticated public")
```
Found:
- PublicProviderMagicLinkCheckout (AllowAny)
- PublicFeaturesView (AllowAny)
- Various webhook views with @csrf_exempt

### 8. Search for webhook views
```
search("webhook_view csrf_exempt", extended=true)
```
Found all webhook endpoints with CSRF exemption

### 9. Read webhook implementation
Read `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (partial reads)

### 10. Search for ViewSet class definitions
```
search("class.*ViewSet class.*APIView permission_classes authentication_classes", mode="broad")
```
Found comprehensive list of all ViewSet and APIView classes

### 11. Read partner API views
Read files:
- `/Users/albertgwo/Work/evvy/backend/partner_api/cx_automation/views.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/distro/views.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/permissions.py`

### 12. Read auth and registration views
Read files:
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/auth.py`
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/register.py`

### 13. Find related code for EvvyUserViewSet
```
search("code related to EvvyUserViewSet")
```
Found all ViewSets that inherit from EvvyUserViewSet

### 14. Read password reset views
Read `/Users/albertgwo/Work/evvy/backend/api/v1/views/reset_password.py`

### 15. Search for throttled endpoints
```
search("throttle_classes", mode="broad")
```
Found throttled endpoints (typically unauthenticated)

## Complete API Authentication Inventory

### Authentication Methods

#### 1. JWT Token Authentication (EvvyJWTAuthentication)
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py`
- Custom JWT authentication extending `JWTAuthentication`
- Checks for blacklisted tokens in cache
- Used by main user-facing API endpoints

#### 2. Session Authentication
**Django REST Framework's SessionAuthentication**
- Used by internal/admin API endpoints
- Cookie-based authentication

#### 3. Partner API Key Authentication
**Files:**
- `/Users/albertgwo/Work/evvy/backend/partner_api/authentication.py`
  - `PartnerAPIKeyAuthentication` - Bearer token for partner integrations
  - `PartnerOnlyAPIKeyAuthentication` - Partner-specific API keys only (distro module)
- Bearer token in Authorization header: `Authorization: Bearer <api_key>`

### Base Classes & Decorators

#### Base ViewSet/APIView Classes

**1. EvvyUserViewSet** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`)
```python
permission_classes = [permissions.IsAuthenticated]
authentication_classes = [EvvyJWTAuthentication]
```

**2. EvvyUserAPIView** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`)
```python
permission_classes = [permissions.IsAuthenticated]
authentication_classes = [EvvyJWTAuthentication]
```

**3. evvy_api_view decorator** (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`)
```python
# Applies IsAuthenticated + EvvyJWTAuthentication
```

**4. EvvyInternalViewSet** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
```python
permission_classes = [IsAuthenticated]
authentication_classes = [SessionAuthentication]
```

**5. EvvyInternalReadOnlyViewSet** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
```python
permission_classes = [IsAuthenticated]
authentication_classes = [SessionAuthentication]
```

**6. EvvyInternalAPIView** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
```python
permission_classes = [IsAuthenticated]
authentication_classes = [SessionAuthentication]
```

**7. evvy_logout_api_view decorator** (`/Users/albertgwo/Work/evvy/backend/api/internal/views.py`)
```python
# Applies SessionAuthentication only (no permission check)
```

### API v1 Endpoints (JWT Authentication)

**Base URL:** `/api/v1/`

#### Router-Registered ViewSets (All require JWT auth via EvvyUserViewSet)
From `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`:

1. **UserTestViewSet** - `/user-tests/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

2. **HealthContextViewSet** - `/health-context/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

3. **TasksViewSet** - `/tasks/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

4. **CartViewSet** - `/cart/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated
   - **Exception:** POST method has no auth required (override in get_permissions)

5. **ConsultViewSet** - `/consults/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

6. **ConsultIntakeViewSet** - `/consult-intake/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

7. **LabOrderIntakeViewSet** - `/lab-order-intake/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

8. **TreatmentPlanInterruptionViewSet** - `/treatment-interruption/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

9. **ProductViewSet** - `/products/`
   - Auth: EvvyJWTAuthentication
   - Permissions: IsAuthenticated

10. **ProviderTestOrderViewSet** - `/provider-test-orders/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated, IsVerified (custom permission)

11. **CalendarTreatmentViewSet** - `/calendar-treatments/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

12. **PDPConfigurationViewSet** - `/pdp-configurations/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

#### One-off APIView Endpoints (JWT Authentication Required)

13. **UserAccountView** - `/account/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

14. **CompareView** - `/compare/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

15. **TrendsView** - `/trends/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

16. **EmailVerificationView** - `/email-verification/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated
    - Throttling: LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle

17. **EmailVerificationConfirmView** - `/email-verification-confirm/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated (allows unauthenticated users to confirm)

18. **AccountOrderTransferVerification** - `/order-transfer-verification/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

19. **AccountOrderTransferConfirmVerification** - `/order-transfer-verification-confirm/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated (allows unauthenticated)

20. **ConsentView** - `/consent/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

21. **MyPlanOldView** - `/my-plan-old/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

22. **MyPlanView** - `/my-plan/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

23. **MyPlanFeedback** - `/my-plan/feedback/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

24. **OrdersView** - `/orders/`, `/orders/attach`, `/orders/process`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

25. **UserConfigView** - `/user-config/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

26. **MalePartnerCheckoutView** - `/male-partner-checkout/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

27. **UserTestResultsView** - `/user-tests/<hash>/pdf-data/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

28. **AnnouncementsView** - `/announcements/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

29. **FAQPageView** - `/faqs/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

30. **ProviderProfileView** - `/provider/profile`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated, IsProvider (custom permission)

31. **Subscription Endpoints** (multiple)
    - `/subscription/`, `/subscriptions/`, `/subscriptions/<id>/`, etc.
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

32. **SurveyView** - `/survey/`
    - Auth: EvvyJWTAuthentication
    - Permissions: IsAuthenticated

#### Public Endpoints (No Authentication Required)

33. **PublicProviderMagicLinkCheckout** - `/provider-test/<slug>/`
    - Auth: None (`authentication_classes = []`)
    - Permissions: AllowAny
    - Public endpoint for magic link checkout

34. **PublicFeaturesView** - `/public-features/`
    - Auth: None (implicit AllowAny)
    - Permissions: AllowAny
    - Returns feature flags for unauthenticated users

35. **EcommProductView** - `/ecomm-products/<sku>/`
    - Auth: None (implicit AllowAny)
    - Permissions: AllowAny
    - Public endpoint to get product by SKU

36. **RegisterView** - `/register/`
    - Auth: None (unauthenticated by design)
    - Permissions: None
    - Throttling: LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle
    - Creates new user account

37. **RegisterProviderView** - `/provider/register`
    - Auth: None (unauthenticated by design)
    - Permissions: None
    - Throttling: LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle
    - Creates new provider account

38. **EvvyTokenObtainPairView** (JWT login endpoint)
    - Auth: None (login endpoint)
    - Permissions: None
    - Throttling: LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle

39. **EvvyTokenBlacklistView** (JWT logout endpoint)
    - Auth: None (but requires tokens)
    - Permissions: None
    - Throttling: TokenLogoutAnonMinuteRateThrottle, TokenLogoutAnonHourRateThrottle

40. **EvvyTokenRefreshView** (JWT refresh endpoint)
    - Auth: None (refresh endpoint)
    - Permissions: None
    - Throttling: TokenRefreshAnonMinuteRateThrottle, TokenRefreshAnonHourRateThrottle

41. **EvvyResetPasswordRequestToken** - `/password_reset/`
    - Auth: None (password reset flow)
    - Permissions: None
    - Throttling: LoginAnonMinuteRateThrottle, LoginAnonHourRateThrottle

42. **EvvyResetPasswordValidateToken** - `/password_reset/validate_token/`
    - Auth: None (password reset flow)
    - Permissions: None
    - Throttling: DEFAULT_THROTTLE_CLASSES

43. **EvvyResetPasswordConfirm** - `/password_reset/confirm/`
    - Auth: None (password reset flow)
    - Permissions: None
    - Throttling: DEFAULT_THROTTLE_CLASSES

#### Webhook Endpoints (CSRF Exempt, Custom Verification)

All webhooks decorated with `@csrf_exempt` and use HMAC signature verification or custom token verification:

44. **webhook_view** - `/webhook/`
    - Auth: None (CSRF exempt)
    - Verification: S3 webhook (internal)

45. **shopify_webhook_view** - `/webhooks/shopify`
    - Auth: None (CSRF exempt)
    - Verification: HMAC-SHA256 signature (X-Shopify-Hmac-SHA256 header)

46. **shopify_webhook_graphql_view** - `/webhooks/shopify-graphql`
    - Auth: None (CSRF exempt)
    - Verification: HMAC-SHA256 signature

47. **shopify_fulfillment_webhook_view** - `/webhooks/shopify-fulfillment`
    - Auth: None (CSRF exempt)
    - Verification: HMAC-SHA256 signature

48. **wheel_webhook_view** - `/webhooks/wheel`
    - Auth: None (CSRF exempt)
    - Verification: X-Wheel-Access-Token header

49. **berlin_webhook_view** - `/webhooks/berlin`
    - Auth: None (CSRF exempt)
    - Verification: X-Berlin-Access-Token header

50. **microgen_webhook_view** - `/webhooks/microgen`
    - Auth: None (CSRF exempt)
    - Verification: HMAC-SHA256 signature (X-Microgen-Hmac-SHA256 header)

51. **microgen_batch_webhook_view** - `/webhooks/microgen-batch`
    - Auth: None (CSRF exempt)
    - Verification: HMAC-SHA256 signature

52. **precision_pharmacy_webhook_view** - `/webhooks/precision`
    - Auth: None (CSRF exempt)
    - Verification: HMAC signature (x-hmac-hash header)

53. **survicate_survey_complete_webhook_view** - `/webhooks/survicate-survey-complete`
    - Auth: None (CSRF exempt)
    - Verification: Custom webhook verification

54. **calendly_webhook_view** - `/webhooks/calendly`
    - Auth: None (CSRF exempt)
    - Verification: Custom webhook verification

55. **recharge_webhook_view** - `/webhooks/recharge`
    - Auth: None (CSRF exempt)
    - Verification: HMAC signature (X-Recharge-Hmac-Sha256 header)

56. **viome_webhook_view** - `/webhooks/viome`
    - Auth: None (CSRF exempt)
    - Verification: Custom webhook verification

57. **typeform_webhook_view** - `/webhooks/typeform`
    - Auth: None (CSRF exempt)
    - Verification: Custom webhook verification

58. **junction_webhook_view** - `/webhooks/junction`
    - Auth: None (CSRF exempt)
    - Verification: Svix signature verification (svix-id, svix-timestamp, svix-signature headers)

### Internal Admin API Endpoints (Session Authentication)

**Base URL:** `/api/admin/`

#### Router-Registered ViewSets (All require Session auth)

59. **ResultsViewSet** - `/results/`
    - Auth: SessionAuthentication
    - Permissions: IsAuthenticated, ResultsManagerRequired
    - Custom permission: Must be in Results Managers group

60. **UserSummaryViewSet** - `/users/`
    - Auth: SessionAuthentication
    - Permissions: IsAuthenticated, CoachUserAssignmentRequired
    - Custom permission: Coach must have assignment or be Results Manager

61. **AIMessageViewSet** - `/ai_sally/<user_id>/`
    - Auth: SessionAuthentication
    - Permissions: IsAuthenticated, CoachUserAssignmentForAIRequired
    - Custom permission: Coach must have assignment for specific user

62. **PlanProfileViewSet** - `/plan_profiles/`
    - Auth: SessionAuthentication
    - Permissions: IsAuthenticated, ResultsManagerRequired

63. **PlanItemViewset** - `/plan_items/`
    - Auth: SessionAuthentication
    - Permissions: IsAuthenticated, ResultsManagerRequired

#### One-off APIView Endpoints (Session Authentication)

64. **logout_view** - `/auth/logout/`
    - Auth: SessionAuthentication (decorator)
    - Permissions: None (allows authenticated logout)

65. **CurrentUserView** - `/me/`
    - Auth: SessionAuthentication
    - Permissions: IsAuthenticated

### Partner API Endpoints (API Key Authentication)

**Base URL:** `/api/partner/`

#### CX Automation Module (Partner API Key)

**Base URL:** `/api/partner/cx-automation/`

All views use:
```python
authentication_classes = [PartnerAPIKeyAuthentication]
permission_classes = [PartnerAPIKeyRequired]
```

66. **TestLookupView** - `/test/`
    - Auth: PartnerAPIKeyAuthentication (Bearer token)
    - Permissions: PartnerAPIKeyRequired

67. **TestStatusView** - `/test/<test_hash>/status/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

68. **TestShippingView** - `/test/<test_hash>/shipping-status/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

69. **TestCoachingView** - `/test/<test_hash>/coaching-info/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

70. **TestHealthHistoryView** - `/test/<test_hash>/health-history/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

71. **ConsultLookupView** - `/test/<test_hash>/consult-lookup/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

72. **ConsultStatusView** - `/consult/<consult_id>/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

73. **ConsultIntakeView** - `/consult/<consult_id>/intake/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

74. **PrescriptionStatusView** - `/consult/<consult_id>/prescription/`
    - Auth: PartnerAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired

#### Distro Module (Partner-Only API Key + IP Allowlist)

**Base URL:** `/api/partner/v1/distro/`

All views use:
```python
authentication_classes = [PartnerOnlyAPIKeyAuthentication]
permission_classes = [PartnerAPIKeyRequired, PartnerIPAllowlistRequired]
```

75. **PartnerReportsView** - `/reports/<test_hash>/`
    - Auth: PartnerOnlyAPIKeyAuthentication (Bearer token, partner-specific)
    - Permissions: PartnerAPIKeyRequired, PartnerIPAllowlistRequired
    - Additional: Cohort-based access control

76. **PartnerTestStatusesView** - `/tests/statuses/`
    - Auth: PartnerOnlyAPIKeyAuthentication
    - Permissions: PartnerAPIKeyRequired, PartnerIPAllowlistRequired
    - Additional: Cohort-based access control

### Custom Permission Classes

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/permissions.py`

1. **CanAccessTest** - Object-level permission for test access
   - Staff can access any test
   - Providers can access tests linked via provider_test_orders
   - Patients can only access their own tests

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/account.py`

2. **IsProvider** - Checks if user is in PROVIDERS group

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py`

3. **IsVerified** - Checks if provider profile is verified

**File:** `/Users/albertgwo/Work/evvy/backend/api/internal/views.py`

4. **ResultsManagerRequired** - Must be in RESULTS_MANAGERS group
5. **CoachUserAssignmentRequired** - Must have coach assignment or be Results Manager
6. **CoachUserAssignmentForAIRequired** - Must have coach assignment for specific user

**File:** `/Users/albertgwo/Work/evvy/backend/partner_api/permissions.py`

7. **PartnerAPIKeyRequired** - Checks authentication succeeded and partner is active
8. **PartnerIPAllowlistRequired** - Validates client IP against partner's allowed list

## Summary

### Authentication Methods Used:
1. **JWT Token Auth** (EvvyJWTAuthentication) - Main user API (34 endpoints + all viewsets)
2. **Session Auth** (SessionAuthentication) - Internal admin API (7 endpoints)
3. **Partner API Key Auth** (Bearer token) - Partner integrations (11 endpoints)
4. **No Auth (Public)** - Registration, login, password reset, public features (9 endpoints)
5. **CSRF Exempt Webhooks** - External service webhooks with signature verification (15 endpoints)

### Total Endpoints: 76

**By Authentication Type:**
- JWT Auth: ~46 endpoints
- Session Auth: 7 endpoints
- Partner API Key: 11 endpoints
- Public/No Auth: 9 endpoints
- Webhooks (CSRF exempt): 15 endpoints

**Special Cases:**
- CartViewSet POST: No auth required (override)
- EmailVerificationConfirmView: Allows unauthenticated users
- AccountOrderTransferConfirmVerification: Allows unauthenticated users
- All webhooks: CSRF exempt but use HMAC or custom token verification

### Permission Hierarchy:
1. Public endpoints (no auth)
2. Authenticated endpoints (JWT/Session)
3. Role-based endpoints (ResultsManager, Provider, Coach)
4. Object-level permissions (CanAccessTest)
5. Partner API endpoints (API key + optional IP allowlist)
