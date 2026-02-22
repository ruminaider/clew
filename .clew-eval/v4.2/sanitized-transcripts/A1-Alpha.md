# A1: Order Webhook to PrescriptionFill — Failure Investigation

## Summary

A subscription renewal in this system goes through **two independent paths**: the **ReCharge webhook** (which only sends analytics events, NOT order processing) and the **Shopify `orders/create` webhook** (which is the actual order processor). The PrescriptionFill is created exclusively on the Shopify path. Failures can occur at 7+ distinct gates along the way.

---

## Full Code Path

### Step 1: Shopify Webhook Entry Point

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`, lines 82–145

```python
def shopify_webhook_view(request):
    ...
    if shopify_topic == "orders/create" or shopify_topic == "orders/cancelled":
        process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")
    return HttpResponse(status=200)
```

The HMAC signature is verified first (line 90–104). If verification fails, the webhook returns 403 and no order is processed.

---

### Step 2: Core Order Processing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `_process_shopify_order_impl`, lines 238–790

The order object is created (or fetched if idempotent) and decorated with metadata. Key early-exit conditions:

- **No line items** (line 262–272): logs a warning and returns immediately with no PrescriptionFill.
- **Cancelled order** (line 397): sets `ORDER_STATUS_CANCELLED`, which propagates downstream.

The function iterates over line items and calls `process_order_line_item()` to determine `order_type`. For subscription refill renewals, `is_recurring_subscription_order` is set to `True` (line 493–494).

---

### Step 3: Routing to Prescription Refill Path

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 660–692

There are **two separate code paths** that can invoke `process_shopify_order_for_treatment_refill`:

**Path A — Recurring subscription line items (line 661–672):**
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

**Path B — Ungated RX orders (line 676–682):**
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

**Failure points here:**
- If `order_type` lands in the excluded list (A_LA_CARTE, MIXED_CARE, etc.), Path A is skipped entirely — no PrescriptionFill.
- For UX orders, `order.user` must be set. If user resolution fails, Path B is skipped.
- For UX orders, `can_refill_entire_order()` must return `True`. If any Rx product has no valid prescription, the order falls through to the consult/intake path instead.

---

### Step 4: `process_shopify_order_for_treatment_refill`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 2089–2201

```python
def process_shopify_order_for_treatment_refill(order, payload, order_logger):
    # 1. Parse order note attributes
    order_attrs = _parse_order_note_attributes(payload)  # looks for prescription_fill_id, consult_uid, prescription_ids, user_account_email
    replacement_fill_id = _parse_replacement_fill_id(payload)
    prescription_fill_id = order_attrs.prescription_fill_id or replacement_fill_id

    # 2. Get or create PrescriptionFill
    if prescription_fill_id and _is_valid_uuid(prescription_fill_id):
        prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)   # <-- can raise DoesNotExist
    else:
        prescription_fill, _ = PrescriptionFill.objects.get_or_create(order=order, user=order.user)

    # 3. Resolve user
    user = User.objects.filter(email__iexact=...).first()  # tries user_account_email, cart user, consult user, order email

    # 4. Associate order to PrescriptionFill
    prescription_fill.order = order
    prescription_fill.save()

    # 5. Find prescriptions
    if order_attrs.prescription_ids:
        prescriptions = Prescription.objects.filter(id__in=prescription_id_list)
        # raises if prescription.user != order.user
    elif order.user:
        prescriptions = Prescription.objects.filter(
            user=order.user, product__in=ordered_products, deleted=False
        ).order_by("product_id", "create_date").distinct("product_id")
    else:
        logger.warning(...)  # no prescriptions resolved

    # 6. If neither prescriptions nor OTC treatments exist — EARLY RETURN (no fill sent)
    if not prescriptions.exists() and not otc_treatments.exists():
        logger.error("No prescriptions and no otc treatments found...")
        return

    # 7. Create fill links
    if prescriptions.exists():
        create_prescription_fill_prescriptions(prescription_fill, list(prescriptions), [order])
    if otc_treatments.exists() and order.status != Order.STATUS_CANCELLED:
        create_prescription_fill_otc_treatments(...)

    # 8. Dispatch async task
    send_prescription_refill_request.delay(order.id, prescription_fill.id)
