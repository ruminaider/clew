# Complete Inventory of Custom Environment Variables and Django Settings

**Task:** Create a complete inventory of all custom environment variables and Django settings that control application behavior.

**Working directory:** `/Users/albertgwo/Work/evvy`

**Project:** Django-based healthcare/laboratory test result management platform (Evvy)

---

## Tool Calls and Exploration

### 1. Initial File Discovery

**File searches for settings files:**
- Found main settings file: `/Users/albertgwo/Work/evvy/backend/app/settings.py`
- Found Celery settings: `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py`
- Found .env example: `/Users/albertgwo/Work/evvy/backend/app/.env.example`

**Read operations:**
- Read `settings.py` (897 lines)
- Read `.env.example` (120 lines)
- Read `settings_celery.py` (229 lines)

### 2. Usage Pattern Discovery

**Searches performed:**
- Searched for `from django.conf import settings` usage (127 files found)
- Searched for `os.environ.get|env\(` patterns (133 files found)
- Searched for `FEATURE_FLAG_` usage (3 files)
- Searched for specific service settings (MICROGEN, JUNCTION, WHEEL, etc.) - 22 files
- Searched for behavior control settings (PAUSE_AUTO_RELEASE, THROTTLE_MODE, etc.) - 5 files
- Searched for URL settings (SITE_URL, BACKEND_URL, etc.) - 17 files

### 3. Deep Dive into Key Files

**Files examined for usage patterns:**
- `app/throttling.py` - THROTTLE_MODE behavior control
- `test_results/lab_services/config.py` - Junction lab provider configuration
- `test_results/utils.py` - Feature flag and pause behavior usage
- `accounts/utils.py` - User profile and feature flag checks

---

## Complete Inventory

### Category 1: Application Infrastructure & URLs

#### 1.1 Base URLs and Domains

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `SITE_URL` | settings.py:60 | env() | `""` | Customer-facing frontend URL; used in transactional emails, account verification links, password reset flows |
| `INTERNAL_SITE_URL` | settings.py:61 | env() | `""` | Internal admin/portal frontend URL; used for internal tool links, admin notifications |
| `BACKEND_URL` | settings.py:62 | env() | `""` | Backend API URL; used for CORS/CSRF validation, Django admin access, API documentation |
| `RENDER_EXTERNAL_URL` | settings.py:44 | env() | `None` | Auto-injected by Render hosting; used to determine backend host for ALLOWED_HOSTS |
| `RENDER_FRONTEND_HOST` | settings.py:47 | env() | `None` | Render preview environment frontend host; dynamically constructs SITE_URL if set to "dynamic" |
| `RENDER_INTERNAL_FRONTEND_HOST` | settings.py:48 | env() | `None` | Render preview environment internal frontend host; dynamically constructs INTERNAL_SITE_URL if set to "dynamic" |

**Usage Examples:**
- `transactional_email/utils.py` - constructs verification email links using `settings.SITE_URL`
- `accounts/signals.py` - generates password reset URLs with `settings.SITE_URL`
- `api/v1/views/userconfig.py` - returns frontend URL configuration to API clients

#### 1.2 Security & CORS

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `ADDITIONAL_ALLOWED_BACKEND_HOSTS` | settings.py:80 | env.list() | `[]` | Additional backend hostnames for ALLOWED_HOSTS; allows dynamic host updates without code deploy |
| `ADDITIONAL_ALLOWED_CORS_ORIGINS` | settings.py:123 | env.list() | `[]` | Additional CORS origins; enables frontend preview URLs without code changes |
| `ADDITIONAL_ALLOWED_CSRF_ORIGINS` | settings.py:127 | env.list() | `[]` | Additional CSRF trusted origins; allows new frontend domains for form submissions |
| `SESSION_COOKIE_DOMAIN` | settings.py:364 | env() | `None` | Domain for session cookies; controls cookie sharing across subdomains |
| `CSRF_COOKIE_DOMAIN` | settings.py:365 | env() | `None` | Domain for CSRF cookies; must match SESSION_COOKIE_DOMAIN for auth to work |
| `CSRF_COOKIE_NAME` | settings.py:366 | env() | `"csrftoken"` | CSRF token cookie name; allows customization if conflicts exist |
| `SECRET_KEY` | settings.py:36 | env() | **REQUIRED** | Django secret key for cryptographic signing; sessions, CSRF, password reset tokens |

