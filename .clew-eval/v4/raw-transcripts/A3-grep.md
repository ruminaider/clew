# A3 Exploration Log

## Search 1: Locate pharmacy-related files across the codebase
Searched for files matching "pharmacy" (case-insensitive) across all files in `/Users/albertgwo/Work/evvy`. This returned 144 files, revealing the primary pharmacy integration lives under:
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/` — the Precision pharmacy API client and related tasks
- `/Users/albertgwo/Work/evvy/backend/care/` — PrescriptionFill model and status management
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — high-level order processing tasks that call into Precision
- `/Users/albertgwo/Work/evvy/backend/consults/` — consult models and relationship to prescriptions

Also ran a glob for all `.py` files to get a sense of the overall project structure. The pharmacy is called "Precision."

## Search 2: Find refill-related files
Searched for files containing "refill" across the backend. Found 87 files, confirming the main refill logic lives in:
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` — Celery tasks for sending/retrying fills to Precision
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — reprocess_subscription_refill_orders_daily
- `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` — subscription refill service

Also found `/Users/albertgwo/Work/evvy/backend/scripts/remediate_unfilled_orders.py` which documents a historical bug.

## Search 3: Read the core Precision API client
Read `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` in full (563 lines). This is the `PrecisionAPIClient` class — the central pharmacy API integration layer. Key findings:
- Uses `evvy.precision_api` logger
- API base URL is `settings.PRECISION_API_URL/v2`
- Authenticates via `account-id` + `secret` headers
- Core methods: `create_patient`, `amend_patient`, `create_and_fill_prescription_from_consult`, `create_prescription`, `create_otc_treatment`, `fill_prescription`, `cancel_fill`, `retry_warning_prescription_fill`
- Error handling: `_handle_precision_error_response` parses JSON for `success`, `errorCode`, `message` fields
- On API failure during fill creation: sets `PrescriptionFill.status = WARNING` and clears `sent_to_pharmacy_at`
- `DUPLICATE_ID` errors are deliberately ignored (idempotency for refills)

## Search 4: Read the Precision Celery tasks
Read `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` in full (407 lines). This contains all the Celery tasks that orchestrate calls to `PrecisionAPIClient`. Key findings:
- `send_prescription_to_precision(consult_uid)` — main entry point for new fills
- `send_create_patient_request_to_precision(prescription_fill_id, ...)` — creates patient record
- `send_create_prescription_request_to_precision(prescription_uid, ...)` — creates individual prescription; sets WARNING status on failure
- `send_create_otc_treatment_request_to_precision(otc_treatment_uid, ...)` — creates OTC treatment; sets WARNING on failure
- `send_fill_request_to_precision(fill_uid, ...)` — sends the fill/refill order; uses `ecomm.monitoring` for NewRelic events
- `send_cancel_fill_request_to_precision(fill_uid)` — cancels fill; guards against cancelling shipped/delivered fills
- `send_missing_prescriptions_to_precision()` — healing job: finds complete consults not sent in 2 days
- `retry_failed_prescription_fills()` — retry loop for WARNING-status fills:
  - Only retries fills modified >1 hour ago (avoids immediate re-attempt)
  - Only retries fills <7 days old
  - Limits to 10 retries per run
  - Marks fills as FAILED (with `ConsultTask` created) if failing for >3 days
- `send_notification_for_stuck_prescriptions()` — sends admin email if refill fills have been in CREATED status for >3 business days

## Search 5: Find the `make_request` utility and HTTP-level error handling
Searched for `requests.py` in the utils directory. Found `/Users/albertgwo/Work/evvy/backend/utils/requests.py`. Read it in full (118 lines). Key findings:
- `make_request(method, url, json, data, headers, timeout=10)` is the shared HTTP wrapper
- On non-2xx responses: logs error with status code and URL; attempts to parse JSON body; records a `HTTPRequestError` custom event in NewRelic via `newrelic.agent.record_custom_event`
- Raises `HTTPRequestError(original_error, error_details)` which extends `requests.HTTPError` with more context
- `_format_error_details` normalizes Wheel-style and Precision-style error formats

