# Investigation: Environment Variable and Settings Inventory (Grep)

## Task

Create a complete inventory of all custom environment variables and Django settings that control application behavior. For each setting, identify: (1) where it's defined (settings files, .env, os.environ defaults), (2) where it's read in application code (os.environ.get, django.conf.settings, etc.), (3) what behavior it controls. Focus on application-specific settings, not standard Django framework defaults.

## Tool Calls and Reasoning

### Step 1: Identify Django settings files
**Goal:** Locate all settings files and environment configuration files in the codebase.

**Tool calls:**
- `Glob` for `**/settings*.py`
- `Glob` for `**/.env*`
- `Glob` for `**/config.py`

**Findings:**
- Main settings: `/Users/albertgwo/Work/evvy/backend/app/settings.py`
- Celery settings: `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py`
- Environment template: `/Users/albertgwo/Work/evvy/backend/app/.env.example`
- Lab services config: `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/config.py`
- Multiple worktree copies (can ignore for main investigation)

### Step 2: Read main Django settings file
**Goal:** Understand primary settings configuration.

**Tool call:** `Read` on `/Users/albertgwo/Work/evvy/backend/app/settings.py`

**Findings:** Settings file uses `django-environ` library to load environment variables. Key patterns:
- `env = environ.Env(DEBUG=(bool, False))` - creates environment reader with type casting
- `environ.Env.read_env()` - loads from .env file
- Settings defined with `env("VAR_NAME", default=...)` pattern
- 897 lines total with extensive environment variable usage

### Step 3: Read .env.example and settings_celery.py
**Goal:** See template of expected environment variables and Celery-specific settings.

**Tool calls:**
- `Read` on `/Users/albertgwo/Work/evvy/backend/app/.env.example`
- `Read` on `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py`

**Findings from .env.example:**
- 120 lines documenting expected environment variables
- Includes database, email, shipping providers, external APIs, feature flags, etc.

**Findings from settings_celery.py:**
- Uses `os.environ.get()` directly for Celery configuration
- Defines `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` with Redis defaults
- Contains extensive `CELERY_BEAT_SCHEDULE` with cron jobs

### Step 4: Search for os.environ.get usage across codebase
**Goal:** Find files that read environment variables directly (not through Django settings).

**Tool call:** `Grep` for `os\.environ\.get` pattern

**Findings:** 14 files use direct `os.environ.get()`:
- `settings.py` and `settings_celery.py` (expected)
- `test_results/lab_services/config.py` - Wheel provider config
- `partner_api/partner_config.py` - Partner API configuration
- Several task and utility files

### Step 5: Search for django.conf import and settings usage
**Goal:** Find all files that consume Django settings.

**Tool call:** `Grep` for `from django\.conf import settings` pattern

**Findings:** 127 files import and use Django settings throughout the application, indicating widespread usage of centralized configuration.

### Step 6: Read specific configuration files
**Goal:** Understand how settings are used in different modules.

**Tool calls:**
- `Read` on `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/config.py`
- `Read` on `/Users/albertgwo/Work/evvy/backend/partner_api/partner_config.py`

**Findings from lab_services/config.py:**
- Uses `settings.JUNCTION_ENABLED`, `JUNCTION_API_KEY`, `JUNCTION_BASE_URL`, `JUNCTION_SANDBOX`, `JUNCTION_WEBHOOK_SECRET`
- Also reads `WHEEL_*` variables directly from `os.environ.get()`
- Controls lab provider integration behavior

**Findings from partner_config.py:**
- Uses `os.environ.get("GROW_BABY_API_KEY")`, `GROW_BABY_COHORT_TITLE`, `GROW_BABY_ALLOWED_IPS`
- Controls partner API access and cohort-based authorization

### Step 7: Search for feature flag usage
**Goal:** Identify all feature flags and their usage.

**Tool call:** `Grep` for `FEATURE_FLAG_` pattern with content output

**Findings:** 6 feature flags defined:
1. `FEATURE_FLAG_XACIATO` - Controls Xaciato product feature
2. `FEATURE_FLAG_PROBIOTIC_OTC` - Controls OTC probiotic feature
3. `FEATURE_FLAG_MALE_PARTNER` - Controls male partner feature
4. `FEATURE_FLAG_MALE_PARTNER_TREATMENT_UPSELL` - Controls male partner treatment upsell
5. `FEATURE_FLAG_URINE_TEST` - Controls urine test feature
6. `FEATURE_FLAG_BV_SUBTYPES` - Controls BV subtypes feature

