# A1: Subscription Renewal to PrescriptionFill — Code Path Investigation

## Summary

A subscription renewal creates a Shopify order via ReCharge. That order arrives as an `orders/create` webhook. The code routes it through `process_shopify_order_for_treatment_refill`, which creates or looks up a `PrescriptionFill`, attaches prescriptions to it, then dispatches the async task `send_prescription_refill_request` to send the fill to the Precision pharmacy. There are many guard clauses along this path; any of them silently returning early will leave the PrescriptionFill un-created or un-submitted.

---

## Full Code Path

### 1. Webhook Entry Point

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 82–145)

The `shopify_webhook_view` function receives the `orders/create` Shopify webhook, verifies the HMAC signature (`_verify_hmac_webhook`), and calls `process_shopify_order(payload, is_order_cancellation=False)`.

```python
if shopify_topic == "orders/create" or shopify_topic == "orders/cancelled":
    process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")
```

**Failure point:** If HMAC verification fails (misconfigured `SHOPIFY_WEBHOOK_SECRET`), the webhook returns 403 and no processing occurs.

---

### 2. Top-Level Order Dispatcher

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 204–234)

`process_shopify_order` is a thin error-handling wrapper that calls `_process_shopify_order_impl`. Any uncaught exception is logged to NewRelic and re-raised (the response to Shopify is still 200 from the view level, but the fill is not created).

---

### 3. Core Order Processing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 238–760)

`_process_shopify_order_impl` does the heavy lifting:

1. Creates or retrieves the `Order` via `Order.objects.get_or_create(provider=Order.PROVIDER_SHOPIFY, provider_id=order_number)`.
2. Processes each line item via `process_order_line_item`, which sets `line_item.is_recurring_order_item = True` when `app_id == SHOPIFY_RECHARGE_APP_ID` (294517). This propagates to `is_recurring_subscription_order = True`.
3. Determines overall `order_type` via `_get_overall_order_type_and_sku_from_line_items`. For recurring subscription orders, the `purchase_type` note attribute is deliberately ignored to avoid incorrect carryover from the original order.
4. Routes to the appropriate handler based on `order_type`.

**Critical routing logic (lines 660–672):**

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

**Failure points:**
- If the SKU is not in `get_all_treatment_skus()`, `_get_order_type_from_sku` returns `ORDER_TYPE_OTHER` and the line item is typed `ORDER_TYPE_PRESCRIPTION_TREATMENT` only if the SKU matches `ALL_TREATMENT_REFILL_SKUS` (BA, VP, OA refill SKUs). A new or unregistered refill SKU will silently skip the refill path.
- If the order's `order_type` is `A_LA_CARTE`, `MIXED_CARE`, `DYNAMIC_BUNDLE`, `UNGATED_RX`, or `MALE_PARTNER`, the check above is skipped entirely and `process_shopify_order_for_treatment_refill` is never called.

---

### 4. Treatment Refill Order Processing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 2089–2201)

`process_shopify_order_for_treatment_refill` creates the `PrescriptionFill` and dispatches the pharmacy task:

#### Step 1–2: Find or create PrescriptionFill

```python
prescription_fill_id = order_attrs.prescription_fill_id or replacement_fill_id
if prescription_fill_id and _is_valid_uuid(prescription_fill_id):
    prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)
else:
    lookup_params = {"order": order}
    if order.user:
        lookup_params["user"] = order.user
    prescription_fill, _ = PrescriptionFill.objects.get_or_create(**lookup_params)
```

**Failure points:**
- If `prescription_fill_id` in the note attributes is not a valid UUID and a prior fill exists for the same `(order, user)` pair, `get_or_create` returns the existing draft fill, which is correct. But if the order has no `user` set yet (user lookup failed), the fill is created with `user=None`, potentially creating duplicate fills later when user is attached.

#### Step 3: User resolution

The function tries to find the user via `order_attrs.user_account_email`, then `order.cart.user`, then `consult.user`, then `order.email`. If all fail, `user` remains `None`.

**Failure point:** If no user is resolved, `order.user` is never set. The prescription lookup at step 5 (`Prescription.objects.filter(user=order.user, ...)`) will return an empty queryset, causing an early return at line 2184–2189 with an error log but no exception raised. The Celery task is never dispatched.

#### Step 5: Find prescriptions

```python
elif order.user:
    prescriptions = (
        Prescription.objects.filter(
            user=order.user, product__in=ordered_products, deleted=False
        )
        .order_by("product_id", "create_date")
        .distinct("product_id")
    )
```

**Failure points:**
- No `Prescription` exists for the user and product (expired, deleted, or never created).
- `ordered_products` is empty because the line items couldn't be matched to care products in `get_care_products_from_orders`.

#### Step 6: Guard clause before pharmacy task

```python
if not prescriptions.exists() and not otc_treatments.exists():
    logger.error(
        f"No prescriptions and no otc treatments found for order {order.order_number}. "
        "Unable to send prescription fill request to precision."
    )
    return   # <-- SILENT EARLY RETURN
```

**This is a critical failure point:** The function returns without creating the PrescriptionFill records or dispatching the pharmacy task. The only signal is a logger.error entry, which may not trigger an alert.

