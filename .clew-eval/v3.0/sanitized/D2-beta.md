# Complete Environment Variables and Django Settings Inventory

## Tool Calls and Reasoning

### Discovery Phase

**Tool Call 1-2:** Searched for settings and configuration
- Found main settings file at `/Users/albertgwo/Work/evvy/backend/app/settings.py`
- Found Celery settings at `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py`

**Tool Call 3-4:** Read main settings files
- Identified use of `django-environ` library for environment variable management
- Pattern: `env = environ.Env(DEBUG=(bool, False))` then `env("VAR_NAME", default=value)`

**Tool Call 5:** Searched for `os.environ.get` patterns
- Found additional usage in `app/utils.py`, `settings_celery.py`, `settings.py`

**Tool Call 6:** Searched for Django settings imports
- Identified 30+ files importing `from django.conf import settings`

**Tool Call 7-8:** Searched for specific setting usage patterns
- External services: SHOPIFY, RECHARGE, WHEEL, MICROGEN
- Feature flags and behavior controls

**Tool Call 9-10:** Read throttling and utils files to understand usage
- `THROTTLE_MODE` setting controls whether throttling enforces or just warns
- `FEATURE_FLAG_*` settings enable/disable specific features

**Tool Call 11-12:** Searched for operational settings
- Found `PAUSE_AUTO_RELEASE_RESULTS`, `HYDRATE_DB_ON_INIT`, `RESULTS_PROCESSING_MAX_DELAY_MINUTES`

**Tool Call 13:** Found `.env.example` file
- Complete reference for local development environment variables

**Tool Call 14:** Read `.env.example`
- Comprehensive list of all configurable environment variables

**Tool Call 15-16:** Searched for conditional feature usage and read lab config
- Junction and Microgen provider configurations
- Lab services abstraction layer

**Tool Call 17:** Read `app/utils.py`
- Environment detection utilities based on `NEW_RELIC_ENVIRONMENT`

---

## Complete Inventory of Custom Environment Variables and Django Settings

### 1. Core Application Settings

#### SECRET_KEY
- **Defined:** `backend/app/settings.py` line 36
- **Read from:** `env("SECRET_KEY")` (required, no default)
- **Used in:** Django framework for cryptographic signing
- **Behavior:** Core Django security - session signing, CSRF protection, password reset tokens

#### DEBUG
- **Defined:** `backend/app/settings.py` line 39
- **Read from:** `env("DEBUG", default=False)` with boolean casting
- **Used in:** Django framework throughout application
- **Behavior:** Enables debug mode (detailed error pages, static file serving)

#### NEW_RELIC_ENVIRONMENT
- **Defined:** `backend/app/settings.py` line 193
- **Read from:** `env("NEW_RELIC_ENVIRONMENT", default="unset")`
- **Used in:**
  - `backend/app/utils.py::get_environment()` - environment detection
  - `backend/app/utils.py::is_production_env()`, `is_staging_env()`, `is_local_env()`
- **Behavior:** Determines runtime environment (production/staging/preview/local), affects feature availability and logging

### 2. Database Configuration

#### DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_HOST_PORT
- **Defined:** `backend/app/settings.py` lines 303-307
- **Read from:** `env("DB_NAME")`, `env("DB_USER")`, etc. (all required)
- **Used in:** `settings.DATABASES['default']` configuration
- **Behavior:** PostgreSQL database connection parameters

### 3. URL Configuration

#### RENDER_EXTERNAL_URL
- **Defined:** `backend/app/settings.py` line 44
- **Read from:** `env("RENDER_EXTERNAL_URL", default=None)`
- **Alias:** Set to `RENDER_BACKEND_URL` in settings
- **Used in:**
  - Lines 68-70: Parsed to extract host for ALLOWED_HOSTS
  - Lines 119-120: Added to CSRF_TRUSTED_ORIGINS
- **Behavior:** Automatically injected by Render hosting, used for backend URL detection

#### RENDER_FRONTEND_HOST, RENDER_INTERNAL_FRONTEND_HOST
- **Defined:** `backend/app/settings.py` lines 47-48
- **Read from:** `env("RENDER_FRONTEND_HOST", default=None)`, `env("RENDER_INTERNAL_FRONTEND_HOST", default=None)`
- **Used in:**
  - Lines 49-56: Construct full URLs
  - Lines 91-105: Added to CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS
  - Lines 96-105: Used to dynamically set SITE_URL/INTERNAL_SITE_URL on preview environments
