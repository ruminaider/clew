# Pharmacy API Integration Investigation - Beta Transcript

**Task:** "The pharmacy API is returning errors for some refill orders. Where in the codebase do we call the pharmacy API, how do we handle errors from it, and what retry/monitoring logic exists?"

**Working directory:** /Users/albertgwo/Work/evvy

## Tool Calls and Reasoning

### Initial Search (Tool Calls 1-3)

Searched for pharmacy API-related code with three parallel queries:
1. search("pharmacy API call")
2. search("refill order pharmacy")
3. search("pharmacy error handling retry")

**Key findings:**
- Main refill task: `backend/ecomm/tasks.py::send_prescription_refill_request`
- Pharmacy API client: `backend/shipping/precision/precision.py::PrecisionAPIClient`
- Retry logic: `backend/shipping/precision/tasks.py::retry_failed_prescription_fills`
- Retry method: `backend/shipping/precision/precision.py::retry_warning_prescription_fill`

### Deep Dive into Core Files (Tool Calls 4-5)

Read the main refill task and API client:
- `backend/ecomm/tasks.py` (lines 157-267): Main refill orchestration
- `backend/shipping/precision/precision.py` (full file): API client implementation

**Key insights:**
- Precision Pharmacy is the pharmacy partner
- API version: v2
- Base URL: `settings.PRECISION_API_URL + /v2`
- Authentication: account-id header + secret key

### Error Handling Investigation (Tool Calls 6-7)

Searched for monitoring and read retry task details:
- `backend/shipping/precision/tasks.py` (lines 306-368): Retry task implementation
- Found monitoring integration with NewRelic

### Relationship Tracing (Tool Call 8)

Traced `send_prescription_refill_request` to understand call graph. Found it calls:
- `send_cancel_fill_request_to_precision`
- `send_create_patient_request_to_precision`
- `send_create_prescription_request_to_precision`
- `send_create_otc_treatment_request_to_precision`
- `send_fill_request_to_precision`

### Monitoring Infrastructure (Tool Calls 9-13)

Investigated monitoring setup:
- Searched for NewRelic monitoring integration
- Found `backend/shipping/precision/tasks.py::send_fill_request_to_precision` has comprehensive monitoring
- Located monitoring infrastructure in `backend/ecomm/monitoring/events.py`
- read(`backend/ecomm/monitoring/events.py`) for NewRelic integration

### Request Utility (Tool Call 14)

read(`backend/utils/requests.py`) to understand low-level error handling:
- Custom `HTTPRequestError` wrapper
- NewRelic event recording on HTTP errors
- 10 second default timeout

## Complete Answer

### Where We Call the Pharmacy API

The codebase integrates with **Precision Pharmacy** via API v2. The main entry points are:

#### 1. **Refill Orders** - `backend/ecomm/tasks.py::send_prescription_refill_request`
   - **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 157-267)
   - **Purpose**: Handles prescription refill orders from Shopify
   - **Flow**:
     1. Validates order and prescription fill exist
     2. Handles order cancellations (sends cancel request to Precision)
     3. Verifies shipping address for state restrictions
     4. Checks prescriptions have remaining refills
     5. Updates prescription fill status from DRAFT → CREATED
     6. Creates patient in Precision (if needed)
     7. Creates prescriptions in Precision
     8. Creates OTC treatments in Precision
     9. Sends fill request to Precision