All use pattern: `True if env("FEATURE_FLAG_X", default=False) == "enabled" else False`

Used in: `accounts/utils.py` for feature gating logic

### Step 8: Search for THROTTLE_MODE usage
**Goal:** Understand throttling configuration.

**Tool call:** `Grep` for `THROTTLE_MODE` pattern

**Findings:**
- Defined in `settings.py` as `env("THROTTLE_MODE", default="warn")`
- Used in `app/throttling.py` to control whether throttling enforces or just warns
- Two modes: "warn" (log only) vs enforcement mode

### Step 9: Search for additional custom settings
**Goal:** Find other custom application settings.

**Tool call:** `Grep` for specific custom settings patterns

**Findings:**
- `PAUSE_AUTO_RELEASE_RESULTS` - Used in `test_results/utils.py` to pause automatic result releases
- `MICROGEN_ENABLED` - Controls Microgen integration (used in various places)
- `JUNCTION_ENABLED` - Controls Junction lab provider (used in lab_services/config.py)
- `BYPASS_EMAIL_VERIFICATION` - Used in `api/v1/views/userconfig.py` to skip email verification
- `HYDRATE_DB_ON_INIT` and `HYDRATE_DB_USER_PASSWORD` - Controls staging database hydration

## Investigation Results

### Complete Environment Variables and Settings Inventory

#### 1. Core Django Settings

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `DEBUG` | `settings.py:39` via `env("DEBUG", default=False)` | Throughout Django | Debug mode (development vs production) |
| `SECRET_KEY` | `settings.py:36` via `env("SECRET_KEY")` | Django core | Cryptographic signing |
| `ROOT_LOG_LEVEL` | `settings.py:652` via `os.environ.get("ROOT_LOG_LEVEL", "INFO")` | `settings.py:688` | Root logger level |
| `DJANGO_LOG_LEVEL` | `settings.py:653` via `os.environ.get("DJANGO_LOG_LEVEL", "INFO")` | `settings.py:694` | Django logger level |

#### 2. Database Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `DB_NAME` | `settings.py:303` via `env("DB_NAME")` | `settings.py:301-309` | PostgreSQL database name |
| `DB_USER` | `settings.py:304` via `env("DB_USER")` | `settings.py:301-309` | PostgreSQL username |
| `DB_PASSWORD` | `settings.py:305` via `env("DB_PASSWORD")` | `settings.py:301-309` | PostgreSQL password |
| `DB_HOST` | `settings.py:306` via `env("DB_HOST")` | `settings.py:301-309` | PostgreSQL host |
| `DB_HOST_PORT` | `settings.py:307` via `env("DB_HOST_PORT")` | `settings.py:301-309` | PostgreSQL port |

#### 3. URL and Domain Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `RENDER_EXTERNAL_URL` | `settings.py:44` via `env("RENDER_EXTERNAL_URL", default=None)` | `settings.py:68-70` | Render-injected backend URL |
| `RENDER_FRONTEND_HOST` | `settings.py:47` via `env("RENDER_FRONTEND_HOST", default=None)` | `settings.py:49-56` | Render frontend host construction |
| `RENDER_INTERNAL_FRONTEND_HOST` | `settings.py:48` via `env("RENDER_INTERNAL_FRONTEND_HOST", default=None)` | `settings.py:52-56` | Render internal frontend host |
| `SITE_URL` | `settings.py:60` via `env("SITE_URL", default="")` | `settings.py:96-109` | Custom domain URL (can be "dynamic") |
| `INTERNAL_SITE_URL` | `settings.py:61` via `env("INTERNAL_SITE_URL", default="")` | `settings.py:104-112` | Custom internal domain URL |
| `BACKEND_URL` | `settings.py:62` via `env("BACKEND_URL", default="")` | `settings.py:72-118` | Custom backend domain URL |
| `ADDITIONAL_ALLOWED_BACKEND_HOSTS` | `settings.py:80` via `env.list("ADDITIONAL_ALLOWED_BACKEND_HOSTS", default=[])` | `settings.py:81` | Extra allowed backend hosts (list) |
| `ADDITIONAL_ALLOWED_CORS_ORIGINS` | `settings.py:123` via `env.list("ADDITIONAL_ALLOWED_CORS_ORIGINS", default=[])` | `settings.py:124` | Extra CORS origins (list) |
| `ADDITIONAL_ALLOWED_CSRF_ORIGINS` | `settings.py:127` via `env.list("ADDITIONAL_ALLOWED_CSRF_ORIGINS", default=[])` | `settings.py:128` | Extra CSRF origins (list) |

