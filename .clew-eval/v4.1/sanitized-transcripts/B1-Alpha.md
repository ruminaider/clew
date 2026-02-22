# B1 — Agent Alpha

## Analysis: `process_shopify_order_for_treatment_refill` Signature Change Impact

### Current Signature

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 2089-2091

```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
```

**Parameters:**
- `order: Order` — the Django Order model instance (required)
- `payload: dict[str, Any]` — the raw Shopify webhook payload dict (required)
- `order_logger: OrderEventLogger | None = None` — optional event logger (has default)

---

### All Callers

The function is called in **exactly two places**, both inside `_process_shopify_order_impl` in the same file (`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`). It is not imported or called anywhere else in the codebase.

**Call site 1 — Line 672** (legacy prescription treatment orders):
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

**Call site 2 — Line 682** (ungated RX orders routed to refill path):
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        ...
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

Both call sites pass identical arguments: `(order, payload, order_logger)` — positional, no keyword arguments.

---

### What the Callers Pass

| Argument | Type | Origin |
|---|---|---|
| `order` | `Order` (Django model) | Built up during `_process_shopify_order_impl` from the payload |
| `payload` | `dict[str, Any]` | Passed into `_process_shopify_order_impl` directly from the webhook |
| `order_logger` | `OrderEventLogger` | Passed into `_process_shopify_order_impl` from `process_shopify_order` |

The function uses `payload` internally to call `_parse_order_note_attributes(payload)` and `_parse_replacement_fill_id(payload)`. The `order_logger` argument is accepted but is not actually used inside the function body — it's carried in the signature for consistency with other order-processing functions.

---

### Test Coverage

There are **four test functions** and **one test class** that directly exercise this function:

**1. `test_process_shopify_order_for_treatment_refill` — line 2006** (class `TestUtils`)
- Tests the happy path: a user with an existing `PrescriptionFill` identified via `prescription_fill_id` in `note_attributes`
- Calls through the full `process_shopify_order()` public entry point
- Asserts: correct `order.user_id`, correct `order.business_verticals`, and `send_prescription_refill_request.delay(order.id, prescription_fill.id)` is called

**2. `test_process_shopify_order_for_manual_treatment_refill` — line 2052** (class `TestUtils`)
- Tests manual invoice orders (`source_name: "shopify_draft_order"`) where the fill ID is in `payload["note"]`
- Asserts `order.is_manual_invoice` is set

**3. `test_process_shopify_order_for_replacement_treatment` — line 2098** (class `TestUtils`)
- Tests replacement orders where `payload["note"]` contains `"replacement-{fill_id}"`
- Uses a `PrescriptionFill` with `PRESCRIPTION_FILL_STATUS_DRAFT` status

**4. `TestUngatedRxOrderRouting` — line 3489** (its own test class)
- `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` (line 3507): Mocks the function and verifies it is called once
- `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` (line 3524): Verifies the function is NOT called

Tests 1-3 do NOT directly mock the function — they let it run fully and mock `send_prescription_refill_request` instead. Test class 4 mocks the function at the call-site level.

---

### What Would Break if the Signature Changes

**Adding a required parameter:** Both call sites at lines 672 and 682 would break with a `TypeError` at runtime. Since `_process_shopify_order_impl` is called from the Shopify webhook handler, this would silently fail during order processing.

**Removing `order`:** Would require significant internal refactoring — `order` is used throughout the function body including `order.user`, `order.order_type`, `order.order_number`, `order.cart`, `order.email`, `order.status`, `order.otc_treatments`, `order.id`, and multiple `order.save()` calls.

**Removing `payload`:** Would require restructuring — `payload` is passed to `_parse_order_note_attributes(payload)` and `_parse_replacement_fill_id(payload)`.

**Removing or changing `order_logger`:** Low-risk — the parameter is not actually used inside the function body. The call sites would still need updating at lines 672 and 682, and tests 1-3 exercise the function without checking logger behavior.

**Tests that would fail:** All four test functions and the routing test class would be affected by any breaking signature change. Tests 1-3 call through `process_shopify_order()` and would fail at the invocation point. Test 4's mock patch would still work but assertions test routing, not internals.