- **Behavior:** Render-specific frontend host configuration for CORS and CSRF

#### SITE_URL, INTERNAL_SITE_URL, BACKEND_URL
- **Defined:** `backend/app/settings.py` lines 60-62
- **Read from:** `env("SITE_URL", default="")`, `env("INTERNAL_SITE_URL", default="")`, `env("BACKEND_URL", default="")`
- **Used in:**
  - Lines 72-77: BACKEND_URL parsed for ALLOWED_HOSTS
  - Lines 107-118: All three added to CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS
  - Special value "dynamic" triggers auto-construction from Render URLs
- **Behavior:** Custom domain URLs for production/permanent environments, controls CORS and CSRF validation

#### ADDITIONAL_ALLOWED_BACKEND_HOSTS
- **Defined:** `backend/app/settings.py` line 80
- **Read from:** `env.list("ADDITIONAL_ALLOWED_BACKEND_HOSTS", default=[])`
- **Used in:** Line 81: Extended to ALLOWED_HOSTS
- **Behavior:** Runtime-configurable backend hosts without code deployment

#### ADDITIONAL_ALLOWED_CORS_ORIGINS
- **Defined:** `backend/app/settings.py` line 123
- **Read from:** `env.list("ADDITIONAL_ALLOWED_CORS_ORIGINS", default=[])`
- **Used in:** Line 124: Extended to CORS_ALLOWED_ORIGINS
- **Behavior:** Runtime-configurable CORS origins without code deployment

#### ADDITIONAL_ALLOWED_CSRF_ORIGINS
- **Defined:** `backend/app/settings.py` line 127
- **Read from:** `env.list("ADDITIONAL_ALLOWED_CSRF_ORIGINS", default=[])`
- **Used in:** Line 128: Extended to CSRF_TRUSTED_ORIGINS
- **Behavior:** Runtime-configurable CSRF origins without code deployment

### 4. Session and Cookie Configuration

#### SESSION_COOKIE_DOMAIN
- **Defined:** `backend/app/settings.py` line 364
- **Read from:** `env("SESSION_COOKIE_DOMAIN", default=None)`
- **Used in:** Django session framework
- **Behavior:** Controls cookie domain for session sharing across subdomains

#### CSRF_COOKIE_DOMAIN
- **Defined:** `backend/app/settings.py` line 365
- **Read from:** `env("CSRF_COOKIE_DOMAIN", default=None)`
- **Used in:** Django CSRF middleware
- **Behavior:** Controls cookie domain for CSRF token sharing across subdomains

#### CSRF_COOKIE_NAME
- **Defined:** `backend/app/settings.py` line 366
- **Read from:** `env("CSRF_COOKIE_NAME", default="csrftoken")`
- **Used in:** Django CSRF middleware
- **Behavior:** Customizable CSRF cookie name for conflict avoidance

### 5. API Throttling

#### THROTTLE_MODE
- **Defined:** `backend/app/settings.py` line 408
- **Read from:** `env("THROTTLE_MODE", default="warn")`
- **Used in:**
  - `backend/app/throttling.py` lines 6, 15, 30, 44, 59
  - `UserRateThrottleWithMode` and `AnonRateThrottleWithMode` classes
- **Behavior:** Controls throttling enforcement:
  - "warn": Log throttle violations but don't block requests
  - (other values): Enforce throttling and return 429 responses

### 6. Email and Communication Services

#### EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
- **Defined:** `backend/app/settings.py` lines 437-440
- **Read from:** `env("EMAIL_HOST", default=None)`, etc.
- **Used in:** Django email backend (SMTP)
- **Behavior:** SMTP server configuration for transactional emails

#### MANDRILL_API_KEY
- **Defined:** `backend/app/settings.py` line 441
- **Read from:** `env("MANDRILL_API_KEY", default=None)`
- **Used in:** Mandrill email service integration
- **Behavior:** API authentication for Mandrill (Mailchimp transactional email)