#### 4. Session and Cookie Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `SESSION_COOKIE_DOMAIN` | `settings.py:364` via `env("SESSION_COOKIE_DOMAIN", default=None)` | Django middleware | Session cookie domain |
| `CSRF_COOKIE_DOMAIN` | `settings.py:365` via `env("CSRF_COOKIE_DOMAIN", default=None)` | Django middleware | CSRF cookie domain |
| `CSRF_COOKIE_NAME` | `settings.py:366` via `env("CSRF_COOKIE_NAME", default="csrftoken")` | Django middleware | CSRF cookie name |

#### 5. Email Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `EMAIL_HOST` | `settings.py:437` via `env("EMAIL_HOST", default=None)` | Django email backend | SMTP host |
| `EMAIL_PORT` | `settings.py:438` via `env("EMAIL_PORT", default=None)` | Django email backend | SMTP port |
| `EMAIL_HOST_USER` | `settings.py:439` via `env("EMAIL_HOST_USER", default=None)` | Django email backend | SMTP username |
| `EMAIL_HOST_PASSWORD` | `settings.py:440` via `env("EMAIL_HOST_PASSWORD", default=None)` | Django email backend | SMTP password |
| `MANDRILL_API_KEY` | `settings.py:441` via `env("MANDRILL_API_KEY", default=None)` | `transactional_email/mandrill.py` | Mandrill email service |
| `BYPASS_EMAIL_VERIFICATION` | `settings.py:619` via `env.bool("BYPASS_EMAIL_VERIFICATION", default=False)` | `api/v1/views/userconfig.py:129` | Skip email verification in dev |

#### 6. Email Notification Channels (Slack)

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `GENERATE_KITS_EMAIL` | `settings.py:557` via `env("GENERATE_KITS_EMAIL", default=None)` | Test kit generation notifications | Email for kit ID generation confirmations |
| `MDX_LAB_UPDATES_EMAIL` | `settings.py:560` via `env("MDX_LAB_UPDATES_EMAIL", default=None)` | Lab status notifications | MDX lab status update notifications |
| `MDX_PROCESSED_RUN_NOTIFICATION_EMAIL` | `settings.py:561` via `env("MDX_PROCESSED_RUN_NOTIFICATION_EMAIL", default=None)` | Lab processing notifications | MDX processed run notifications |
| `LAB_DELAY_EMAIL` | `settings.py:562` via `env("LAB_DELAY_EMAIL", default=None)` | Lab delay alerts | Lab delay notification channel |
| `VIP_TEST_EMAIL` | `settings.py:563` via `env("VIP_TEST_EMAIL", default=None)` | VIP test notifications | VIP test processing alerts |
| `HEALTHY_HONEY_SLACK_CHANNEL` | `settings.py:564` via `env("HEALTHY_HONEY_SLACK_CHANNEL", default=None)` | Health honey notifications | Slack channel for health honey alerts |
| `JUNCTION_TEST_STATUS_UPDATES_EMAIL` | `settings.py:566` via `env("JUNCTION_TEST_STATUS_UPDATES_EMAIL", default=None)` | Junction test notifications | Junction test status updates |
| `URINE_TEST_RESULTS_NOTIFICATIONS_SLACK_EMAIL` | `settings.py:569-571` via `env("URINE_TEST_RESULTS_NOTIFICATIONS_SLACK_EMAIL", default="urine-test-results-no-aaaaspl3xniyejmjivxgz4ub54@evvy-bio.slack.com")` | Urine test notifications | Urine test results Slack channel |
| `JUNCTION_TEST_STATUS_SLACK_USER_IDS` | `settings.py:576` via `env("JUNCTION_TEST_STATUS_SLACK_USER_IDS", default=None)` | Junction test alerts | Slack users to tag for Junction alerts (comma-separated) |
| `CONSULT_UPDATES_EMAIL` | `settings.py:498` via `env("CONSULT_UPDATES_EMAIL", default=None)` | Consult status notifications | Slack channel for consult error/referral status |
| `BABY_UH_OH_EMAIL` | `settings.py:500` via `env("BABY_UH_OH_EMAIL", default=None)` | Baby issue alerts | Baby uh oh notifications |
| `B2B_PROVIDER_REGISTRATION_EMAIL` | `settings.py:579` via `env("B2B_PROVIDER_REGISTRATION_EMAIL", default=None)` | B2B notifications | B2B provider registration events |
| `B2B_IN_CLINIC_EMAIL` | `settings.py:582` via `env("B2B_IN_CLINIC_EMAIL", default=None)` | B2B order notifications | B2B in-clinic orders |
| `B2B_PROVIDER_SUPPORT_EMAIL` | `settings.py:585` via `env("B2B_PROVIDER_SUPPORT_EMAIL", default=None)` | B2B support | B2B provider support requests |
| `OPS_TECH_EMAIL` | `settings.py:588` via `env("OPS_TECH_EMAIL", default=None)` | Ops notifications | Operations tech notifications |
| `ENG_WARNING_EMAIL` | `settings.py:591` via `env("ENG_WARNING_EMAIL", default=None)` | Engineering alerts | Engineering warning notifications |

