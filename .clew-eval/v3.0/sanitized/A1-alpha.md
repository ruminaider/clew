# A1 Investigation: Subscription Renewal to PrescriptionFill Creation

**Task:** A customer reported their subscription renewal didn't create a prescription fill. Investigate the code path from order webhook to PrescriptionFill creation and identify where failures can occur.

## Investigation Process

### 1. Initial Search for Entry Points
Searched for:
- PrescriptionFill model usage
- Webhook handling code
- Subscription renewal logic

Found key entry point: `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

### 2. Webhook Flow Analysis

**Entry Point: Shopify Webhook Handler**
- File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`
- Function: `shopify_webhook_view()` (lines 82-145)
- Handles topics: `orders/create` and `orders/cancelled`
- Calls: `process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")`

**Main Order Processing**
- File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- Wrapper: `process_shopify_order()` (line 204) - handles error logging
- Implementation: `_process_shopify_order_impl()` (line 238) - main logic

### 3. Order Processing Flow

The order processing follows this sequence:

1. **Order Creation/Retrieval** (lines 336-350)
   ```python
   order, _ = Order.objects.get_or_create(
       provider=Order.PROVIDER_SHOPIFY,
       provider_id=order_number,
   )
   ```

2. **Line Item Processing** (lines 454-495)
   - Extracts subscription metadata from order notes
   - Processes each line item
   - Determines if it's a recurring subscription order

3. **Order Type Determination** (lines 562-567)
   ```python
   order_type, order_sku = _get_overall_order_type_and_sku_from_line_items(
       created_line_items, order_custom_attributes, is_recurring_subscription_order
   )
   ```

4. **Order Type Routing** (lines 637-692)

   The code branches based on order type:

   **For care orders** (lines 637-647):
   - Types: VAGINITIS_CARE, STI_CARE, UTI_CARE, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, MALE_PARTNER
   - Routes to: `process_shopify_order_for_care()`

   **For test orders** (lines 648-654):
   - Types: TEST, EXPANDED_TEST, URINE_TEST
   - Routes to: `process_shopify_order_for_test()`

   **Critical: Prescription Refill Path** (lines 661-672):
   ```python
   if (
       order.order_type not in [
           Order.ORDER_TYPE_A_LA_CARTE,
           Order.ORDER_TYPE_MIXED_CARE,
           Order.ORDER_TYPE_DYNAMIC_BUNDLE,
           Order.ORDER_TYPE_UNGATED_RX,
           Order.ORDER_TYPE_MALE_PARTNER,
       ]
       and Order.ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
   ):
       process_shopify_order_for_treatment_refill(order, payload, order_logger)
   ```

   **For ungated RX orders** (lines 676-692):
   - Checks if order can be refilled with `can_refill_entire_order()`
   - If yes: routes to `process_shopify_order_for_treatment_refill()`
   - If no: routes to consult/intake path

### 4. PrescriptionFill Creation Logic

**Function:** `process_shopify_order_for_treatment_refill()` (line 2089)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

**Step-by-step breakdown:**

1. **Parse Order Attributes** (lines 2096-2099)
   ```python
   order_attrs = _parse_order_note_attributes(payload)
   replacement_fill_id = _parse_replacement_fill_id(payload)
   prescription_fill_id = order_attrs.prescription_fill_id or replacement_fill_id
   ```

2. **Get or Create PrescriptionFill** (lines 2101-2108)
   ```python
   if prescription_fill_id and _is_valid_uuid(prescription_fill_id):
       prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)
   else:
       lookup_params = {"order": order}
       if order.user:
           lookup_params["user"] = order.user
       prescription_fill, _ = PrescriptionFill.objects.get_or_create(**lookup_params)
   ```

3. **Determine User** (lines 2110-2138)
   - Try from consult_uid
   - Try from user_account_email
   - Try from cart user
   - Try from order email
   - Set user on order

4. **Link Order to PrescriptionFill** (lines 2140-2143)
   ```python
   prescription_fill.order = order
   prescription_fill.save()
   PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
   ```

5. **Get Prescriptions** (lines 2145-2180)
   - If prescription_ids provided: use those specific prescriptions
   - Otherwise: get user's evergreen prescriptions matching ordered products
   - Validate user on prescriptions matches order user

6. **Validate Prescriptions/OTC Treatments Exist** (lines 2184-2189)
   ```python
   if not prescriptions.exists() and not otc_treatments.exists():
       logger.error(
           f"No prescriptions and no otc treatments found for order {order.order_number}. "
           "Unable to send prescription fill request to precision."
       )
       return
   ```

7. **Create PrescriptionFill Records** (lines 2191-2195)
   ```python
   if prescriptions.exists():
       create_prescription_fill_prescriptions(prescription_fill, list(prescriptions), [order])
   if otc_treatments.exists() and order.status != Order.STATUS_CANCELLED:
       create_prescription_fill_otc_treatments(prescription_fill, list(otc_treatments))
   ```

8. **Send to Pharmacy** (line 2198)
   ```python
   send_prescription_refill_request.delay(order.id, prescription_fill.id)
   ```

