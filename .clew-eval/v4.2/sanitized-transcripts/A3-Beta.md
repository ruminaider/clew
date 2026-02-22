# A3: Pharmacy API Error Handling and Retry Logic

## Summary

The pharmacy integration is with **Precision Pharmacy** (not Wheel, which is a separate telehealth provider used for consultations). The primary API client is `PrecisionAPIClient` in `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`. All API calls flow through a shared `make_request` utility at `/Users/albertgwo/Work/evvy/backend/utils/requests.py`. Error handling combines HTTP-level checks, application-level JSON success/errorCode inspection, and a `PrescriptionFill.status` state machine (`warning` → retry → `failed`). Monitoring is via NewRelic APM custom events plus email alerts.

---

## 1. Where We Call the Pharmacy API

### `PrecisionAPIClient` (`/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`)

This class owns all direct HTTP communication with the Precision Pharmacy v2 API. It authenticates via `account-id` and `secret` headers.

```python
class PrecisionAPIClient:
    def __init__(self):
        self.secret_key = settings.PRECISION_SECRET_KEY
        self.api_version = API_VERISON_V2
        self.base_url = settings.PRECISION_API_URL + f"/{self.api_version}"
        self.account_id = settings.PRECISION_ACCOUNT_ID
```

Five public API-calling methods:

| Method | Endpoint | Purpose |
|---|---|---|
| `create_patient()` | `POST /v2/patients/create` | Register a patient in Precision |
| `amend_patient()` | `POST /v2/patients/update` | Update patient data |
| `create_prescription()` | `POST /v2/prescriptions/create` | Send an Rx to the pharmacy |
| `create_otc_treatment()` | `POST /v2/prescriptions/create` | Send an OTC item to the pharmacy |
| `fill_prescription()` | `POST /v2/refills/create` | Create a fill/dispense order |
| `cancel_fill()` | `POST /v2/refills/cancel` | Cancel a fill order |

All six delegate to `_make_request()`:

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

### `make_request` utility (`/Users/albertgwo/Work/evvy/backend/utils/requests.py`)

The shared HTTP wrapper used across the entire backend. It adds timing logs, NewRelic custom events on HTTP errors, and enriches `requests.HTTPError` with response body details:

```python
DEFAULT_TIMEOUT = 10  # 10 second timeout on all calls

def make_request(method, url, json=None, data=None, headers=None, timeout=DEFAULT_TIMEOUT):
    start_time = time.time()
    response = requests.request(method, url, headers=headers, data=data, json=json, timeout=timeout)
    # ...
    if not response.ok:
        error_context = {
            "status_code": response.status_code, "method": method, "url": url, ...
        }
        newrelic.agent.record_custom_event("HTTPRequestError", error_context)
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise HTTPRequestError(e, error_details) from e
    return response
```

### Entry Points for Refill Orders

The top-level Celery task for refill orders is in `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`:

```python
@shared_task
def send_prescription_refill_request(order_id, prescription_fill_id):
    """
    Assumptions:
    - Order has an associated prescription fill ID
    - Prescriptions have been sent to the pharmacy
    - If there are no prescriptions, then it is an otc-only order
    """
```

This task orchestrates the full refill sequence by calling the Precision-specific tasks directly (not `.delay()`):
1. `send_create_patient_request_to_precision(...)` — creates/confirms patient record
2. For each Rx: `send_create_prescription_request_to_precision(...)` — registers each prescription
3. For each OTC: `send_create_otc_treatment_request_to_precision(...)` — registers each OTC item
4. `send_fill_request_to_precision(...)` — creates the actual dispense/fill order

---

## 2. Error Handling

### Layer 1: HTTP-level errors (`make_request`)

Any non-2xx HTTP response raises `HTTPRequestError` (a subclass of `requests.HTTPError`) with the response body embedded. The error is also recorded as a NewRelic custom event `"HTTPRequestError"`.