#### 2. **API Client** - `backend/shipping/precision/precision.py::PrecisionAPIClient`
   - **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` (lines 39-562)
   - **Key Methods**:
     - `create_patient()` - Creates patient record (line 52)
     - `create_prescription()` - Creates prescription order (line 218)
     - `create_otc_treatment()` - Creates OTC treatment order (line 298)
     - `fill_prescription()` - Creates fill/refill order (line 403)
     - `cancel_fill()` - Cancels fill order (line 497)
   - **Base URL**: `{PRECISION_API_URL}/v2`
   - **Authentication**:
     - Header: `account-id: {PRECISION_ACCOUNT_ID}`
     - Header: `secret: {PRECISION_SECRET_KEY}`

#### 3. **Task Wrappers** - `backend/shipping/precision/tasks.py`
   - `send_prescription_to_precision()` - Initial prescription send (line 58)
   - `send_fill_request_to_precision()` - Fill request with monitoring (line 191)
   - `send_cancel_fill_request_to_precision()` - Cancel request (line 254)
   - `process_precision_pharmacy_webhook()` - Webhook handler (line 33)

### Error Handling

The error handling is multi-layered:

#### 1. **API Client Level** (`PrecisionAPIClient`)
   - **Method**: `_handle_precision_error_response()` (lines 529-553)
   - **Behavior**:
     - Checks `success` field in response JSON
     - Extracts `errorCode` and `message` from response
     - Allows ignoring specific error codes (e.g., "DUPLICATE_ID")
     - Raises `requests.HTTPError` with formatted error message
     - Logs all errors to `evvy.precision_api` logger

   **Example from `create_prescription()` (lines 278-286)**:
   ```python
   ignore_errors = ["DUPLICATE_ID"]
   self._handle_precision_error_response(
       resp,
       {"prescription_uid": str(prescription.uid)},
       ignore_errors=ignore_errors,
   )
   ```

#### 2. **HTTP Request Level** (`utils/requests.py`)
   - **File**: `/Users/albertgwo/Work/evvy/backend/utils/requests.py` (lines 41-80)
   - **Features**:
     - 10 second timeout on all requests
     - Custom `HTTPRequestError` exception with response details
     - NewRelic event recording: `HTTPRequestError` custom event with:
       - status_code
       - method
       - url
       - response headers
       - response JSON or text (first 500 chars)
     - Detailed error logging to `evvy.requests` logger

#### 3. **Task Level Error Handling**

   **`send_fill_request_to_precision()` (lines 191-250)**:
   - Wraps API call in try/except
   - On error:
     - Logs exception with `logger.exception()`
     - Logs fulfillment failure to NewRelic via `order_logger.log_fulfillment_failed()`
     - Updates `PrescriptionFill.status` to `WARNING`
     - Sets `sent_to_pharmacy_at` to `None`
     - Re-raises exception

   **`send_prescription_refill_request()` (lines 157-267)**:
   - Validates state restrictions and refills before API calls
   - Creates `ConsultTask` records on validation failures:
     - Task type: `TASK_TYPE_TREATMENT_REFILL_FAILURE`
     - Contains error reason for admin review
   - Cancellation errors (lines 178-188):
     - Logs error
     - Creates ConsultTask for manual intervention
     - Re-raises exception

### Retry Logic

#### 1. **Automatic Retry Task** - `retry_failed_prescription_fills()`
   - **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (lines 306-368)
   - **Trigger**: Celery scheduled task
   - **Filters**:
     - Status = `PRESCRIPTION_FILL_STATUS_WARNING`
     - Modified > 1 hour ago (avoids immediate retries)
     - Created < 7 days ago (avoids very old failures)
     - Limit: 10 fills per run
   - **Behavior**:
     - Checks if fill has been failing > 3 days
     - If yes: marks as `FAILED` and creates `ConsultTask` for admin
     - If no: calls `client.retry_warning_prescription_fill(fill)`
     - Tracks success/failure counts
   - **Safeguards**:
     - 1 hour cooldown between retries
     - 3 day timeout → permanent failure status
     - Rate limited to 10 retries per job run

#### 2. **Retry Method** - `retry_warning_prescription_fill()`
   - **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` (lines 201-216)
   - **Validation**: Only retries fills with `WARNING` status
   - **Process**:
     1. Calls `_send_prescription_fill_to_precision()`
     2. On success: updates status to `CREATED`
     3. On failure: logs error and re-raises exception
   - **Note**: Does NOT automatically update status on failure (handled by caller)

#### 3. **Manual Retry**
   - Admin can trigger retry via Django admin actions
   - Creates `ConsultTask` records for manual review

### Monitoring Logic

#### 1. **NewRelic Integration**

**Custom Attributes** (added in `send_fill_request_to_precision`):
- `prescription_fill_id`
- `fulfillment_provider` = "precision"
- `order_id`
- `order_number`

**Custom Events** (via `HTTPRequestError` in `utils/requests.py`):
- Event name: `HTTPRequestError`
- Attributes: status_code, method, url, response_headers, response_json/text