## Search 6: Find the ecomm monitoring infrastructure
Searched for `FulfillmentProvider`, `OrderErrorCategory`, `create_order_logger` across `ecomm/`. Found the monitoring package at `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/`. Read the `__init__.py`, `pipeline.py`, `events.py`, and `enums.py` files. Key findings:
- `FulfillmentProvider` enum: `WHEEL`, `PRECISION`, `BERLIN`, `SHOPIFY`
- `OrderErrorCategory` enum: `VALIDATION`, `PROVIDER_API`, `NETWORK`, `PAYMENT`, `SHIPPING`, `SYSTEM`, `UNKNOWN`
- `OrderEventLogger` (extends `BaseEventLogger`): logs events to NewRelic with order/user/provider context
- `log_fulfillment_sent`, `log_fulfillment_completed`, `log_fulfillment_failed` methods used by `send_fill_request_to_precision`
- All events go to NewRelic as custom events + custom metrics

Also read `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` which has `ExceptionContextMiddleware` (adds user context to NewRelic on exception) and `CheckoutMonitoringMiddleware` (records checkout errors including SSL errors as NewRelic custom metrics).

## Search 7: Find Celery beat schedule entries for Precision tasks
Read `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` in full (228 lines). Found all scheduled tasks related to Precision:
- `heal-precision-pharmacy` → `send_missing_prescriptions_to_precision` — runs daily at 1:15AM and 7:15PM
- `report-stuck-prescriptions` → `send_notification_for_stuck_prescriptions` — runs daily at 10:00AM
- `retry-failed-prescription-fills` → `retry_failed_prescription_fills` — runs daily at 2:30AM, 10:30AM, 6:30PM (3x/day)

## Search 8: Understand PrescriptionFill status constants
Searched for `PRESCRIPTION_FILL_STATUS` in `care/models.py`. Found the status lifecycle:
- `draft` → `created` → `shipped` → `delivered`
- `warning` — failed to send to Precision (retriable)
- `failed` — permanently failed after >3 days of retries
- `cancelled`

## Search 9: Check ecomm tasks for refill flow
Read the first 80 lines of `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`. Confirmed it imports `send_cancel_fill_request_to_precision`, `send_create_otc_treatment_request_to_precision`, `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_fill_request_to_precision` from `shipping.precision.tasks` — meaning the ecomm layer orchestrates these calls for order processing.

## Search 10: Review Precision utility functions for address validation and payload building
Read `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` in full (879 lines). Key findings:
- `validate_shipping_address` — validates required address fields before any API call; raises `ValueError` if missing; prioritizes order shipping address over consult intake
- `get_precision_prescription_creation_payload` — builds the `/prescriptions/create` payload; raises `Exception` if product not in formulary
- `get_precision_carrier_and_method` — picks UPS vs USPS based on PO box detection and product type
- Webhook handlers: `process_precision_shipped_webhook`, `process_precision_delivered_webhook` — update `PrescriptionFill` status, fire Braze analytics events, mark Shopify orders as fulfilled
- Idempotency: `is_prescription_fill_webhook_already_handled` uses Django cache (1-hour TTL) to deduplicate webhook processing

## Search 11: Remediation script for historical unfilled orders
Read first 50 lines of `/Users/albertgwo/Work/evvy/backend/scripts/remediate_unfilled_orders.py`. This script documents a historical bug (~302 orders June 2025 – Feb 2026) where subscription renewal orders never received prescription fills. It includes a decision tree for remediation and references `fill_failed` as a root cause category.

---

## Final Answer

### Where the pharmacy API is called

The pharmacy used is **Precision Pharmacy**, accessed via the `PrecisionAPIClient` class in:

**`/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`**

This class makes HTTP calls to the Precision v2 REST API (`settings.PRECISION_API_URL/v2`) authenticated with `account-id` + `secret` headers. It is the sole HTTP-level caller for all Precision interactions.

The API endpoints called are:
- `POST /v2/patients/create` — create patient record (`create_patient`)
- `POST /v2/patients/update` — amend patient record (`amend_patient`)
- `POST /v2/prescriptions/create` — create prescription or OTC treatment (`create_prescription`, `create_otc_treatment`, `_create_fill_packaging_item_prescription`)
- `POST /v2/refills/create` — create/submit a fill order (`fill_prescription`)
- `POST /v2/refills/cancel` — cancel a fill order (`cancel_fill`)

All HTTP calls go through a shared utility:

**`/Users/albertgwo/Work/evvy/backend/utils/requests.py`** — `make_request(method, url, json, headers, timeout=10)`

