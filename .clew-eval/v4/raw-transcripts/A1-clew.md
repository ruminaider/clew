# A1 Exploration Log

## Search 1: Order webhook to PrescriptionFill creation
Query: "order webhook PrescriptionFill creation"

Found the core entities:
- `PrescriptionFillOrder` model at `/Users/albertgwo/Work/evvy/backend/care/models.py:831`
- `create_prescription_fill_prescriptions` at `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py:821`
- `_process_shopify_order_impl` at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:238` (the main processing function)
- `process_shopify_order_for_treatment_refill` at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2089`
- `prescription_fill_post_save` signal at `/Users/albertgwo/Work/evvy/backend/care/signals.py:140`

## Search 2: Subscription renewal and prescription fill
Query: "subscription renewal prescription fill"

Found that subscription renewal flow appears to come through the same Shopify webhook as orders, with the distinction being `is_recurring_subscription_order=True`. Also found `SubscriptionService` class at `/Users/albertgwo/Work/evvy/backend/subscriptions/subscription_service.py`.

## Search 3: Process Shopify order for treatment refill
Query: "process shopify order refill treatment"

Confirmed `process_shopify_order_for_treatment_refill` at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2089` is the key function. It's called from `_process_shopify_order_impl` for orders where `ORDER_TYPE_PRESCRIPTION_TREATMENT` is in line item types.

Also found: `process_shopify_order` (wrapper) at line 204, `process_shopify_order_for_treatment_refill` docstring says it "Supports both legacy consult-based orders and new evergreen prescription orders."

## Search 4: Shopify webhook and subscription charges
Query: "shopify webhook order paid subscription charge"

Found:
- `shopify_webhook_view` at `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:82` — the entry point
- `process_shopify_subscription_webhook` at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2219`
- `handle_charge_upcoming_webhook` at `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py:26`
- `recharge_webhook_view` at `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:369`

Key finding: `shopify_webhook_view` only handles `orders/create` and `orders/cancelled` topics. Subscription renewal orders come in as standard Shopify orders (`orders/create`) with recurring subscription metadata.

## Search 5: create_prescription_fill_prescriptions implementation
Query: "create prescription fill prescriptions"

Read `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py:821-843`. This function:
1. Gets line item quantities from all orders
2. For each prescription, calculates fill quantity
3. Gets `precision_reference_id` for the treatment
4. Uses `PrescriptionFillPrescriptions.objects.get_or_create(...)` to link prescriptions to the fill

## Search 6: send_prescription_refill_request task
Query: "send prescription refill request task celery"

Found the Celery task at `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:157`. This is the most critical function after PrescriptionFill creation. It:
1. Fetches the Order and PrescriptionFill
2. If order is cancelled, attempts to cancel the fill
3. Verifies shipping address state restrictions
4. Checks all prescriptions have remaining refills (raises Exception if not)
5. Updates status from DRAFT to CREATED
6. Creates patient in Precision pharmacy
7. For each prescription, sends create prescription request to Precision
8. For each OTC treatment, sends create OTC treatment request
9. Calls `send_fill_request_to_precision(prescription_fill.id, ...)`

## Search 7: Shipping address verification
Query: "verify shipping address prescription refill state restrictions"

Found `verify_shipping_address_for_prescription_refill` at `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:144`. Returns early with error if:
- `shipping_address.province_code not in VALID_STATES`, OR
- No shipping address but `consult_intake.state_code not in VALID_STATES`

## Search 8: process_order_line_item and recurring flag
Query: "process order line item subscription recurring is_recurring_order_item"

Found that `process_order_line_item` at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:1322` determines if a line item is a recurring subscription order item. The `is_recurring_subscription_order` flag affects:
- Whether `purchase_type` custom attributes are honored (they are skipped for recurring subscription orders to prevent misclassification)
- The overall order type determination

## Search 9: Prescription.can_refill and refills_remaining
Query: "Prescription can_refill expiration refills_remaining"

Found at `/Users/albertgwo/Work/evvy/backend/care/models.py:646-666`:
- `refills_remaining`: Returns 0 if expired; otherwise `num_allowed_refills - fill_count + 1` (with product-level cap)
- `can_refill`: Returns True only if `refills_remaining > 0 AND is_refillable_product AND expiration_date > today AND not product.is_disabled_for_refill AND not product.is_deprecated`

## Search 10: Parse order note attributes
Query: "parse order note attributes prescription fill id consult uid"

Found `_parse_order_note_attributes` at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2037`. Parses `note_attributes` from the Shopify payload for:
- `prescription_fill_id`
- `_evvyCartId`
- `consult_uid`
- `user_account_email`
- `prescription_ids`

