# B1 Exploration Log

## Search 1: search for the shopify order processing function for treatment refills

search("shopify order processing treatment refill")

**Key findings:**
- Found the primary function: `process_shopify_order_for_treatment_refill` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` at lines 2089-2201
- The result's `related` field showed: "Called by: _process_shopify_order_impl, _parse_order_note_attributes, _parse_replacement_fill_id"
- Found the test function: `test_process_shopify_order_for_treatment_refill` in `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py`
- Additional tests: `test_process_shopify_order_for_manual_treatment_refill`, `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path`
- The internal caller `_process_shopify_order_impl` was also surfaced (lines 238-790)

## Search 2: Trace the function's call graph

search("code related to process_shopify_order_for_treatment_refill")

**Key findings:**
- The trace showed outbound calls (what the function calls) but the the index does not have explicit inbound "called by" edges for this function — the related field from Search 1 showed callers from a different mechanism
- Confirmed the function calls: `_parse_order_note_attributes`, `_parse_replacement_fill_id`, `_is_valid_uuid`, `PrescriptionFill.objects.get/get_or_create`, `get_care_products_from_orders`, `create_prescription_fill_prescriptions`, `create_prescription_fill_otc_treatments`, `send_prescription_refill_request.delay`, `mark_order_cart_as_purchased`

## Search 3: Read the function signature and body

read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") lines 2089-2201

**Key finding — exact signature:**
```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
```

Parameters:
- `order: Order` — the Django ORM Order object
- `payload: dict[str, Any]` — the raw Shopify webhook JSON payload
- `order_logger: OrderEventLogger | None = None` — optional structured event logger (defaults to None)

## Search 4: Grep for all call sites

**Command:** search("process_shopify_order_for_treatment_refill")

**All occurrences found:**
1. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:672` — first call site in `_process_shopify_order_impl`
2. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:682` — second call site in `_process_shopify_order_impl`
3. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2089` — the function definition itself
4. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2757` — a comment in `can_refill_entire_order` noting it mirrors the lookup logic
5. `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py:5` — a comment explaining what went wrong (not a call)
6. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py:2006` — test method definition
7. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py:3487` — `@patch` decorator for routing test
8. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py:3511` — docstring comment

## Search 5: Read the two call sites in `_process_shopify_order_impl`

read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") lines 640-692

**Call site 1 (line 672)** — Called when a non-excluded order type contains prescription treatment line items:
```python
if (
    order.order_type
    not in [
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
Arguments passed: `order`, `payload`, `order_logger`

**Call site 2 (line 682)** — Called when an ungated RX order routes to the refill path:
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        logger.info(...)
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        ...
```
Arguments passed: `order`, `payload`, `order_logger`

## Search 6: Read the test methods in detail

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py`

### Test class context:
- Lines 65-2894: `class TestUtils(TestCase)` — the three primary tests live here, all decorated with `@patch("ecomm.utils.send_prescription_refill_request")`
- Lines 3487-3532: `class TestUngatedRxOrderRouting(TestCase)` — routing tests using `@patch("ecomm.utils.process_shopify_order_for_treatment_refill")`

### Test 1: `test_process_shopify_order_for_treatment_refill` (line 2006)
- Exercises the standard refill path using `note_attributes` to pass `prescription_fill_id`
- Calls `process_shopify_order(payload, is_order_cancellation=False)` (the public wrapper)
- Verifies the order is linked to the correct user and `send_prescription_refill_request.delay(order.id, prescription_fill.id)` is called

### Test 2: `test_process_shopify_order_for_manual_treatment_refill` (line 2052)
- Exercises manual invoice (draft order) path: `source_name: "shopify_draft_order"`, fill ID in `note` field
- Calls `process_shopify_order(payload, is_order_cancellation=False)`
- Verifies `order.is_manual_invoice` is True and the refill task fires

### Test 3: `test_process_shopify_order_for_replacement_treatment` (line 2098)
- Exercises replacement fill path: fill ID in `note` field as `replacement-{id}`
- Calls `process_shopify_order(payload, is_order_cancellation=False)`
- Verifies fill task fires with the draft fill's ID

### Test 4 & 5: `TestUngatedRxOrderRouting` (lines 3507-3532)
- `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` — mocks `process_shopify_order_for_treatment_refill` and asserts it is called once when user has valid prescriptions
- `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` — asserts `process_shopify_order_for_treatment_refill` is NOT called when user has no prescriptions

## Search 7: Check the reprocess script for any direct calls

**File:** `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py`

The script does NOT call `process_shopify_order_for_treatment_refill` directly. Instead it reimplements the same logic inline in `_reprocess_order()` (lines 160-235), duplicating the prescription fill creation and `send_prescription_refill_request.delay` call. The function name appears only in a comment explaining which function orders should have been routed to.

## Search 8: Read the `can_refill_entire_order` comment context

read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") lines 2740-2768

There is an important comment at line 2757:
```python
# Mirror the "evergreen prescription" lookup used by
# process_shopify_order_for_treatment_refill() so the same prescriptions
# will be found downstream.
# NOTE: This mirrors the `elif order.user:` branch of the downstream
# function.  If an order carries explicit `prescription_ids` in its note
# attributes, the downstream function uses those IDs instead.  UX orders
# do not carry prescription_ids today, but if that changes this function
# should be updated to match.
```

This is a **coupling note** — if `process_shopify_order_for_treatment_refill`'s prescription lookup logic changes, `can_refill_entire_order` must be updated to stay in sync.

---

## Final Answer

### The Function

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 2089-2201

```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
    """
    Custom order processing logic for prescription refill, replacement, and otc treatment orders.
    Supports both legacy consult-based orders and new evergreen prescription orders.
    """