```

**Failure points:**
- `prescription_fill_id` provided but UUID is invalid or doesn't exist in DB → `PrescriptionFill.DoesNotExist` exception.
- User resolution fails: if `user_account_email` is missing/wrong, cart has no user, no consult, and order email doesn't match a user — `order.user` remains `None`.
- `prescription_ids` in note attributes references a prescription owned by a different user → exception raised (lines 2158–2162).
- No prescriptions found AND no OTC treatments → function returns early without calling `send_prescription_refill_request` (line 2184–2189).
- Evergreen prescription lookup (the `elif order.user:` branch) finds no match because `deleted=True` or the product doesn't match a line item.

---

### Step 5: `send_prescription_refill_request` Celery Task

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, lines 157–267

```python
def send_prescription_refill_request(order_id, prescription_fill_id):
    ...
    if order.status == Order.STATUS_CANCELLED:
        # tries to cancel fill in Precision; returns early
        ...

    if prescriptions.exists():
        # Gate 1: verify shipping address is in a supported state
        invalid_state_code, shipping_address = verify_shipping_address_for_prescription_refill(...)
        if invalid_state_code:
            ConsultTask.objects.create(task_type=TASK_TYPE_TREATMENT_REFILL_FAILURE, ...)
            return  # SILENT FAILURE — no PrescriptionFill advance

        # Gate 2: all prescriptions must have remaining refills
        if not order.is_manual_invoice and not get_all_prescriptions_have_remaining_refills(prescriptions):
            ConsultTask.objects.create(task_type=TASK_TYPE_TREATMENT_REFILL_FAILURE, ...)
            raise Exception(...)  # TASK FAILURE

    # Advance status to CREATED
    prescription_fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_CREATED
    prescription_fill.save()

    # Send to Precision (pharmacy)
    send_create_patient_request_to_precision(...)
    for treatment_prescription in prescriptions:
        send_create_prescription_request_to_precision(...)
    send_fill_request_to_precision(prescription_fill.id, ...)
```

**Failure points:**
- Shipping address is in an unsupported state → `ConsultTask` created, function returns without advancing PrescriptionFill status.
- `prescription.refills_remaining == 0` or prescription is expired → task raises and creates a `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)`.

---

### Step 6: `Prescription.can_refill` Gate (for UX Orders)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, lines 659–666

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

For UX orders, `can_refill_entire_order()` iterates every Rx product and checks `can_refill`. Any of these conditions being False routes the order away from the refill path:
- `refills_remaining == 0`
- Prescription is expired (`expiration_date <= today`)
- Product is `is_disabled_for_refill` or `is_deprecated`

---

### Step 7: ReCharge Webhook — NOT Involved in PrescriptionFill Creation

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`, lines 26–63 (`handle_charge_upcoming_webhook`) and lines 66–124 (`handle_subscription_webhook`)

The ReCharge `charge/upcoming` webhook only sends a Braze analytics event. The `subscription/*` webhooks only update `active_subscriptions` in Braze. **Neither creates a PrescriptionFill or an Order.** The actual subscription renewal order creation is done by ReCharge triggering a new Shopify order, which arrives via the Shopify `orders/create` webhook.

---

## Summary of Failure Points

| Location | Condition | Outcome |
|---|---|---|
| `shopify_webhook_view` (line 90–104) | HMAC verification fails | 403, no processing |
| `_process_shopify_order_impl` (line 262) | No line items in payload | Return, no PrescriptionFill |
| `_process_shopify_order_impl` (line 661–672) | Order type is in excluded list or no PRESCRIPTION_TREATMENT line items | `process_shopify_order_for_treatment_refill` not called |
| `_process_shopify_order_impl` (line 676–682) | UX order: user not found or `can_refill_entire_order` returns False | Routed to consult/intake path instead |
| `process_shopify_order_for_treatment_refill` (line 2103) | `prescription_fill_id` in note attributes doesn't exist in DB | `PrescriptionFill.DoesNotExist` exception |
| `process_shopify_order_for_treatment_refill` (line 2178–2180) | No user resolved, no `prescription_ids` in note attributes | Prescriptions not fetched (empty queryset) |
| `process_shopify_order_for_treatment_refill` (line 2158–2162) | `prescription_ids` in note attributes but prescription belongs to different user | Exception raised |
| `process_shopify_order_for_treatment_refill` (line 2184–2189) | No prescriptions found AND no OTC treatments | Early return, `send_prescription_refill_request` never called |
| `send_prescription_refill_request` (line 199–210) | Shipping address is in unsupported state | `ConsultTask` created, fill not sent |
| `send_prescription_refill_request` (line 212–223) | `refills_remaining == 0` on any prescription | Task raises, `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` created |
| `Prescription.can_refill` (line 659–666) | Expired prescription, disabled product, or 0 refills | UX orders not routed to refill path |

---

## Key Files

- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` — webhook entry points (Shopify and ReCharge)
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — `_process_shopify_order_impl`, `process_shopify_order_for_treatment_refill`, `can_refill_entire_order`
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — `send_prescription_refill_request` Celery task
- `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` — ReCharge webhook handlers (analytics only, no PrescriptionFill)
- `/Users/albertgwo/Work/evvy/backend/care/models.py` — `Prescription.can_refill` property
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` — `create_prescription_fill_prescriptions`
