# B1 Exploration Log

## Search 1: Locate the treatment refill Shopify order processing function

Searched for `def.*process.*shopify.*order|def.*refill.*order` across all Python files in `/Users/albertgwo/Work/evvy/backend`.

Found the target function at:

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, line 2089**

```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
    """
    Custom order processing logic for prescription refill, replacement, and otc treatment orders.
    Supports both legacy consult-based orders and new evergreen prescription orders.
    """
```

Parameters:
- `order: Order` — the ORM Order object, already created/fetched before this call
- `payload: dict[str, Any]` — the raw Shopify webhook payload dict
- `order_logger: OrderEventLogger | None = None` — optional structured event logger (defaults to None; function creates one internally if not provided)

Also found related functions at the same file:
- `process_shopify_order` (line 204) — top-level wrapper with error handling
- `_process_shopify_order_impl` (line 238) — main dispatcher that calls the refill function
- `process_shopify_order_for_test` (line 1600)
- `process_shopify_order_for_care` (line 1807)
- `process_shopify_order_for_pcr_add_on` (line 1964)

## Search 2: Find all direct callers of process_shopify_order_for_treatment_refill

Searched for `process_shopify_order_for_treatment_refill\(` across the backend.

Found **two call sites**, both inside `_process_shopify_order_impl` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:

**Call site 1 — line 672** (prescription treatment line-item path):
```python
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

**Call site 2 — line 682** (ungated RX / "UX" order path):
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        logger.info(...)
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        logger.info(...)
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(...)
```

In both call sites the arguments passed are **`(order, payload, order_logger)`** — the same three positional arguments.

`order_logger` at these call sites is always the non-None `OrderEventLogger` instance constructed at the top of `_process_shopify_order_impl` (line 322). The `order_logger: OrderEventLogger | None = None` default in the function signature exists only to support direct calls in tests or scripts, not because callers actually pass `None`.

## Search 3: Understand the broader call chain to the refill function

The entry points that eventually reach `process_shopify_order_for_treatment_refill` are:

1. **Shopify webhook handler** — `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`, line 131:
   ```python
   process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")
   ```
   This calls `process_shopify_order` (the public wrapper), which calls `_process_shopify_order_impl`, which routes to `process_shopify_order_for_treatment_refill`.

2. **Shopify tasks** — `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`:
   - `process_shopify_order_from_api()` (line 20) calls `process_shopify_order(shopify_payload, is_order_cancellation=...)`
   - Called by `process_unprocessed_shopify_orders_by_email()` (line 48) and `process_unprocessed_shopify_orders_by_checkout_token()` (line 54)
   - Also called by the `retry_failed_shopify_orders` Celery task (line 61)

No code calls `process_shopify_order_for_treatment_refill` directly from outside `ecomm/utils.py` (the two call sites are the only invocations).

## Search 4: Examine what the function does with each argument

Read the full body of `process_shopify_order_for_treatment_refill` (lines 2089–2201):

- **`order`** is used to:
  - Get/create `PrescriptionFill` via `PrescriptionFill.objects.get_or_create(order=order, user=order.user)`
  - Set `order.user` and call `order.save()`
  - Set `prescription_fill.order = order` and save
  - Create `PrescriptionFillOrder(prescription_fill=..., order=order)`
  - Call `get_care_products_from_orders([order])`
  - Filter `Prescription.objects.filter(user=order.user, ...)`
  - Read `order.otc_treatments.all()`
  - Check `order.status != Order.STATUS_CANCELLED`
  - Pass `order.id` to `send_prescription_refill_request.delay(order.id, prescription_fill.id)`

- **`payload`** is used to:
  - Call `_parse_order_note_attributes(payload)` — extracts `prescription_fill_id`, `consult_uid`, `user_account_email`, `prescription_ids`, `cart_id` from `note_attributes`
  - Call `_parse_replacement_fill_id(payload)` — extracts replacement fill ID from `note` field

- **`order_logger`** is referenced in the function signature but is **not actually used in the function body** (no calls to `order_logger.*` appear inside `process_shopify_order_for_treatment_refill`). The parameter exists for API consistency with `process_shopify_order_for_care` and similar functions, but the function currently ignores it.

## Search 5: Find test coverage

Located tests in `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py`.

**Tests that directly test `process_shopify_order_for_treatment_refill` behavior** (all in `class TestUtils(TestCase)`, lines 65+):

| Test name | Line | What it covers |
|---|---|---|
| `test_process_shopify_order_for_treatment_refill` | 2006 | Standard refill: `note_attributes` with `prescription_fill_id`, user email lookup, task called with correct order+fill IDs |
| `test_process_shopify_order_for_manual_treatment_refill` | 2052 | Manual (draft) invoice order: `source_name="shopify_draft_order"`, fill ID in `note` field |
| `test_process_shopify_order_for_replacement_treatment` | 2097 | Replacement: `note` field contains `"replacement-{fill_id}"`, routes to same function |
| `test_process_shopify_order_for_otc_treatments` | 2141 | OTC (non-Rx) products only: `_lineEvvyTreatmentSlug` property, OTC treatments attached to consult |

**Tests that verify routing TO the refill function** (in `class TestUngatedRxOrderRouting(TestCase)`, line 3489):

| Test name | Line | What it covers |
|---|---|---|
| `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` | 3507 | Ungated RX (UX) order with valid prescriptions → routes to refill function |
| `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` | 3524 | Ungated RX without prescriptions → routes to consult, NOT refill |

