# B1: Treatment Refill Function Impact Analysis - Beta Approach

## Task
"We're considering changing the signature of the function that processes shopify orders for treatment refills. What would break? Find all callers, understand what arguments they pass, and identify any test coverage."

## Tool Calls and Reasoning

### 1. Initial Search for the Function
**Tool**: search("def.*process.*shopify.*order")

**Result**: Found multiple related functions:
- `process_shopify_order_for_treatment_refill` at line 2089 in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (TARGET)
- `_process_shopify_order_impl` at line 238 (main implementation)
- `process_shopify_order` at line 204 (public wrapper)
- Several other specialized processors for different order types

### 2. Find All References
**Tool**: search("process_shopify_order")

**Result**: 19 files reference variants of this function, including:
- Core implementation: `backend/ecomm/utils.py`
- Tests: `backend/ecomm/tests/test_utils.py`, `backend/ecomm/tests/test_shopify_tasks.py`
- Webhooks: `backend/api/v1/views/webhooks.py`
- Tasks: `backend/ecomm/shopify/tasks.py`
- Scripts: `backend/scripts/reprocess_subscription_refill_orders.py`

### 3. Read Function Signature
**Tool**: read("utils.py") lines 2089-2200
**Finding**: Complete function signature and implementation

```python
def process_shopify_order_for_treatment_refill(
    order: Order,
    payload: dict[str, Any],
    order_logger: OrderEventLogger | None = None
):
```

**Parameters**:
1. `order: Order` - Django Order model instance (required)
2. `payload: dict[str, Any]` - Shopify webhook payload (required)
3. `order_logger: OrderEventLogger | None` - Optional event logger

### 4. Find Direct Callers
**Tool**: search("process_shopify_order_for_treatment_refill\(")

**Result**: Found 2 call sites in `backend/ecomm/utils.py`:

#### Call Site 1 (Line 672):
```python
# Inside _process_shopify_order_impl()
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

**Arguments passed**:
- `order`: The Order instance created from payload
- `payload`: The full Shopify webhook payload dict
- `order_logger`: The OrderEventLogger instance from parent function

#### Call Site 2 (Line 682):
```python
# Inside _process_shopify_order_impl(), for Ungated RX orders
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        logger.info(
            f"UX order {order.order_number}: routing to refill path "
            f"(all Rx products have valid prescriptions for user {order.user.id})"
        )
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

**Arguments passed**: Same as Call Site 1
- `order`: The Order instance
- `payload`: The Shopify webhook payload
- `order_logger`: The OrderEventLogger instance

### 5. Understand Calling Context
**Tool**: read("_process_shopify_order_impl") function (line 238)

**Finding**: This is the main order processing implementation that:
1. Receives webhook payload from Shopify
2. Creates/updates Order model instances
3. Routes to specialized processors based on order type
4. Calls `process_shopify_order_for_treatment_refill` for prescription refill orders

### 6. Find Entry Points
**Tool**: read("process_shopify_order") wrapper (line 204)

**Finding**: Public wrapper that:
- Creates OrderEventLogger
- Wraps `_process_shopify_order_impl` with error handling
- Logs errors to NewRelic

**Chain**: `process_shopify_order` → `_process_shopify_order_impl` → `process_shopify_order_for_treatment_refill`

### 7. Trace Webhook Entry Point
**Tool**: read("backend/api/v1/views/webhooks.py") (line 131)

**Finding**:
```python
# In shopify_webhook_view()
if shopify_topic == "orders/create" or shopify_topic == "orders/cancelled":
    process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")
```

