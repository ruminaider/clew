# Impact Analysis: `process_shopify_order_for_treatment_refill` Signature Change

## Function Location and Signature

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 2089–2201

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
- `order: Order` — the Django ORM order model instance
- `payload: dict[str, Any]` — the raw Shopify webhook payload dict
- `order_logger: OrderEventLogger | None = None` — optional logger (defaults to `None`)

---

## All Call Sites

There are exactly **two call sites**, both inside `_process_shopify_order_impl` in the same file:

### Call Site 1 — Prescription Treatment Line Items (line 672)

```python
# /Users/albertgwo/Work/evvy/backend/ecomm/utils.py, line 660–672
# Orders with prescription refills could be labeled with the "Test" order type, so check the line items.
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

- **Arguments passed:** `(order, payload, order_logger)`
- **Trigger condition:** Order type is NOT one of the excluded types, but a line item has `ORDER_TYPE_PRESCRIPTION_TREATMENT`
- `order_logger` is the `OrderEventLogger` created at the top of `_process_shopify_order_impl`

### Call Site 2 — Ungated RX Orders with Valid Prescriptions (line 682)

```python
# /Users/albertgwo/Work/evvy/backend/ecomm/utils.py, line 676–682
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        logger.info(...)
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        logger.info(...)
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(...)
```

- **Arguments passed:** `(order, payload, order_logger)`
- **Trigger condition:** Order type is `ORDER_TYPE_UNGATED_RX`, the user exists, and `can_refill_entire_order()` returns `True`
- Same `order_logger` instance is passed here too

Both call sites are in the same function `_process_shopify_order_impl` (lines 238–790), which is called exclusively by `process_shopify_order` (the public-facing wrapper, lines 204–234).

---

## What `payload` and `order` Carry (Internal Usage)

Inside `process_shopify_order_for_treatment_refill`, the following fields are read from `payload` (via helper functions):

- `payload["note_attributes"]` — parsed by `_parse_order_note_attributes(payload)` for:
  - `prescription_fill_id`
  - `consult_uid`
  - `user_account_email`
  - `prescription_ids`
  - `cart_id`
- `payload["note"]` — parsed by `_parse_replacement_fill_id(payload)` for replacement fill ID (e.g., `"replacement-<uuid>"`)

From `order`, the function accesses:
- `order.user`, `order.email`, `order.cart`, `order.order_number`, `order.status`, `order.otc_treatments`

---

## Test Coverage

### Direct Tests (call the function indirectly via `process_shopify_order`)

All tests are in `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py`.

#### 1. `test_process_shopify_order_for_treatment_refill` (line 2006)
Decorated with `@patch("ecomm.utils.send_prescription_refill_request")`.
- Sets up user, consult, prescription, `PrescriptionFill` with a known UUID
- Payload has `note_attributes` with `prescription_fill_id`
- Calls `process_shopify_order(payload, is_order_cancellation=False)` — routes through the function
- Asserts `mock_task.delay.assert_called_with(order.id, prescription_fill.id)`

#### 2. `test_process_shopify_order_for_manual_treatment_refill` (line 2052)
Decorated with `@patch("ecomm.utils.send_prescription_refill_request")`.
- `source_name: "shopify_draft_order"` (manual invoice), fill ID passed in `payload["note"]`
- Asserts `is_manual_invoice = True` and `mock_task.delay.assert_called_with(order.id, prescription_fill.id)`

#### 3. `test_process_shopify_order_for_replacement_treatment` (line 2098)
Decorated with `@patch("ecomm.utils.send_prescription_refill_request")`.
- `payload["note"]` = `"replacement-<uuid>"` (replacement fill flow)
- Asserts `mock_task.delay.assert_called_with(order.id, draft_fill.id)`

### Routing Tests (mock the function, test routing logic)

#### 4. `TestUngatedRxOrderRouting` class (lines 3487–3532)
Decorated with `@patch("ecomm.utils.process_shopify_order_for_treatment_refill")` at the class level.
Contains two test methods:
- `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` (line 3507) — verifies `mock_refill.assert_called_once()` when user has valid prescriptions
- `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` (line 3524) — verifies `mock_refill.assert_not_called()`

Note: the routing test only asserts `assert_called_once()` — it does NOT verify the specific arguments (`order`, `payload`, `order_logger`).

---

## What Would Break If the Signature Changes

### Scenario A: Adding a required parameter

Both call sites in `_process_shopify_order_impl` (lines 672 and 682) would need to be updated. Both currently pass `(order, payload, order_logger)`.

### Scenario B: Removing or renaming `payload`

The function body reads extensively from `payload` (note attributes, replacement fill ID). Additionally, the existing integration tests construct specific payload dicts and pass them through `process_shopify_order()` — they would fail or need restructuring.

### Scenario C: Removing `order_logger` (or making it required)

- Both call sites pass `order_logger` as a positional third argument. If removed, both call sites break.
- If made required (removing `= None`), the routing tests that mock the function would still pass (they do not check arguments), but any call without passing `order_logger` would raise a `TypeError`.

### Scenario D: Changing `order` type

The `Order` model is accessed extensively inside the function (`order.user`, `order.email`, `order.cart`, `order.order_number`, `order.status`, `order.otc_treatments`). All four integration tests construct an `Order` via `process_shopify_order()`, which creates the order from the payload, so they would be insensitive to the type annotation change but would break if the actual runtime object type changes.

---

## Summary Table

| Location | Type | Arguments Passed |
|---|---|---|
| `backend/ecomm/utils.py:672` | Caller (prescription line item path) | `(order, payload, order_logger)` |
| `backend/ecomm/utils.py:682` | Caller (ungated RX refill path) | `(order, payload, order_logger)` |
| `backend/ecomm/tests/test_utils.py:2006` | Integration test (direct, via `process_shopify_order`) | n/a — tests via wrapper |
| `backend/ecomm/tests/test_utils.py:2052` | Integration test (direct, via `process_shopify_order`) | n/a — tests via wrapper |
| `backend/ecomm/tests/test_utils.py:2098` | Integration test (direct, via `process_shopify_order`) | n/a — tests via wrapper |
| `backend/ecomm/tests/test_utils.py:3487–3532` | Routing test (mocked) | Mocked — args not asserted |

The backfill script at `backend/scripts/reprocess_subscription_refill_orders.py` does **not** call `process_shopify_order_for_treatment_refill` directly — it re-implements the prescription fill creation logic inline (to avoid re-processing the full webhook payload), so it would be unaffected by a signature change.
