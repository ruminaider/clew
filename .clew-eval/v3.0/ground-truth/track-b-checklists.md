# Track B Ground-Truth Checklists (V3.0 Viability Evaluation)

**Codebase:** /Users/albertgwo/Work/evvy
**Generated:** 2026-02-19
**Purpose:** Frozen reference for scoring agent performance on enumeration scenarios

---

## D1: Celery Task Call Site Enumeration

> "Find every place in the codebase where a Celery task is enqueued — called with `.delay()`, `.apply_async()`, or `send_task()`. For each call site, identify which task is being called, what arguments are passed, and the business context."

### Viability: YES

The evvy codebase has 170+ Celery task call sites across the backend. Below are 10 representative examples across different business domains.

### Ground-Truth Checklist

1. **`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:763`**
   - Task: `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)`
   - Context: Order fulfillment pipeline — sends order to Berlin warehouse for processing
   - Arguments: order payload (dict), cancellation flag (bool), order ID (int)

2. **`/Users/albertgwo/Work/evvy/backend/shipping/tasks.py:768`**
   - Task: `send_order_to_berlin_for_fulfillment.delay(order.payload, is_order_cancellation, order.id)`
   - Context: Retry logic for failed Berlin fulfillment orders
   - Arguments: order payload from DB, cancellation status, order ID

3. **`/Users/albertgwo/Work/evvy/backend/consults/utils.py:218`**
   - Task: `send_consult_intake_ineligible_event.delay(consult.uid, refer_out_reason)`
   - Context: Analytics event when patient is ineligible for care consultation
   - Arguments: consult UID (UUID), referral-out reason (str)

4. **`/Users/albertgwo/Work/evvy/backend/analytics/tasks.py:1154`**
   - Task: `send_estimated_treatment_started_event.delay(treatment_plan.id)`
   - Context: Scheduled task to send analytics event when treatment plan estimated start date arrives
   - Arguments: treatment plan ID (int)

5. **`/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py:162-163`**
   - Task 1: `send_consult_intake_submitted_event.delay(consult_uid)`
   - Task 2: `send_consult_intake_reviewed_email.delay(consult_uid)`
   - Context: After submitting consult intake to Wheel API — triggers both analytics event and patient email
   - Arguments: consult UID (UUID)

6. **`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:229`**
   - Task: `send_prescription_refills_paid_event.delay(prescription_fill_id, order.provider_id)`
   - Context: After processing subscription refill order payment
   - Arguments: prescription fill ID (int), provider ID (int or None)

7. **`/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:450`**
   - Task: `process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)`
   - Context: Load-balancing webhook — delays test processing to avoid thundering herd
   - Arguments: test hash (str), countdown delay in seconds (int)

8. **`/Users/albertgwo/Work/evvy/backend/consults/utils.py:404`**
   - Task: `submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)`
   - Context: Submits lab order to Wheel with 5-minute delay (300 seconds)
   - Arguments: lab order UID (UUID), 5-minute countdown

9. **`/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py:599`**
   - Task: `send_treatment_delivered_event.delay(consult.uid)`
   - Context: Analytics event when Precision Pharmacy delivers prescription treatment
   - Arguments: consult UID (UUID)

10. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py:148`**
    - Task: `send_provider_ordered_test_klaviyo_event.delay(test_hash, provider_test_order.id)`
    - Context: Provider orders a test kit for a patient — triggers Klaviyo marketing event
    - Arguments: test hash (str), provider test order ID (int)

11. **`/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/results_processor.py:139`**
    - Task: `send_urine_test_results_ready_analytics_events.delay(urine_test.hash)`
    - Context: Urine test results processing complete — triggers analytics events for care eligibility
    - Arguments: urine test hash (str)

12. **`/Users/albertgwo/Work/evvy/backend/care/signals.py:121`**
    - Task: `create_or_reset_calendar_treatments.apply_async(args=[instance.treatment_plan_id], countdown=5)`
    - Context: Django signal after treatment plan update — re-generates calendar with 5-second delay
    - Arguments: treatment plan ID (int), 5-second countdown

---

## D2: Environment Variable and Settings Inventory

> "Create a complete inventory of all custom environment variables and Django settings that control application behavior."

### Viability: YES

The evvy codebase defines 80+ custom environment variables in `backend/app/settings.py` and references them throughout the codebase.

### Ground-Truth Checklist

1. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:36`**
   - Setting: `SECRET_KEY = env("SECRET_KEY")`
   - Purpose: Django secret key for cryptographic signing

2. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:39`**
   - Setting: `DEBUG = env("DEBUG", default=False)`
   - Purpose: Django debug mode toggle

3. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:60-62`**
   - Setting: `SITE_URL`, `INTERNAL_SITE_URL`, `BACKEND_URL`
   - Purpose: Dynamic URL configuration for multi-environment deployments (production vs preview)

4. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:652-653`**
   - Setting: `ROOT_LOG_LEVEL = os.environ.get("ROOT_LOG_LEVEL", "INFO")`
   - Setting: `DJANGO_LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO")`
   - Purpose: Configurable logging levels for root logger and Django logger

5. **`/Users/albertgwo/Work/evvy/backend/app/settings_celery.py:8-9`**
   - Setting: `CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis-queue:6379/0")`
   - Setting: `CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis-queue:6379/0")`
   - Purpose: Redis connection URLs for Celery task queue

6. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:441`**
   - Setting: `MANDRILL_API_KEY = env("MANDRILL_API_KEY", default=None)`
   - Purpose: Mandrill (transactional email) API authentication

7. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:443-444`**
   - Setting: `BRAZE_API_KEY`, `BRAZE_API_URL`
   - Purpose: Braze (marketing automation) API credentials

8. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:493-496`**
   - Setting: `WHEEL_ACCESS_TOKEN`, `WHEEL_API_KEY`, `WHEEL_API_URL`, `WHEEL_OPS_EMAIL`
   - Purpose: Wheel Health (telehealth platform) API configuration

9. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:505-508`**
   - Setting: `MICROGEN_SECRET_KEY`, `MICROGEN_API_URL`, `MICROGEN_API_KEY`, `MICROGEN_API_APP_ID`
   - Purpose: Microgen Diagnostics (lab partner) API credentials

10. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:514-517`**
    - Setting: `JUNCTION_API_KEY`, `JUNCTION_BASE_URL`, `JUNCTION_WEBHOOK_SECRET`
    - Purpose: Junction/Vital (urine test lab partner) API configuration

11. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:520-522`**
    - Setting: `PRECISION_SECRET_KEY`, `PRECISION_API_URL`, `PRECISION_ACCOUNT_ID`
    - Purpose: Precision Pharmacy (prescription fulfillment) API credentials

12. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:525-528`**
    - Setting: `BERLIN_ACCESS_TOKEN`, `BERLIN_API_URL`, `BERLIN_CLIENT_ID`, `BERLIN_CLIENT_SECRET`
    - Purpose: Berlin Packaging (fulfillment warehouse) OAuth2 credentials

13. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:468-472`**
    - Setting: `SHOPIFY_BASE_URL`, `SHOPIFY_STOREFRONT_ACCESS_TOKEN`, `SHOPIFY_ADMIN_ACCESS_TOKEN`, `SHOPIFY_WEBHOOK_SECRET`, `SHOPIFY_WEBHOOK_GRAPHQL_SECRET`
    - Purpose: Shopify ecommerce integration (storefront + admin API + webhooks)

14. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:554`**
    - Setting: `KLAVIYO_SECRET_KEY = env("KLAVIYO_SECRET_KEY", default="")`
    - Purpose: Klaviyo (email marketing) API key

15. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:543`**
    - Setting: `OPENAI_API_KEY = env("OPENAI_API_KEY", default=None)`
    - Purpose: OpenAI API key for AI-assisted features

16. **`/Users/albertgwo/Work/evvy/backend/test_results/lab_services/config.py:243-251`**
    - Setting: Wheel config loaded from `os.environ.get("WHEEL_API_KEY")`, `WHEEL_BASE_URL`, `WHEEL_SANDBOX`, `WHEEL_WEBHOOK_SECRET`, `WHEEL_APP_ID`
    - Purpose: Lab services abstraction layer — runtime Wheel configuration

17. **`/Users/albertgwo/Work/evvy/backend/partner_api/partner_config.py:43-45`**
    - Setting: `grow_baby_api_key = os.environ.get("GROW_BABY_API_KEY")`
    - Setting: `grow_baby_cohort_title = os.environ.get("GROW_BABY_COHORT_TITLE")`
    - Setting: `grow_baby_allowed_ips = os.environ.get("GROW_BABY_ALLOWED_IPS")`
    - Purpose: Partner API integration for Grow Baby study

18. **`/Users/albertgwo/Work/evvy/backend/partner_api/docs.py:23`**
    - Setting: `os.environ.get("ENABLE_PARTNER_API_DOCS", "").lower() == "true"`
    - Purpose: Feature flag to enable/disable partner API documentation endpoint

---

## D3: Email Confirmation Debugging (mode-negative test)

> "A user reported that their subscription order was processed successfully but no confirmation email was sent. Investigate the email sending pipeline."

