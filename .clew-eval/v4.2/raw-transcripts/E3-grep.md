# Order Creation Chain: Full Side-Effect Map

## Entry Point

The order creation chain is triggered by a Shopify webhook. The webhook endpoint is in:

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

```python
if shopify_topic == "orders/create" or shopify_topic == "orders/cancelled":
    process_shopify_order(payload, is_order_cancellation=shopify_topic == "orders/cancelled")
```

---

## Top-Level Orchestrator

**Function:** `process_shopify_order()` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 204)

This is a wrapper with top-level error handling that calls `_process_shopify_order_impl()`. If any exception propagates, it is caught and logged to NewRelic, then re-raised. There is no retry mechanism at this level.

**Function:** `_process_shopify_order_impl()` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 238)

This is the main orchestrator. It performs sequential stages:

1. **Order validation and parsing** (payload parsing, email validation)
2. **Address processing**
3. **Line item processing**
4. **Payment processing** (metrics logging)
5. **Order-type-specific routing**
6. **Fulfillment dispatching**

---

## Records Created During Order Processing

### 1. `Order` (ecomm)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (line 11)

Created via `get_or_create` at line 336 of `ecomm/utils.py`:
```python
order, _ = Order.objects.get_or_create(
    provider=Order.PROVIDER_SHOPIFY,
    provider_id=order_number,
)
```
Fields set: `checkout_id`, `checkout_token`, `order_number`, `shopify_order_id`, `shopify_customer_id`, `email`, `total_line_items_price`, `is_testing_order`, `is_manual_invoice`, `payload`, `shipping_method`, `order_type`, `sku`, `business_verticals`, `checkout_source`, `is_subscription_order`.

### 2. `OrderShippingAddress` (ecomm)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (line 262)

Created via `get_or_create` at line 382 of `ecomm/utils.py` when the payload contains a `shipping_address`:
```python
shipping_address_record, _ = OrderShippingAddress.objects.get_or_create(order=order)
```
OneToOne relationship to `Order`.

### 3. `OrderLineItem` (ecomm)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (line 184)

Created per line item via `get_or_create` inside `process_order_line_item()` at line 1401 of `ecomm/utils.py`. The creation is wrapped in `transaction.atomic()` with a `select_for_update()` lock on the Order row to prevent race conditions from duplicate webhook deliveries.

Fields set: `sku`, `product_id`, `variant_id`, `order_type`, `quantity`, `price`, `business_vertical`, `purchase_type`, `metadata`, `care_product`, `ecomm_product`, `is_bulk_order`.

### 4. `RelatedOrder` (ecomm)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (line 294)

Created at line 573 of `ecomm/utils.py` when the order payload includes a `parent_order_number` attribute (cross-sell analytics):
```python
RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)
```

---

## Order-Type-Specific Side Effects

### A. Test Orders (`ORDER_TYPE_TEST`, `ORDER_TYPE_EXPANDED_TEST`)
Handled by `process_shopify_order_for_test()` at line 1600 of `ecomm/utils.py`.

- **`ProviderTestOrder`** (providers app): Created or linked when a `provider_magic` note attribute is present. Either an existing unlinked `ProviderTestOrder` is found and linked (`pto.ecomm_order = order`), or a new one is created:
  ```python
  pto = ProviderTestOrder.objects.create(
      provider=provider,
      patient_email=patient_email_candidate,
      order_method=ProviderTestOrder.PATIENT_PAID,
      ecomm_order=order,
  )
  ```
  This creation is wrapped in a broad `try/except` that logs a warning on failure but does NOT re-raise, so a failure here does not abort the order.

### B. Urine Test Orders (`ORDER_TYPE_URINE_TEST`)
Handled by `create_urine_tests_and_unregistered_testkit_orders_for_order()` at line 1194 of `ecomm/utils.py`.

- **`UrineTest`** records: Created in bulk via `UrineTest.objects.bulk_create()`, one per unit quantity in the order's urine test line items.
- **Junction lab order**: A Celery task `create_unregistered_testkit_order_for_urine_test.delay()` is queued to create the order in the Junction lab system.

### C. Care Orders (Vaginitis/STI/UTI/Care types)
Handled by `process_shopify_order_for_care()` at line 1807 of `ecomm/utils.py`.