#### BRAZE_API_KEY, BRAZE_API_URL
- **Defined:** `backend/app/settings.py` lines 443-444
- **Read from:** `env("BRAZE_API_KEY", default=None)`, `env("BRAZE_API_URL", default=None)`
- **Used in:** `analytics/braze/` module
- **Behavior:** Braze marketing automation API authentication

#### NOTION_API_KEY, NOTION_BRAZE_PAGE_ID
- **Defined:** `backend/app/settings.py` lines 447-448
- **Read from:** `env("NOTION_API_KEY", default=None)`, `env("NOTION_BRAZE_PAGE_ID", default=None)`
- **Used in:** `scripts/generate_braze_constants.py`
- **Behavior:** Notion API for syncing Braze documentation

### 7. Shipping Providers

#### USPS_USER_ID (Legacy)
- **Defined:** `backend/app/settings.py` line 452
- **Read from:** `env("USPS_USER_ID", default=None)`
- **Used in:** Legacy USPS Web Tools API (deprecated January 2026)
- **Behavior:** USPS shipping label generation (legacy)

#### USPS_CLIENT_ID, USPS_CLIENT_SECRET, USPS_API_URL
- **Defined:** `backend/app/settings.py` lines 455-457
- **Read from:** `env("USPS_CLIENT_ID", default=None)`, `env("USPS_CLIENT_SECRET", default=None)`, `env("USPS_API_URL", default="https://apis.usps.com")`
- **Used in:** New USPS REST API (OAuth 2.0)
- **Behavior:** Modern USPS API authentication for shipping

#### FEDEX_API_KEY, FEDEX_API_SECRET, FEDEX_API_URL
- **Defined:** `backend/app/settings.py` lines 486-488
- **Read from:** `env("FEDEX_API_KEY", default=None)`, `env("FEDEX_API_SECRET", default=None)`, `env("FEDEX_API_URL", default="https://apis-sandbox.fedex.com")`
- **Used in:** FedEx shipping integration
- **Behavior:** FedEx API authentication, URL defaults to sandbox

### 8. E-commerce Integrations

#### RECHARGE_API_KEY, RECHARGE_API_URL, RECHARGE_WEBHOOK_SECRET
- **Defined:** `backend/app/settings.py` lines 460-462
- **Read from:** `env("RECHARGE_API_KEY", default=None)`, etc.
- **Used in:**
  - `subscriptions/recharge.py::RechargeAPIClient.__init__()` line 48
- **Behavior:** Recharge subscription platform API authentication and webhook verification

#### SHOPIFY_BASE_URL
- **Defined:** `backend/app/settings.py` line 468
- **Read from:** `env("SHOPIFY_BASE_URL", default="evvybio.myshopify.com")`
- **Used in:** Shopify API clients
- **Behavior:** Shopify store URL

#### SHOPIFY_STOREFRONT_ACCESS_TOKEN, SHOPIFY_ADMIN_ACCESS_TOKEN
- **Defined:** `backend/app/settings.py` lines 469-470
- **Read from:** `env("SHOPIFY_STOREFRONT_ACCESS_TOKEN", default=None)`, `env("SHOPIFY_ADMIN_ACCESS_TOKEN", default=None)`
- **Used in:**
  - `ecomm/shopify/shopify.py::ShopifyAPIClient.__init__()` line 34
  - `ecomm/shopify/shopify_admin.py::ShopifyAdminAPIClient.__init__()` line 46
- **Behavior:** Shopify API authentication (storefront for customer-facing, admin for backend operations)

#### SHOPIFY_WEBHOOK_SECRET, SHOPIFY_WEBHOOK_GRAPHQL_SECRET
- **Defined:** `backend/app/settings.py` lines 471-472
- **Read from:** `env("SHOPIFY_WEBHOOK_SECRET", default=None)`, `env("SHOPIFY_WEBHOOK_GRAPHQL_SECRET", default=None)`
- **Used in:** Shopify webhook verification
- **Behavior:** HMAC verification for Shopify webhooks (REST vs GraphQL)

#### SHARE_A_SALE_API_TOKEN, SHARE_A_SALE_API_SECRET, SHARE_A_SALE_EVVY_MERCHANT_ID
- **Defined:** `backend/app/settings.py` lines 481-483
- **Read from:** `env("SHARE_A_SALE_API_TOKEN", default=None)`, etc.
- **Used in:** Share-A-Sale affiliate tracking
- **Behavior:** Affiliate marketing platform API authentication

