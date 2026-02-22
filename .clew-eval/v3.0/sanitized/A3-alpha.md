# A3 Alpha Transcript: Pharmacy API Integration Investigation

## Task
"The pharmacy API is returning errors for some refill orders. Where in the codebase do we call the pharmacy API, how do we handle errors from it, and what retry/monitoring logic exists?"

## Investigation Process

### 1. Initial Search for Pharmacy API References
First, I searched for pharmacy API-related code across the codebase:
- Found 9 files matching "pharmacy.*api"
- Found 21 files matching "refill.*order"
- Found 144 files matching "pharmacy"

Key files identified:
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` - Main API client
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` - Helper utilities
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` - Celery tasks

### 2. Core Pharmacy API Integration

#### API Client: `PrecisionAPIClient`
Located in `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`

**Configuration:**
- Base URL: `settings.PRECISION_API_URL + "/v2"`
- Authentication: Uses `PRECISION_SECRET_KEY` and `PRECISION_ACCOUNT_ID`
- HTTP wrapper: Uses `make_request()` from `utils.requests`

**Main API Endpoints:**
1. **Create Patient** (`/v2/patients/create`)
   - Creates patient in Precision system
   - Uses external_id (user ID, order ID, or consult UID)
   - Ignores DUPLICATE_ID errors

2. **Create Prescription** (`/v2/prescriptions/create`)
   - Creates individual prescriptions
   - Uses precision_reference_id format: `{prescription_uid}_qty{quantity}`
   - Ignores DUPLICATE_ID errors

3. **Create OTC Treatment** (`/v2/prescriptions/create`)
   - Same endpoint as prescriptions
   - For non-prescription items (e.g., probiotics)
   - Also uses reference ID with quantity suffix

4. **Fill Prescription** (`/v2/refills/create`)
   - Creates fill order combining prescriptions + OTC treatments
   - Includes shipping address validation
   - Includes packaging items (bags, boxes, inserts)
   - Determines carrier/method (UPS vs USPS)

5. **Cancel Fill** (`/v2/refills/cancel`)
   - Cancels unfulfilled orders
   - Cannot cancel shipped/delivered orders

6. **Amend Patient** (`/v2/patients/update`)
   - Updates patient information

### 3. Error Handling Architecture

#### Primary Error Handler: `_handle_precision_error_response()`
Located in `precision.py` lines 529-553

**Logic:**
```python
def _handle_precision_error_response(self, resp, log_data, ignore_errors=None):
    ignore_errors = ignore_errors or []
    resp_json = resp.json()

    # If successful, return
    if resp_json.get("success", False):
        return

    # Check for ignored error codes
    error_code = resp_json.get("errorCode", "")
    message = resp_json.get("message", "")
    if error_code in ignore_errors:
        return

    # Log and raise error
    error_msg = "Error creating prescription in precision for data %s: %s - %s" % (
        str(log_data), error_code, message
    )
    logger.error(error_msg)
    raise requests.HTTPError(error_msg, response=resp)
```

**Ignored Errors:**
- `DUPLICATE_ID` - Ignored in create_patient, create_prescription, create_otc_treatment, and fill_prescription
- This allows idempotent retries

#### Status Tracking: PrescriptionFill Model
Located in `/Users/albertgwo/Work/evvy/backend/care/models.py`

**Status Flow:**
1. `draft` - User started checkout but hasn't purchased
2. `created` - Successfully sent to Precision
3. `shipped` - Precision has shipped (webhook received)
4. `delivered` - Package delivered (webhook received)
5. `warning` - API call failed, eligible for retry
6. `cancelled` - Order cancelled
7. `failed` - Permanent failure (after 3 days of retries)

**Error State Transitions:**
- On API error during fill creation: `status = "warning"`, `sent_to_pharmacy_at = None`
- On successful retry: `status = "created"`, `sent_to_pharmacy_at = current_time`
- After 3 days in warning: `status = "failed"`, creates ConsultTask

### 4. Retry Logic

#### Automatic Retry: `retry_failed_prescription_fills()`
Located in `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` lines 306-368

**Scheduled Execution:**
- Runs 3x daily at 2:30AM, 10:30AM, 6:30PM
- Configured in `settings_celery.py` line 197-200

**Safeguards:**
```python
one_hour_ago = timezone.now() - timedelta(hours=1)
seven_days_ago = timezone.now() - timedelta(days=7)

