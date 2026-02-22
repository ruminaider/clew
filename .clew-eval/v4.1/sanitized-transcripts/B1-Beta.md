# B1 — Agent Beta

## Function Definition

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 2089-2201

```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
```

The function takes three parameters:
- `order: Order` — a Django ORM Order model instance (required)
- `payload: dict[str, Any]` — the raw Shopify webhook payload dict (required)
- `order_logger: OrderEventLogger | None = None` — optional logger instance (has a default of `None`)

---

## All Call Sites (Production Code)

There are exactly **two call sites** in production code, both inside `_process_shopify_order_impl` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:

### Call Site 1 — Line 672 (Prescription treatment routing)
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

### Call Site 2 — Line 682 (Ungated RX routing to refill path)
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(...)
```

Both call sites pass all three arguments positionally. `order_logger` is a non-None `OrderEventLogger` constructed earlier in the function.

The `reprocess_subscription_refill_orders.py` script does **not** call this function directly — it replicates the same logic inline.

---

## What Would Break if the Signature Changes

### The `order_logger` parameter
- Both call sites pass it positionally as the third argument. If you rename or remove it, both call sites break.
- If you add a new required parameter before `order_logger`, both positional call sites break.

### The `order` parameter
- Used extensively inside the function (user resolution, prescription lookup, ORM access). Changing type or removing it breaks both call sites and all internal logic.

### The `payload` parameter
- Inside the function, `_parse_order_note_attributes(payload)` and `_parse_replacement_fill_id(payload)` are called on it. If you change the payload type/shape or replace it with a structured object, this breaks.

---

## Test Coverage

### Direct unit tests (calling via `process_shopify_order` wrapper):

All in `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py`:

| Test | Line | Description |
|---|---|---|
| `test_process_shopify_order_for_treatment_refill` | 2006 | Standard refill via `prescription_fill_id` in `note_attributes` |
| `test_process_shopify_order_for_manual_treatment_refill` | 2052 | Manual draft order refill; fill ID from `note` field |
| `test_process_shopify_order_for_replacement_treatment` | 2098 | Replacement fill via `note: "replacement-{fill_id}"` |
| `test_process_shopify_order_for_otc_treatments` | 2141 | OTC treatment order routing through this function |

### Routing tests (mock the function directly):

Class `TestUngatedRxOrderRouting` (line 3489):

| Test | Line | Description |
|---|---|---|
| `test__ux_order_with_valid_prescriptions__routes_to_refill_path` | 3507 | Asserts `mock_refill.assert_called_once()` |
| `test__ux_order_without_prescriptions__routes_to_consult_path` | 3524 | Asserts `mock_refill.assert_not_called()` |

The routing tests use `@patch("ecomm.utils.process_shopify_order_for_treatment_refill")`, so they are insulated from the function's internals.

---

## Summary of Breakage Risk

| Change | Impact |
|---|---|
| Add new **required** positional parameter (anywhere) | Breaks both call sites in `_process_shopify_order_impl` |
| Remove or rename `order_logger` | Breaks both call sites |
| Remove or reorder `order` or `payload` | Breaks both call sites + all 4 direct unit tests |
| Add new **optional** parameter at the end | No callers break; default value handles it |
| Rename the function | Breaks both call sites, the `@patch` target in `TestUngatedRxOrderRouting`, and the reference in the monitoring runbook |
| Change `payload` from `dict` to a structured object | Must update both call sites and all 4 unit tests that construct payloads as dicts |
