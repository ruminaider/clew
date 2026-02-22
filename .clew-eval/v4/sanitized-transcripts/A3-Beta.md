# A3 Exploration Log

## Search 1: Pharmacy API calls (broad entry point)
Query: `search("pharmacy API call")`

Found:
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` — `pharmacies()` action on `ConsultIntakeViewSet` (line 953) calls Wheel's pharmacy search API
- `/Users/albertgwo/Work/evvy/backend/consults/wheel/wheel.py` — `WheelAPIClient.search_pharmacies()` (line 867) — searches Wheel's pharmacy API
- `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils.py` — `get_pharmacy_info()` (line 405) — retrieves pharmacy info from consult intake; Precision Compounding used by default

## Search 2: Refill order pharmacy (main refill flow)
Query: `search("refill order pharmacy")`

Found:
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — `send_prescription_refill_request(order_id, prescription_fill_id)` (line 157) — the main Celery task that sends prescription refill data to Precision pharmacy
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — `process_shopify_order_for_treatment_refill()` (line 2089) — orchestrates the refill flow triggered from Shopify order webhook
- `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` — `_reprocess_order()` (line 160) — script for reprocessing subscription refill orders

## Search 3: Error handling and retry logic
Query: `search("pharmacy error handling retry")`

Found:
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` — `retry_warning_prescription_fill()` (line 201) — PrecisionAPIClient method that retries a WARNING-status fill
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` — `retry_failed_prescription_fills()` (line 306) — Celery task with full safeguards: only retries fills modified >1 hour ago, less than 7 days old, limited to 10 per run; escalates to FAILED after 3 days

## Search 4: WheelAPIClient prescription send
Query: `search("WheelAPIClient prescription send")`

Found:
- `/Users/albertgwo/Work/evvy/backend/consults/wheel/wheel.py` — `get_consult_prescription_details()` (line 327) — fetches finalized prescription details from Wheel
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` — `_send_prescription_fill_to_precision()` (line 178) — PrecisionAPIClient method that sends individual prescriptions and OTC treatments then calls `fill_prescription()`
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` — `send_prescription_to_precision()` (line 58) — Celery task for new consults (not refills)

## Search 5: Read precision.py in full
Read `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` (full file)

Key findings:
- `PrecisionAPIClient` class — the main client for all Precision Pharmacy API calls
- `_make_request()` wraps `utils.requests.make_request` with `account-id` and `secret` authentication headers
- `_handle_precision_error_response()` — handles non-HTTP errors where Precision returns `{"success": false, "errorCode": "...", "message": "..."}` format; ignores `DUPLICATE_ID` errors selectively; raises `requests.HTTPError` otherwise
- `create_patient()` — creates a patient record; silently logs and re-raises on exception; ignores DUPLICATE_ID
- `create_prescription()` — sends individual Rx to Precision; ignores DUPLICATE_ID (for refills)
- `fill_prescription()` — creates the fill order (refill) at `/refills/create` endpoint; on success, updates `PrescriptionFill.status = CREATED` and `sent_to_pharmacy_at`
- `create_and_fill_prescription_from_consult()` — full pipeline: creates DB objects, sends to Precision, catches any exception and sets status = WARNING

## Search 6: Read shipping/precision/tasks.py in full
Read `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (full file)

Key findings:
- `send_prescription_to_precision()` — Celery task for initial consult prescription send; catches create_patient exception but continues; does NOT retry automatically
- `send_create_prescription_request_to_precision()` — individual Rx Celery task; on exception, sets fill status to WARNING and re-raises
- `send_create_otc_treatment_request_to_precision()` — individual OTC Celery task; same WARNING status pattern on failure
- `send_fill_request_to_precision()` — Celery task for the refill order; uses `OrderEventLogger` for NewRelic monitoring (log_fulfillment_sent, log_fulfillment_completed, log_fulfillment_failed with `OrderErrorCategory.PROVIDER_API`); sets fill to WARNING on failure
- `retry_failed_prescription_fills()` — Celery task with safeguards:
  - Only retries fills with `status=WARNING`, modified >1 hour ago, <7 days old
  - Limits to 10 fills per run
  - If fill has been failing >3 days, escalates to `PRESCRIPTION_FILL_STATUS_FAILED` and creates a `ConsultTask` with `TASK_TYPE_PRESCRIPTION_FILL_FAILURE`
- `send_missing_prescriptions_to_precision()` — healing task: finds consults completed in last 2 days but not sent to pharmacy, resubmits
- `send_notification_for_stuck_prescriptions()` — sends admin email for refill fills stuck in CREATED status >3 business days
- `process_precision_pharmacy_webhook()` — handles webhook callbacks: received (no-op), shipped, delivered, warning (no-op), unknown (error logged)

## Search 7: Read ecomm/tasks.py refill section
Read `send_prescription_refill_request()` (lines 157–267) in `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`

