# A1 Clew Investigation: Subscription Renewal → PrescriptionFill Creation

## Task
"A customer reported their subscription renewal didn't create a prescription fill. Investigate the code path from order webhook to PrescriptionFill creation and identify where failures can occur."

## Investigation Process

### Search 1: Find Entry Points
```bash
clew search "subscription renewal webhook"
clew search "PrescriptionFill creation"
clew search "order webhook shopify"
```

**Key findings:**
- `backend/subscriptions/service.py::handle_subscription_webhook` - handles subscription lifecycle webhooks
- `backend/ecomm/utils.py::_process_shopify_order_impl` - main order processing function
- `backend/ecomm/utils.py::process_shopify_order_for_treatment_refill` - specific handler for treatment refill orders
- `backend/care/models.py::PrescriptionFill` - the target model

### Search 2: Trace Order Processing Flow
```bash
clew trace "ecomm/utils.py::_process_shopify_order_impl" --direction outbound --depth 2
clew search "create PrescriptionFill from order"
```

**Key findings:**
- Found `process_shopify_order_for_treatment_refill` is the critical function
- Found routing logic at lines 660-693 in `_process_shopify_order_impl`
- Identified `send_prescription_refill_request` task in `backend/ecomm/tasks.py`

### Read 3: Understand Routing Logic
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 600-720

**Key findings:**
- Line 670: Orders with `ORDER_TYPE_PRESCRIPTION_TREATMENT` in line items route to treatment refill
- Lines 676-692: `ORDER_TYPE_UNGATED_RX` orders check if user has valid prescriptions via `can_refill_entire_order()`
  - If yes → route to `process_shopify_order_for_treatment_refill`
  - If no → route to consult/intake path

### Read 4: Analyze Treatment Refill Processing
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 2089-2201