### Layer 2: Application-level JSON error codes (`_handle_precision_error_response`)

The Precision API returns `{"success": true/false, "errorCode": "...", "message": "..."}` for application errors even on HTTP 200. Every public method calls this handler:

```python
def _handle_precision_error_response(self, resp, log_data, ignore_errors=None):
    resp_json = resp.json()
    if resp_json.get("success", False):
        return  # ok

    error_code = resp_json.get("errorCode", "")
    message = resp_json.get("message", "")
    if error_code in ignore_errors:
        return  # tolerated error

    error_msg = "Error creating prescription in precision for data %s: %s - %s" % (
        str(log_data), error_code, message
    )
    logger.error(error_msg)
    raise requests.HTTPError(error_msg, response=resp)
```

`DUPLICATE_ID` errors are explicitly ignored in `create_patient`, `create_prescription`, `create_otc_treatment`, and `fill_prescription` — this is intentional because refills may re-register previously created records.

### Layer 3: Status machine transitions on failure

Every Celery task that calls Precision sets `PrescriptionFill.status = WARNING` and clears `sent_to_pharmacy_at` when it catches an exception:

From `send_fill_request_to_precision` (lines 228–248 in `tasks.py`):
```python
except Exception as e:
    logger.exception(f"Error sending fill request {fill_uid} to Precision: {str(e)}")

    # Log fulfillment failure to NewRelic
    if fill.order:
        order_logger.log_fulfillment_failed(
            fill.order,
            FulfillmentProvider.PRECISION,
            str(e),
            OrderErrorCategory.PROVIDER_API,
            additional_attributes={
                "prescription_fill_id": fill_uid,
                "error_type": type(e).__name__,
            },
        )

    with transaction.atomic():
        fill.refresh_from_db()
        fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING
        fill.sent_to_pharmacy_at = None
        fill.save()
    raise
```

The same `WARNING` status pattern is applied in:
- `send_create_prescription_request_to_precision` (lines 147–152 in `tasks.py`)
- `send_create_otc_treatment_request_to_precision` (lines 181–185 in `tasks.py`)
- `PrecisionAPIClient.create_and_fill_prescription_from_consult` (lines 168–176 in `precision.py`)

### `PrescriptionFill` status lifecycle

Defined in `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 721–738):

```
draft → created → shipped → delivered
                ↓ (on API failure)
              warning → (retry) → created
                      ↘ (after 3 days) → failed
```

The `can_cancel` property (line 823) only allows cancellation from `created` status with a non-null `sent_to_pharmacy_at`, ensuring failed/warning fills aren't sent a cancel call.

### `ConsultTask` records for human review

On certain failure paths, a `ConsultTask` record is created for manual resolution:
- Cancel failure in `send_prescription_refill_request`: creates `TASK_TYPE_TREATMENT_REFILL_FAILURE`
- Invalid state shipping address: creates `TASK_TYPE_TREATMENT_REFILL_FAILURE`
- No refills remaining: creates `TASK_TYPE_TREATMENT_REFILL_FAILURE`
- After 3+ days in WARNING: creates `TASK_TYPE_PRESCRIPTION_FILL_FAILURE` (in `retry_failed_prescription_fills`)

---

## 3. Retry and Monitoring Logic

### Automated retry: `retry_failed_prescription_fills`

File: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`, lines 306–368.

Scheduled via Celery Beat (in `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py`):
```python
"retry-failed-prescription-fills": {
    "task": "shipping.precision.tasks.retry_failed_prescription_fills",
    "schedule": crontab(hour=[2, 10, 18], minute=30),  # 3x/day: 2:30AM, 10:30AM, 6:30PM
},
```

Safeguards built into the task:
1. **Cooling-off period**: Only retries fills modified > 1 hour ago (`modify_date__lt=one_hour_ago`)
2. **Age limit**: Only retries fills < 7 days old (`create_date__gt=seven_days_ago`)
3. **Batch cap**: Processes at most 10 fills per run (`.order_by("modify_date")[:10]`)
4. **Escalation to FAILED**: If a fill has been in WARNING > 3 days, it is set to `FAILED` status and a `ConsultTask` is created for human review