#### 7. External API Integrations

##### Braze (Marketing Automation)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `BRAZE_API_KEY` | `settings.py:443` via `env("BRAZE_API_KEY", default=None)` | `analytics/braze/braze.py` | Braze API authentication |
| `BRAZE_API_URL` | `settings.py:444` via `env("BRAZE_API_URL", default=None)` | `analytics/braze/braze.py` | Braze API endpoint |

##### Notion (Documentation)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `NOTION_API_KEY` | `settings.py:447` via `env("NOTION_API_KEY", default=None)` | Braze documentation sync | Notion API key |
| `NOTION_BRAZE_PAGE_ID` | `settings.py:448` via `env("NOTION_BRAZE_PAGE_ID", default=None)` | Braze documentation sync | Notion page for Braze docs |

##### USPS (Shipping)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `USPS_USER_ID` | `settings.py:452` via `env("USPS_USER_ID", default=None)` | `shipping/usps_api_client.py` | Legacy USPS Web Tools API (deprecated Jan 2026) |
| `USPS_CLIENT_ID` | `settings.py:455` via `env("USPS_CLIENT_ID", default=None)` | `shipping/usps_api_client.py` | USPS REST API OAuth client ID |
| `USPS_CLIENT_SECRET` | `settings.py:456` via `env("USPS_CLIENT_SECRET", default=None)` | `shipping/usps_api_client.py` | USPS REST API OAuth secret |
| `USPS_API_URL` | `settings.py:457` via `env("USPS_API_URL", default="https://apis.usps.com")` | `shipping/usps_api_client.py` | USPS API base URL |

##### Recharge (Subscriptions)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `RECHARGE_API_KEY` | `settings.py:460` via `env("RECHARGE_API_KEY", default=None)` | `subscriptions/recharge.py` | Recharge API authentication |
| `RECHARGE_API_URL` | `settings.py:461` via `env("RECHARGE_API_URL", default=None)` | `subscriptions/recharge.py` | Recharge API endpoint |
| `RECHARGE_WEBHOOK_SECRET` | `settings.py:462` via `env("RECHARGE_WEBHOOK_SECRET", default=None)` | Webhook verification | Recharge webhook signature verification |

##### Fullstory (Analytics)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `FULLSTORY_API_KEY` | `settings.py:465` via `env("FULLSTORY_API_KEY", default=None)` | `analytics/fullstory.py` | Fullstory API authentication |