### 9. Lab Services Providers

#### WHEEL_ACCESS_TOKEN, WHEEL_API_KEY, WHEEL_API_URL
- **Defined:** `backend/app/settings.py` lines 493-495
- **Read from:** `env("WHEEL_ACCESS_TOKEN", default=None)`, `env("WHEEL_API_KEY", default=None)`, `env("WHEEL_API_URL", default="https://sandbox-api.wheel.health")`
- **Used in:** Wheel telemedicine consult integration
- **Behavior:** Wheel API authentication, URL defaults to sandbox

#### MICROGEN_SECRET_KEY, MICROGEN_API_URL, MICROGEN_API_KEY, MICROGEN_API_APP_ID
- **Defined:** `backend/app/settings.py` lines 505-508
- **Read from:** `env("MICROGEN_SECRET_KEY", default="")`, etc.
- **Used in:**
  - `test_results/microgen/microgen.py::MicrogenAPIClient.__init__()` line 31
  - Webhook signature verification
- **Behavior:** Microgen lab API authentication

#### MICROGEN_ENABLED
- **Defined:** `backend/app/settings.py` line 509
- **Read from:** `env.bool("MICROGEN_ENABLED", default=True)`
- **Used in:**
  - `test_results/microgen/tasks.py::process_microgen_test_results()` line 118
  - `test_results/microgen/tasks.py::process_test_results_stuck_in_sequencing_status()` line 98
- **Behavior:** Feature flag to enable/disable Microgen lab integration

#### RESULTS_PROCESSING_MAX_DELAY_MINUTES
- **Defined:** `backend/app/settings.py` line 510
- **Read from:** `env.int("RESULTS_PROCESSING_MAX_DELAY_MINUTES", default=0)`
- **Used in:** `test_results/microgen/tasks.py` for load balancing with random delays
- **Behavior:** Maximum random delay (in minutes) before processing test results to prevent thundering herd

#### JUNCTION_ENABLED
- **Defined:** `backend/app/settings.py` line 513
- **Read from:** `env.bool("JUNCTION_ENABLED", default=False)`
- **Used in:**
  - `test_results/lab_services/config.py::LabServicesConfig.get_provider_config()` line 113
- **Behavior:** Feature flag to enable/disable Junction lab integration

#### JUNCTION_API_KEY, JUNCTION_BASE_URL, JUNCTION_SANDBOX, JUNCTION_WEBHOOK_SECRET
- **Defined:** `backend/app/settings.py` lines 514-517
- **Read from:** `env("JUNCTION_API_KEY", default="")`, `env("JUNCTION_BASE_URL", default="https://api.sandbox.tryvital.io")`, `env.bool("JUNCTION_SANDBOX", default=True)`, `env("JUNCTION_WEBHOOK_SECRET", default="")`
- **Used in:**
  - `test_results/lab_services/config.py::LabServicesConfig.get_provider_config()` lines 113-119
  - Junction API client and webhook verification
- **Behavior:** Junction lab services API configuration

#### PRECISION_SECRET_KEY, PRECISION_API_URL, PRECISION_ACCOUNT_ID
- **Defined:** `backend/app/settings.py` lines 520-522
- **Read from:** `env("PRECISION_SECRET_KEY", default="")`, etc.
- **Used in:**
  - `shipping/precision/precision.py::PrecisionAPIClient.__init__()` line 40
- **Behavior:** Precision Pharmacy API authentication for prescription fulfillment

### 10. Third-Party Services

#### BERLIN_ACCESS_TOKEN, BERLIN_API_URL, BERLIN_CLIENT_ID, BERLIN_CLIENT_SECRET
- **Defined:** `backend/app/settings.py` lines 525-528
- **Read from:** `env("BERLIN_ACCESS_TOKEN", default=None)`, etc.
- **Used in:**
  - `shipping/berlin/berlin.py::BerlinAPIClient.__init__()` line 13
- **Behavior:** Berlin fulfillment API authentication

