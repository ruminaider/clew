# A3: Pharmacy API Calls, Error Handling, and Retry/Monitoring Logic

## Summary

The pharmacy used is **Precision Pharmacy**. All API calls are centralized in a `PrecisionAPIClient` class. The flow covers creating patients, prescriptions, OTC treatments, and fill (refill) orders. Errors cause fills to be marked with a `WARNING` status, and automated retry jobs attempt to recover them.

---

## 1. Where the Pharmacy API is Called

### Primary Client

**`/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`** — `PrecisionAPIClient`

This is the single class responsible for all Precision Pharmacy API interactions. It wraps API calls through `_make_request()`, which delegates to `utils.requests.make_request`.

**API Endpoints used (all under `settings.PRECISION_API_URL/v2/`):**

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/patients/create` | Create a patient record |
| POST | `/patients/update` | Amend patient info |
| POST | `/prescriptions/create` | Create a prescription or OTC treatment |
| POST | `/refills/create` | Submit a fill order (refill) |
| POST | `/refills/cancel` | Cancel a fill order |

**Key methods:**
- `create_patient(user, order, consult)` — creates/ensures patient exists in Precision
- `amend_patient(consult)` — updates patient data
- `create_prescription(prescription, fill_quantity, ...)` — registers a Rx in Precision
- `create_otc_treatment(otc_treatment, ...)` — registers OTC items in Precision
- `fill_prescription(prescription_fill, ...)` — submits the actual fill order (calls `/refills/create`)
- `cancel_fill(prescription_fill)` — cancels an in-progress fill
- `create_and_fill_prescription_from_consult(consult, pharmacy_patient_id)` — orchestrates the full initial-fill flow
- `_send_prescription_fill_to_precision(prescription_fill)` — internal method that calls create_prescription + create_otc_treatment + fill_prescription in sequence

**Authentication** (set in `_make_request`):
```python
headers = {
    "account-id": self.account_id,
    "secret": self.secret_key,
}
```
Config values come from `settings.PRECISION_SECRET_KEY`, `settings.PRECISION_API_URL`, `settings.PRECISION_ACCOUNT_ID`.

---

### HTTP Layer

**`/Users/albertgwo/Work/evvy/backend/utils/requests.py`** — `make_request()`

All HTTP calls pass through this function:
- Sets a `DEFAULT_TIMEOUT = 10` seconds
- On HTTP errors: logs the status code, URL, and response body
- Records a `HTTPRequestError` custom event to **New Relic** via `newrelic.agent.record_custom_event`
- Raises a custom `HTTPRequestError` (subclass of `requests.HTTPError`) with enriched error details

```python
def make_request(method, url, json=None, data=None, headers=None, timeout=DEFAULT_TIMEOUT):
    ...
    if not response.ok:
        logger.error(f"HTTP {response.status_code} error from {method} {url}")
        newrelic.agent.record_custom_event("HTTPRequestError", error_context)
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise HTTPRequestError(e, error_details) from e
```

---

## 2. Error Handling

### At the API Client Level

**`_handle_precision_error_response(resp, log_data, ignore_errors=None)`** in `precision.py`:

Precision returns `{"success": false, "errorCode": "...", "message": "..."}` even on 200 responses when there's a logical error. This method:
- Returns silently if `resp_json["success"]` is true
- Skips specific error codes listed in `ignore_errors` — most calls pass `["DUPLICATE_ID"]` to handle idempotent retries
- Raises `requests.HTTPError` for all other errors, logging the error code and message

```python
def _handle_precision_error_response(self, resp, log_data, ignore_errors=None):
    resp_json = resp.json()
    if resp_json.get("success", False):
        return
    error_code = resp_json.get("errorCode", "")
    if error_code in ignore_errors:
        return
    error_msg = "Error creating prescription in precision for data %s: %s - %s" % (...)
    logger.error(error_msg)
    raise requests.HTTPError(error_msg, response=resp)
```

### On Fill Failures — Status Transitions

When any step in sending a prescription fill to Precision fails, the `PrescriptionFill.status` is set to `PRESCRIPTION_FILL_STATUS_WARNING` ("warning") and `sent_to_pharmacy_at` is cleared.

This is done in multiple places:
- `create_and_fill_prescription_from_consult()` in `precision.py`
- `send_create_prescription_request_to_precision()` task in `tasks.py`
- `send_create_otc_treatment_request_to_precision()` task in `tasks.py`
- `send_fill_request_to_precision()` task in `tasks.py`

Example from `send_fill_request_to_precision`:
```python
except Exception as e:
    logger.exception(f"Error sending fill request {fill_uid} to Precision: {str(e)}")
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

**PrescriptionFill status values** (defined in `/Users/albertgwo/Work/evvy/backend/care/models.py`):
- `"created"` — successfully sent to Precision
- `"warning"` — failed; eligible for automatic retry
- `"failed"` — permanently failed after 3+ days of retries

### ConsultTask Error Records

When a refill fails (during `send_prescription_refill_request`), a `ConsultTask` is created with type `TASK_TYPE_TREATMENT_REFILL_FAILURE` so that a human can review the issue:

```python
ConsultTask.objects.create(
    task_type=ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE,
    task_data={"reason": error_message},
)
```

---

## 3. Retry Logic

### Automated Retry — `retry_failed_prescription_fills` (Celery Beat)

**`/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`** — `retry_failed_prescription_fills()`

This scheduled Celery task runs **3 times daily** (2:30 AM, 10:30 AM, 6:30 PM) per the schedule in `settings_celery.py`:

```python
"retry-failed-prescription-fills": {
    "task": "shipping.precision.tasks.retry_failed_prescription_fills",
    "schedule": crontab(hour=[2, 10, 18], minute=30),
},
```