#### Step 7: Dispatch async task

```python
send_prescription_refill_request.delay(order.id, prescription_fill.id)
```

This is a Celery task — failure here is invisible at the point of dispatch.

---

### 5. Celery Task: send_prescription_refill_request

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 156–267)

This task does the actual pharmacy interaction:

1. Checks if the order is cancelled → tries to cancel the fill at Precision.
2. If there are prescriptions, validates:
   a. **State check** (lines 199–210): calls `verify_shipping_address_for_prescription_refill`. If the shipping state is not in `VALID_STATES`, creates a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` and returns early.
   b. **Refill count check** (lines 212–223): calls `get_all_prescriptions_have_remaining_refills`. If `prescription.num_allowed_refills - prescription.fill_count < 0`, raises an exception AND creates a failure task.
3. Updates the PrescriptionFill status from `draft` → `created`.
4. Calls `send_create_patient_request_to_precision`.
5. Calls `send_create_prescription_request_to_precision` for each prescription.
6. Calls `send_fill_request_to_precision` to actually place the order.

**Failure points:**
- **State restriction** (lines 202–210): user's shipping address is in an unsupported state. Returns early, creates a `ConsultTask` but the fill is never sent.
- **No refills remaining** (lines 212–223): `prescription.num_allowed_refills - prescription.fill_count < 0`. Note: this check does NOT use `Prescription.can_refill` (which checks `expiration_date`, `is_refillable_product`, and `is_disabled_for_refill`). It only checks fill count. So a prescription that is expired or disabled may still pass this check and proceed. Conversely, a prescription with exactly 0 remaining (fill_count == num_allowed_refills) is permitted (condition is strictly `< 0`).
- **Precision API failures** in `send_create_patient_request_to_precision` or `send_fill_request_to_precision`: these are synchronous calls within the Celery task. An HTTP error will raise an exception that will cause Celery to retry (if configured) or drop the task.
- **Missing consult** on legacy orders: `consult = prescription_fill.consult` may be `None` for evergreen prescription orders. The code handles this (`consult.uid if consult else None`), but if the downstream call requires a consult, it will fail.

---

### 6. Prescription.can_refill vs. Task's Refill Check

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 659–666)

```python
@property
def can_refill(self):
    return (
        self.refills_remaining > 0
        and self.is_refillable_product
        and self.expiration_date > get_current_time().date()
        and not self.product.is_disabled_for_refill
        and not self.product.is_deprecated
    )
```

The `can_refill_entire_order` function used for Ungated RX routing (line 2732) uses `Prescription.can_refill`. But the `send_prescription_refill_request` Celery task uses `get_all_prescriptions_have_remaining_refills` (line 212), which only checks `num_allowed_refills - fill_count < 0` — not `expiration_date`, `is_disabled_for_refill`, or `is_deprecated`. This inconsistency means:

- An **expired prescription** will pass the task's check but fail at `can_refill_entire_order` (for Ungated RX). For legacy subscription refill orders, the expired prescription will go through to Precision, which may reject it.
- A **deprecated or disabled product** can pass the task's refill count check.

---

## Complete Failure Point Summary

| # | Location | Failure Mode | Signal |
|---|----------|-------------|--------|
| 1 | `webhooks.py:90–104` | HMAC verification fails | 403 response; logged |
| 2 | `utils.py:262–272` | Payload has no line items | `logger.warning`; returns |
| 3 | `utils.py:1486–1491` | `app_id` != `SHOPIFY_RECHARGE_APP_ID` | Order not flagged as recurring; may get wrong order_type |
| 4 | `utils.py:660–672` | SKU not in treatment refill set OR order_type is a care type | `process_shopify_order_for_treatment_refill` never called |
| 5 | `utils.py:2121–2133` | User not resolvable from email/consult/cart | `order.user` is None; prescription lookup returns nothing |
| 6 | `utils.py:2168–2189` | No prescriptions and no OTC treatments found | `logger.error`; early return — no Celery task dispatched |
| 7 | `tasks.py:199–210` | Shipping state not in `VALID_STATES` | `ConsultTask` failure record; returns without sending |
| 8 | `tasks.py:212–223` | No refills remaining (`fill_count > num_allowed_refills`) | `ConsultTask` failure record; exception raised |
| 9 | `tasks.py:232+` | Precision API failures | Celery task exception; retry/drop depending on config |
| 10 | `care/models.py:659` | Expired prescription passes task check but not `can_refill` | Prescription sent to Precision; Precision may reject |

---

## Key Files

- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` — webhook entry points
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — `process_shopify_order`, `_process_shopify_order_impl`, `process_shopify_order_for_treatment_refill`, `can_refill_entire_order`
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — `send_prescription_refill_request` Celery task
- `/Users/albertgwo/Work/evvy/backend/care/models.py` — `PrescriptionFill` model, `Prescription.can_refill`
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` — `create_prescription_fill_prescriptions`
- `/Users/albertgwo/Work/evvy/backend/consults/service.py` — `get_all_prescriptions_have_remaining_refills`
- `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` — `SHOPIFY_RECHARGE_APP_ID`, `ALL_TREATMENT_REFILL_SKUS`