## Search 11: can_refill_entire_order for ungated RX
Query: "can refill entire order ungated rx valid prescriptions"

Found at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2732`. For ungated RX orders, this function checks if all Rx products in the order have valid refillable prescriptions. Called from `_process_shopify_order_impl` line 677 to route UX orders to the refill path.

## Search 12: Webhook entry point
Query: "webhook view orders paid shopify"

Read `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:82-145`. The entry point:
- Verifies HMAC signature
- Routes `orders/create` and `orders/cancelled` to `process_shopify_order(payload, ...)`
- Returns HTTP 200 synchronously regardless

## Search 13: send_fill_request_to_precision
Query: "send fill request to precision prescription fill"

Found at `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py:191`. On failure, sets `fill.status = PRESCRIPTION_FILL_STATUS_WARNING` and clears `sent_to_pharmacy_at`. This is a Celery task so it can be retried.

---

## Final Answer

### Code Path: Subscription Renewal Order to PrescriptionFill Creation

#### Step 1: Webhook Receipt
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (line 82)
**Function:** `shopify_webhook_view`

When Shopify fires an `orders/create` event for a subscription renewal, the webhook view:
1. Verifies the HMAC signature (`X-Shopify-Hmac-SHA256`). If invalid, returns 403.
2. Parses the JSON body. If malformed, returns 400.
3. Routes the payload to `process_shopify_order(payload, is_order_cancellation=False)`.

```python
if shopify_topic == "orders/create" or shopify_topic == "orders/cancelled":
    process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")
```

**Failure point:** If HMAC verification fails or JSON is malformed, the webhook is rejected and no order processing occurs.

---

#### Step 2: Error-Handling Wrapper
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 204)
**Function:** `process_shopify_order`

This wrapper calls `_process_shopify_order_impl` and catches any Exception, logging it to NewRelic. All errors are re-raised after logging.

**Failure point:** Any unhandled exception from the inner function is logged but re-raised. The webhook returns HTTP 200 regardless (the view doesn't check the return value), so Shopify won't retry on application-level errors.

---

#### Step 3: Main Order Processing
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 238)
**Function:** `_process_shopify_order_impl`

This function is the main orchestrator. Key steps for subscription renewal:

1. **Early exit if no line items** (line 262): Returns without processing.

2. **Order creation via `get_or_create`** (line 336): Idempotent — uses `(provider=SHOPIFY, provider_id=order_number)` as the unique key.

3. **Line item processing** (line 470): Calls `process_order_line_item` for each line item. For subscription renewals, `is_recurring_subscription_order` is set to `True` when any line item has `is_recurring_order_item=True`.

4. **Order type determination** (line 565): `_get_overall_order_type_and_sku_from_line_items` classifies the order. Subscription refill orders are not allowed to use `purchase_type` from note attributes (which may carry stale data from the original order):
   ```python
   if not is_recurring_subscription_order:
       # honor purchase_type attribute from original order
   ```

5. **Routing to refill processing** (line 661):
   ```python
   if (
       order.order_type not in [ORDER_TYPE_A_LA_CARTE, ORDER_TYPE_MIXED_CARE, ...]
       and Order.ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
   ):
       process_shopify_order_for_treatment_refill(order, payload, order_logger)
   ```

   Additionally, for ungated RX orders (line 676):
   ```python
   if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
       if can_refill_entire_order(order.user, order):
           process_shopify_order_for_treatment_refill(order, payload, order_logger)
   ```

**Failure points in this step:**
- If the subscription renewal order's line items aren't classified as `ORDER_TYPE_PRESCRIPTION_TREATMENT`, the refill path is never entered.
- If `is_recurring_subscription_order` is incorrectly False, `purchase_type` from old note attributes could reclassify the order as `ORDER_TYPE_A_LA_CARTE` or `ORDER_TYPE_MIXED_CARE`, which are explicitly excluded from the refill routing condition.
- If the order has no user set by `_update_order_user`, ungated RX orders won't route to the refill path.

---

#### Step 4: Refill-Specific Processing
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 2089)
**Function:** `process_shopify_order_for_treatment_refill`

This function creates the PrescriptionFill object and links it to prescriptions:

1. **Parse note attributes** (line 2097): Calls `_parse_order_note_attributes` to extract `prescription_fill_id`, `consult_uid`, `user_account_email`, `prescription_ids` from `note_attributes`.

2. **Get or create PrescriptionFill** (line 2102-2108):
   ```python
   if prescription_fill_id and _is_valid_uuid(prescription_fill_id):
       prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)
   else:
       lookup_params = {"order": order}
       if order.user:
           lookup_params["user"] = order.user
       prescription_fill, _ = PrescriptionFill.objects.get_or_create(**lookup_params)
   ```
   For subscription renewals, there is typically no `prescription_fill_id` in note_attributes, so a new PrescriptionFill is created via `get_or_create`.

3. **Resolve user and consult** (lines 2111-2142): Tries multiple strategies to find the user (from email attribute, cart, consult, order email). Sets `prescription_fill.order = order` and saves.

4. **Find prescriptions** (lines 2148-2180):
   ```python
   if order_attrs.prescription_ids:
       # Use explicit IDs
   elif order.user:
       prescriptions = Prescription.objects.filter(
           user=order.user, product__in=ordered_products, deleted=False
       ).order_by("product_id", "create_date").distinct("product_id")
   else:
       logger.warning("No prescription IDs ... no user found, cannot process prescriptions")
   ```

5. **Early return if no prescriptions and no OTC treatments** (line 2184):
   ```python
   if not prescriptions.exists() and not otc_treatments.exists():
       logger.error(f"No prescriptions and no otc treatments found for order {order.order_number}. ...")
       return
   ```
   CRITICAL: This silently returns without raising an exception, so no ConsultTask is created.

6. **Create PrescriptionFillPrescriptions** (line 2192):
   ```python
   if prescriptions.exists():
       create_prescription_fill_prescriptions(prescription_fill, list(prescriptions), [order])
   ```

7. **Dispatch async task** (line 2198):
   ```python
   send_prescription_refill_request.delay(order.id, prescription_fill.id)
   ```

**Failure points in this step:**
- If `note_attributes` is missing `prescription_fill_id` AND the order already has a PrescriptionFill linked to it, `get_or_create(order=order, user=user)` may return the old fill, potentially merging a new renewal into an old fill's record.
- If no user can be resolved (email not matching any account, no cart, no consult), `order.user` is None, `lookup_params` has no user, and a PrescriptionFill is created with only the order as the key.
- If `order.user` is None, the prescription lookup falls into the warning branch and returns no prescriptions, causing the early `return` at line 2184. **No prescription fill is sent to the pharmacy.**
- Invalid `prescription_ids` format in note_attributes raises an exception (line 2162-2167).

---

#### Step 5: Linking Prescriptions to the Fill
**File:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` (line 821)
**Function:** `create_prescription_fill_prescriptions`