#### INTERCOM_API_KEY, INTERCOM_API_URL
- **Defined:** `backend/app/settings.py` lines 531-532
- **Read from:** `env("INTERCOM_API_KEY", default=None)`, `env("INTERCOM_API_URL", default=None)`
- **Used in:**
  - `support/intercom.py::IntercomAPIClient.__init__()` line 24
- **Behavior:** Intercom customer support platform API

#### SURVICATE_API_KEY, SURVICATE_API_URL, SURVICATE_SECRET_KEY
- **Defined:** `backend/app/settings.py` lines 535-537
- **Read from:** `env("SURVICATE_API_KEY", default=None)`, etc.
- **Used in:** Survicate survey platform integration
- **Behavior:** Survey and feedback collection API

#### CALENDLY_SECRET_KEY
- **Defined:** `backend/app/settings.py` line 540
- **Read from:** `env("CALENDLY_SECRET_KEY", default=None)`
- **Used in:** Calendly webhook verification
- **Behavior:** Calendly scheduling webhook authentication

#### FULLSTORY_API_KEY
- **Defined:** `backend/app/settings.py` line 465
- **Read from:** `env("FULLSTORY_API_KEY", default=None)`
- **Used in:** FullStory analytics integration
- **Behavior:** FullStory session replay API authentication

#### OPENAI_API_KEY
- **Defined:** `backend/app/settings.py` line 543
- **Read from:** `env("OPENAI_API_KEY", default=None)`
- **Used in:** OpenAI API integrations (AI features)
- **Behavior:** OpenAI API authentication

#### VIOME_WEBHOOK_SECRET
- **Defined:** `backend/app/settings.py` line 475
- **Read from:** `env("VIOME_WEBHOOK_SECRET", default=None)`
- **Used in:** `ecomm/services/viome.py` webhook verification
- **Behavior:** Viome partnership webhook authentication

#### TYPEFORM_WEBHOOK_SECRET
- **Defined:** `backend/app/settings.py` line 478
- **Read from:** `env("TYPEFORM_WEBHOOK_SECRET", default=None)`
- **Used in:** Typeform webhook verification
- **Behavior:** Typeform survey webhook authentication

#### KLAVIYO_SECRET_KEY
- **Defined:** `backend/app/settings.py` line 554
- **Read from:** `env("KLAVIYO_SECRET_KEY", default="")`
- **Used in:** Klaviyo marketing platform (may be deprecated based on migration docs)
- **Behavior:** Klaviyo email marketing API authentication

### 11. Partner API

#### PARTNER_API_KEY
- **Defined:** `backend/app/settings.py` line 362
- **Read from:** `env("PARTNER_API_KEY", default=None)`
- **Used in:** `partner_api/partner_config.py::_initialize_partners()` for B2B partner authentication
- **Behavior:** API key for partner integrations

### 12. Feature Flags

#### FEATURE_FLAG_XACIATO
- **Defined:** `backend/app/settings.py` line 595
- **Read from:** `env("FEATURE_FLAG_XACIATO", default=False) == "enabled"`
- **Used in:** Product availability (Xaciato treatment)
- **Behavior:** Enables/disables Xaciato product

#### FEATURE_FLAG_PROBIOTIC_OTC
- **Defined:** `backend/app/settings.py` line 597-599
- **Read from:** `env("FEATURE_FLAG_PROBIOTIC_OTC", default=False) == "enabled"`
- **Used in:** OTC probiotic product availability
- **Behavior:** Enables/disables over-the-counter probiotic products

#### FEATURE_FLAG_MALE_PARTNER
- **Defined:** `backend/app/settings.py` line 601-603
- **Read from:** `env("FEATURE_FLAG_MALE_PARTNER", default=False) == "enabled"`
- **Used in:** Male partner testing features
- **Behavior:** Enables/disables male partner test offerings

#### FEATURE_FLAG_MALE_PARTNER_TREATMENT_UPSELL
- **Defined:** `backend/app/settings.py` line 605-607
- **Read from:** `env("FEATURE_FLAG_MALE_PARTNER_TREATMENT_UPSELL", default=False) == "enabled"`
- **Used in:** Male partner treatment upsell flows
- **Behavior:** Enables/disables male partner treatment upsells