**Order Event Logging** (via `OrderEventLogger`):
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` (lines 20-150)
- **Events**:
  - `log_fulfillment_sent()` - When request sent to Precision
  - `log_fulfillment_completed()` - When request succeeds
  - `log_fulfillment_failed()` - When request fails
    - Includes `OrderErrorCategory.PROVIDER_API`
    - Includes error type and prescription_fill_id

**Attributes captured in order events**:
- order_id, order_number, order_type
- provider_id, shopify_order_id
- checkout_source, is_testing_order
- total_line_items_price
- user_id, user_uuid
- fulfillment provider
- error category and details
- processing time
- prescription_fill_id

#### 2. **Django Logging**

Multiple loggers used:
- `evvy.precision_api` - API client operations
- `evvy.precision.tasks` - Task-level operations
- `evvy.requests` - HTTP request/response details
- `evvy.ecomm.monitoring` - Order event logging

#### 3. **Admin Notifications**

**Stuck Prescriptions** - `send_notification_for_stuck_prescriptions()`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (line 372)
- **Trigger**: Scheduled task
- **Detection**: Fills in `CREATED` status for > 3 business days
- **Action**: Sends email to `settings.CONSULT_UPDATES_EMAIL`

**Failed Retries**:
- Creates `ConsultTask` with type `TASK_TYPE_PRESCRIPTION_FILL_FAILURE`
- Contains prescription_fill_id, failure_reason, consult_uid
- Admin views these in Django admin

#### 4. **Webhook Monitoring**

**Precision Webhooks** - `process_precision_pharmacy_webhook()`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (lines 33-54)
- **Types**:
  - `received` - Order received by pharmacy (logged only)
  - `shipped` - Order shipped (updates status, tracking number)
  - `delivered` - Order delivered (updates status)
  - `warning` - Pharmacy warning (logged only)
- **Processing**:
  - `process_precision_shipped_webhook()` - Updates PrescriptionFill status, sends Braze events
  - `process_precision_delivered_webhook()` - Updates PrescriptionFill status
  - Logs to `evvy.precision.tasks`

### Summary of API Call Points

1. **Initial consult prescriptions**: `send_prescription_to_precision()` → `create_and_fill_prescription_from_consult()`
2. **Refill orders**: `send_prescription_refill_request()` → `send_fill_request_to_precision()` → `fill_prescription()`
3. **Cancellations**: `send_cancel_fill_request_to_precision()` → `cancel_fill()`
4. **Retries**: `retry_failed_prescription_fills()` → `retry_warning_prescription_fill()`

### Key Configuration

Settings required:
- `PRECISION_API_URL` - Base URL for Precision API
- `PRECISION_ACCOUNT_ID` - Account identifier
- `PRECISION_SECRET_KEY` - API secret key
- `CONSULT_UPDATES_EMAIL` - Admin notification email

### Troubleshooting Current Issue

Based on this investigation, to debug current refill order errors:

1. **Check NewRelic**: Query for `HTTPRequestError` events with `url LIKE '%precision%'`
2. **Check Django Admin**: Look for `ConsultTask` records with type `TASK_TYPE_TREATMENT_REFILL_FAILURE`
3. **Check Logs**: Search `evvy.precision_api` logger for error messages
4. **Check Database**: Query `PrescriptionFill` with status = `WARNING` or `FAILED`
5. **Check Retry Status**: See if retry task is running and what it's reporting
6. **Check Order Events**: Query NewRelic for `OrderEvent` with `event_type=fulfillment_failed` and `provider=precision`

### Files Referenced

**Core API Integration:**
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/precision.py` - API client
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` - Celery tasks
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` - Webhook processors
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` - Refill orchestration

**Monitoring & Error Handling:**
- `/Users/albertgwo/Work/evvy/backend/utils/requests.py` - HTTP wrapper with error handling
- `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` - Order event logging
- `/Users/albertgwo/Work/evvy/backend/app/middleware/monitoring.py` - Middleware monitoring

**Data Models:**
- `/Users/albertgwo/Work/evvy/backend/care/models.py` - PrescriptionFill model
- `/Users/albertgwo/Work/evvy/backend/consults/models.py` - ConsultTask model

## Tool Usage Summary

- **Total tool calls**: 14
- **Search operations**: 5
- **Read operations**: 8
- **Trace operations**: 1

All key information was found within the tool budget, providing comprehensive understanding of the pharmacy API integration, error handling, retry logic, and monitoring infrastructure.