**Critical flow identified:**
1. Parse order attributes for prescription_fill_id
2. Get or create PrescriptionFill
3. Resolve user from multiple sources (email, cart, consult)
4. Link order to PrescriptionFill
5. Get prescriptions (from IDs or user's evergreen prescriptions)
6. Validate prescriptions exist
7. Create PrescriptionFillPrescriptions records
8. Call `send_prescription_refill_request.delay()` async task

### Read 5: Examine Async Task
Read `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` lines 157-267

**Additional validation/failure points:**
- Line 173: If order is cancelled, try to cancel fill
- Lines 196-210: Check shipping address state restrictions
- Lines 212-223: Verify prescriptions have remaining refills (unless manual invoice)
- Line 226: Update prescription fill status to CREATED
- Lines 232-266: Send to Precision pharmacy API

### Search 6: Understand Subscription Integration
```bash
clew search "subscription charge success renewal"
```

Read `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` and webhook view

**Key finding:**
- ReCharge (subscription provider) creates orders directly in Shopify when subscriptions renew
- Those Shopify orders trigger standard order webhooks
- No special "charge/success" webhook creates orders - ReCharge does that externally

### Trace 7: Map Dependencies
```bash
clew trace "ecomm/utils.py::process_shopify_order_for_treatment_refill" --direction outbound --depth 1
```

Confirmed call chain to `create_prescription_fill_prescriptions` and `send_prescription_refill_request`

## Code Path Summary

### Complete Flow: Subscription Renewal → PrescriptionFill

1. **ReCharge Subscription Renewal**
   - ReCharge processes subscription charge
   - ReCharge creates order in Shopify (external to Evvy backend)
   - Shopify sends order webhook to Evvy

2. **Shopify Webhook Receipt**
   - File: `backend/api/v1/views/webhooks.py::shopify_webhook_view` (line 82)
   - Validates webhook signature
   - Calls `_process_shopify_order_impl()`

3. **Order Processing Entry**
   - File: `backend/ecomm/utils.py::_process_shopify_order_impl` (line 238)
   - Creates/updates Order record (line 336)
   - Processes line items to determine order type
   - Routes to appropriate handler based on order type

4. **Routing Decision** (lines 660-692)
   - **Path A:** If `ORDER_TYPE_PRESCRIPTION_TREATMENT` in line items → treatment refill
   - **Path B:** If `ORDER_TYPE_UNGATED_RX` AND `can_refill_entire_order()` returns True → treatment refill
   - **Path C:** If `ORDER_TYPE_UNGATED_RX` AND no valid prescriptions → consult/intake path
   - **Otherwise:** Other order type handlers

5. **Treatment Refill Processing**
   - File: `backend/ecomm/utils.py::process_shopify_order_for_treatment_refill` (line 2089)
   - Parse order attributes (line 2097)
   - Get/create PrescriptionFill (lines 2102-2108)
   - Resolve user from multiple sources (lines 2110-2138)
   - Link order to PrescriptionFill (lines 2140-2143)
   - Query prescriptions (lines 2151-2180)
   - Create PrescriptionFillPrescriptions records (line 2193)
   - Queue async task (line 2198)

6. **Async Pharmacy Submission**
   - File: `backend/ecomm/tasks.py::send_prescription_refill_request` (line 157)
   - Validate shipping address (lines 199-210)
   - Check prescription refills remaining (lines 212-223)
   - Update status to CREATED (line 226)
   - Send to Precision pharmacy API (line 266)

## Key Files Involved

1. **`backend/api/v1/views/webhooks.py`**
   - `shopify_webhook_view()` - webhook entry point
   - Lines 82-145

2. **`backend/ecomm/utils.py`**
   - `_process_shopify_order_impl()` - main order processor (lines 238-790)
   - `process_shopify_order_for_treatment_refill()` - treatment refill handler (lines 2089-2201)
   - `can_refill_entire_order()` - validation for ungated RX (lines 2732-2791)

3. **`backend/ecomm/tasks.py`**
   - `send_prescription_refill_request()` - async pharmacy submission (lines 157-267)

4. **`backend/shipping/precision/utils.py`**
   - `create_prescription_fill_prescriptions()` - links prescriptions to fill (lines 821-843)

5. **`backend/care/models.py`**
   - `PrescriptionFill` model (lines 721-828)
   - `PrescriptionFillOrder` junction table (lines 831-845)

6. **`backend/subscriptions/service.py`**
   - Subscription webhooks (not directly involved in order creation)

## Potential Failure Points

### 1. **Order Routing Failures**
**Location:** `backend/ecomm/utils.py` lines 660-692

**Scenario:** Order doesn't route to treatment refill handler
- Order type not recognized as `ORDER_TYPE_PRESCRIPTION_TREATMENT`
- For ungated RX: `can_refill_entire_order()` returns False
  - User doesn't have valid prescriptions for all Rx products
  - Prescriptions are deleted or expired
- Result: Order processes but PrescriptionFill never created

**Detection:** Check order logs for routing decision. Order would route to consult/intake path instead.

### 2. **User Resolution Failures**
**Location:** `backend/ecomm/utils.py` lines 2110-2138

**Scenario:** Cannot find or match user to order
- Email mismatch between subscription and Evvy account
- No user_account_email in order attributes
- No cart associated with order
- No consult_uid in order attributes
- Email lookup fails (case sensitivity already handled)

**Impact:**
- If no user found: line 2178 warning logged, may proceed without prescriptions
- Line 2184-2189: If no prescriptions/treatments found → ERROR logged, early return, NO fill created

**Detection:** Check for warning "No prescription IDs provided for order X and no user found"

### 3. **Prescription Resolution Failures**
**Location:** `backend/ecomm/utils.py` lines 2148-2180

**Scenario:** Cannot find prescriptions for order
- No prescription_ids in order attributes
- User has no active prescriptions for ordered products
- Prescriptions marked as deleted
- Product mismatch between order and prescriptions

**Impact:**
- Lines 2184-2189: If neither prescriptions nor OTC treatments exist → ERROR, early return
- PrescriptionFill created but empty, never sent to pharmacy

**Detection:** Error log "No prescriptions and no otc treatments found for order X"

### 4. **Prescription ID Validation Failures**
**Location:** `backend/ecomm/utils.py` lines 2151-2167

**Scenario:** Invalid prescription IDs in order
- Malformed prescription_ids string
- Prescription belongs to different user than order user
- Prescription IDs don't exist

**Impact:** Exception raised at line 2167, halts processing
- PrescriptionFill created but not populated
- Async task never queued

**Detection:** Error log "Invalid prescription_ids format" or "User on prescription X is not the same as the order user"

### 5. **Async Task Failures**
**Location:** `backend/ecomm/tasks.py` lines 157-267

**Scenarios:**
a) **Cancelled Order** (lines 173-190)
   - If order status is CANCELLED and fill can't be cancelled
   - Creates ConsultTask for manual review

b) **Invalid Shipping State** (lines 199-210)
   - Shipping address in state without care support
   - Creates ConsultTask TREATMENT_REFILL_FAILURE
   - Early return, fill never sent

c) **No Refills Remaining** (lines 212-223)
   - Prescription has 0 refills left (unless manual invoice)
   - Creates ConsultTask TREATMENT_REFILL_FAILURE
   - Raises exception

d) **Precision API Failures** (lines 232-266)
   - Patient creation fails
   - Prescription creation in Precision fails
   - Fill request to pharmacy fails
   - These would raise exceptions and potentially retry