#### FEATURE_FLAG_URINE_TEST
- **Defined:** `backend/app/settings.py` line 609-611
- **Read from:** `env("FEATURE_FLAG_URINE_TEST", default=False) == "enabled"`
- **Used in:** Urine test product availability
- **Behavior:** Enables/disables urine test offerings

#### FEATURE_FLAG_BV_SUBTYPES
- **Defined:** `backend/app/settings.py` line 613-615
- **Read from:** `env("FEATURE_FLAG_BV_SUBTYPES", default=False) == "enabled"`
- **Used in:**
  - `accounts/utils.py::get_bv_subtypes_enabled()` line 178
  - API responses for BV subtype information
- **Behavior:** Enables/disables BV subtype reporting in results

### 13. Development and Testing

#### BYPASS_EMAIL_VERIFICATION
- **Defined:** `backend/app/settings.py` line 619
- **Read from:** `env.bool("BYPASS_EMAIL_VERIFICATION", default=False)`
- **Used in:** User registration flows
- **Behavior:** Skips email verification requirement (development only)

#### HYDRATE_DB_ON_INIT
- **Defined:** `backend/app/settings.py` line 631
- **Read from:** `env("HYDRATE_DB_ON_INIT", default=False) == "yes"`
- **Used in:** `app/management/commands/staging_hydrate.py`
- **Behavior:** Automatically seed database with test data on initialization (staging environments)

#### HYDRATE_DB_USER_PASSWORD
- **Defined:** `backend/app/settings.py` line 632
- **Read from:** `env("HYDRATE_DB_USER_PASSWORD", default=None)`
- **Used in:** Database hydration script for test user password
- **Behavior:** Default password for test users created during hydration

#### PAUSE_AUTO_RELEASE_RESULTS
- **Defined:** `backend/app/settings.py` line 649
- **Read from:** `env("PAUSE_AUTO_RELEASE_RESULTS", default=False)`
- **Used in:** `test_results/tasks.py::post_process_test_results()` conditional logic
- **Behavior:** Emergency kill switch to prevent automatic results release

### 14. Notification Email Channels

#### WHEEL_OPS_EMAIL
- **Defined:** `backend/app/settings.py` line 496
- **Read from:** `env("WHEEL_OPS_EMAIL", default=None)`
- **Used in:** Wheel operations notifications
- **Behavior:** Email address for Wheel-related operational alerts

#### CONSULT_UPDATES_EMAIL
- **Defined:** `backend/app/settings.py` line 498
- **Read from:** `env("CONSULT_UPDATES_EMAIL", default=None)`
- **Used in:** Slack notifications for consult errors/referrals
- **Behavior:** Slack email for consult status alerts

#### BABY_UH_OH_EMAIL
- **Defined:** `backend/app/settings.py` line 500
- **Read from:** `env("BABY_UH_OH_EMAIL", default=None)`
- **Used in:** Notifications for infant-related issues
- **Behavior:** Slack email for baby product alerts

#### GENERATE_KITS_EMAIL
- **Defined:** `backend/app/settings.py` line 557
- **Read from:** `env("GENERATE_KITS_EMAIL", default=None)`
- **Used in:** Test kit ID generation notifications
- **Behavior:** Email confirmation when test kit IDs are generated

#### MDX_LAB_UPDATES_EMAIL
- **Defined:** `backend/app/settings.py` line 560
- **Read from:** `env("MDX_LAB_UPDATES_EMAIL", default=None)`
- **Used in:** MDX lab status update notifications
- **Behavior:** Slack email for MDX lab updates

#### MDX_PROCESSED_RUN_NOTIFICATION_EMAIL
- **Defined:** `backend/app/settings.py` line 561
- **Read from:** `env("MDX_PROCESSED_RUN_NOTIFICATION_EMAIL", default=None)`
- **Used in:** MDX processing run notifications
- **Behavior:** Email for MDX run completion alerts

#### LAB_DELAY_EMAIL
- **Defined:** `backend/app/settings.py` line 562
- **Read from:** `env("LAB_DELAY_EMAIL", default=None)`
- **Used in:** Lab delay notifications
- **Behavior:** Email for lab processing delay alerts

#### VIP_TEST_EMAIL
- **Defined:** `backend/app/settings.py` line 563
- **Read from:** `env("VIP_TEST_EMAIL", default=None)`
- **Used in:** VIP customer test notifications
- **Behavior:** Email for VIP test tracking