failed_fills = PrescriptionFill.objects.filter(
    status=PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING,
    modify_date__lt=one_hour_ago,  # Only retry fills that failed >1 hour ago
    create_date__gt=seven_days_ago,  # Only retry fills <7 days old
).order_by("modify_date")[:10]  # Limit to 10 retries per run
```

**Retry Logic:**
1. Finds fills in "warning" status
2. Waits 1 hour before first retry (avoid immediate retries)
3. Only retries fills less than 7 days old
4. Limits to 10 retries per execution
5. After 3 days: marks as "failed" and creates ConsultTask for manual intervention

#### Manual Retry: `retry_warning_prescription_fill()`
Located in `precision.py` lines 201-216

```python
def retry_warning_prescription_fill(self, prescription_fill: PrescriptionFill):
    if prescription_fill.status != PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING:
        raise ValueError(
            f"Cannot retry fill {prescription_fill.id} - status is {prescription_fill.status}"
        )

    try:
        self._send_prescription_fill_to_precision(prescription_fill)
        prescription_fill.refresh_from_db()
        prescription_fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_CREATED
        prescription_fill.save()
        logger.info(f"Successfully retried prescription fill {prescription_fill.id}")
    except Exception as e:
        logger.error(f"Retry failed for prescription fill {prescription_fill.id}: {str(e)}")
        raise
```

### 5. Monitoring & Alerting

#### NewRelic Monitoring
Located in `/Users/albertgwo/Work/evvy/backend/utils/requests.py` and `tasks.py`

**HTTP Request Monitoring:**
```python
# In make_request() - lines 73
error_context = {
    "status_code": response.status_code,
    "method": method,
    "url": url,
    "response_headers": dict(response.headers),
    "response_json": resp_json  # if JSON
}
newrelic.agent.record_custom_event("HTTPRequestError", error_context)
```

**Task-Level Monitoring:**
```python
# In send_fill_request_to_precision - lines 202-206
newrelic.agent.add_custom_attribute("prescription_fill_id", fill_uid)
newrelic.agent.add_custom_attribute("fulfillment_provider", "precision")
if fill.order:
    newrelic.agent.add_custom_attribute("order_id", fill.order.id)
    newrelic.agent.add_custom_attribute("order_number", fill.order.order_number)
```

#### Order Monitoring System
Uses `ecomm.monitoring.create_order_logger()` pattern:

```python
order_logger = create_order_logger()
order_logger.log_fulfillment_sent(fill.order, FulfillmentProvider.PRECISION)

# On success:
order_logger.log_fulfillment_completed(fill.order, FulfillmentProvider.PRECISION)

# On failure:
order_logger.log_fulfillment_failed(
    fill.order,
    FulfillmentProvider.PRECISION,
    str(e),
    OrderErrorCategory.PROVIDER_API,
    additional_attributes={"prescription_fill_id": fill_uid}
)
```

#### Email Alerts for Stuck Prescriptions
Task: `send_notification_for_stuck_prescriptions()`
- Scheduled daily at 10:00AM
- Finds fills in "created" status for >3 business days
- Only alerts for refills
- Sends email to `settings.CONSULT_UPDATES_EMAIL`

#### Healing Job for Missing Prescriptions
Task: `send_missing_prescriptions_to_precision()`
- Scheduled 2x daily at 1:15AM and 7:15PM
- Finds consults completed in last 2 days but not sent to pharmacy
- Validates prescriptions match recommendations
- Automatically resubmits

### 6. Webhook Processing

#### Webhook Endpoint
Located in `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` lines 302-312

```python
@csrf_exempt
def precision_pharmacy_webhook_view(request):
    data = request.body
    verified = _verify_hmac_webhook(
        data, request.headers.get("x-hmac-hash", ""), settings.PRECISION_SECRET_KEY
    )
    if not verified:
        return HttpResponse("invalid signature for precision webhook", status=403)

    payload = json.loads(data)
    process_precision_pharmacy_webhook.delay(payload)
    return HttpResponse(status=200)
```

#### Webhook Types
Handled in `tasks.py` lines 32-54:

1. **"received"** - No action, just logged
2. **"shipped"** - Updates status to "shipped", adds tracking number
3. **"delivered"** - Updates status to "delivered", tracks delivery time
4. **"warning"** - Logged but no specific action

#### Webhook Processing Logic
**Shipped Webhook** (`process_precision_shipped_webhook`):
- Cache-based deduplication (1 hour lock)
- Updates `shipping_tracking_number` and `shipped_at`
- Sends Braze events for customer notifications
- Marks Shopify order as fulfilled
- Handles replacement shipments

**Delivered Webhook** (`process_precision_delivered_webhook`):
- Updates `delivered_at` timestamp
- Updates treatment plan status
- Sends analytics events to Braze/Klaviyo

### 7. HTTP Request Wrapper

Located in `/Users/albertgwo/Work/evvy/backend/utils/requests.py`

**Custom Error Handling:**
```python
class HTTPRequestError(requests.HTTPError):
    """Enhanced error with response body details"""