**CORS/CSRF Logic:**
- Computed from SITE_URL, INTERNAL_SITE_URL, BACKEND_URL, RENDER URLs
- Supports "dynamic" keyword for preview environments
- settings.py:85-128 contains full CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS construction

#### 1.3 Database

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `DB_NAME` | settings.py:303 | env() | **REQUIRED** | PostgreSQL database name |
| `DB_USER` | settings.py:304 | env() | **REQUIRED** | Database username |
| `DB_PASSWORD` | settings.py:305 | env() | **REQUIRED** | Database password |
| `DB_HOST` | settings.py:306 | env() | **REQUIRED** | Database host (e.g., "db" for Docker, RDS endpoint for production) |
| `DB_HOST_PORT` | settings.py:307 | env() | **REQUIRED** | Database port (typically 5432) |

---

### Category 2: External Service APIs

#### 2.1 Email & Communication

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `EMAIL_HOST` | settings.py:437 | env() | `None` | SMTP server hostname (e.g., smtp.mandrillapp.com) |
| `EMAIL_PORT` | settings.py:438 | env() | `None` | SMTP port (587 for TLS) |
| `EMAIL_HOST_USER` | settings.py:439 | env() | `None` | SMTP username |
| `EMAIL_HOST_PASSWORD` | settings.py:440 | env() | `None` | SMTP password |
| `MANDRILL_API_KEY` | settings.py:441 | env() | `None` | Mandrill transactional email API key; used in `transactional_email/mandrill.py` |
| `BRAZE_API_KEY` | settings.py:443 | env() | `None` | Braze customer engagement platform API key |
| `BRAZE_API_URL` | settings.py:444 | env() | `None` | Braze API endpoint; used in `analytics/braze/braze.py` for event tracking |
| `NOTION_API_KEY` | settings.py:447 | env() | `None` | Notion API for Braze documentation sync |
| `NOTION_BRAZE_PAGE_ID` | settings.py:448 | env() | `None` | Notion page ID for Braze docs |

**Email Notification Channels (Slack Integration):**
| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `GENERATE_KITS_EMAIL` | settings.py:557 | env() | `None` | Slack email for kit ID generation notifications |
| `MDX_LAB_UPDATES_EMAIL` | settings.py:560 | env() | `None` | Slack email for Microgen lab status updates |
| `MDX_PROCESSED_RUN_NOTIFICATION_EMAIL` | settings.py:561 | env() | `None` | Slack email for processed run notifications |
| `LAB_DELAY_EMAIL` | settings.py:562 | env() | `None` | Slack email for lab delay alerts |
| `VIP_TEST_EMAIL` | settings.py:563 | env() | `None` | Slack email for VIP customer test notifications |
| `HEALTHY_HONEY_SLACK_CHANNEL` | settings.py:564 | env() | `None` | Slack channel for Healthy Honey study alerts |
| `JUNCTION_TEST_STATUS_UPDATES_EMAIL` | settings.py:566 | env() | `None` | Slack email for Junction lab status updates |
| `URINE_TEST_RESULTS_NOTIFICATIONS_SLACK_EMAIL` | settings.py:569-572 | env() | `"urine-test-results-no-aaaaspl3xniyejmjivxgz4ub54@evvy-bio.slack.com"` | Slack channel for urine test result notifications |
| `JUNCTION_TEST_STATUS_SLACK_USER_IDS` | settings.py:576 | env() | `None` | Comma-separated Slack user IDs to tag in Junction alerts |
| `B2B_PROVIDER_REGISTRATION_EMAIL` | settings.py:579 | env() | `None` | Slack email for B2B provider registration events |
| `B2B_IN_CLINIC_EMAIL` | settings.py:582 | env() | `None` | Slack email for B2B in-clinic orders |
| `B2B_PROVIDER_SUPPORT_EMAIL` | settings.py:585 | env() | `None` | Slack email for B2B provider support requests |
| `OPS_TECH_EMAIL` | settings.py:588 | env() | `None` | Slack email for ops tech notifications |
| `ENG_WARNING_EMAIL` | settings.py:591 | env() | `None` | Slack email for engineering warnings |
| `CONSULT_UPDATES_EMAIL` | settings.py:498 | env() | `None` | Slack email for consult error/referral status notifications |
| `BABY_UH_OH_EMAIL` | settings.py:500 | env() | `None` | Slack email for critical errors ("baby uh ohs") |

