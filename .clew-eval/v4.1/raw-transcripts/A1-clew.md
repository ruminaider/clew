# A1-clew Raw Transcript

**Agent ID:** a00aef7ec6e9dcda0
**Tool:** clew (Bash + Read)
**Test:** A1 — Subscription renewal → PrescriptionFill creation failure
**Tool calls:** 24
**Tokens:** 71,227

## Final Answer

## Code Path: Order Webhook to PrescriptionFill Creation

### Entry Point: Shopify Webhook

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 80-145)

The webhook handler `shopify_webhook_view` receives `orders/create` or `orders/cancelled` events from Shopify. It:
1. Verifies the HMAC signature using `SHOPIFY_WEBHOOK_SECRET` (returns 403 if invalid)
2. Calls `process_shopify_order(payload, is_order_cancellation=...)` for both event types

**Failure Point 1:** If the HMAC signature fails (misconfigured secret, payload corruption), the webhook is rejected with a 403 and the order is never processed.

---

### Stage 1: Main Order Processing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `_process_shopify_order_impl()` (lines 238-790)

This large function handles the full order pipeline. For subscription renewals, the critical path is:

1. **Subscription detection** — The `app_id` in the payload is checked against `SHOPIFY_RECHARGE_APP_ID` (line 836). If the order comes from Recharge, `_determine_checkout_source()` returns `Order.CHECKOUT_SOURCE_SUBSCRIPTION` and all line items have `is_recurring_order_item = True` set (line 1491).

2. **Order type classification** — `_get_overall_order_type_and_sku_from_line_items()` classifies the order. For subscription refills with prescription treatment SKUs, the `line_item_order_types` list will contain `Order.ORDER_TYPE_PRESCRIPTION_TREATMENT`.

3. **Routing to refill path** — At lines 660-672, if the order type is NOT one of the bundle/care/mixed types AND the line items include `ORDER_TYPE_PRESCRIPTION_TREATMENT`, then `process_shopify_order_for_treatment_refill()` is called.

**Failure Point 2:** If the `app_id` is missing or not recognized as Recharge, `is_recurring_order_item` will not be set, and the order may be misclassified.

**Failure Point 3:** If the subscription renewal order SKU maps to a line item order type other than `ORDER_TYPE_PRESCRIPTION_TREATMENT`, the routing guard at line 661 will not pass and `process_shopify_order_for_treatment_refill` will never be called.

---

### Stage 2: `process_shopify_order_for_treatment_refill()`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 2089-2202

**Step 1 — Parse note attributes** (lines 2097-2099):
Extracts `prescription_fill_id`, `consult_uid`, `user_account_email`, and `prescription_ids` from `payload["note_attributes"]`. For Recharge subscription renewals, these note attributes are typically NOT present.

**Failure Point 4:** If a `prescription_fill_id` IS present but references a non-existent UUID, `PrescriptionFill.objects.get(id=prescription_fill_id)` will raise `PrescriptionFill.DoesNotExist` (line 2103), crashing the entire function.

**Step 2 — Get or create PrescriptionFill** (lines 2102-2108):
- If a valid `prescription_fill_id` is in the notes, it uses that existing fill.
- Otherwise, does `PrescriptionFill.objects.get_or_create(order=order, user=order.user)`.

**Failure Point 5:** If `order.user` is `None` at this point, the `get_or_create` lookup omits the `user` filter, potentially matching an existing fill for a different user on the same order.

**Step 3 — User resolution** (lines 2121-2138):
Tries four fallback strategies in order:
1. `order_attrs.user_account_email` (from note attributes)
2. `order.cart.user` (from linked cart)
3. `consult.user` (from linked consult)
4. `order.email` (from Shopify order email field)

**Failure Point 6:** If none of these resolve to a user, the function continues with `user = None`. This means `order.user` stays None and the prescription lookup falls through.

**Step 4 — Prescription lookup** (lines 2150-2180):

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

**Failure Point 7:** If the user has no active `Prescription` records matching the ordered products, the queryset is empty.

**Failure Point 8:** If `ordered_products` is empty because `get_care_products_from_orders` found no `care_product` on the line items, the prescription filter returns nothing.

**Step 5 — Early return if no prescriptions or OTC treatments** (lines 2184-2189):

```python
if not prescriptions.exists() and not otc_treatments.exists():
    logger.error(
        f"No prescriptions and no otc treatments found for order {order.order_number}. "
        "Unable to send prescription fill request to precision."
    )
    return  # <<< SILENT FAILURE
```

**Failure Point 9 (most common):** This is the most common silent failure mode. The function logs an error and returns without creating the PrescriptionFill or raising an exception. This will not retry automatically.

**Step 6 — Create PrescriptionFillPrescriptions records** (lines 2192-2195):
Creates join table records linking each `Prescription` to the `PrescriptionFill`.

**Step 7 — Dispatch Celery task** (line 2198):
```python
send_prescription_refill_request.delay(order.id, prescription_fill.id)
```

---

### Stage 3: `send_prescription_refill_request` Celery Task

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, lines 157-267

**Failure Point 10 — State restriction check** (lines 199-210):
If the patient's shipping state is unsupported, creates a `ConsultTask` with type `TASK_TYPE_TREATMENT_REFILL_FAILURE` and returns early.

**Failure Point 11 — Refills remaining check** (lines 212-223):
If any prescription has 0 remaining refills, the task raises an exception (Celery retries). A `ConsultTask` is also created.

**Failure Point 12 — Prescription status transition** (lines 225-227):
If the fill was already in a non-DRAFT status, this will silently overwrite the status.

**Failure Point 13 — Precision API errors** (lines 232-266):
The task calls `send_create_patient_request_to_precision()`, `send_create_prescription_request_to_precision()`, and `send_fill_request_to_precision()`. Any can fail, causing Celery retry.

---

### Summary of Failure Points

| # | Location | Failure Mode | Symptom |
|---|----------|-------------|---------|
| 1 | `webhooks.py:94` | HMAC verification fails | 403, webhook dropped entirely |
| 2 | `utils.py:1487-1491` | Recharge `app_id` not recognized | Line items not flagged as recurring |
| 3 | `utils.py:660-672` | SKU maps to wrong order type | Refill function never called |
| 4 | `utils.py:2103` | Invalid `prescription_fill_id` UUID | Unhandled `DoesNotExist` exception |
| 5 | `utils.py:2106-2108` | `order.user` is None during `get_or_create` | PrescriptionFill may be mis-keyed |
| 6 | `utils.py:2121-2133` | All user resolution strategies fail | No prescriptions found |
| 7 | `utils.py:2170-2176` | No active `Prescription` for ordered products | Early return |
| 8 | `utils.py:2146` | Line item `care_product` not set | Empty product list |
| 9 | `utils.py:2184-2189` | No prescriptions AND no OTC treatments | **Silent log + return** |
| 10 | `tasks.py:199-210` | Shipping state not supported | ConsultTask created |
| 11 | `tasks.py:212-223` | Prescription out of refills | Exception + ConsultTask |
| 12 | `tasks.py:226-227` | Duplicate webhook | Status overwritten silently |
| 13 | `tasks.py:232-266` | Precision pharmacy API failure | Task retried |

### Most Likely Cause

The most common root cause for "subscription renewal didn't create a prescription fill" is **Failure Point 9** (lines 2184-2189). This happens when the user's Prescription records can't be matched to the ordered products, the user account email doesn't match any Evvy user, or the line items have no `care_product` linked.