def make_request(method, url, json=None, data=None, headers=None, timeout=10):
    response = requests.request(method, url, headers=headers, data=data, json=json, timeout=timeout)

    if not response.ok:
        # Extract error details from JSON or text
        error_details = _format_error_details(resp_json) if JSON else response.text[:500]

        # Log to NewRelic
        newrelic.agent.record_custom_event("HTTPRequestError", error_context)

    # Raise custom error with details
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise HTTPRequestError(e, error_details) from e
```

## Summary Answer

### Where We Call the Pharmacy API

The codebase integrates with **Precision Pharmacy API** (v2) via `PrecisionAPIClient` in `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py`.

**Primary API calls:**
1. **Create Patient** - Registers user in Precision system
2. **Create Prescription** - Sends individual prescription items
3. **Create OTC Treatment** - Sends non-prescription items (probiotics)
4. **Fill Prescription** - Creates fulfillment order with shipping details
5. **Cancel Fill** - Cancels unfulfilled orders
6. **Amend Patient** - Updates patient information

**Call sites:**
- Celery tasks in `shipping/precision/tasks.py`:
  - `send_prescription_to_precision()` - Main entry point for new consults
  - `send_fill_request_to_precision()` - Creates fill order
  - `send_create_prescription_request_to_precision()` - Individual prescription
  - `send_create_otc_treatment_request_to_precision()` - OTC items

### How We Handle Errors

**Three-tier error handling:**

1. **API-level** (`_handle_precision_error_response`):
   - Ignores `DUPLICATE_ID` errors for idempotency
   - Logs error code + message from API response
   - Raises `requests.HTTPError` for non-ignored errors

2. **Task-level** (Celery tasks):
   - Catches exceptions during API calls
   - Sets `PrescriptionFill.status = "warning"`
   - Clears `sent_to_pharmacy_at` timestamp
   - Logs to application logger and NewRelic
   - Re-raises exception for Celery retry mechanisms

3. **HTTP wrapper** (`make_request` in `utils/requests.py`):
   - Enhances errors with response body details
   - Records custom events in NewRelic
   - Provides detailed error context for debugging

**Status tracking:**
- Uses `PrescriptionFill.status` field with states: draft → created → shipped → delivered
- Error states: "warning" (retriable) → "failed" (permanent after 3 days)

### Retry and Monitoring Logic

**Automatic Retry System:**
- **Task:** `retry_failed_prescription_fills()`
- **Schedule:** 3x daily (2:30AM, 10:30AM, 6:30PM)
- **Safeguards:**
  - Only retries "warning" status fills
  - Waits 1 hour before first retry
  - Only retries fills < 7 days old
  - Limits to 10 retries per execution
  - After 3 days: marks as "failed" and creates admin task

**Monitoring:**
1. **NewRelic Integration:**
   - Custom events for HTTP errors with full context
   - Transaction attributes for prescription_fill_id, order_id
   - Request/response logging

2. **Order Monitoring System:**
   - `log_fulfillment_sent()` - Tracks when fill sent
   - `log_fulfillment_completed()` - Tracks success
   - `log_fulfillment_failed()` - Tracks failures with category

3. **Email Alerts:**
   - **Stuck Prescriptions:** Daily at 10AM, alerts on fills in "created" status >3 business days
   - **Missing Prescriptions:** Healing job 2x daily finds completed consults not sent to pharmacy

4. **Webhook Processing:**
   - Receives "shipped" and "delivered" events from Precision
   - HMAC signature verification
   - Cache-based deduplication (1 hour)
   - Updates status and triggers customer notifications

**Healing Jobs:**
- `send_missing_prescriptions_to_precision()` - 2x daily at 1:15AM, 7:15PM
- `heal_prescription_fill_orders()` - 3x daily at 2AM, 10AM, 6PM
- `heal_otc_treatment_only_orders()` - 3x daily at 2:15AM, 10:15AM, 6:15PM

## Key Insights for Debugging Refill Errors

1. **Check PrescriptionFill status:** Look for "warning" or "failed" status
2. **Review NewRelic:** Search for `HTTPRequestError` custom events with Precision URL
3. **Check retry attempts:** Fills in "warning" for >3 days become "failed"
4. **Verify address:** Most common issue is missing shipping address fields
5. **Check for duplicate IDs:** System ignores these, but may indicate race conditions
6. **Review Celery logs:** Tasks log detailed error context before re-raising
7. **Monitor email alerts:** Daily stuck prescription reports at 10AM