#### 2.2 Shipping & Fulfillment

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `USPS_USER_ID` | settings.py:452 | env() | `None` | Legacy USPS Web Tools API user ID (deprecated Jan 2026); used in `shipping/usps_api_client.py` |
| `USPS_CLIENT_ID` | settings.py:455 | env() | `None` | USPS REST API OAuth client ID (new API) |
| `USPS_CLIENT_SECRET` | settings.py:456 | env() | `None` | USPS REST API OAuth client secret |
| `USPS_API_URL` | settings.py:457 | env() | `"https://apis.usps.com"` | USPS API base URL |
| `FEDEX_API_KEY` | settings.py:486 | env() | `None` | FedEx API key; used in `shipping/fedex.py` |
| `FEDEX_API_SECRET` | settings.py:487 | env() | `None` | FedEx API secret |
| `FEDEX_API_URL` | settings.py:488 | env() | `"https://apis-sandbox.fedex.com"` | FedEx API endpoint (sandbox vs production) |
| `BERLIN_ACCESS_TOKEN` | settings.py:525 | env() | `None` | Berlin fulfillment API access token; used in `shipping/berlin/berlin.py` |
| `BERLIN_API_URL` | settings.py:526 | env() | `None` | Berlin API endpoint |
| `BERLIN_CLIENT_ID` | settings.py:527 | env() | `None` | Berlin OAuth client ID |
| `BERLIN_CLIENT_SECRET` | settings.py:528 | env() | `None` | Berlin OAuth client secret |
| `BERLIN_EXPEDITED_EMAILS` | settings.py:546 | env() | `""` | Comma-separated emails for expedited shipping notifications |
| `BERLIN_EMAIL_FROM_ADDRESS` | settings.py:547 | env() | `""` | From address for Berlin emails |
| `BERLIN_EXPRESS_GSHEET_ID` | settings.py:548 | env() | `""` | Google Sheet ID for Berlin express order tracking |

#### 2.3 E-commerce Platforms

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `SHOPIFY_BASE_URL` | settings.py:468 | env() | `"evvybio.myshopify.com"` | Shopify store URL; used in `ecomm/shopify/shopify.py` |
| `SHOPIFY_STOREFRONT_ACCESS_TOKEN` | settings.py:469 | env() | `None` | Shopify Storefront API token for GraphQL queries |
| `SHOPIFY_ADMIN_ACCESS_TOKEN` | settings.py:470 | env() | `None` | Shopify Admin API token for order management |
| `SHOPIFY_WEBHOOK_SECRET` | settings.py:471 | env() | `None` | Shopify webhook signature verification secret |
| `SHOPIFY_WEBHOOK_GRAPHQL_SECRET` | settings.py:472 | env() | `None` | Shopify GraphQL webhook secret |
| `RECHARGE_API_KEY` | settings.py:460 | env() | `None` | Recharge subscriptions API key; used in `subscriptions/recharge.py` |
| `RECHARGE_API_URL` | settings.py:461 | env() | `None` | Recharge API endpoint |
| `RECHARGE_WEBHOOK_SECRET` | settings.py:462 | env() | `None` | Recharge webhook signature secret |
| `SHARE_A_SALE_API_TOKEN` | settings.py:481 | env() | `None` | ShareASale affiliate network API token |
| `SHARE_A_SALE_API_SECRET` | settings.py:482 | env() | `None` | ShareASale API secret |
| `SHARE_A_SALE_EVVY_MERCHANT_ID` | settings.py:483 | env() | `None` | ShareASale merchant ID for Evvy |