```

**Parameters:**
- `order: Order` — Django ORM Order object (required)
- `payload: dict[str, Any]` — raw Shopify webhook JSON payload dict (required)
- `order_logger: OrderEventLogger | None = None` — optional structured logger (optional, defaults to None)

---

### All Callers

There are exactly **two call sites** in production code, both inside `_process_shopify_order_impl` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:

**Call site 1 — lines 661-672** (prescription treatment line item path):
```python
if (
    order.order_type
    not in [
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
This fires for any order type NOT in the exclusion list that contains at least one prescription treatment line item. All three arguments are passed: `order`, `payload`, `order_logger`.

**Call site 2 — lines 676-682** (ungated RX refill path):
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
```
This fires when an ungated RX order has a user who has valid prescriptions for all Rx products. All three arguments are passed: `order`, `payload`, `order_logger`.

Both callers always pass all three arguments. Changing the signature by adding, removing, or reordering any of the three parameters would break both call sites identically.

---

### What Would Break if the Signature Changes

**Direct breakage (production code):**

1. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:672` — `_process_shopify_order_impl` call site 1
2. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:682` — `_process_shopify_order_impl` call site 2

**Indirect coupling (not a call, but tightly coupled logic):**

3. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2757-2763` — `can_refill_entire_order()` contains a documented comment warning that it mirrors `process_shopify_order_for_treatment_refill`'s prescription lookup logic. If the prescription-finding logic within the function changes (e.g., how it uses `order_attrs.prescription_ids` vs the evergreen lookup), `can_refill_entire_order` must be updated in parallel or the routing gate will diverge from the actual processing.

4. `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` — `_reprocess_order()` (lines 160-235) is a manual reimplementation of the same logic. If the signature or internal algorithm changes, this script will silently diverge and produce incorrect backfill results.

---

### Test Coverage

All tests call the function indirectly through the public wrapper `process_shopify_order(payload, is_order_cancellation)`, not directly.

**In `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py` — class `TestUtils`:**

| Test | Line | What it exercises |
|---|---|---|
| `test_process_shopify_order_for_treatment_refill` | 2006 | Standard refill: `note_attributes` contains `prescription_fill_id` |
| `test_process_shopify_order_for_manual_treatment_refill` | 2052 | Manual invoice (draft order): fill ID in `note` field, `source_name="shopify_draft_order"` |
| `test_process_shopify_order_for_replacement_treatment` | 2098 | Replacement fill: `note` field contains `replacement-{fill_id}` |

All three use `@patch("ecomm.utils.send_prescription_refill_request")` to mock the async task and assert `mock_task.delay.assert_called_with(order.id, prescription_fill.id)`.

**In class `TestUngatedRxOrderRouting` (line 3487):**

| Test | Line | What it exercises |
|---|---|---|
| `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` | 3507 | Asserts `process_shopify_order_for_treatment_refill` is called once when user has valid prescriptions |
| `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` | 3524 | Asserts function is NOT called when user has no prescriptions |

The routing tests mock `process_shopify_order_for_treatment_refill` itself, so they verify routing logic but do NOT exercise the function's body.

**Coverage gap:** The `test_process_shopify_order_for_otc_treatments` test (line 2141) exercises OTC treatment processing but the OTC path routes through a different code path (not via `process_shopify_order_for_treatment_refill`).

---

### Summary of Impact for a Signature Change

If you add, rename, or remove any parameter:

- **2 production call sites** must be updated (both in `_process_shopify_order_impl` in `ecomm/utils.py`)
- **3 integration tests** will fail if you change the required positional arguments `order` or `payload` (all call via the wrapper and build payload dicts directly)
- **2 routing tests** use `@patch` and call `mock_refill.assert_called_once()` without checking arguments — these will not fail on signature changes but also won't catch logic regressions
- **`can_refill_entire_order`** must be reviewed if you change how prescription lookups work inside the function (documented coupling comment at line 2757)
- **`_reprocess_order` in the backfill script** has a silent duplicate of the same algorithm that will not fail at test time but will diverge in production backfills