**Retry safeguards:**
- Only retries fills with `status == "warning"`
- Only retries fills modified **more than 1 hour ago** (avoids immediate re-retry)
- Only retries fills **less than 7 days old** (avoids retrying very stale failures)
- Processes **at most 10 fills per run** to avoid overwhelming the system

**Escalation to permanent failure:**
- If a fill has been in WARNING state for **more than 3 days**, it's marked as `PRESCRIPTION_FILL_STATUS_FAILED`
- A `ConsultTask` with type `TASK_TYPE_PRESCRIPTION_FILL_FAILURE` is created for human review

```python
if fill.modify_date < timezone.now() - timedelta(days=3):
    fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_FAILED
    fill.save()
    ConsultTask.objects.get_or_create(
        consult=fill.consult,
        task_type=ConsultTask.TASK_TYPE_PRESCRIPTION_FILL_FAILURE,
        defaults={
            "task_data": {
                "prescription_fill_id": str(fill.id),
                "failure_reason": "Prescription fill failed after 3 days of retry attempts",
            }
        },
    )
```

**The actual retry logic** is in `retry_warning_prescription_fill()` in `precision.py`:
- Validates the fill is in WARNING status
- Calls `_send_prescription_fill_to_precision()` (same flow as original send)
- On success: sets status back to CREATED

### Healing Job — `send_missing_prescriptions_to_precision` (Celery Beat)

A separate healing job runs **twice daily** (1:15 AM and 7:15 PM) that looks for consults that completed in the last 2 days but were never sent to the pharmacy (`sent_to_pharmacy_at` is null):

```python
"heal-precision-pharmacy": {
    "task": "shipping.precision.tasks.send_missing_prescriptions_to_precision",
    "schedule": crontab(hour=[1, 19], minute=15),
},
```

It re-triggers `send_prescription_to_precision.delay(consult.uid)` for any missed consults.

### Webhook Deduplication Cache

**`/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py`** — `is_prescription_fill_webhook_already_handled()`

To prevent duplicate processing of Precision's shipped/delivered webhooks, Django's cache is used:
- Lock key: `prescription_fill_{event_type}_{reference_id}`
- TTL: 1 hour
- Replacement shipments use a separate key to allow reprocessing

---

## 4. Monitoring

### New Relic Integration

`send_fill_request_to_precision` adds New Relic custom transaction attributes:
```python
newrelic.agent.add_custom_attribute("prescription_fill_id", fill_uid)
newrelic.agent.add_custom_attribute("fulfillment_provider", "precision")
newrelic.agent.add_custom_attribute("order_id", fill.order.id)
newrelic.agent.add_custom_attribute("order_number", fill.order.order_number)
```

The `make_request()` utility also records `HTTPRequestError` custom events to New Relic with `status_code`, `method`, `url`, `response_headers`, and `response_json`.

### OrderEventLogger / `ecomm.monitoring`

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/`** — structured event logging system

The fill task uses `create_order_logger()` to log fulfillment lifecycle events to New Relic via `OrderEventLogger`:
- `log_fulfillment_sent(order, FulfillmentProvider.PRECISION)` — before API call
- `log_fulfillment_completed(order, FulfillmentProvider.PRECISION)` — on success
- `log_fulfillment_failed(order, FulfillmentProvider.PRECISION, str(e), OrderErrorCategory.PROVIDER_API)` — on failure

Events are emitted as New Relic custom events via `BaseEventLogger` (in `utils/monitoring/base.py`).

### Stuck Prescription Email Alerts

**`send_notification_for_stuck_prescriptions`** runs daily at 10 AM:
- Finds fills in CREATED status for more than 3 business days
- Filters for refill fills specifically
- Sends an admin email summary to `settings.CONSULT_UPDATES_EMAIL`

```python
"report-stuck-prescriptions": {
    "task": "shipping.precision.tasks.send_notification_for_stuck_prescriptions",
    "schedule": crontab(hour=10, minute=0),
},
```

### Logging

Three named loggers are used:
- `"evvy.precision_api"` — in `precision.py`
- `"evvy.precision.tasks"` — in `tasks.py`
- `"evvy.precision.utils"` — in `utils.py`

All major API call successes, failures, and retries are logged at INFO or ERROR level.

---

## 5. Webhook Inbound Handler

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`** — `precision_pharmacy_webhook_view`

Precision calls back to `/precision-pharmacy-webhook/` when orders are received, shipped, or delivered. The view:
1. Verifies the HMAC signature using `settings.PRECISION_SECRET_KEY`
2. Dispatches `process_precision_pharmacy_webhook.delay(payload)` as an async Celery task
3. Returns 200 immediately

`process_precision_pharmacy_webhook` in `tasks.py` then routes to:
- `process_precision_shipped_webhook(payload)` — updates fill status to SHIPPED, fires Braze analytics, updates Shopify fulfillment
- `process_precision_delivered_webhook(payload)` — updates fill status to DELIVERED, fires Braze analytics

---

## Key Files Reference

| File | Role |
|---|---|
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` | `PrecisionAPIClient` — all API calls |
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` | Celery tasks: send, retry, webhook processing, healing jobs |
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` | Payload builders, webhook processing logic |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` | `send_prescription_refill_request` — orchestrates refill order flow |
| `/Users/albertgwo/Work/evvy/backend/utils/requests.py` | HTTP wrapper with New Relic error recording |
| `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/` | Structured monitoring: OrderEventLogger, enums, pipeline |
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` | `precision_pharmacy_webhook_view` |
| `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` | Celery Beat schedule for all pharmacy jobs |
| `/Users/albertgwo/Work/evvy/backend/care/models.py` | `PrescriptionFill` status constants |