## Potential Failure Points

Based on the code analysis, here are the critical failure points where a subscription renewal might NOT create a PrescriptionFill:

### 1. **Order Type Misclassification** (CRITICAL)
- **Location:** Lines 661-672 in `_process_shopify_order_impl()`
- **Failure:** If the order type is incorrectly classified as A_LA_CARTE, MIXED_CARE, DYNAMIC_BUNDLE, UNGATED_RX, or MALE_PARTNER, the refill processing is skipped
- **Cause:** Incorrect line item metadata or order custom attributes
- **Impact:** `process_shopify_order_for_treatment_refill()` never called

### 2. **Missing Line Item Order Type** (CRITICAL)
- **Location:** Line 670 - check for `Order.ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types`
- **Failure:** If line items are not properly tagged with PRESCRIPTION_TREATMENT order type
- **Cause:** Line item processing error or incorrect product configuration
- **Impact:** `process_shopify_order_for_treatment_refill()` never called

### 3. **User Resolution Failure** (HIGH)
- **Location:** Lines 2110-2138 in `process_shopify_order_for_treatment_refill()`
- **Failure:** If user cannot be resolved from any source (consult_uid, email, cart)
- **Cause:** Missing or invalid email, missing cart, invalid consult_uid
- **Impact:** `lookup_params` for get_or_create only has {"order": order}, which may create duplicate fills

### 4. **No Valid Prescriptions Found** (HIGH)
- **Location:** Lines 2184-2189
- **Failure:** Early return if no prescriptions and no OTC treatments exist
- **Cause:**
  - User has no active prescriptions for the ordered products
  - Prescriptions expired
  - prescription_ids attribute points to wrong/deleted prescriptions
- **Impact:** Function returns early, no PrescriptionFill created, error logged

### 5. **Prescription Validation Failure** (MEDIUM)
- **Location:** Lines 2157-2167
- **Failure:** Exception thrown if prescription user doesn't match order user
- **Cause:** prescription_ids attribute points to another user's prescriptions
- **Impact:** Exception raised, entire order processing may fail

### 6. **Missing Order Note Attributes** (MEDIUM)
- **Location:** Lines 2037-2066 `_parse_order_note_attributes()`
- **Failure:** If subscription renewal doesn't include proper note_attributes
- **Cause:** ReCharge/subscription service not passing through required metadata
- **Impact:** prescription_fill_id, cart_id, consult_uid all None, falls back to less reliable resolution

### 7. **Ungated RX Routing Failure** (MEDIUM)
- **Location:** Lines 676-692
- **Failure:** If `can_refill_entire_order()` returns False for ungated RX order
- **Cause:** Some products don't have valid prescriptions
- **Impact:** Routes to consult/intake path instead of refill path

### 8. **Invalid UUID Format** (LOW)
- **Location:** Line 2102 `_is_valid_uuid(prescription_fill_id)`
- **Failure:** If prescription_fill_id is present but not a valid UUID
- **Cause:** Corrupted data in order attributes
- **Impact:** Falls back to get_or_create logic

### 9. **Webhook Validation Failures** (LOW)
- **Location:** Lines 90-117 in webhook handler
- **Failure:** Webhook signature verification or JSON parsing fails
- **Impact:** Webhook rejected, order never processed

### 10. **Line Items Empty** (LOW)
- **Location:** Lines 262-272
- **Failure:** Webhook has no line_items array or empty array
- **Impact:** Early return, order not processed

## Key Files Involved

1. `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` - Webhook entry point
2. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` - Main order processing logic
3. `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py` - Retry logic for failed orders
4. `/Users/albertgwo/Work/evvy/backend/care/models.py` - PrescriptionFill model (referenced)
5. `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` - Subscription webhook handlers

## Recommended Investigation Steps

To diagnose a specific customer case:

1. **Check order was received:** Search logs for order_number in webhook handler
2. **Check order type:** Verify order.order_type and line_item_order_types in database
3. **Check routing decision:** Look for logs showing which processing path was taken
4. **Check prescription lookup:** Verify user has active prescriptions for ordered products
5. **Check note_attributes:** Examine order payload for prescription_fill_id, prescription_ids, user_account_email
6. **Check subscription metadata:** Verify is_recurring_subscription_order was True
7. **Check for errors:** Search for "No prescriptions and no otc treatments found" error message

## Tool Calls Used

1. Changed to project directory
2. search("PrescriptionFill") (75 files)
3. search("subscription renewal") (2 files)
4. search("shopify webhook") (30 files)
5. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py") (full file)
6. read("/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py") (full file)
7. search("process_shopify_order") function definitions
8. read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (offset 204, limit 200)
9. search("PrescriptionFill.create") patterns
10. read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (offset 1807, limit 300)
11. read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (offset 2089, limit 150)
12. read("/Users/albertgwo/Work/evvy/backend/subscriptions/service.py") (offset 1, limit 100)
13. search("handle_charge_upcoming") function
14. read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (offset 400, limit 200)
15. read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (offset 600, limit 200)

**Total tool calls: 15**