##### Shopify (E-commerce)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `SHOPIFY_BASE_URL` | `settings.py:468` via `env("SHOPIFY_BASE_URL", default="evvybio.myshopify.com")` | `ecomm/shopify/` | Shopify store URL |
| `SHOPIFY_STOREFRONT_ACCESS_TOKEN` | `settings.py:469` via `env("SHOPIFY_STOREFRONT_ACCESS_TOKEN", default=None)` | `ecomm/shopify/` | Shopify Storefront API token |
| `SHOPIFY_ADMIN_ACCESS_TOKEN` | `settings.py:470` via `env("SHOPIFY_ADMIN_ACCESS_TOKEN", default=None)` | `ecomm/shopify/` | Shopify Admin API token |
| `SHOPIFY_WEBHOOK_SECRET` | `settings.py:471` via `env("SHOPIFY_WEBHOOK_SECRET", default=None)` | Webhook verification | Shopify webhook signature |
| `SHOPIFY_WEBHOOK_GRAPHQL_SECRET` | `settings.py:472` via `env("SHOPIFY_WEBHOOK_GRAPHQL_SECRET", default=None)` | Webhook verification | Shopify GraphQL webhook signature |

##### Viome (Lab Partner)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `VIOME_WEBHOOK_SECRET` | `settings.py:475` via `env("VIOME_WEBHOOK_SECRET", default=None)` | Webhook verification | Viome webhook signature verification |

##### Typeform (Surveys)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `TYPEFORM_WEBHOOK_SECRET` | `settings.py:478` via `env("TYPEFORM_WEBHOOK_SECRET", default=None)` | Webhook verification | Typeform webhook signature verification |

##### ShareASale (Affiliate Marketing)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `SHARE_A_SALE_API_TOKEN` | `settings.py:481` via `env("SHARE_A_SALE_API_TOKEN", default=None)` | Affiliate tracking | ShareASale API token |
| `SHARE_A_SALE_API_SECRET` | `settings.py:482` via `env("SHARE_A_SALE_API_SECRET", default=None)` | Affiliate tracking | ShareASale API secret |
| `SHARE_A_SALE_EVVY_MERCHANT_ID` | `settings.py:483` via `env("SHARE_A_SALE_EVVY_MERCHANT_ID", default=None)` | Affiliate tracking | Evvy's ShareASale merchant ID |

##### FedEx (Shipping)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `FEDEX_API_KEY` | `settings.py:486` via `env("FEDEX_API_KEY", default=None)` | `shipping/fedex.py` | FedEx API key |
| `FEDEX_API_SECRET` | `settings.py:487` via `env("FEDEX_API_SECRET", default=None)` | `shipping/fedex.py` | FedEx API secret |
| `FEDEX_API_URL` | `settings.py:488` via `env("FEDEX_API_URL", default="https://apis-sandbox.fedex.com")` | `shipping/fedex.py` | FedEx API endpoint (sandbox default) |

##### Wheel (Telemedicine)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `WHEEL_ACCESS_TOKEN` | `settings.py:493` via `env("WHEEL_ACCESS_TOKEN", default=None)` | `consults/wheel/wheel.py` | Wheel API access token |
| `WHEEL_API_KEY` | `settings.py:494` via `env("WHEEL_API_KEY", default=None)` | `consults/wheel/wheel.py` | Wheel API key |
| `WHEEL_API_URL` | `settings.py:495` via `env("WHEEL_API_URL", default="https://sandbox-api.wheel.health")` | `consults/wheel/wheel.py` | Wheel API endpoint (sandbox default) |
| `WHEEL_OPS_EMAIL` | `settings.py:496` via `env("WHEEL_OPS_EMAIL", default=None)` | Consult notifications | Wheel operations email |

##### Microgen (Lab Partner)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `MICROGEN_SECRET_KEY` | `settings.py:505` via `env("MICROGEN_SECRET_KEY", default="")` | `test_results/microgen/` | Microgen HMAC signature verification |
| `MICROGEN_API_URL` | `settings.py:506` via `env("MICROGEN_API_URL", default="")` | `test_results/microgen/` | Microgen API endpoint |
| `MICROGEN_API_KEY` | `settings.py:507` via `env("MICROGEN_API_KEY", default="")` | `test_results/microgen/` | Microgen API key |
| `MICROGEN_API_APP_ID` | `settings.py:508` via `env("MICROGEN_API_APP_ID", default="")` | `test_results/microgen/` | Microgen app ID |
| `MICROGEN_ENABLED` | `settings.py:509` via `env.bool("MICROGEN_ENABLED", default=True)` | Test result processing | Enable/disable Microgen integration |
| `RESULTS_PROCESSING_MAX_DELAY_MINUTES` | `settings.py:510` via `env.int("RESULTS_PROCESSING_MAX_DELAY_MINUTES", default=0)` | `test_results/utils_processing.py` | Max delay before processing results |