All direct tests call `process_shopify_order(payload, is_order_cancellation=False)` and let it route through `_process_shopify_order_impl` — there are **no tests that call `process_shopify_order_for_treatment_refill` directly**. The routing tests use `@patch("ecomm.utils.process_shopify_order_for_treatment_refill")` to intercept the call and verify `mock_refill.assert_called_once()`.

## Search 6: Check for any other callers (scripts, management commands)

Searched the scripts directory for `process_shopify_order_for_treatment_refill`.

Found `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` — this script does **not** call `process_shopify_order_for_treatment_refill` directly. Instead it **reimplements** the same logic inline (creates prescription fills, calls `create_prescription_fill_prescriptions`, `create_prescription_fill_otc_treatments`, `send_prescription_refill_request.delay`). The script docstring explicitly mentions it was written because recurring subscription orders were being routed to the wrong function.

## Final Answer

### The Function

**`process_shopify_order_for_treatment_refill`** is defined at:

```
/Users/albertgwo/Work/evvy/backend/ecomm/utils.py, line 2089
```

Current signature:
```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
```

### All Callers

There are exactly **two call sites**, both inside `_process_shopify_order_impl` in the same file:

**1. Line 672 — Prescription treatment line-item path:**
```python
process_shopify_order_for_treatment_refill(order, payload, order_logger)
```
Triggered when the order has at least one line item of type `ORDER_TYPE_PRESCRIPTION_TREATMENT` and the overall order type is not `A_LA_CARTE`, `MIXED_CARE`, `DYNAMIC_BUNDLE`, `UNGATED_RX`, or `MALE_PARTNER`.

**2. Line 682 — Ungated RX (UX) order path:**
```python
process_shopify_order_for_treatment_refill(order, payload, order_logger)
```
Triggered when the order type is `ORDER_TYPE_UNGATED_RX`, there is a user on the order, and `can_refill_entire_order(order.user, order)` returns True (all Rx products have valid, non-expired prescriptions with refills remaining).

Both callers pass:
- `order` — the `Order` ORM instance, already persisted to the DB
- `payload` — the raw Shopify webhook dict
- `order_logger` — a fully initialized `OrderEventLogger` (never `None` from these callers)

No external callers (no views, tasks, scripts, or management commands) invoke this function directly. The public entry point is always `process_shopify_order(payload, is_order_cancellation)`.

### What Would Break if the Signature Changes

**Changing `order` (first parameter):**
- Both callers at lines 672 and 682 pass the `Order` ORM object. The function accesses `order.user`, `order.id`, `order.email`, `order.cart`, `order.order_number`, `order.status`, `order.otc_treatments`, and calls `order.save()`. Any change to this parameter type would break both call sites.

**Changing `payload` (second parameter):**
- The function calls `_parse_order_note_attributes(payload)` to extract `prescription_fill_id`, `consult_uid`, `user_account_email`, `prescription_ids`, and `cart_id` from `payload["note_attributes"]`.
- It also calls `_parse_replacement_fill_id(payload)` which reads `payload["note"]`.
- Both call sites pass the raw Shopify webhook dict. If `payload` were removed or changed to a parsed struct, the internal helper calls would break.

**Changing `order_logger` (third parameter):**
- Currently `order_logger` is accepted but **never used** inside the function body. Removing it would only affect the two call sites at lines 672 and 682, which always pass it positionally. The `| None = None` default means existing tests calling the function without `order_logger` would still work.

**Adding a new required parameter:**
- Both call sites at lines 672 and 682 would fail with a `TypeError` at runtime (missing argument).
- All four tests in `TestUtils` that call `process_shopify_order(...)` and route through to the refill function would break.
- The two routing tests in `TestUngatedRxOrderRouting` mock the function, so they would NOT break if a new parameter is added (the mock accepts any arguments).

### Test Coverage

Tests are in `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py`.

**Directly testing the refill function's behavior** (class `TestUtils`, all using `@patch("ecomm.utils.send_prescription_refill_request")`):

- **Line 2006** — `test_process_shopify_order_for_treatment_refill`: standard refill with `prescription_fill_id` in `note_attributes`, user resolved by email. Asserts `mock_task.delay.assert_called_with(order.id, prescription_fill.id)`.
- **Line 2052** — `test_process_shopify_order_for_manual_treatment_refill`: draft order (`source_name="shopify_draft_order"`), fill ID in `note` field. Asserts `order.is_manual_invoice` is True.
- **Line 2097** — `test_process_shopify_order_for_replacement_treatment`: replacement scenario where `note` contains `"replacement-{fill_id}"`.
- **Line 2141** — `test_process_shopify_order_for_otc_treatments`: OTC-only products without prescriptions; verifies OTC treatments are attached to an existing active consult.

**Routing tests** (class `TestUngatedRxOrderRouting`, line 3489):
- **Line 3507** — verifies UX order with valid prescriptions routes to `process_shopify_order_for_treatment_refill` (uses mock patch).
- **Line 3524** — verifies UX order without prescriptions does NOT route to the refill function.

**No tests call `process_shopify_order_for_treatment_refill` directly** — all go through `process_shopify_order(payload, is_order_cancellation=False)`.

### Notable Gaps

1. The `order_logger` parameter is unused inside the function (no `order_logger.log_event(...)` calls), so there is no test asserting logger behavior for this function path.
2. The script at `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` duplicates the logic rather than calling the function, so changes to `process_shopify_order_for_treatment_refill` will NOT automatically fix historical reprocessing runs — that script would need a separate update.
3. Error path coverage is limited: the test for invalid `prescription_ids` format (line 2163 in the function) has no corresponding test case.