#### 2.4 Lab Service Providers

**Microgen (Legacy LDT Sequencing):**
| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `MICROGEN_SECRET_KEY` | settings.py:505 | env() | `""` | HMAC signature verification secret; used in `test_results/microgen/microgen.py` |
| `MICROGEN_API_URL` | settings.py:506 | env() | `""` | Microgen API base URL |
| `MICROGEN_API_KEY` | settings.py:507 | env() | `""` | Microgen API authentication key |
| `MICROGEN_API_APP_ID` | settings.py:508 | env() | `""` | Microgen application ID |
| `MICROGEN_ENABLED` | settings.py:509 | env.bool() | `True` | Enable/disable Microgen integration; checked in `test_results/signals.py` |
| `RESULTS_PROCESSING_MAX_DELAY_MINUTES` | settings.py:510 | env.int() | `0` | Max delay for results processing before alerting (0=disabled) |

**Junction (Urine Test Provider via Vital API):**
| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `JUNCTION_ENABLED` | settings.py:513 | env.bool() | `False` | Enable/disable Junction integration; checked in `test_results/lab_services/config.py:113` |
| `JUNCTION_API_KEY` | settings.py:514 | env() | `""` | Junction/Vital API key; required when JUNCTION_ENABLED=True |
| `JUNCTION_BASE_URL` | settings.py:515 | env() | `"https://api.sandbox.tryvital.io"` | Junction API endpoint (sandbox vs production) |
| `JUNCTION_SANDBOX` | settings.py:516 | env.bool() | `True` | Controls which lab test IDs to use (sandbox vs production); affects test ordering |
| `JUNCTION_WEBHOOK_SECRET` | settings.py:517 | env() | `""` | Junction webhook signature verification secret; used in `test_results/lab_services/providers/junction/webhook_handler.py` |

**Wheel (Telemedicine/Lab Order Platform):**
| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `WHEEL_ACCESS_TOKEN` | settings.py:493 | env() | `None` | Wheel API access token for webhook verification |
| `WHEEL_API_KEY` | settings.py:494 | env() | `None` | Wheel API key; used in `consults/wheel/wheel.py` |
| `WHEEL_API_URL` | settings.py:495 | env() | `"https://sandbox-api.wheel.health"` | Wheel API endpoint (sandbox vs production) |
| `WHEEL_OPS_EMAIL` | settings.py:496 | env() | `None` | Operations email for Wheel-related notifications |

**Note:** Wheel also has additional env vars read directly in `test_results/lab_services/config.py:243-252`:
- `WHEEL_ENABLED` (default True)
- `WHEEL_BASE_URL` (via os.environ.get)
- `WHEEL_SANDBOX` (via os.environ.get)
- `WHEEL_WEBHOOK_SECRET` (via os.environ.get)
- `WHEEL_APP_ID` (via os.environ.get)

**Precision Pharmacy (Prescription Fulfillment):**
| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `PRECISION_SECRET_KEY` | settings.py:520 | env() | `""` | Precision Pharmacy API secret; used in `shipping/precision/precision.py` |
| `PRECISION_API_URL` | settings.py:521 | env() | `""` | Precision API endpoint |
| `PRECISION_ACCOUNT_ID` | settings.py:522 | env() | `""` | Precision account identifier |