```python
for fill in failed_fills:
    if fill.modify_date < timezone.now() - timedelta(days=3):
        fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_FAILED
        fill.save()
        ConsultTask.objects.get_or_create(
            consult=fill.consult,
            task_type=ConsultTask.TASK_TYPE_PRESCRIPTION_FILL_FAILURE,
            defaults={"task_data": {"failure_reason": "Prescription fill failed after 3 days..."}}
        )
        continue
    client.retry_warning_prescription_fill(fill)
```

The actual retry is delegated to `PrecisionAPIClient.retry_warning_prescription_fill()` (lines 201–216 in `precision.py`), which calls `_send_prescription_fill_to_precision()` and updates status back to `CREATED` on success.

### Healing task: `send_missing_prescriptions_to_precision`

File: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`, lines 282–302.

Scheduled:
```python
"heal-precision-pharmacy": {
    "task": "shipping.precision.tasks.send_missing_prescriptions_to_precision",
    "schedule": crontab(hour=[1, 19], minute=15),  # 2x/day: 1:15AM, 7:15PM
},
```

Finds consults that were completed in the last 2 days with `sent_to_pharmacy_at__isnull=True` and resubmits them to Precision. Acts as a safety net against missed webhook/task failures at the initial prescription send stage.

### Stuck prescription notifications: `send_notification_for_stuck_prescriptions`

File: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`, lines 372–406.

Scheduled:
```python
"report-stuck-prescriptions": {
    "task": "shipping.precision.tasks.send_notification_for_stuck_prescriptions",
    "schedule": crontab(hour=10, minute=0),  # daily at 10:00AM
},
```

Sends admin email to `settings.CONSULT_UPDATES_EMAIL` listing refill `PrescriptionFill` records that have been in `CREATED` status for more than 3 business days without transitioning to `SHIPPED`.

### NewRelic monitoring (`OrderEventLogger`)

File: `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`.

The `send_fill_request_to_precision` task uses `create_order_logger()` to instrument the fill lifecycle with NewRelic custom events:

- `log_fulfillment_sent()` → emits `order_fulfillment_sent` event with order/provider context
- `log_fulfillment_completed()` → emits `order_fulfillment_completed` on success
- `log_fulfillment_failed()` → emits `order_fulfillment_failed` with `error_category=PROVIDER_API` and truncated `error_details`

NewRelic attributes added per fill attempt:
```python
newrelic.agent.add_custom_attribute("prescription_fill_id", fill_uid)
newrelic.agent.add_custom_attribute("fulfillment_provider", "precision")
newrelic.agent.add_custom_attribute("order_id", fill.order.id)
newrelic.agent.add_custom_attribute("order_number", fill.order.order_number)
```

Additionally, `make_request` records `HTTPRequestError` custom events in NewRelic for every non-2xx HTTP response, regardless of which API is being called.

---

## Key File Index

| File | Role |
|---|---|
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` | `PrecisionAPIClient` — all API calls to Precision pharmacy |
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` | Celery tasks: send prescription, send fill, retry, healing, notifications |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 156–267) | Top-level `send_prescription_refill_request` Celery task for refill orders |
| `/Users/albertgwo/Work/evvy/backend/utils/requests.py` | `make_request` utility: timeout, NewRelic HTTPRequestError events |
| `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 721–828) | `PrescriptionFill` model with status constants (`warning`, `failed`, etc.) |
| `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` | `OrderEventLogger` — NewRelic fulfillment event logging |
| `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/enums.py` | `FulfillmentProvider`, `OrderErrorCategory`, `OrderEventType` enums |
| `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` | Celery Beat schedules for all retry/healing/monitoring tasks |