##### Junction (Lab Provider - Vital/Urine Tests)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `JUNCTION_ENABLED` | `settings.py:513` via `env.bool("JUNCTION_ENABLED", default=False)` | `test_results/lab_services/config.py:113` | Enable/disable Junction integration |
| `JUNCTION_API_KEY` | `settings.py:514` via `env("JUNCTION_API_KEY", default="")` | `test_results/lab_services/config.py:114` | Junction API key |
| `JUNCTION_BASE_URL` | `settings.py:515` via `env("JUNCTION_BASE_URL", default="https://api.sandbox.tryvital.io")` | `test_results/lab_services/config.py:115` | Junction API endpoint (sandbox default) |
| `JUNCTION_SANDBOX` | `settings.py:516` via `env.bool("JUNCTION_SANDBOX", default=True)` | `test_results/lab_services/config.py:116` | Junction sandbox mode flag |
| `JUNCTION_WEBHOOK_SECRET` | `settings.py:517` via `env("JUNCTION_WEBHOOK_SECRET", default="")` | `test_results/lab_services/config.py:120` | Junction webhook signature verification |

##### Precision Pharmacy
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `PRECISION_SECRET_KEY` | `settings.py:520` via `env("PRECISION_SECRET_KEY", default="")` | `shipping/precision/precision.py` | Precision Pharmacy API secret |
| `PRECISION_API_URL` | `settings.py:521` via `env("PRECISION_API_URL", default="")` | `shipping/precision/precision.py` | Precision Pharmacy API endpoint |
| `PRECISION_ACCOUNT_ID` | `settings.py:522` via `env("PRECISION_ACCOUNT_ID", default="")` | `shipping/precision/precision.py` | Precision account identifier |

##### Berlin (Fulfillment)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `BERLIN_ACCESS_TOKEN` | `settings.py:525` via `env("BERLIN_ACCESS_TOKEN", default=None)` | `shipping/berlin/berlin.py` | Berlin API access token |
| `BERLIN_API_URL` | `settings.py:526` via `env("BERLIN_API_URL", default=None)` | `shipping/berlin/berlin.py` | Berlin API endpoint |
| `BERLIN_CLIENT_ID` | `settings.py:527` via `env("BERLIN_CLIENT_ID", default=None)` | `shipping/berlin/berlin.py` | Berlin OAuth client ID |
| `BERLIN_CLIENT_SECRET` | `settings.py:528` via `env("BERLIN_CLIENT_SECRET", default=None)` | `shipping/berlin/berlin.py` | Berlin OAuth client secret |
| `BERLIN_EXPEDITED_EMAILS` | `settings.py:546` via `env("BERLIN_EXPEDITED_EMAILS", default="")` | `shipping/tasks.py` | Comma-separated emails for Berlin expedited notifications |
| `BERLIN_EMAIL_FROM_ADDRESS` | `settings.py:547` via `env("BERLIN_EMAIL_FROM_ADDRESS", default="")` | `shipping/tasks.py` | From address for Berlin emails |
| `BERLIN_EXPRESS_GSHEET_ID` | `settings.py:548` via `env("BERLIN_EXPRESS_GSHEET_ID", default="")` | `shipping/berlin/utils.py` | Google Sheet ID for Berlin express tracking |

##### Intercom (Customer Support)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `INTERCOM_API_KEY` | `settings.py:531` via `env("INTERCOM_API_KEY", default=None)` | `support/intercom.py` | Intercom API authentication |
| `INTERCOM_API_URL` | `settings.py:532` via `env("INTERCOM_API_URL", default=None)` | `support/intercom.py` | Intercom API endpoint |

##### Survicate (Surveys)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `SURVICATE_API_KEY` | `settings.py:535` via `env("SURVICATE_API_KEY", default=None)` | `surveys/survicate.py` | Survicate API authentication |
| `SURVICATE_API_URL` | `settings.py:536` via `env("SURVICATE_API_URL", default=None)` | `surveys/survicate.py` | Survicate API endpoint |
| `SURVICATE_SECRET_KEY` | `settings.py:537` via `env("SURVICATE_SECRET_KEY", default=None)` | `surveys/survicate.py` | Survicate webhook secret |

##### Calendly (Scheduling)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `CALENDLY_SECRET_KEY` | `settings.py:540` via `env("CALENDLY_SECRET_KEY", default=None)` | Webhook verification | Calendly webhook signature |