This is called by `PrecisionAPIClient._make_request()`:
```python
def _make_request(self, method, url, json=None, extra_headers=None):
    headers = {
        "account-id": self.account_id,
        "secret": self.secret_key,
    }
    if extra_headers:
        headers.update(extra_headers)
    return make_request(method, url, json=json, headers=headers)
```

The `PrecisionAPIClient` is instantiated in Celery tasks in:

**`/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`**

Tasks that call the API:
- `send_prescription_to_precision(consult_uid)` — full flow: create patient + fill prescriptions
- `send_create_patient_request_to_precision(prescription_fill_id, ...)` — patient creation only
- `send_create_prescription_request_to_precision(prescription_uid, ...)` — individual prescription
- `send_create_otc_treatment_request_to_precision(otc_treatment_uid, ...)` — OTC treatment
- `send_fill_request_to_precision(fill_uid, ...)` — final fill/refill order submission
- `send_cancel_fill_request_to_precision(fill_uid)` — cancellation

These tasks are also imported and dispatched from:

**`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`** — for the order processing pipeline.

---

### How errors from the pharmacy API are handled

Error handling operates at three levels:

#### 1. HTTP-level errors (`utils/requests.py`)
`make_request` calls `response.raise_for_status()` on non-2xx responses. Before raising, it:
- Logs the HTTP status code, method, and URL at ERROR level
- Parses the JSON body (if `Content-Type: application/json`) and logs it
- Records a `HTTPRequestError` custom event in NewRelic via `newrelic.agent.record_custom_event("HTTPRequestError", error_context)`
- Raises `HTTPRequestError(original_error, error_details)` — a subclass of `requests.HTTPError` with enriched message

#### 2. Application-level errors (`precision/precision.py`)
`PrecisionAPIClient._handle_precision_error_response(resp, log_data, ignore_errors)`:
```python
def _handle_precision_error_response(self, resp, log_data, ignore_errors=None):
    ignore_errors = ignore_errors or []
    resp_json = resp.json()
    if resp_json.get("success", False):
        return
    error_code = resp_json.get("errorCode", "")
    message = resp_json.get("message", "")
    if error_code in ignore_errors:
        return
    error_msg = "Error creating prescription in precision for data %s: %s - %s" % (...)
    logger.error(error_msg)
    raise requests.HTTPError(error_msg, response=resp)
```
This handles the Precision-specific application-level error format (200 OK but `success: false`). `DUPLICATE_ID` errors are explicitly ignored to support idempotent refill sends.

#### 3. Task-level errors (`precision/tasks.py`)
Each task catches exceptions and:
- Logs at ERROR level with `logger.exception(...)` (which includes the traceback)
- Sets `PrescriptionFill.status = PRESCRIPTION_FILL_STATUS_WARNING` and clears `sent_to_pharmacy_at`
- Re-raises the exception (so Celery records it as a task failure)

Example from `send_fill_request_to_precision`:
```python
except Exception as e:
    logger.exception(f"Error sending fill request {fill_uid} to Precision: {str(e)}")
    if fill.order:
        order_logger.log_fulfillment_failed(
            fill.order, FulfillmentProvider.PRECISION, str(e),
            OrderErrorCategory.PROVIDER_API,
            additional_attributes={"prescription_fill_id": fill_uid, "error_type": type(e).__name__},
        )
    with transaction.atomic():
        fill.refresh_from_db()
        fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING
        fill.sent_to_pharmacy_at = None
        fill.save()
    raise
```

The monitoring calls go to the `OrderEventLogger` in `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`, which logs `FULFILLMENT_FAILED` events to NewRelic with order context.

The `PrescriptionFill` status lifecycle for errors:
- `warning` — transient failure, eligible for retry
- `failed` — permanent failure after 3+ days of retries (creates a `ConsultTask` for manual intervention)

---

### Retry and monitoring logic

#### Retry logic

**Automatic retry of WARNING-status fills** (`retry_failed_prescription_fills` in `precision/tasks.py`):
```python
@shared_task
def retry_failed_prescription_fills():
    one_hour_ago = timezone.now() - timedelta(hours=1)
    seven_days_ago = timezone.now() - timedelta(days=7)
    failed_fills = PrescriptionFill.objects.filter(
        status=PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING,
        modify_date__lt=one_hour_ago,    # only retry fills that failed >1 hour ago
        create_date__gt=seven_days_ago,  # only retry fills <7 days old
    ).order_by("modify_date")[:10]       # limit to 10 per run
    ...
    for fill in failed_fills:
        if fill.modify_date < timezone.now() - timedelta(days=3):
            fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_FAILED
            fill.save()
            ConsultTask.objects.get_or_create(
                consult=fill.consult,
                task_type=ConsultTask.TASK_TYPE_PRESCRIPTION_FILL_FAILURE,
                defaults={"task_data": {...}}
            )
            permanent_failures += 1
            continue
        client.retry_warning_prescription_fill(fill)
```