#### HEALTHY_HONEY_SLACK_CHANNEL
- **Defined:** `backend/app/settings.py` line 564
- **Read from:** `env("HEALTHY_HONEY_SLACK_CHANNEL", default=None)`
- **Used in:** Health-related notifications
- **Behavior:** Slack channel for health monitoring

#### JUNCTION_TEST_STATUS_UPDATES_EMAIL
- **Defined:** `backend/app/settings.py` line 566
- **Read from:** `env("JUNCTION_TEST_STATUS_UPDATES_EMAIL", default=None)`
- **Used in:** Junction lab status notifications
- **Behavior:** Slack email for Junction test status updates

#### URINE_TEST_RESULTS_NOTIFICATIONS_SLACK_EMAIL
- **Defined:** `backend/app/settings.py` line 569-572
- **Read from:** `env("URINE_TEST_RESULTS_NOTIFICATIONS_SLACK_EMAIL", default="urine-test-results-no-aaaaspl3xniyejmjivxgz4ub54@evvy-bio.slack.com")`
- **Used in:** `test_results/signals.py::_send_urine_test_status_change_alert()` line 35
- **Behavior:** Slack notifications for urine test results

#### JUNCTION_TEST_STATUS_SLACK_USER_IDS
- **Defined:** `backend/app/settings.py` line 576
- **Read from:** `env("JUNCTION_TEST_STATUS_SLACK_USER_IDS", default=None)`
- **Used in:** Junction test status alerts (tags users)
- **Behavior:** Comma-separated Slack user IDs to mention in alerts

#### B2B_PROVIDER_REGISTRATION_EMAIL
- **Defined:** `backend/app/settings.py` line 579
- **Read from:** `env("B2B_PROVIDER_REGISTRATION_EMAIL", default=None)`
- **Used in:** B2B provider registration notifications
- **Behavior:** Email for new provider registrations

#### B2B_IN_CLINIC_EMAIL
- **Defined:** `backend/app/settings.py` line 582
- **Read from:** `env("B2B_IN_CLINIC_EMAIL", default=None)`
- **Used in:** B2B in-clinic order notifications
- **Behavior:** Email for in-clinic orders

#### B2B_PROVIDER_SUPPORT_EMAIL
- **Defined:** `backend/app/settings.py` line 585
- **Read from:** `env("B2B_PROVIDER_SUPPORT_EMAIL", default=None)`
- **Used in:** B2B provider support requests
- **Behavior:** Email for provider support tickets

#### OPS_TECH_EMAIL
- **Defined:** `backend/app/settings.py` line 588
- **Read from:** `env("OPS_TECH_EMAIL", default=None)`
- **Used in:** Technical operations notifications
- **Behavior:** Email for ops-tech alerts

#### ENG_WARNING_EMAIL
- **Defined:** `backend/app/settings.py` line 591
- **Read from:** `env("ENG_WARNING_EMAIL", default=None)`
- **Used in:** Engineering warning notifications
- **Behavior:** Email for engineering alerts/warnings

### 15. AWS Configuration