Key findings:
- Orchestration task that coordinates the full refill sequence
- Handles order cancellations by calling `send_cancel_fill_request_to_precision()`; creates `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` on cancel failure
- Validates state restrictions (Rx-restricted states) — logs error and creates ConsultTask on invalid state
- Checks prescription refills remaining — raises exception if no refills available (non-manual-invoice orders)
- Calls tasks sequentially (not async): `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision` per Rx, `send_create_otc_treatment_request_to_precision` per OTC, then `send_fill_request_to_precision`

## Search 8: Read ecomm/monitoring/events.py and enums.py
Read `OrderEventLogger` class and `OrderErrorCategory` enum.

Key findings:
- `OrderEventLogger` logs to NewRelic via `BaseEventLogger`; carries `correlation_id`
- Methods: `log_fulfillment_sent`, `log_fulfillment_completed`, `log_fulfillment_failed`, `log_processing_error`
- `OrderErrorCategory` values: VALIDATION, PROVIDER_API, NETWORK, PAYMENT, SHIPPING, SYSTEM, UNKNOWN
- `FulfillmentProvider` values: WHEEL, PRECISION, BERLIN, SHOPIFY

## Search 9: utils/requests.py — the shared HTTP utility
Read `/Users/albertgwo/Work/evvy/backend/utils/requests.py` (full file)

Key findings:
- `make_request()` is the shared HTTP utility used by both PrecisionAPIClient and WheelAPIClient
- Default timeout: 10 seconds
- On non-2xx responses: logs HTTP status, records NewRelic custom event `HTTPRequestError` with full context (status, method, url, response_headers, response_json/text)
- Formats Wheel-style errors (errors array with dataPath/message) into human-readable strings
- Raises `HTTPRequestError` (custom subclass of `requests.HTTPError`) with enriched error details

## Search 10: Celery beat schedule
Read `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` (full file)

Key scheduled tasks related to pharmacy:
- `heal-precision-pharmacy`: `send_missing_prescriptions_to_precision` — runs 1:15AM and 7:15PM daily
- `report-stuck-prescriptions`: `send_notification_for_stuck_prescriptions` — runs 10:00AM daily
- `retry-failed-prescription-fills`: `retry_failed_prescription_fills` — runs 2:30AM, 10:30AM, 6:30PM daily (3x/day)
- `reprocess-subscription-refill-orders`: `reprocess_subscription_refill_orders_daily` — runs 4:00AM daily

## Search 11: WheelAPIClient retry decorator
Read `wheel.py` lines 898–903 and searched for `@retry`

Found: WheelAPIClient's `_make_request()` at line 898 has `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=4000)` — 3 attempts with exponential backoff starting at 4 seconds. PrecisionAPIClient does NOT have this automatic retry at the HTTP level.

## Search 12: handle_consult_creation_exception
Read `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils.py` lines 453–461

Found: sets `consult.status = Consult.STATUS_ERROR` and sends admin email via `send_consult_status_error_email()`.

---

## Final Answer

### Where the Pharmacy API Is Called

There are two pharmacy backends:

**1. Precision Compounding Pharmacy (primary pharmacy for Rx fills)**

The primary API client is `PrecisionAPIClient` in `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`. All calls go through `_make_request()` which calls the shared `utils.requests.make_request()` with authentication headers (`account-id`, `secret`). The Precision API base URL is `{PRECISION_API_URL}/v2`.

Entry points where Precision is called:
- `create_patient()` — `POST /v2/patients/create`
- `amend_patient()` — `POST /v2/patients/update`
- `create_prescription()` — `POST /v2/prescriptions/create`
- `create_otc_treatment()` — `POST /v2/prescriptions/create`
- `fill_prescription()` — `POST /v2/refills/create` (the fill/refill order)
- `cancel_fill()` — `POST /v2/refills/cancel`

For refill orders specifically, the flow is triggered when a Shopify refill order webhook arrives:
1. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_treatment_refill()` (line 2089) — parses the order, creates prescription fill DB records, then calls:
2. `send_prescription_refill_request.delay(order.id, prescription_fill.id)` (line 2198)
3. `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, `send_prescription_refill_request()` (line 157) — calls in sequence:
   - `send_create_patient_request_to_precision()` (from `shipping.precision.tasks`)
   - `send_create_prescription_request_to_precision()` per prescription
   - `send_create_otc_treatment_request_to_precision()` per OTC treatment
   - `send_fill_request_to_precision(prescription_fill.id, order_shipping_address=shipping_address)`

**2. Wheel (telemedicine consult creation, pharmacy search)**

`WheelAPIClient` in `/Users/albertgwo/Work/evvy/backend/consults/wheel/wheel.py`:
- `search_pharmacies()` (line 867) — `GET /v1/pharmacies?...` — used when users search for local pickup pharmacies
- `get_consult_prescription_details()` (line 327) — fetches finalized prescription from Wheel after provider completes consult

### How Errors Are Handled

**At the HTTP layer (`/Users/albertgwo/Work/evvy/backend/utils/requests.py`):**
- `make_request()` (line 41) has a 10-second default timeout
- Non-2xx responses trigger: (a) logging at ERROR level, (b) NewRelic `HTTPRequestError` custom event with `status_code`, `method`, `url`, `response_headers`, and parsed JSON/text body
- Raises `HTTPRequestError` (subclass of `requests.HTTPError`) with enriched details