**Detection:**
- Check ConsultTask table for TASK_TYPE_TREATMENT_REFILL_FAILURE
- Check Celery task logs for exceptions
- Check PrescriptionFill.status - should be CREATED if successful

### 6. **Silent Failures**

**Scenario:** PrescriptionFill created but never processed
- Line 2198 `send_prescription_refill_request.delay()` queues task
- If Celery worker is down, task never runs
- If Redis/queue is full, task may be dropped

**Detection:**
- PrescriptionFill exists with status=DRAFT (never updated to CREATED)
- No corresponding ConsultTask entries
- No logs in `send_prescription_refill_request` task

### 7. **Race Conditions**

**Scenario:** Multiple webhooks for same order
- Shopify may send duplicate webhooks
- `get_or_create` at line 2108 prevents duplicate PrescriptionFill
- But downstream processing could run twice

**Detection:** Multiple task invocations with same order_id, duplicate Precision API calls

## Diagnostic Checklist for Reported Issue

For a specific subscription renewal that didn't create a PrescriptionFill:

1. **Find the order:**
   - Query: `Order.objects.filter(order_number=XXX, provider='shopify')`
   - Check: Does order exist? What is order_type?

2. **Check routing:**
   - Did order route to treatment refill path?
   - Log search: "routing to refill path" or "routing to consult/intake path"

3. **Check PrescriptionFill:**
   - Query: `PrescriptionFill.objects.filter(order=order)`
   - Exists? What status (DRAFT vs CREATED)?

4. **Check user resolution:**
   - Does order.user exist?
   - Does user email match subscription email?

5. **Check prescriptions:**
   - Query: `Prescription.objects.filter(user=user, product__in=[ordered_products], deleted=False)`
   - Do valid prescriptions exist for ordered products?

6. **Check task execution:**
   - Celery logs for `send_prescription_refill_request` with this order_id
   - Any ConsultTask entries for this order?

7. **Check error logs:**
   - Search for order_number in application logs
   - Look for "Unable to send prescription fill request" or similar

## Most Likely Root Causes (Ranked)

1. **User has no valid prescriptions for subscription products** (lines 2184-2189)
   - Evergreen prescription query returns empty
   - Order routes to refill but fails validation

2. **Email mismatch prevents user lookup** (lines 2120-2133)
   - Subscription uses different email than Evvy account
   - No prescriptions found because no user

3. **Prescription refills exhausted** (task lines 212-223)
   - Prescription exists but refills=0
   - Async task creates failure ConsultTask

4. **Order type misclassification** (lines 660-692)
   - Product not recognized as treatment refill type
   - Routes to wrong handler entirely

5. **Celery worker/queue issues**
   - Task queued but never executed
   - PrescriptionFill stuck in DRAFT status

## Tool Calls Used: 15

1. `clew search "subscription renewal webhook"`
2. `clew search "PrescriptionFill creation"`
3. `clew search "order webhook shopify"`
4. `clew trace "ecomm/utils.py::_process_shopify_order_impl" --direction outbound --depth 2`
5. `clew search "create PrescriptionFill from order"`
6. `Read /Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2089-2208`
7. `Read /Users/albertgwo/Work/evvy/backend/ecomm/utils.py:238-338`
8. `clew search "treatment refill order type"`
9. `Read /Users/albertgwo/Work/evvy/backend/ecomm/utils.py:700-790`
10. `Read /Users/albertgwo/Work/evvy/backend/ecomm/utils.py:600-720`
11. `Read /Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:157-277`
12. `clew search "subscription charge success renewal"`
13. `clew search "handle_charge_success webhook"`
14. `Read /Users/albertgwo/Work/evvy/backend/subscriptions/service.py:0-150`
15. `Read /Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:369-449`
16. `clew search "subscription renewal creates order Shopify"`
17. `Read /Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py:821-850`
18. `clew trace "ecomm/utils.py::process_shopify_order_for_treatment_refill" --direction outbound --depth 1`

## Summary

The code path from subscription renewal to PrescriptionFill creation is a multi-stage process with **7 major failure points**. The flow starts with ReCharge creating a Shopify order, which triggers a webhook to `_process_shopify_order_impl`. The order is routed based on type and prescription availability to `process_shopify_order_for_treatment_refill`, which creates the PrescriptionFill and queues an async task. The async task validates state restrictions and refill availability before submitting to the Precision pharmacy API.

The most likely failure scenarios are: (1) user has no valid prescriptions for subscription products, (2) email mismatch prevents user lookup, or (3) prescription refills are exhausted. Each scenario has specific log messages and database states that can be used for diagnosis.