```python
def create_prescription_fill_prescriptions(
    prescription_fill, prescriptions, orders
):
    product_slug_to_quantities_map = get_line_item_quantities_from_all_orders(orders)
    for prescription in prescriptions:
        fill_quantity = get_prescription_fill_quantity(...)
        precision_reference_id = get_precision_reference_id_for_treatment(...)
        PrescriptionFillPrescriptions.objects.get_or_create(
            prescriptionfill=prescription_fill,
            prescription=prescription,
            defaults={...}
        )
```

**Failure point:** If `get_line_item_quantities_from_all_orders` raises or if `get_prescription_fill_quantity` returns 0, the fill quantity could be wrong. `get_or_create` is idempotent, so retries are safe.

---

#### Step 6: Async Celery Task — send_prescription_refill_request
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (line 157)
**Function:** `send_prescription_refill_request` (Celery task)

1. **Cancellation check** (line 173): If order is cancelled, tries to cancel the fill in Precision.

2. **Shipping address state restriction check** (line 199):
   ```python
   invalid_state_code, shipping_address = verify_shipping_address_for_prescription_refill(order, consult_intake)
   if invalid_state_code:
       logger.error(...)
       ConsultTask.objects.create(task_type=TASK_TYPE_TREATMENT_REFILL_FAILURE, ...)
       return  # silently returns, no retry
   ```

3. **Refill count check** (line 212):
   ```python
   if not order.is_manual_invoice and not get_all_prescriptions_have_remaining_refills(prescriptions):
       raise Exception(error_message)  # causes task to fail/retry
   ```
   The check in `get_all_prescriptions_have_remaining_refills` is:
   ```python
   for prescription in prescriptions:
       if prescription.num_allowed_refills - prescription.fill_count < 0:
           return False
   ```
   Note: This checks `< 0`, not `<= 0`, meaning it only fails when the fill_count has already exceeded the allowed refills.

