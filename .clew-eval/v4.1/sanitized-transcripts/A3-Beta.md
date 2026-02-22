# A3 — Agent Beta

## Pharmacy API Integration: Precision Compounding Pharmacy

The codebase integrates exclusively with **Precision Compounding Pharmacy** (not Wheel, which is used for physician consults). All pharmacy API communication lives under `backend/shipping/precision/`.

---

### 1. Where the Pharmacy API Is Called

**Client:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`

This file contains the `PrecisionAPIClient` class, which is the sole HTTP gateway to the Precision pharmacy API (v2). It uses `account-id` and `secret` headers for authentication and calls these endpoints:

| Method | Endpoint | Client method |
|---|---|---|
| POST | `/v2/patients/create` | `create_patient()` |
| POST | `/v2/patients/update` | `amend_patient()` |
| POST | `/v2/prescriptions/create` | `create_prescription()`, `create_otc_treatment()`, `_create_fill_packaging_item_prescription()` |
| POST | `/v2/refills/create` | `fill_prescription()` |
| POST | `/v2/refills/cancel` | `cancel_fill()` |

All HTTP calls route through the shared utility `make_request()` at `/Users/albertgwo/Work/evvy/backend/utils/requests.py`:

```python
def make_request(method, url, json=None, data=None, headers=None, timeout=DEFAULT_TIMEOUT):
    # ...
    response = requests.request(method, url, headers=headers, data=data, json=json, timeout=timeout)
    # Records error details to NewRelic on non-2xx, raises HTTPRequestError
```

**Entry points for refill orders specifically:**

- **`send_prescription_refill_request(order_id, prescription_fill_id)`** — `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (line 157). This is the Celery task triggered when a refill order is paid. It calls `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_create_otc_treatment_request_to_precision`, then `send_fill_request_to_precision` in sequence.

- **`send_otc_treatment_fill_request(order_id, prescription_fill_id)`** — same file, for OTC-only refill orders.

**Tasks that make individual Precision API calls:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- `send_prescription_to_precision` — initial consult fulfillment
- `send_create_patient_request_to_precision`
- `send_create_prescription_request_to_precision`
- `send_create_otc_treatment_request_to_precision`
- `send_fill_request_to_precision`
- `send_cancel_fill_request_to_precision`

---

### 2. Error Handling

**Layer 1 — HTTP-level errors (`make_request` in `utils/requests.py`):**
- Any non-2xx HTTP response triggers a `newrelic.agent.record_custom_event("HTTPRequestError", ...)` event with status code, URL, method, response headers, and JSON body.
- The response body is parsed and a custom `HTTPRequestError` (subclass of `requests.HTTPError`) is raised with a human-readable `error_details` message.

**Layer 2 — Application-level errors (`_handle_precision_error_response` in `precision.py`, lines 529-553):**
- Precision's API returns `{"success": false, "errorCode": "...", "message": "..."}` even on HTTP 200.
- This method parses the JSON, checks `success`, and raises `requests.HTTPError` with the `errorCode` and `message` if the operation failed.
- Certain error codes are **ignored by design**: `DUPLICATE_ID` is ignored on `create_patient`, `create_prescription`, `create_otc_treatment`, and `fill_prescription` — this is intentional to support idempotent retries.

```python
def _handle_precision_error_response(self, resp, log_data, ignore_errors=None):
    resp_json = resp.json()
    if resp_json.get("success", False):
        return
    error_code = resp_json.get("errorCode", "")
    if error_code in ignore_errors:
        return
    logger.error(error_msg)
    raise requests.HTTPError(error_msg, response=resp)
```

**Layer 3 — Fill status update on exception (tasks):**
- When any `send_fill_request_to_precision` or `send_create_prescription_request_to_precision` task catches an exception, it sets the `PrescriptionFill.status` to `PRESCRIPTION_FILL_STATUS_WARNING` and clears `sent_to_pharmacy_at`, then re-raises. This marks the fill as failed and eligible for retry.

```python
# In send_fill_request_to_precision (tasks.py, line 228-248)
except Exception as e:
    order_logger.log_fulfillment_failed(fill.order, FulfillmentProvider.PRECISION, str(e), OrderErrorCategory.PROVIDER_API, ...)
    fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING
    fill.sent_to_pharmacy_at = None
    fill.save()
    raise
```

**Layer 4 — ConsultTask creation on hard failures:**
- In `send_prescription_refill_request`, errors like invalid shipping state or missing refills create a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE`, which is the signal for human review.

---

### 3. Retry Logic

**Active retry (scheduled Celery beat task):** `retry_failed_prescription_fills` — `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (line 306)

Scheduled in `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` at 2:30 AM, 10:30 AM, and 6:30 PM daily:

```python
"retry-failed-prescription-fills": {
    "task": "shipping.precision.tasks.retry_failed_prescription_fills",
    "schedule": crontab(hour=[2, 10, 18], minute=30),
},
```

Safeguards built into the retry task:
1. **Cooling-off period**: Only retries fills modified more than 1 hour ago (avoids thrashing).
2. **Expiration window**: Only retries fills created within the last 7 days.
3. **Rate limit**: Maximum 10 fills retried per run.
4. **Permanent failure escalation**: Fills that have been in WARNING status for more than 3 days are transitioned to `PRESCRIPTION_FILL_STATUS_FAILED` and a `ConsultTask` of type `TASK_TYPE_PRESCRIPTION_FILL_FAILURE` is created for human intervention.

The actual retry calls `PrecisionAPIClient.retry_warning_prescription_fill(fill)`, which calls `_send_prescription_fill_to_precision()` and if successful transitions the fill back to `PRESCRIPTION_FILL_STATUS_CREATED`.

**Healing job (missing prescriptions):** `send_missing_prescriptions_to_precision` — scheduled at 1:15 AM and 7:15 PM daily. It finds consults that completed in the last 2 days but were never sent to the pharmacy (`sent_to_pharmacy_at__isnull=True`) and re-queues them.

---

### 4. Monitoring

**NewRelic custom events:**
- `make_request` records `HTTPRequestError` custom events on any non-2xx HTTP response, with structured attributes: `status_code`, `method`, `url`, `response_headers`, `response_json`/`response_text`.
- `send_fill_request_to_precision` (tasks.py, lines 202-242) adds NewRelic transaction attributes: `prescription_fill_id`, `fulfillment_provider`, `order_id`, `order_number`.

**Order event logging via `OrderEventLogger`** (`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`):
- `log_fulfillment_sent` — logged when fill is dispatched to Precision.
- `log_fulfillment_completed` — logged on success.
- `log_fulfillment_failed` — logged on error with `error_category=OrderErrorCategory.PROVIDER_API`, `error_details` (truncated at 500 chars), and all order/user context. Events are recorded in NewRelic via the base logger.

**Stuck prescription email alert:** `send_notification_for_stuck_prescriptions` runs daily at 10:00 AM. It finds `CREATED` status prescription fills where `sent_to_pharmacy_at` is more than 3 business days ago and the fill is a refill, and emails `settings.CONSULT_UPDATES_EMAIL`.

**Application logger:** `evvy.precision_api` (in `precision.py`) and `evvy.precision.tasks` (in `tasks.py`) — every API call logs payload details at INFO level, errors at ERROR level with structured context.

**Webhook receiver:** `precision_pharmacy_webhook_view` at `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (line 302) — verifies HMAC signature using `settings.PRECISION_SECRET_KEY`, then dispatches `process_precision_pharmacy_webhook.delay(payload)` which handles `received`, `shipped`, `delivered`, and `warning` webhook types.
