# A3-grep Raw Transcript

**Agent ID:** a7adaf42578393b02
**Tool:** grep (Grep, Glob, Read)
**Test:** A3 — Pharmacy API errors, call sites, error handling, retry logic
**Tool calls:** 29
**Tokens:** 87,719

## Final Answer

## Pharmacy API Integration in the Evvy Codebase

The pharmacy API used throughout the codebase is **Precision Pharmacy's v2 REST API**. All integration code lives under `/Users/albertgwo/Work/evvy/backend/shipping/precision/`.

---

### 1. Where the Pharmacy API Is Called

#### Primary Client: `PrecisionAPIClient`
**File:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`

This class is the sole entry point for all outbound calls to Precision. It uses the shared `make_request` utility (authenticated via `account-id` and `secret` headers). It exposes these API methods:

| Method | Endpoint | Purpose |
|---|---|---|
| `create_patient()` | `POST /v2/patients/create` | Register a patient in Precision |
| `amend_patient()` | `POST /v2/patients/update` | Update a patient's record |
| `create_prescription()` | `POST /v2/prescriptions/create` | Create a prescription in Precision |
| `create_otc_treatment()` | `POST /v2/prescriptions/create` | Create an OTC treatment (same endpoint) |
| `fill_prescription()` | `POST /v2/refills/create` | Submit a fill/refill order |
| `cancel_fill()` | `POST /v2/refills/cancel` | Cancel a fill order |

#### All Call Sites (Celery Tasks)
**File:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`

- `send_prescription_to_precision(consult_uid)` — creates patient + all prescriptions + fill
- `send_create_patient_request_to_precision(prescription_fill_id, ...)`
- `send_create_prescription_request_to_precision(prescription_uid, ...)`
- `send_create_otc_treatment_request_to_precision(otc_treatment_uid, ...)`
- `send_fill_request_to_precision(fill_uid, ...)`
- `send_cancel_fill_request_to_precision(fill_uid)`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 232-266, 288-304)

Refill orders trigger the full precision flow directly: patient create -> prescription create -> OTC create -> fill request.

#### Inbound Webhook
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 302-312)

Precision calls back via `POST /webhooks/precision/`. Verifies HMAC-SHA256 signature, dispatches to `process_precision_pharmacy_webhook.delay(payload)`.

Webhook task handles: `received`, `shipped`, `delivered`, `warning`, and unknown types.

---

### 2. Error Handling

#### Application-level: `_handle_precision_error_response()`
**File:** `precision.py`, lines 529-553

Precision returns `200 OK` even for logical errors. This method checks `success` boolean, extracts `errorCode` and `message`. `DUPLICATE_ID` errors are ignored for safe retries. Other errors raise `requests.HTTPError`.

#### HTTP-level: `make_request()` / `HTTPRequestError`
**File:** `/Users/albertgwo/Work/evvy/backend/utils/requests.py`

All HTTP 4xx/5xx responses: log at ERROR, parse JSON body, record NewRelic `HTTPRequestError` event, raise `HTTPRequestError`.

#### Task-level error handling

- **`send_fill_request_to_precision`**: On exception, logs `order_fulfillment_failed` to NewRelic, sets `PrescriptionFill.status = "warning"`, clears `sent_to_pharmacy_at`, re-raises.
- **`send_create_prescription_request_to_precision`** and **`send_create_otc_treatment_request_to_precision`**: Similarly set fill to "warning" status on failure and re-raise.
- **`send_create_patient_request_to_precision`**: Logs exception but does NOT re-raise — patient creation failure is non-fatal.

#### PrescriptionFill status lifecycle
```
draft -> created -> shipped -> delivered
               \-> warning -> (retry) -> created OR failed (after 3 days)
                         \-> cancelled
```

---

### 3. Retry and Monitoring Logic

#### Automated Retry: `retry_failed_prescription_fills`
**File:** `shipping/precision/tasks.py`, lines 306-368

Scheduled at **2:30 AM, 10:30 AM, and 6:30 PM daily**:

Safeguards:
- Only retries fills modified more than 1 hour ago
- Only retries fills less than 7 days old
- Hard cap of 10 retries per run
- Fills failing for more than 3 days promoted from "warning" to "failed" with ConsultTask created for manual CX review
- Idempotent because `DUPLICATE_ID` errors are suppressed

#### Healing: `send_missing_prescriptions_to_precision`
Scheduled at **1:15 AM and 7:15 PM daily**. Finds consults with `sent_to_pharmacy_at=None` in last 2 days and re-submits.

#### Alerting: `send_notification_for_stuck_prescriptions`
Scheduled at **10:00 AM daily**. Finds refill PrescriptionFill records stuck in "created" status for more than 3 business days and emails `settings.CONSULT_UPDATES_EMAIL`.

#### NewRelic Monitoring
- `send_fill_request_to_precision`: custom attributes for `prescription_fill_id`, `fulfillment_provider`, `order_id`, `order_number`
- `order_logger.log_fulfillment_sent/completed/failed` events
- `make_request()` records `HTTPRequestError` events for all HTTP-level failures
- `BaseEventLogger` provides `@background_task_with_metrics` decorator