#### AWS_ACCESS_KEY, AWS_ACCESS_SECRET
- **Defined:** `backend/app/settings.py` lines 635-636
- **Read from:** `env("AWS_ACCESS_KEY", default=None)`, `env("AWS_ACCESS_SECRET", default=None)`
- **Aliases:** Also set as `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for django-storages compatibility (lines 638-639)
- **Used in:** S3 file storage operations
- **Behavior:** AWS credentials for S3 access

#### AWS_S3_ENDPOINT_URL
- **Defined:** `backend/app/settings.py` lines 642-643
- **Read from:** `env("AWS_S3_ENDPOINT_URL", default=None)`
- **Used in:** Local development only (LocalStack)
- **Behavior:** Custom S3 endpoint for local testing

#### PERF_S3_BUCKET_NAME
- **Defined:** `backend/app/settings.py` line 646
- **Read from:** `env("PERF_S3_BUCKET_NAME", default="devvy")`
- **Used in:** `scripts/performance/run_perf_tests.py` for performance test results
- **Behavior:** S3 bucket for storing performance testing data

### 16. Logging Configuration

#### ROOT_LOG_LEVEL
- **Defined:** `backend/app/settings.py` line 652
- **Read from:** `os.environ.get("ROOT_LOG_LEVEL", "INFO")`
- **Used in:** `settings.LOGGING['root']['level']` line 688
- **Behavior:** Sets root logger level (DEBUG/INFO/WARNING/ERROR)

#### DJANGO_LOG_LEVEL
- **Defined:** `backend/app/settings.py` line 653
- **Read from:** `os.environ.get("DJANGO_LOG_LEVEL", "INFO")`
- **Used in:** Django framework loggers (lines 694, 699, 704, 709)
- **Behavior:** Sets Django-specific logger levels

### 17. Celery Configuration

#### CELERY_BROKER_URL
- **Defined:** `backend/app/settings_celery.py` line 8
- **Read from:** `os.environ.get("CELERY_BROKER_URL", "redis://redis-queue:6379/0")`
- **Used in:** Celery task queue broker
- **Behavior:** Redis URL for Celery message broker

#### CELERY_RESULT_BACKEND
- **Defined:** `backend/app/settings_celery.py` line 9
- **Read from:** `os.environ.get("CELERY_RESULT_BACKEND", "redis://redis-queue:6379/0")`
- **Used in:** Celery result storage
- **Behavior:** Redis URL for storing task results

### 18. Caching

#### REDIS_CACHE_LOCATION
- **Defined:** `backend/app/settings.py` line 838
- **Read from:** `os.environ.get("REDIS_CACHE_LOCATION", None)`
- **Used in:** Django cache backend configuration (lines 842-866)
- **Behavior:** Redis URL for caching, falls back to LocMemCache if not set

### 19. Google Services

#### GOOGLE_JSON_CREDS
- **Defined:** `backend/app/settings.py` line 551
- **Read from:** `env("GOOGLE_JSON_CREDS", default="")`
- **Used in:** Google Sheets API (service account credentials)
- **Behavior:** JSON credentials for Google Sheets API access

#### BERLIN_EXPRESS_GSHEET_ID, BERLIN_EXPEDITED_EMAILS, BERLIN_EMAIL_FROM_ADDRESS
- **Defined:** `backend/app/settings.py` lines 546-548
- **Read from:** `env("BERLIN_EXPEDITED_EMAILS", default="")`, `env("BERLIN_EMAIL_FROM_ADDRESS", default="")`, `env("BERLIN_EXPRESS_GSHEET_ID", default="")`
- **Used in:** Berlin express order notifications
- **Behavior:** Configuration for Berlin expedited shipping emails and Google Sheets tracking

---

## Summary Statistics

- **Total Custom Environment Variables:** 120+
- **Categories:**
  - Core Application: 4
  - Database: 5
  - URL/CORS Configuration: 10
  - Session/Cookie: 3
  - API Throttling: 1
  - Email Services: 4
  - Shipping Providers: 9
  - E-commerce: 10
  - Lab Services: 17
  - Third-Party Services: 15
  - Partner API: 1
  - Feature Flags: 6
  - Development/Testing: 4
  - Notification Emails: 18
  - AWS: 4
  - Logging: 2
  - Celery: 2
  - Caching: 1
  - Google Services: 4

- **Files Defining Settings:**
  - Primary: `backend/app/settings.py`
  - Celery: `backend/app/settings_celery.py`

- **Configuration Pattern:**
  - Uses `django-environ` library
  - Format: `env("VAR_NAME", default=value)` with optional type casting
  - Special types: `env.bool()`, `env.int()`, `env.list()`
  - Some legacy `os.environ.get()` usage

- **Reading Pattern in Application Code:**
  - Import: `from django.conf import settings`
  - Access: `settings.SETTING_NAME`
  - 30+ files import settings

- **Behavior Control Categories:**
  1. **Service Integration:** API keys, URLs, secrets for external services
  2. **Feature Toggles:** Feature flags enable/disable functionality
  3. **Operational Controls:** Pause mechanisms, delays, bypass flags
  4. **Environment Detection:** NEW_RELIC_ENVIRONMENT drives environment-specific behavior
  5. **Notification Routing:** Email/Slack channels for different alert types
  6. **Security:** CORS, CSRF, session, cookie domains