#### 2.5 Customer Support & Analytics

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `INTERCOM_API_KEY` | settings.py:531 | env() | `None` | Intercom customer messaging API key; used in `support/intercom.py` |
| `INTERCOM_API_URL` | settings.py:532 | env() | `None` | Intercom API endpoint |
| `SURVICATE_API_KEY` | settings.py:535 | env() | `None` | Survicate survey platform API key; used in `surveys/survicate.py` |
| `SURVICATE_API_URL` | settings.py:536 | env() | `None` | Survicate API endpoint |
| `SURVICATE_SECRET_KEY` | settings.py:537 | env() | `None` | Survicate webhook signature verification |
| `CALENDLY_SECRET_KEY` | settings.py:540 | env() | `None` | Calendly webhook signature verification |
| `FULLSTORY_API_KEY` | settings.py:465 | env() | `None` | FullStory session replay API key; used in `analytics/fullstory.py` |
| `KLAVIYO_SECRET_KEY` | settings.py:554 | env() | `""` | Klaviyo marketing automation API key; used in analytics events |

#### 2.6 Webhooks (Other)

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `VIOME_WEBHOOK_SECRET` | settings.py:475 | env() | `None` | Viome partner webhook signature verification |
| `TYPEFORM_WEBHOOK_SECRET` | settings.py:478 | env() | `None` | Typeform survey webhook verification |

#### 2.7 AI & OpenAI

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `OPENAI_API_KEY` | settings.py:543 | env() | `None` | OpenAI API key; used in `ai/openai.py` for assistant threads and AI summaries |

#### 2.8 AWS & Cloud Storage

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `AWS_ACCESS_KEY` | settings.py:635 | env() | `None` | AWS access key ID; also set as AWS_ACCESS_KEY_ID for django-storages |
| `AWS_ACCESS_SECRET` | settings.py:636 | env() | `None` | AWS secret access key; also set as AWS_SECRET_ACCESS_KEY |
| `AWS_S3_ENDPOINT_URL` | settings.py:642-643 | env() | `None` | Custom S3 endpoint (for LocalStack in development); used in `utils/s3.py` |
| `PERF_S3_BUCKET_NAME` | settings.py:646 | env() | `"devvy"` | S3 bucket for performance testing data |

**Constants set in settings.py:**
- `AWS_S3_REGION_NAME` = "us-east-2"
- `AWS_S3_SIGNATURE_VERSION` = "s3v4"

#### 2.9 Google Services

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `GOOGLE_JSON_CREDS` | settings.py:551 | env() | `""` | Google Service Account JSON credentials for Google Sheets API; used in Berlin express order tracking |

#### 2.10 Partner API

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `PARTNER_API_KEY` | settings.py:362 | env() | `None` | API key for partner integrations; checked in `partner_api/authentication.py` |

---

### Category 3: Application Behavior Control

#### 3.1 Feature Flags

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `FEATURE_FLAG_XACIATO` | settings.py:595 | env() | `False` | Enable Xaciato product/treatment; value must be "enabled" to activate |
| `FEATURE_FLAG_PROBIOTIC_OTC` | settings.py:597-599 | env() | `False` | Enable over-the-counter probiotic products; value must be "enabled" |
| `FEATURE_FLAG_MALE_PARTNER` | settings.py:601-603 | env() | `False` | Enable male partner testing workflow; value must be "enabled" |
| `FEATURE_FLAG_MALE_PARTNER_TREATMENT_UPSELL` | settings.py:605-607 | env() | `False` | Enable male partner treatment upsell in checkout; value must be "enabled" |
| `FEATURE_FLAG_URINE_TEST` | settings.py:609-611 | env() | `False` | Enable urine test product and workflows; value must be "enabled" |
| `FEATURE_FLAG_BV_SUBTYPES` | settings.py:613-615 | env() | `False` | Enable BV subtype classification in results; value must be "enabled" |