- **`ConsultOrder`** (consults): A through-table linking `Consult` and `Order`, created via `get_or_create` at line 1858:
  ```python
  ConsultOrder.objects.get_or_create(consult=consult, order=order)
  ```
  Relationship: `ConsultOrder.consult` → `Consult`, `ConsultOrder.order` → `Order`.

- **`ConsultTask`** (consults, on failure): If the care order is missing a valid `consult_uid`, a `ConsultTask` with `TASK_TYPE_A_LA_CARE_FAILURE` is created (line 1952) to alert ops:
  ```python
  ConsultTask.objects.create(
      task_type=ConsultTask.TASK_TYPE_A_LA_CARE_FAILURE,
      task_data={"reason": error_message},
  )
  ```

### D. Treatment Refill Orders (`ORDER_TYPE_PRESCRIPTION_TREATMENT` line items)
Handled by `process_shopify_order_for_treatment_refill()` at line 2089 of `ecomm/utils.py`.

#### Records created:

1. **`PrescriptionFill`** (care): Created or fetched via `get_or_create` (line 2108):
   ```python
   prescription_fill, _ = PrescriptionFill.objects.get_or_create(**lookup_params)
   ```
   Fields set: `consult`, `order`, `status` (transitions from DRAFT to CREATED in the downstream Celery task).

2. **`PrescriptionFillOrder`** (care): Through table linking `PrescriptionFill` and `Order` (line 2143):
   ```python
   PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
   ```

3. **`PrescriptionFillPrescriptions`** (care): Created by `create_prescription_fill_prescriptions()` from `shipping/precision/utils.py` (line 2193). Links specific `Prescription` objects to the `PrescriptionFill`.

4. **`PrescriptionFillOTCTreatments`** (care): Created by `create_prescription_fill_otc_treatments()` (line 2195). Links `OTCTreatment` objects to the `PrescriptionFill`.

After these records are created, the Celery task `send_prescription_refill_request.delay(order.id, prescription_fill.id)` is queued.

**Inside `send_prescription_refill_request` task** (`ecomm/tasks.py`, line 157):
- Updates `PrescriptionFill.status` from DRAFT → CREATED
- Calls Precision pharmacy API to:
  - Create patient record (`send_create_patient_request_to_precision`)
  - Create individual prescription records (`send_create_prescription_request_to_precision` for each)
  - Create OTC treatment records (`send_create_otc_treatment_request_to_precision` for each)
  - Submit the fill request (`send_fill_request_to_precision`)

On failure inside this task, a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` is created.

### E. PCR Add-On Orders (`ORDER_TYPE_PCR_ADD_ON`)
Handled by `process_shopify_order_for_pcr_add_on()` at line 1964 of `ecomm/utils.py`.

- Calls `add_expanded_vpcr_panel_to_test_kit(test_kit, order)` from `test_results/utils.py` which creates a new PCR `LabTest` record linked to the existing `Test` kit.

### F. Ungated RX Orders (`ORDER_TYPE_UNGATED_RX`)
At line 676-692 of `ecomm/utils.py`. Routing depends on whether the user has valid refillable prescriptions:

- **Refillable path**: Routes to `process_shopify_order_for_treatment_refill()` (same as D above).
- **Consult path**: Calls `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay()` (Celery task).
  - This task creates a `Consult` (type=UNGATED_RX) and `ConsultIntake` and `ConsultOrder` if no in-progress consult exists for the user.

---

## Cross-Cutting Side Effects (All Order Types)

### OTC Treatment Attachment
`attach_otc_treatments_to_existing_consult(order)` is called at line 733 of `ecomm/utils.py` for all order types:
- Creates `ConsultOTCTreatment` records (care app) linking `OTCTreatment` objects to the user's most recent `Consult` if the treatment plan is still active.

### Gift Card Processing
If the order payload includes gift card payments or gift card line items, `process_gift_cards.delay(order.id, payload)` is queued (line 740). This creates:
- **`GiftCardOrderRedemption`** records for gift cards used as payment.
- **`GiftCard`** records (ecomm) for gift cards purchased as line items, and creates a `PartnerRelationship` for male partner treatment vouchers.

### Fulfillment to Berlin (Shipping Provider)
For ALL non-urine-test orders, `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` is queued at line 763. This:
- Calls `BerlinAPIClient.create_order()` via `/createOrder` HTTP endpoint.
- On success: sets `order.sent_to_berlin_at = timezone.now()`.
- On failure: raises exception, logged via `OrderEventLogger`.

### Analytics Events (Async Celery Tasks)
- `send_any_paid_event.delay(order.order_number)` — for all non-cancelled orders with a user
- `send_consult_paid_event.delay(consult.uid, order.provider_id)` — for care orders
- `send_prescription_refills_paid_event.delay(...)` — for refill orders
- `send_ungated_rx_order_paid_event.delay(order.order_number)` — for ungated RX orders
- `send_additional_tests_paid_event.delay(...)` — for PCR add-on orders
- `track_event(BrazeEventName.VAGINAL_TEST_PURCHASE, ...)` / `track_event(BrazeEventName.UTI_PURCHASE, ...)` — for test orders

---

## Relationship Graph Summary

```
Order (ecomm)
  ├── OrderShippingAddress (1:1, on_delete=CASCADE)
  ├── OrderLineItem (1:N, on_delete=CASCADE)
  │     ├── care_product → care.Product
  │     └── ecomm_product → ecomm.Product
  ├── ConsultOrder (N:N through table)
  │     └── → Consult (consults)
  ├── PrescriptionFill (FK: order, nullable)
  │     ├── PrescriptionFillOrder (through table)
  │     ├── PrescriptionFillPrescriptions (through table)
  │     │     └── → Prescription (care)
  │     └── PrescriptionFillOTCTreatments (through table)
  │           └── → OTCTreatment (care)
  ├── Test.ecomm_order (FK from Test, nullable, set_null on delete)
  ├── UrineTest.ecomm_order (FK from UrineTest, nullable)
  ├── RelatedOrder.cross_sell_order / parent_order (cross-sell analytics)
  └── ProviderTestOrder.ecomm_order (FK from ProviderTestOrder, nullable)