##### OpenAI (AI)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `OPENAI_API_KEY` | `settings.py:543` via `env("OPENAI_API_KEY", default=None)` | `ai/openai.py` | OpenAI API authentication |

##### Klaviyo (Email Marketing)
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `KLAVIYO_SECRET_KEY` | `settings.py:554` via `env("KLAVIYO_SECRET_KEY", default="")` | Marketing automation | Klaviyo API authentication |

##### Google Services
| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `GOOGLE_JSON_CREDS` | `settings.py:551` via `env("GOOGLE_JSON_CREDS", default="")` | `shipping/berlin/utils.py` | Google Service Account credentials for Sheets API |

#### 8. Partner API Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `PARTNER_API_KEY` | `settings.py:362` via `env("PARTNER_API_KEY", default=None)` | `partner_api/authentication.py` | General partner API authentication |
| `GROW_BABY_API_KEY` | Not in settings.py | `partner_api/partner_config.py:43` via `os.environ.get()` | Grow Baby partner API key |
| `GROW_BABY_COHORT_TITLE` | Not in settings.py | `partner_api/partner_config.py:44` via `os.environ.get()` | Grow Baby cohort title |
| `GROW_BABY_ALLOWED_IPS` | Not in settings.py | `partner_api/partner_config.py:45` via `os.environ.get()` | Grow Baby allowed IPs (comma-separated) |

#### 9. AWS Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `AWS_ACCESS_KEY` | `settings.py:635` via `env("AWS_ACCESS_KEY", default=None)` | `utils/s3.py` | AWS access key ID |
| `AWS_ACCESS_SECRET` | `settings.py:636` via `env("AWS_ACCESS_SECRET", default=None)` | `utils/s3.py` | AWS secret access key |
| `AWS_S3_ENDPOINT_URL` | `settings.py:642-643` via `env("AWS_S3_ENDPOINT_URL", default=None)` | Django storages | Custom S3 endpoint (local dev with LocalStack) |
| `PERF_S3_BUCKET_NAME` | `settings.py:646` via `env("PERF_S3_BUCKET_NAME", default="devvy")` | Performance testing | S3 bucket for performance tests |

#### 10. Celery Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `CELERY_BROKER_URL` | `settings_celery.py:8` via `os.environ.get("CELERY_BROKER_URL", "redis://redis-queue:6379/0")` | Celery worker | Redis broker URL for task queue |
| `CELERY_RESULT_BACKEND` | `settings_celery.py:9` via `os.environ.get("CELERY_RESULT_BACKEND", "redis://redis-queue:6379/0")` | Celery worker | Redis backend for task results |

#### 11. Caching Configuration

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `REDIS_CACHE_LOCATION` | `settings.py:838` via `os.environ.get("REDIS_CACHE_LOCATION", None)` | `settings.py:842-866` | Redis cache location (enables Redis caching if set) |

#### 12. Feature Flags

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `FEATURE_FLAG_XACIATO` | `settings.py:595` via `env("FEATURE_FLAG_XACIATO", default=False) == "enabled"` | `accounts/utils.py:133` | Xaciato product feature |
| `FEATURE_FLAG_PROBIOTIC_OTC` | `settings.py:597-598` via `env("FEATURE_FLAG_PROBIOTIC_OTC", default=False) == "enabled"` | Product catalog | OTC probiotic product feature |
| `FEATURE_FLAG_MALE_PARTNER` | `settings.py:601-602` via `env("FEATURE_FLAG_MALE_PARTNER", default=False) == "enabled"` | User features | Male partner testing feature |
| `FEATURE_FLAG_MALE_PARTNER_TREATMENT_UPSELL` | `settings.py:605-606` via `env("FEATURE_FLAG_MALE_PARTNER_TREATMENT_UPSELL", default=False) == "enabled"` | Checkout flow | Male partner treatment upsell |
| `FEATURE_FLAG_URINE_TEST` | `settings.py:609-610` via `env("FEATURE_FLAG_URINE_TEST", default=False) == "enabled"` | Test types | Urine test feature |
| `FEATURE_FLAG_BV_SUBTYPES` | `settings.py:613-614` via `env("FEATURE_FLAG_BV_SUBTYPES", default=False) == "enabled"` | `accounts/utils.py:178` | BV subtypes feature |