**Full Call Chain**:
```
Shopify webhook → shopify_webhook_view()
  → process_shopify_order(payload, is_order_cancellation)
    → _process_shopify_order_impl(payload, is_order_cancellation, order_logger)
      → process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

### 8. Check Task/API Entry Points
**Tool**: read("backend/ecomm/shopify/tasks.py")

**Finding**: Additional entry points:
- `process_shopify_order_from_api()` - Processes orders fetched from Shopify API (not webhooks)
- `process_unprocessed_shopify_orders_by_email()` - Reprocesses orders by email
- `process_unprocessed_shopify_orders_by_checkout_token()` - Reprocesses by checkout token
- `retry_failed_shopify_orders()` - Celery task to retry failed orders

All of these call `process_shopify_order(payload, is_order_cancellation)` which eventually calls our target function.

### 9. Check Scripts
**Tool**: read("backend/scripts/reprocess_subscription_refill_orders.py")

**Finding**: This script does NOT call `process_shopify_order_for_treatment_refill` directly. Instead, it reimplements the same logic in `_reprocess_order()` for backfilling purposes. This means:
- Script would NOT break from signature change
- But script logic should stay in sync with function logic (manual maintenance burden)

### 10. Test Coverage Analysis
**Tool**: search("test.*treatment.*refill|test.*replacement.*treatment")

**Finding**: 3 direct test methods found in `backend/ecomm/tests/test_utils.py`:

#### Test 1: `test_process_shopify_order_for_treatment_refill` (line 2006)
```python
def test_process_shopify_order_for_treatment_refill(self, mock_task):
```
**Coverage**:
- Tests standard refill with `prescription_fill_id` in note_attributes
- Verifies user association
- Verifies prescription fill creation
- Mocks `send_prescription_refill_request` task
- Calls via public API: `process_shopify_order(payload, is_order_cancellation=False)`

**Payload structure used**:
```python
payload = {
    "order_number": 1234,
    "email": "test@example.com",
    "note_attributes": [
        {"name": "prescription_fill_id", "value": str(prescription_fill.id)}
    ],
    "test": False,
    "total_line_items_price": "50.00",
    "line_items": [{"sku": "RFLBA001", ...}],
}
```

#### Test 2: `test_process_shopify_order_for_manual_treatment_refill` (line 2052)
```python
def test_process_shopify_order_for_manual_treatment_refill(self, mock_task):
```
**Coverage**:
- Tests manual/draft order refills
- Uses `note` field (not `note_attributes`) for prescription_fill_id
- Tests `source_name: "shopify_draft_order"` path
- Verifies `is_manual_invoice` flag

**Payload structure used**:
```python
payload = {
    "order_number": 1234,
    "email": "test@example.com",
    "note": str(prescription_fill.id),  # Different from Test 1
    "source_name": "shopify_draft_order",  # Manual order flag
    "test": False,
    "total_line_items_price": "50.00",
    "line_items": [{"sku": "RFLBA001", ...}],
}
```

#### Test 3: `test_process_shopify_order_for_replacement_treatment` (line 2098)
```python
def test_process_shopify_order_for_replacement_treatment(self, mock_task):
```
**Coverage**:
- Tests replacement treatment flow
- Uses `note` field with `"replacement-{fill_id}"` format
- Tests linking to DRAFT status prescription fills

**Payload structure used**:
```python
payload = {
    "order_number": 1234,
    "email": "test@example.com",
    "note": f"replacement-{str(draft_fill.id)}",  # Special format
    "test": False,
    "total_line_items_price": "50.00",
    "line_items": [{"sku": "RPLBA001", ...}],
}
```

#### Test 4: `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` (line 3507)
**Coverage**:
- Tests routing logic for Ungated RX orders
- Verifies orders WITH valid prescriptions route to treatment_refill path
- Mocks `process_shopify_order_for_treatment_refill` directly to verify it's called

#### Test 5: `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` (line 3524)
**Coverage**:
- Tests routing logic for Ungated RX orders
- Verifies orders WITHOUT prescriptions do NOT route to treatment_refill path
- Negative test case

### 11. Check Helper Functions Used
**Tool**: search("helper function definitions")

**Finding**: The function depends on these helpers:
- `_parse_order_note_attributes(payload)` - Parses note_attributes from payload
- `_parse_replacement_fill_id(payload)` - Parses replacement fill ID from note field
- `_is_valid_uuid(value)` - Validates UUID format
- `get_care_products_from_orders([order])` - Gets care products from order
- `create_prescription_fill_prescriptions()` - Creates prescription records
- `create_prescription_fill_otc_treatments()` - Creates OTC treatment records
- `send_prescription_refill_request.delay()` - Celery task to send to pharmacy
- `mark_order_cart_as_purchased()` - Marks cart as purchased

These are all internal dependencies that would need updating if signature changes significantly.

## Summary

### Direct Callers (What Would Break)

**2 call sites in `_process_shopify_order_impl()`** (`backend/ecomm/utils.py`):

1. **Line 672**: Standard prescription treatment orders
   - Called when: `order.order_type` is PRESCRIPTION_TREATMENT
   - Arguments: `process_shopify_order_for_treatment_refill(order, payload, order_logger)`

2. **Line 682**: Ungated RX orders (refillable prescriptions)
   - Called when: `order.order_type == ORDER_TYPE_UNGATED_RX` AND user has valid prescriptions
   - Arguments: `process_shopify_order_for_treatment_refill(order, payload, order_logger)`

### Arguments Currently Passed

All callers pass the same 3 arguments in the same order:
1. `order: Order` - Django model instance (already created/retrieved from DB)
2. `payload: dict[str, Any]` - Full Shopify webhook payload containing:
   - `order_number`, `email`, `line_items`, `note`, `note_attributes`, etc.
3. `order_logger: OrderEventLogger | None` - Optional logger (always provided by callers)

### Entry Points (Indirect Impact)

Changing the signature would NOT break these directly, but they're part of the call chain:
- **Webhook handler**: `shopify_webhook_view()` in `backend/api/v1/views/webhooks.py`
- **API processors**: Functions in `backend/ecomm/shopify/tasks.py`
  - `process_shopify_order_from_api()`
  - `process_unprocessed_shopify_orders_by_email()`
  - `process_unprocessed_shopify_orders_by_checkout_token()`
  - `retry_failed_shopify_orders()` (Celery task)

### Test Coverage

**5 test methods** in `backend/ecomm/tests/test_utils.py`:

1. `test_process_shopify_order_for_treatment_refill` - Standard refill path
2. `test_process_shopify_order_for_manual_treatment_refill` - Manual/draft orders
3. `test_process_shopify_order_for_replacement_treatment` - Replacement orders
4. `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` - UX routing (positive)
5. `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` - UX routing (negative)

**Coverage includes**:
- All 3 payload formats: note_attributes, note field, replacement format
- Manual invoice orders vs standard orders
- User association from email and cart
- Prescription fill creation and linking
- Task dispatch verification (mocked)
- Order type routing logic

**Not directly covered** (would need review):
- Consult UID lookup and association
- Multiple prescription IDs in comma-separated format
- Prescription validation (user mismatch error path)
- OTC treatment handling
- Edge cases around missing user/prescriptions

### Related Code (Manual Sync Required)

**Script**: `backend/scripts/reprocess_subscription_refill_orders.py`
- Reimplements the same logic for backfilling
- Does NOT call the function directly
- Would need manual updates to stay in sync with signature changes

## Impact Assessment

### Breaking Changes from Signature Modification

**If you change the signature**, you MUST update:

1. **2 call sites** in `_process_shopify_order_impl()` (lines 672, 682)
2. **5 test methods** in `test_utils.py` that call through to this function
3. **Documentation/comments** that reference the function signature

**Potentially affected**:
4. The backfill script logic (if semantics change, not just signature)

### Recommended Approach for Changes

1. **Add optional parameters at the end** - Least breaking, only tests need updates
2. **Use `**kwargs` for new params** - More flexible but less type-safe
3. **Create new function version** - Safest for gradual migration
4. **Refactor signature entirely** - Most work, but could improve design

### Current Function Responsibilities

The function is doing A LOT:
1. Parse order attributes from payload
2. Get or create PrescriptionFill
3. Determine user from multiple sources (email, cart, consult)
4. Set user on order
5. Link prescription fill to order
6. Get ordered products
7. Filter prescriptions by IDs or user
8. Validate prescription ownership
9. Get OTC treatments
10. Create prescription fill records
11. Send to pharmacy (async task)
12. Mark cart as purchased

**Refactoring opportunity**: This function has high cyclomatic complexity and could benefit from being broken into smaller, more focused functions with clearer contracts.