### Viability: YES

The evvy codebase has a comprehensive email pipeline with transactional email sending, templated emails via Mandrill, and order/subscription hooks.

### Ground-Truth Checklist

1. **`/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:45-59`**
   - Function: `send_templated_email(to_address, template_id, context={}, ...)`
   - Purpose: Core email sending utility — uses Mandrill templates, checks duplicate constraints, logs to EmailSent model

2. **`/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:20-43`**
   - Function: `send_transactional_email(subject="", body="", from_address=..., to_addresses=[])`
   - Purpose: Simple SMTP email sending (used for non-templated emails)

3. **`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:229`**
   - Task: `send_prescription_refills_paid_event.delay(prescription_fill_id, order.provider_id)`
   - Context: Subscription refill order payment — triggers analytics event (may also send email)

4. **`/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py:1199-1232`**
   - Task: `send_account_transfer_verification_email(user_id, order_email, order_number)`
   - Purpose: Sends email when order email doesn't match user account email — verification flow
   - Template: `TEMPLATE_ACCOUNT_ORDER_TRANSFER`

5. **`/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py:705`**
   - Call site: `send_account_transfer_verification_email.delay(user.id, order.email, order_number)`
   - Context: Order completion hook — triggers verification email if email mismatch

6. **`/Users/albertgwo/Work/evvy/backend/transactional_email/constants.py`** (implied)
   - Setting: `DISABLED_EMAIL_FLOWS` dictionary
   - Purpose: Feature flag to disable specific email templates without code changes
   - Check: `constants.DISABLED_EMAIL_FLOWS.get(template_id, False)` at line 57 of utils.py

7. **`/Users/albertgwo/Work/evvy/backend/transactional_email/models.py`** (implied)
   - Model: `EmailSent`
   - Purpose: Tracks all sent emails with template ID, recipient, context, timestamp
   - Used for: Duplicate detection, debugging, audit trail

8. **`/Users/albertgwo/Work/evvy/backend/transactional_email/mandrill.py`** (implied from imports)
   - Integration: Mandrill email service provider
   - Purpose: Actual email dispatch — `send_templated_email` delegates to Mandrill API

9. **`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:691`**
   - Task: `send_ungated_rx_order_paid_event.delay(order.order_number)`
   - Context: Ungated RX order paid — triggers analytics event (likely includes email notification)

10. **`/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py:49`**
    - Check: `if not settings.RECHARGE_API_KEY: raise ValueError(...)`
    - Context: Subscription processing via Recharge API — if API key missing, subscriptions fail silently

11. **`/Users/albertgwo/Work/evvy/backend/app/settings.py:437-441`**
    - Setting: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `MANDRILL_API_KEY`
    - Purpose: SMTP and Mandrill configuration — missing values cause email send failures

12. **`/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:195-196`** (within `send_templated_email`)
    - Error handling: If Mandrill send fails, falls back to `send_transactional_email(...)` (SMTP)
    - Purpose: Redundancy in email sending — Mandrill failure doesn't block all emails

---

## D4: Authentication and Permission Mapping

> "Find all API endpoints that require authentication and identify which authentication method each uses."

### Viability: YES

The evvy codebase has a comprehensive authentication and permission system with custom JWT authentication, role-based permissions, and per-endpoint permission classes.

### Ground-Truth Checklist

1. **`/Users/albertgwo/Work/evvy/backend/api/v1/authentication.py:7-26`**
   - Class: `EvvyJWTAuthentication(JWTAuthentication)`
   - Purpose: Custom JWT authentication with token blacklist checking via cache
   - Used by: All authenticated API endpoints (via `EvvyUserAPIView` and `EvvyUserViewSet`)

2. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py:11-13`**
   - Class: `EvvyUserViewSet(viewsets.ModelViewSet)`
   - Permission: `permission_classes = [permissions.IsAuthenticated]`
   - Authentication: `authentication_classes = [EvvyJWTAuthentication]`
   - Usage: Base class for all authenticated ModelViewSet endpoints

3. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py:16-18`**
   - Class: `EvvyUserAPIView(APIView)`
   - Permission: `permission_classes = [permissions.IsAuthenticated]`
   - Authentication: `authentication_classes = [EvvyJWTAuthentication]`
   - Usage: Base class for all authenticated APIView endpoints

4. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py:37-39`**
   - Class: `PublicProviderMagicLinkCheckout(APIView)`
   - Permission: `permission_classes = [permissions.AllowAny]`
   - Authentication: `authentication_classes = []`
   - Purpose: Public endpoint for provider magic link checkout (no auth required)

5. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/account.py:134-136`**
   - Class: `IsProvider(permissions.BasePermission)`
   - Check: `request.user.groups.filter(name=GROUP_NAME_PROVIDERS).exists()`
   - Usage: Provider-only endpoints require this permission

6. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/account.py:139-150`**
   - Class: `ProviderProfileView(EvvyUserAPIView)`
   - Permission: `EvvyUserAPIView.permission_classes + [IsProvider]`
   - Purpose: Provider profile management — requires both authentication AND provider group membership

7. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py:47-51`**
   - Class: `IsVerified(permissions.BasePermission)`
   - Check: `get_provider_profile(request.user).verified`
   - Purpose: Verified provider status — checks database field

8. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py:54-56`**
   - Class: `ProviderTestOrderViewSet(EvvyUserViewSet)`
   - Permission: `EvvyUserViewSet.permission_classes + [IsProvider, IsVerified]`
   - Purpose: Provider test ordering — requires authentication + provider role + verification

9. **`/Users/albertgwo/Work/evvy/backend/api/v1/permissions.py:11-36`**
   - Class: `CanAccessTest(permissions.BasePermission)`
   - Logic: Staff can access any test, providers can access tests linked via `provider_test_orders`, patients can only access their own tests
   - Purpose: Object-level permission for test result access

10. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/user_test_results.py:40`**
    - Class: `UserTestResultsView(EvvyUserAPIView)`
    - Permission: `EvvyUserAPIView.permission_classes + [CanAccessTest]`
    - Purpose: Test result viewing — requires authentication + object-level test access check

11. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:56`**
    - Decorator: `@csrf_exempt` on `process_shopify_webhook_fulfillment_create`
    - Purpose: External webhook from Shopify — bypasses CSRF protection (uses webhook signature validation instead)

12. **`/Users/albertgwo/Work/evvy/backend/api/internal/views.py:94`**
    - Class: Internal API view with `permission_classes = [IsAuthenticated]`
    - Purpose: Internal-only endpoints (not exposed to public frontend)

13. **`/Users/albertgwo/Work/evvy/backend/api/internal/views.py:154`**
    - Class: Internal view with `permission_classes = [ResultsManagerRequired, IsAuthenticated]`
    - Purpose: Results manager role — custom permission for lab operations team

14. **`/Users/albertgwo/Work/evvy/backend/api/internal/views.py:167`**
    - Class: Internal view with `permission_classes = [IsAuthenticated, CoachUserAssignmentRequired]`
    - Purpose: Coaching call assignment — requires specific coach-user relationship

15. **`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py:21-34`**
    - Function decorator: `evvy_api_view(*args, **kwargs)`
    - Purpose: Decorator factory for function-based views — applies `IsAuthenticated` + `EvvyJWTAuthentication`

---

## Notes

- **D1 (Celery Tasks):** The codebase has 170+ `.delay()` call sites. Manual enumeration would be time-consuming. Pattern searches for `.delay(`, `.apply_async(` are essential. Business context requires reading surrounding code.

- **D2 (Environment Variables):** 80+ environment variables defined. Settings are loaded via `django-environ` (`env()` function) and direct `os.environ.get()` calls. Custom settings are defined throughout `settings.py` and referenced in integration code. Requires searching both patterns.

- **D3 (Email Debugging):** Email pipeline has multiple layers: `send_templated_email` (Mandrill) → fallback to `send_transactional_email` (SMTP), EmailSent tracking model, `DISABLED_EMAIL_FLOWS` feature flags, and async Celery tasks. Debugging requires tracing from order completion hooks through task dispatch to actual send calls.

- **D4 (Authentication):** Authentication is layered: base JWT auth (`EvvyJWTAuthentication`) + base permission classes (`IsAuthenticated`) + role-specific permissions (`IsProvider`, `IsVerified`) + object-level permissions (`CanAccessTest`). Public endpoints explicitly set `AllowAny`. Webhooks use `@csrf_exempt` + custom signature validation.

---

**Evaluation Instructions:**

For each scenario, agents should produce a checklist of ≥5 specific artifacts (file paths, line numbers, entity names, business context). Score based on:

1. **Coverage**: Does the agent find the majority of relevant artifacts listed above?
2. **Precision**: Are the identified artifacts correct and relevant?
3. **Depth**: Does the agent explain the business context and technical details?
4. **Enumeration Completeness**: For D1/D2/D4, does the agent acknowledge the full scope (e.g., "found 170+ call sites, here are 10 representative examples")?

Agents that rely solely on semantic search without grep/pattern matching will likely miss critical artifacts in D1, D2, and D4.
