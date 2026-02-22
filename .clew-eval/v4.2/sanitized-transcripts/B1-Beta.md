# B1: Shopify Order Processing for Treatment Refills

## Target Function

**`process_shopify_order_for_treatment_refill`**

File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, line 2089

### Signature

```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
```

**Parameters:**
- `order: Order` — Django ORM model instance of the ecomm Order
- `payload: dict[str, Any]` — The raw Shopify webhook JSON payload (dict)
- `order_logger: OrderEventLogger | None = None` — Optional monitoring/logging object (defaults to None)

### What the function does (summary)

1. Parses `note_attributes` from `payload` to extract `prescription_fill_id`, `cart_id`, `consult_uid`, `user_account_email`, and `prescription_ids`
2. Parses `payload["note"]` for a replacement fill ID (handles "replacement-{id}" prefixes)
3. Looks up or creates a `PrescriptionFill` by the parsed ID, or by `(order, user)` if no ID is present
4. Resolves the user from note attributes, cart, consult, or order email (in that priority order)
5. Associates the fill with the order via `PrescriptionFillOrder`
6. Resolves prescriptions — either by explicit `prescription_ids` in note attributes, or by querying user's active prescriptions for the ordered products
7. Finds OTC treatments on the order
8. Calls `create_prescription_fill_prescriptions` and `create_prescription_fill_otc_treatments`
9. Dispatches `send_prescription_refill_request.delay(order.id, prescription_fill.id)` (async Celery task)
10. Calls `mark_order_cart_as_purchased` if a cart ID is present

---

## Callers

There are **two call sites** in the main codebase, both inside `_process_shopify_order_impl` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`.

### Call site 1 — Line 672

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

**Arguments passed:**
- `order` — the `Order` object that was created/retrieved earlier in `_process_shopify_order_impl`
- `payload` — the full raw Shopify webhook dict passed into `_process_shopify_order_impl`
- `order_logger` — the `OrderEventLogger` instance created by `create_order_logger()` in the public wrapper `process_shopify_order`

### Call site 2 — Line 682

```python
# Ungated RX orders: route to refill path if all Rx products have valid prescriptions,
# otherwise fall back to consult/intake path.
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        logger.info(...)
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        ...
```

**Arguments passed:** Same pattern — `order`, `payload`, `order_logger`. This path is only reached for `ORDER_TYPE_UNGATED_RX` orders where the user has valid prescriptions for all Rx products in the order.

### Entry Point

Both call sites are reached exclusively through the public entry point:

```python
# /Users/albertgwo/Work/evvy/backend/ecomm/utils.py, line 204
def process_shopify_order(payload: dict[str, Any], is_order_cancellation: bool):
    """Wrapper for order processing with comprehensive error handling and monitoring."""
    order_logger = create_order_logger()
    return _process_shopify_order_impl(payload, is_order_cancellation, order_logger)