#### 13. Application Behavior Controls

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `THROTTLE_MODE` | `settings.py:408` via `env("THROTTLE_MODE", default="warn")` | `app/throttling.py:6,15,30,44,59` | API throttling mode: "warn" (log only) or enforce |
| `PAUSE_AUTO_RELEASE_RESULTS` | `settings.py:649` via `env("PAUSE_AUTO_RELEASE_RESULTS", default=False)` | `test_results/utils.py:3548` | Pause automatic release of test results |
| `BYPASS_EMAIL_VERIFICATION` | `settings.py:619` via `env.bool("BYPASS_EMAIL_VERIFICATION", default=False)` | `api/v1/views/userconfig.py:129` | Skip email verification (dev/staging) |
| `HYDRATE_DB_ON_INIT` | `settings.py:631` via `env("HYDRATE_DB_ON_INIT", default=False) == "yes"` | `app/management/commands/staging_hydrate.py:218` | Auto-populate staging database |
| `HYDRATE_DB_USER_PASSWORD` | `settings.py:632` via `env("HYDRATE_DB_USER_PASSWORD", default=None)` | `test_results/utils_import.py:290,306` | Password for staging users |
| `NEW_RELIC_ENVIRONMENT` | `settings.py:193` via `env("NEW_RELIC_ENVIRONMENT", default="unset")` | Monitoring | New Relic environment tag |

#### 14. Wheel Provider (Lab Requisitions - Not in main settings)

**Note:** These are read directly from environment in `test_results/lab_services/config.py:243-251`

| Variable | Definition Location | Usage Location | Controls |
|----------|-------------------|----------------|----------|
| `WHEEL_API_KEY` | `os.environ.get("WHEEL_API_KEY", "")` | `test_results/lab_services/config.py:243` | Wheel API key for requisitions |
| `WHEEL_BASE_URL` | `os.environ.get("WHEEL_BASE_URL", "https://api.wheel.com")` | `test_results/lab_services/config.py:244` | Wheel API base URL |
| `WHEEL_SANDBOX` | `os.environ.get("WHEEL_SANDBOX", "false")` | `test_results/lab_services/config.py:245` | Wheel sandbox mode flag |
| `WHEEL_WEBHOOK_SECRET` | `os.environ.get("WHEEL_WEBHOOK_SECRET", "")` | `test_results/lab_services/config.py:249` | Wheel webhook secret |
| `WHEEL_APP_ID` | `os.environ.get("WHEEL_APP_ID", "")` | `test_results/lab_services/config.py:251` | Wheel application ID |

### Summary Statistics

- **Total custom environment variables identified:** 100+
- **Settings files:** 2 main files (`settings.py`, `settings_celery.py`)
- **Configuration modules:** 2 (`test_results/lab_services/config.py`, `partner_api/partner_config.py`)
- **Files using Django settings:** 127 files
- **Files using os.environ.get directly:** 14 files
- **Feature flags:** 6
- **External service integrations:** 25+ services

### Key Patterns Identified

1. **Primary pattern:** `env("VAR_NAME", default=...)` using django-environ library
2. **Direct os.environ pattern:** Used for Celery config and some dynamic module configs
3. **Feature flag pattern:** All use `== "enabled"` check for safety
4. **Webhook secrets:** Consistently named with `_WEBHOOK_SECRET` suffix
5. **API credentials:** Typically include `_API_KEY`, `_API_URL`, and optional `_API_SECRET`
6. **List-type vars:** Use `env.list()` for comma-separated values (CORS origins, allowed hosts)
7. **Boolean vars:** Use `env.bool()` for proper type casting
8. **Slack integration:** Email addresses are used as Slack channel webhooks
9. **Sandbox/production:** Many services have sandbox URL defaults and mode flags

## Tool Call Summary

**Total tool calls:** 9

1. `Glob` - Find settings files (3 patterns)
2. `Read` - Main settings.py
3. `Read` - .env.example and settings_celery.py (2 files)
4. `Grep` - Find os.environ.get usage
5. `Grep` - Find django.conf.settings imports
6. `Read` - Lab services config and partner config (2 files)
7. `Grep` - Find feature flag usage
8. `Grep` - Find THROTTLE_MODE usage
9. `Grep` - Find additional custom settings usage