```

---

## Failure Handling Summary

| Step | Failure Mode | Consequence |
|------|-------------|-------------|
| `Order.get_or_create` | DB error | Exception propagates, logged to NewRelic, no order created |
| `OrderShippingAddress.get_or_create` | DB error | Exception propagates, order creation aborted |
| `process_order_line_item` (atomic) | DB error | Transaction rolls back for that line item; exception propagates |
| `ConsultOrder.get_or_create` (care orders) | Consult not found | `ConsultTask(TASK_TYPE_A_LA_CARE_FAILURE)` created; order saved without consult link |
| `ProviderTestOrder` creation | Any error | `logger.warning()` only; does NOT re-raise; order processing continues |
| `send_prescription_refill_request` Celery task | Invalid state / Precision API down | `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` created; task raises and Celery may retry |
| `send_order_to_berlin_for_fulfillment` Celery task | Berlin API returns non-200 | Exception raised; `retry_failed_berlin_order_fulfillments` daily task retries unfulfilled orders |
| `create_unregistered_testkit_order_for_urine_test` Celery task | Junction API failure | Task may retry via Celery retry policy |
| Gift card processing | Any error | Task raises and logs; order processing itself is unaffected (task is async) |
| Missing consult_uid in ungated RX / care order | No matching Consult found | `ConsultTask(TASK_TYPE_A_LA_CARE_FAILURE)` created as ops alert |

---

## Key Service Files

| File | Purpose |
|------|---------|
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` | Webhook entry point |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | Main orchestration: `process_shopify_order`, `_process_shopify_order_impl`, `process_shopify_order_for_care`, `process_shopify_order_for_test`, `process_shopify_order_for_treatment_refill`, `process_shopify_order_for_pcr_add_on`, `process_order_line_item` |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` | Celery tasks: `send_prescription_refill_request`, `attach_otc_treatments_to_existing_consult`, `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`, `process_gift_cards` |
| `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` | `send_order_to_berlin_for_fulfillment` Celery task |
| `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` | `Order`, `OrderLineItem`, `OrderShippingAddress`, `RelatedOrder`, `PartnerRelationship` models |
| `/Users/albertgwo/Work/evvy/backend/care/models.py` | `PrescriptionFill`, `PrescriptionFillOrder`, `PrescriptionFillPrescriptions`, `PrescriptionFillOTCTreatments`, `OTCTreatment` models |
| `/Users/albertgwo/Work/evvy/backend/consults/models.py` | `ConsultOrder`, `ConsultTask` models |
| `/Users/albertgwo/Work/evvy/backend/shipping/berlin/berlin.py` | `BerlinAPIClient.create_order()` |
| `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` | `create_prescription_fill_prescriptions`, `create_prescription_fill_otc_treatments` |