```

There are **no direct calls** to `process_shopify_order_for_treatment_refill` from outside `utils.py` in production code. The backfill script (`reprocess_subscription_refill_orders.py`) reimplements equivalent logic directly rather than calling this function.

---

## What `payload` Is Used For Inside the Function

The function consumes the following fields from `payload`:
- `payload["note_attributes"]` — list of `{name, value}` dicts; parsed for `prescription_fill_id`, `cart_id`, `consult_uid`, `user_account_email`, `prescription_ids`
- `payload["note"]` — plain-text string; used as fallback fill ID for manual draft orders, with prefix stripping ("replacement-", "OID", etc.)

No other fields from `payload` are read directly inside `process_shopify_order_for_treatment_refill` itself (other fields like `email` and `line_items` have already been used higher up to construct the `Order` object before this function is called).

---

## Test Coverage

### Direct integration tests (via `process_shopify_order`)

All tests are in `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py` inside the `TestUtils` class (line 65).

**1. `test_process_shopify_order_for_treatment_refill` (line 2006)**
- Decorated with `@patch("ecomm.utils.send_prescription_refill_request")`
- Constructs a payload with `note_attributes: [{name: "prescription_fill_id", value: <id>}]`
- Asserts `order.business_verticals`, `order.user_id`, and `mock_task.delay.assert_called_with(order.id, prescription_fill.id)`

**2. `test_process_shopify_order_for_manual_treatment_refill` (line 2052)**
- Decorated with `@patch("ecomm.utils.send_prescription_refill_request")`
- Payload uses `note: str(prescription_fill.id)` and `source_name: "shopify_draft_order"` (manual invoice path)
- Asserts `order.is_manual_invoice` is `True` and task called correctly

**3. `test_process_shopify_order_for_replacement_treatment` (line 2098)**
- Decorated with `@patch("ecomm.utils.send_prescription_refill_request")`
- Payload uses `note: f"replacement-{str(draft_fill.id)}"` (replacement prefix parsing)
- Asserts task called with `(order.id, draft_fill.id)`

**4. `test_process_shopify_order_for_otc_treatments` (line 2141)**
- No mock on `send_prescription_refill_request` — exercises OTC treatment path
- Uses `_lineEvvyTreatmentSlug` line item properties
- Asserts `otc_treatments.count() == 2` and proper `ConsultOTCTreatment` associations

### UX/Ungated RX routing tests (mock-based)

In `TestUngatedRxOrderRouting` class (line 3489), decorated with:
```python
@patch("ecomm.utils.process_shopify_order_for_treatment_refill")
@patch("ecomm.utils.add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult")
```

**5. `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` (line 3507)**
- Asserts `mock_refill.assert_called_once()` when user has valid prescriptions

**6. `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` (line 3524)**
- Asserts `mock_refill.assert_not_called()` when no prescriptions exist

---

## Impact Analysis: What Would Break If the Signature Changes

### If `order` parameter is renamed or reordered:
- Both call sites in `_process_shopify_order_impl` (lines 672 and 682) pass positionally: `process_shopify_order_for_treatment_refill(order, payload, order_logger)` — would break if positional order changes.

### If `payload` parameter is renamed or reordered:
- Same two call sites pass it positionally as the second argument — would break.

### If `order_logger` is made required (remove default `None`):
- The function already has a default of `None`, and the logger is not used inside `process_shopify_order_for_treatment_refill` itself (confirmed by reading the full body — it only calls `logger.error/warning` using the module-level logger, not `order_logger`). However, all call sites already pass it, so this would not immediately break callers. But changing it to required would be a source-incompatible change.

### If the function signature adds a new required parameter:
- Both internal call sites at lines 672 and 682 would need to be updated.
- The test suite calls this function only indirectly via `process_shopify_order(payload, is_order_cancellation=False)`, except tests 5 and 6 which mock the function entirely. Tests 1–4 would fail at the call site inside `_process_shopify_order_impl` if a required argument is missing.

### If `payload` is replaced with structured data (e.g., a parsed object):
- The function itself reads `payload` only via `_parse_order_note_attributes(payload)` and `_parse_replacement_fill_id(payload)` — both of which access `payload["note_attributes"]` and `payload["note"]`. All higher-level processing (line items, email, shipping) happens before this function is called. Replacing `payload` with a structured type would require updating those two helper functions and the two call sites.

### Backfill script:
The script at `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` does **not** call `process_shopify_order_for_treatment_refill` directly — it reimplements equivalent logic inline (lines 160–235). A signature change would not affect it, but it would remain out of sync with any new logic added to the canonical function.

---

## File Reference Summary

| File | Lines | Role |
|------|-------|------|
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | 2089–2201 | Function definition |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | 660–692 | Both call sites (inside `_process_shopify_order_impl`) |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | 204–234 | Public entry point `process_shopify_order` |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | 2037–2086 | Helper parsers `_parse_order_note_attributes`, `_parse_replacement_fill_id` |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py` | 2005–2204 | Tests 1–4 (direct integration via `process_shopify_order`) |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py` | 3487–3533 | Tests 5–6 (UX routing, function mocked) |
| `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` | 1–235 | Backfill script (reimplements logic, does not call function) |