Safeguards:
- Minimum 1-hour delay between attempts
- Maximum retry window: 7 days from creation
- Batch cap: 10 fills per run
- Escalation: after 3 days, fill marked `failed` + `ConsultTask` created for manual intervention

Scheduled via Celery beat (`settings_celery.py`):
```python
"retry-failed-prescription-fills": {
    "task": "shipping.precision.tasks.retry_failed_prescription_fills",
    "schedule": crontab(hour=[2, 10, 18], minute=30),  # 3x daily
},
```

**Manual retry** — `PrecisionAPIClient.retry_warning_prescription_fill(prescription_fill)` — guards against retrying non-WARNING fills, then calls `_send_prescription_fill_to_precision`.

**Healing job for missed prescriptions** (`send_missing_prescriptions_to_precision`):
- Finds consults completed in last 2 days with `pharmacy_type=PRECISION` and `sent_to_pharmacy_at=null`
- Verifies prescriptions match recommendations via Wheel's `check_recommended_prescriptions_against_prescribed`
- Dispatches `send_prescription_to_precision.delay(consult.uid)` for each

Scheduled:
```python
"heal-precision-pharmacy": {
    "task": "shipping.precision.tasks.send_missing_prescriptions_to_precision",
    "schedule": crontab(hour=[1, 19], minute=15),  # 2x daily
},
```

#### Monitoring logic

**NewRelic custom events** (from `utils/requests.py`):
- `HTTPRequestError` event recorded on any non-2xx HTTP response with context: `status_code`, `method`, `url`, `response_headers`, `response_json`

**NewRelic via `ecomm/monitoring`** (from `send_fill_request_to_precision`):
- `FULFILLMENT_SENT` event when fill is dispatched to Precision
- `FULFILLMENT_COMPLETED` event on success
- `FULFILLMENT_FAILED` event on error (with `error_category=PROVIDER_API`, `error_details`, `prescription_fill_id`, `error_type`)
- Custom attributes: `prescription_fill_id`, `fulfillment_provider=precision`, `order_id`, `order_number` added via `newrelic.agent.add_custom_attribute`

**Admin email alerts** (`send_notification_for_stuck_prescriptions`):
- Finds fills in CREATED status for >3 business days that are refills
- Sends summary email to `settings.CONSULT_UPDATES_EMAIL`

Scheduled:
```python
"report-stuck-prescriptions": {
    "task": "shipping.precision.tasks.send_notification_for_stuck_prescriptions",
    "schedule": crontab(hour=10, minute=0),  # daily at 10:00AM
},
```

**Structured logging** via `logger = logging.getLogger("evvy.precision_api")` / `"evvy.precision.tasks"` — all operations log at INFO/ERROR/WARNING with object IDs (fill id, consult uid, prescription uid) for traceability.

**Webhook idempotency guard** (`is_prescription_fill_webhook_already_handled` in `precision/utils.py`):
- Uses Django cache (1-hour TTL) to prevent duplicate processing of `shipped` and `delivered` webhooks
- Supports a separate cache key path for `replacement=True` webhook payloads

---

### Summary file map

| Purpose | File |
|---|---|
| Precision API client (all HTTP calls) | `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` |
| Celery tasks for Precision | `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` |
| Payload builders + webhook handlers | `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` |
| Shared HTTP utility + NewRelic HTTP errors | `/Users/albertgwo/Work/evvy/backend/utils/requests.py` |
| ecomm monitoring (fulfillment events) | `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` |
| Monitoring enums (FulfillmentProvider, etc.) | `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/enums.py` |
| PrescriptionFill model + status constants | `/Users/albertgwo/Work/evvy/backend/care/models.py` |
| Celery beat schedule (all cron entries) | `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` |
| ecomm tasks (orchestrates Precision calls) | `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` |
| Historical remediation script | `/Users/albertgwo/Work/evvy/backend/scripts/remediate_unfilled_orders.py` |