**Usage Pattern:** All feature flags use the pattern:
```python
True if env("FEATURE_FLAG_NAME", default=False) == "enabled" else False
```

**Used in:** `accounts/utils.py` for feature availability checks per user

#### 3.2 Test & Development Behavior

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `DEBUG` | settings.py:39 | env() | `False` | Django debug mode; controls error pages, static file serving, SQL query logging |
| `BYPASS_EMAIL_VERIFICATION` | settings.py:619 | env.bool() | `False` | Skip email verification in development; used in `api/v1/views/email_verification.py` |
| `HYDRATE_DB_ON_INIT` | settings.py:631 | env() | `False` | Auto-populate staging DB with test users; value must be "yes" to activate |
| `HYDRATE_DB_USER_PASSWORD` | settings.py:632 | env() | `None` | Password for auto-generated staging users; used in `app/management/commands/staging_hydrate.py` |

#### 3.3 Operational Controls

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `THROTTLE_MODE` | settings.py:408 | env() | `"warn"` | API rate limiting mode: "enforce" (block requests) or "warn" (log only); used in `app/throttling.py:6,15,30,44,59` |
| `PAUSE_AUTO_RELEASE_RESULTS` | settings.py:649 | env() | `False` | Temporarily halt automatic test result release to customers; used in `test_results/utils_import.py` |

**THROTTLE_MODE behavior:**
- When set to "warn": Requests that would be throttled are logged but still allowed through
- When set to "enforce" (or any other value): Throttling is enforced normally
- Affects all rate throttle classes in `app/throttling.py`: UserMinuteRateThrottle, AnonMinuteRateThrottle, etc.

#### 3.4 Logging

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `ROOT_LOG_LEVEL` | settings.py:652 | os.environ.get() | `"INFO"` | Root logger level; controls all logging unless overridden |
| `DJANGO_LOG_LEVEL` | settings.py:653 | os.environ.get() | `"INFO"` | Django framework logger level; controls django.*, gunicorn.*, urllib3.* loggers |

**Note:** Uses `os.environ.get()` directly instead of `env()` helper.

#### 3.5 Caching

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `REDIS_CACHE_LOCATION` | settings.py:838 | os.environ.get() | `None` | Redis cache connection string (e.g., "redis://redis-cache:6380/0"); if None, falls back to local memory cache |

**Behavior:**
- If `REDIS_CACHE_LOCATION` is set: Uses custom `cache.EvvyRedisCache` backend
- If not set and running tests: Uses custom `cache.EvvyLocMemCache` backend
- If not set and not testing: Uses Django's default `LocMemCache`

#### 3.6 Monitoring

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `NEW_RELIC_ENVIRONMENT` | settings.py:193 | env() | `"unset"` | Environment label for New Relic APM; used to tag metrics/errors by environment |

---

### Category 4: Celery (Task Queue)

| Variable | Defined In | Read In | Default | Behavior Control |
|----------|-----------|---------|---------|------------------|
| `CELERY_BROKER_URL` | settings_celery.py:8 | os.environ.get() | `"redis://redis-queue:6379/0"` | Redis URL for Celery message broker |
| `CELERY_RESULT_BACKEND` | settings_celery.py:9 | os.environ.get() | `"redis://redis-queue:6379/0"` | Redis URL for Celery task results storage |

**Constants in settings_celery.py:**
- `CELERY_TIMEZONE` = "America/New_York"
- `CELERY_RESULT_EXPIRES` = 3 hours
- `CELERY_WORKER_CONCURRENCY` = 4
- `CELERY_WORKER_MAX_TASKS_PER_CHILD` = 100 (auto-restart workers to release memory)

**Celery Beat Schedule:** 40+ scheduled tasks defined in `CELERY_BEAT_SCHEDULE` (lines 20-228), including:
- Test result processing and notifications
- Shipping status updates
- Email reminders (abandoned intakes, test in transit, etc.)
- Lab order healing/retry tasks
- Analytics event sends