4. **Status update** (line 226):
   ```python
   prescription_fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_CREATED
   prescription_fill.save()
   ```

5. **Create patient in Precision** (line 232): `send_create_patient_request_to_precision(...)` — separate task.

6. **Create prescriptions in Precision** (line 240): For each prescription, `send_create_prescription_request_to_precision(...)` — separate task per prescription.

7. **Send fill to Precision** (line 266):
   ```python
   send_fill_request_to_precision(prescription_fill.id, order_shipping_address=shipping_address)
   ```

**Failure points in this step:**
- **State restriction:** If the subscription renewal order ships to a state not in `VALID_STATES`, the task returns early and creates a `ConsultTask` for manual review, but the task itself doesn't retry — this is a permanent failure.
- **No remaining refills:** If `prescription.num_allowed_refills - prescription.fill_count < 0` (i.e., already exceeded refills), the task raises an Exception, creating a `ConsultTask` and triggering Celery retry behavior.
- **No consult on fill:** If `prescription_fill.consult` is None (evergreen prescriptions without a legacy consult), `consult_intake` is None and the state check falls back to the shipping address only. This is the happy path for evergreen prescriptions.
- **Missing shipping address:** If the order has no `OrderShippingAddress` record and no consult intake, `invalid_state_code` will be None and processing continues without a state check.

---

#### Step 7: Sending to Precision Pharmacy
**File:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (line 191)
**Function:** `send_fill_request_to_precision` (Celery task)

Calls `PrecisionAPIClient().fill_prescription(fill, order_shipping_address)`.

On failure:
```python
except Exception as e:
    fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_WARNING
    fill.sent_to_pharmacy_at = None
    fill.save()
    raise  # re-raises for Celery retry
```

**Failure point:** If the Precision API is down or returns an error, the fill status is set to `WARNING` and the task is retried by Celery.

---

### Summary of Failure Points

The following conditions can cause a subscription renewal to NOT create a prescription fill or fail to send it to the pharmacy:

| # | Location | Failure Condition | Observable Effect |
|---|----------|-------------------|-------------------|
| 1 | `shopify_webhook_view` | Invalid HMAC signature | 403 response, no processing |
| 2 | `_process_shopify_order_impl` | Line items not classified as `PRESCRIPTION_TREATMENT` | Refill path never entered |
| 3 | `_process_shopify_order_impl` | `is_recurring_subscription_order` is False + old `purchase_type` in note_attributes | Order misclassified as A_LA_CARTE/MIXED_CARE, excluded from refill routing |
| 4 | `process_shopify_order_for_treatment_refill` | No user resolved from email/cart/consult/order | `prescriptions` query skipped, early return at line 2184 |
| 5 | `process_shopify_order_for_treatment_refill` | User has no matching prescriptions for ordered products | Early return at line 2184 — PrescriptionFill exists but is empty |
| 6 | `process_shopify_order_for_treatment_refill` | Invalid `prescription_ids` format in note_attributes | Exception raised, order processing halts |
| 7 | `send_prescription_refill_request` (Celery task) | Shipping address state not in `VALID_STATES` | Task returns silently, ConsultTask created |
| 8 | `send_prescription_refill_request` | `prescription.fill_count > num_allowed_refills` | Exception raised, Celery retry; ConsultTask created |
| 9 | `send_prescription_refill_request` | `Prescription.can_refill` False (expired, deprecated, disabled, 0 refills remaining) | For ungated RX orders caught earlier by `can_refill_entire_order`; for legacy flow, `get_all_prescriptions_have_remaining_refills` check is less strict (only fails at `< 0`, not `<= 0`) |
| 10 | `send_fill_request_to_precision` | Precision API error | Fill status set to WARNING, ConsultTask not created, Celery retry |

### Key Files

- **Webhook entry:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 82-145)
- **Main processing orchestrator:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 204, 238-790)
- **Order type routing:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 660-692)
- **PrescriptionFill creation:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 2089-2201)
- **Note attribute parsing:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 2037-2086)
- **Pharmacy submission task:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 157-267)
- **State restriction check:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 144-153)
- **PrescriptionFill model:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 721-828)
- **Prescription.can_refill:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 646-666)
- **Link prescriptions to fill:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` (lines 821-843)
- **Precision API submission:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py` (lines 191-250)