**At the Precision API response layer (`_handle_precision_error_response()`, line 529 in `precision.py`):**
- Precision sometimes returns HTTP 200 with `{"success": false, "errorCode": "...", "message": "..."}` — this method catches those
- `DUPLICATE_ID` errors are selectively ignored (important for refills where prescriptions may already exist)
- Other errors are logged and re-raised as `requests.HTTPError`

**At the Celery task layer:**

In `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`:
- `send_create_prescription_request_to_precision()` (line 129): On exception, sets `PrescriptionFill.status = WARNING`, clears `sent_to_pharmacy_at`, and re-raises
- `send_create_otc_treatment_request_to_precision()` (line 157): Same WARNING pattern
- `send_fill_request_to_precision()` (line 191): On exception, calls `order_logger.log_fulfillment_failed(order, FulfillmentProvider.PRECISION, str(e), OrderErrorCategory.PROVIDER_API, ...)` (NewRelic), sets fill to WARNING, re-raises
- `send_prescription_to_precision()` (line 58): For initial consults — catches `create_patient` exception but logs and continues (swallows it); no automatic retry

In `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, `send_prescription_refill_request()` (line 157):
- Cancelled order with cancel failure → logs error, creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)`
- Invalid shipping state → logs error, creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)`, returns (no retry)
- No refills remaining → logs error, creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)`, raises exception

In `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`, `create_and_fill_prescription_from_consult()` (line 119):
- On `_send_prescription_fill_to_precision()` failure: sets fill status to WARNING and `sent_to_pharmacy_at = None`, logs error, re-raises

**For Wheel API:**
In `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils.py`, `handle_consult_creation_exception()` (line 453):
- Sets `consult.status = STATUS_ERROR`, saves, and sends admin email via `send_consult_status_error_email()`

### Retry and Monitoring Logic

**Automatic HTTP-level retries (Wheel only):**
- `WheelAPIClient._make_request()` (line 898, `wheel.py`): `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=4000)` — 3 attempts with exponential backoff starting at 4 seconds using the `retrying` library
- `PrecisionAPIClient._make_request()`: NO automatic HTTP-level retries

**Celery scheduled retry jobs:**

1. `retry_failed_prescription_fills()` in `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (line 306), scheduled 3x/day (2:30AM, 10:30AM, 6:30PM):
   - Fetches fills with `status=WARNING`, modified >1 hour ago, <7 days old
   - Processes up to 10 fills per run
   - Calls `client.retry_warning_prescription_fill(fill)` which re-runs `_send_prescription_fill_to_precision()`
   - Escalation: if fill has been failing >3 days, sets `status = PRESCRIPTION_FILL_STATUS_FAILED` and creates `ConsultTask(TASK_TYPE_PRESCRIPTION_FILL_FAILURE)` to flag for manual review

2. `send_missing_prescriptions_to_precision()` (line 282), scheduled daily at 1:15AM and 7:15PM:
   - Healing job for consults completed in last 2 days but `sent_to_pharmacy_at` is null
   - Re-submits via `send_prescription_to_precision.delay(consult.uid)`

3. `send_notification_for_stuck_prescriptions()` (line 372), scheduled daily at 10:00AM:
   - Finds PrescriptionFills in CREATED status for >3 business days
   - Sends admin email to `CONSULT_UPDATES_EMAIL` listing stuck refill fills

**NewRelic monitoring** via `OrderEventLogger` (`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`):
- `log_fulfillment_sent()` — emits `order_fulfillment_sent` event when fill request is dispatched
- `log_fulfillment_completed()` — emits `order_fulfillment_completed` on success
- `log_fulfillment_failed()` — emits `order_fulfillment_failed` with `error_category=PROVIDER_API` and truncated error details (500 chars)
- `newrelic.agent.add_custom_attribute("fulfillment_provider", "precision")` — tagged on fill tasks for filtering

The shared `make_request()` also records a `HTTPRequestError` NewRelic custom event containing `status_code`, `method`, `url`, `response_headers`, and `response_json`/`response_text` for every non-2xx response.

### Summary of Key Files

| File | Role |
|------|------|
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` | `PrecisionAPIClient` — all Precision HTTP calls, error response parsing |
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` | Celery tasks for Precision API (send, retry, heal, notify) |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` | `send_prescription_refill_request()` — refill orchestration |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | `process_shopify_order_for_treatment_refill()` — entry from Shopify webhook |
| `/Users/albertgwo/Work/evvy/backend/consults/wheel/wheel.py` | `WheelAPIClient` — Wheel telemedicine API (pharmacy search, consult Rx) |
| `/Users/albertgwo/Work/evvy/backend/utils/requests.py` | `make_request()` — shared HTTP client with NewRelic error recording |
| `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` | `OrderEventLogger` — NewRelic structured event logging |
| `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/enums.py` | `OrderErrorCategory`, `FulfillmentProvider`, `OrderEventType` enums |
| `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` | Celery beat schedules for heal/retry/alert tasks |