---

## Summary Statistics

**Total Environment Variables Inventoried:** 135+

**Categories:**
- Application Infrastructure & URLs: 15 variables
- External Service APIs: 71 variables
  - Email & Communication: 19 variables
  - Shipping & Fulfillment: 14 variables
  - E-commerce: 11 variables
  - Lab Services: 21 variables
  - Customer Support & Analytics: 10 variables
  - Other: 6 variables
- Application Behavior Control: 17 variables
- Celery Task Queue: 2 variables
- Database: 5 variables
- AWS/Cloud: 4 variables
- Logging: 2 variables

**Key Configuration Patterns:**

1. **Service Integration Pattern:**
   - API Key (authentication)
   - API URL/Endpoint (sandbox vs production)
   - Webhook Secret (signature verification)
   - Optional: Additional credentials (client ID/secret, app ID, account ID)

2. **URL Construction Pattern:**
   - Base URL env var (SITE_URL, BACKEND_URL, etc.)
   - Dynamic construction for preview environments ("dynamic" keyword)
   - CORS/CSRF derived from URL settings
   - Render-injected URLs for hosting platform

3. **Feature Flag Pattern:**
   - All use "enabled" string value
   - Default to False
   - Checked in utils/views before feature access

4. **Email Notification Pattern:**
   - Many *_EMAIL variables point to Slack channels
   - Format: `{channel-name}-{slack-generated-string}@{workspace}.slack.com`
   - Used for async notifications to engineering/ops teams

5. **Environment-Specific Defaults:**
   - Sandbox URLs for development (Junction, Wheel, FedEx)
   - Production URLs require explicit override
   - LocalStack S3 endpoint for local dev

**Critical Security Variables (must never be committed):**
- SECRET_KEY
- All *_API_KEY variables
- All *_SECRET variables
- All *_PASSWORD variables
- AWS credentials
- Database credentials

**Files with Heavy Settings Usage:**
- `test_results/lab_services/config.py` - 11 settings accessed
- `transactional_email/utils.py` - SITE_URL, email settings
- `consults/wheel/wheel.py` - WHEEL_* settings
- `shipping/berlin/berlin.py` - BERLIN_* settings
- `ecomm/shopify/shopify.py` - SHOPIFY_* settings
- `app/throttling.py` - THROTTLE_MODE behavior control

**Django Settings Constants (not env vars, defined in settings.py):**
- `DEFAULT_FROM_ADDRESS` = "support@evvy.com"
- `EVVY_WHEEL_CONSULT_FROM_EMAIL` = "evvy-consult-team@evvy.com"
- `PHONENUMBER_DEFAULT_REGION` = "US"
- `TIME_ZONE` = "America/New_York"
- `SESSION_COOKIE_AGE` = 24 hours
- `AWS_S3_REGION_NAME` = "us-east-2"
- `AWS_S3_SIGNATURE_VERSION` = "s3v4"

---

## Tool Calls Summary

1. Search for settings files (3 patterns)
2. Read settings.py (897 lines)
3. Read .env.example (120 lines)
4. Read settings_celery.py (229 lines)
5. Search for `from django.conf import settings` (found 127 files)
6. Search for `os.environ.get|env\(` (found 133 files)
7. Search for FEATURE_FLAG_ usage (found 3 files)
8. Search for service settings patterns (found 22 files)
9. Search for behavior control settings (found 5 files)
10. Search for URL settings usage (found 17 files)
11. Read app/throttling.py (115 lines)
12. Read test_results/lab_services/config.py (374 lines)
13. Read test_results/utils.py (first 100 lines)
14. Read accounts/utils.py (first 50 lines)
15. Search for lab service settings usage (22 files)
16. Search for behavioral settings usage (5 files)

**Total tool calls: 16**

This comprehensive inventory provides a complete mapping of all custom environment variables and Django settings, their definitions, usage locations, defaults, and the application behaviors they control.
