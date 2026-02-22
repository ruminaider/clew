# E3 — Agent Alpha

## Order Creation Chain: Full Trace

### Entry Point

Order processing is triggered via the Shopify webhook handler. The webhook view calls `process_shopify_order()`, and all logic flows through `_process_shopify_order_impl()`.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 204–790)
**Celery task layer:** `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`

---

### Stage 1: Order Record Creation

`_process_shopify_order_impl()` first calls:

```python
order, _ = Order.objects.get_or_create(
    provider=Order.PROVIDER_SHOPIFY,
    provider_id=order_number,
)
```

This is idempotent. If the order already exists, it updates fields in-place. Then immediately:

```python
OrderShippingAddress.objects.get_or_create(order=order)
```

The shipping address record is created as a 1:1 companion to the Order.

**Models created:**
- `Order` (`ecomm/models/order.py`, line 11)
- `OrderShippingAddress` (`ecomm/models/order.py`, line 262)

---

### Stage 2: Line Item Processing (`process_order_line_item`)

For each line item in the Shopify payload, `process_order_line_item()` is called (line 1322). Inside a `transaction.atomic()` block with `select_for_update()` to prevent race conditions:

```python
line_item, created = OrderLineItem.objects.get_or_create(
    order=locked_order,
    shopify_id=shopify_id,
    defaults={...}
)
```

**Model created:**
- `OrderLineItem` (`ecomm/models/order.py`, line 184) — one per Shopify line item

**Side effects per line item type:**

**A. OTC products (regulatory_category = OVER_THE_COUNTER):**
```python
OTCTreatment.objects.bulk_create([OTCTreatment(order=order, product=care_product, user=user) ...])
```
Model created: `OTCTreatment` (`care/models.py`)

**B. UTI / Urine test orders (ORDER_TYPE_URINE_TEST):**
```python
UrineTest.objects.bulk_create([UrineTest(ecomm_order=order, lab=UrineTest.LAB_JUNCTION, status=Test.STATUS_ORDERED) ...])
```
Then calls `create_unregistered_testkit_order_for_urine_test` (Celery task) for each UrineTest.
Model created: `UrineTest` (`test_results/models/test.py`)

**C. Male partner treatment voucher (MPT_VOUCHER_SKU):**
Via `_validate_mpt_voucher_line_item()` (inside `transaction.atomic()`):
- Calls Shopify API to create a gift card
- Creates `GiftCard` record and sets `gift_card_id`/`gift_card_code` on the line item

```python
GiftCard.objects.get_or_create(order=..., shopify_id=..., gift_card_code=..., value=...)
```
Model created: `GiftCard` (`ecomm/models/product.py`, line 148)

---

### Stage 3: Cross-Sell / Related Order

If the Shopify payload contains a `parent_order_number` custom attribute:

```python
RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)
```

**Model created:**
- `RelatedOrder` (`ecomm/models/order.py`, line 294) — links the originating order to the cross-sold order for analytics

---

### Stage 4: Order-Type-Specific Processing

The orchestrator branches on `order.order_type`:

#### 4A. Care Orders (`process_shopify_order_for_care`) — lines 1807–1961

Care order types include: `ORDER_TYPE_VAGINITIS_CARE`, `ORDER_TYPE_STI_CARE`, `ORDER_TYPE_UTI_CARE`, `ORDER_TYPE_A_LA_CARTE`, `ORDER_TYPE_DYNAMIC_BUNDLE`, `ORDER_TYPE_MIXED_CARE`, `ORDER_TYPE_MALE_PARTNER`.

This function:
1. Looks up `Consult` by `consult_uid` from note attributes
2. Sets `consult.order = order` and saves
3. **Creates:** `ConsultOrder.objects.get_or_create(consult=consult, order=order)` — the through-table linking Consult to Order
4. Updates `consult.status` to `STATUS_ORDERED` if it was `STATUS_OPTED_IN`
5. If the consult has selected treatments (`has_selected_treatments_purchase_type`), calls `add_ordered_products_to_consult(consult, order)` to finalize `SelectedTreatment` records
6. If products ordered don't match selected treatments, **creates** a `ConsultTask` alert record

On failure (no consult found for a non-staff, non-test user):
```python
ConsultTask.objects.create(task_type=ConsultTask.TASK_TYPE_A_LA_CARE_FAILURE, task_data={"reason": error_message})
```

**Models created:**
- `ConsultOrder` (`consults/models.py`) — many-to-many through table between Consult and Order
- `ConsultTask` (on failure/mismatch alert)

#### 4B. Test Orders (`process_shopify_order_for_test`) — lines 1600–1786

For provider magic-link orders:
- Looks up or creates a `ProviderTestOrder`
- If no existing PTO by id, email, or checkout email: `ProviderTestOrder.objects.create(provider=..., patient_email=..., order_method=PATIENT_PAID, ecomm_order=order)`

**Model created:**
- `ProviderTestOrder` (`providers/models.py`)

#### 4C. PCR Add-On (`process_shopify_order_for_pcr_add_on`) — lines 1964–2009

Calls `add_expanded_vpcr_panel_to_test_kit(test_kit, order)` which creates a `LabTest` record (`test_results/utils.py`, line 279).

**Model created:**
- `LabTest` (via `add_expanded_vpcr_panel_to_test_kit`)

#### 4D. Prescription Refill / Treatment Refill (`process_shopify_order_for_treatment_refill`) — lines 2089–2201

This is the most complex branch and handles Rx refills:

1. **Creates or gets `PrescriptionFill`:**
   ```python
   prescription_fill, _ = PrescriptionFill.objects.get_or_create(order=order, user=user)
   ```

2. **Creates `PrescriptionFillOrder`** (through table):
   ```python
   PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
   ```

3. Calls `create_prescription_fill_prescriptions()` which for each `Prescription`:
   ```python
   PrescriptionFillPrescriptions.objects.get_or_create(
       prescriptionfill=prescription_fill, prescription=prescription,
       defaults={"fill_quantity": ..., "precision_reference_id": ...}
   )
   ```

4. Calls `create_prescription_fill_otc_treatments()` which for each `OTCTreatment`:
   ```python
   PrescriptionFillOTCTreatments.objects.get_or_create(
       prescriptionfill=prescription_fill, otctreatment=otc_treatment,
       defaults={"fill_quantity": ..., "precision_reference_id": ...}
   )
   ```

5. Enqueues Celery task: `send_prescription_refill_request.delay(order.id, prescription_fill.id)`

**Models created:**
- `PrescriptionFill` (`care/models.py`)
- `PrescriptionFillOrder` (`care/models.py`)
- `PrescriptionFillPrescriptions` (`care/models.py`)
- `PrescriptionFillOTCTreatments` (`care/models.py`)

#### 4E. Ungated RX Orders (ORDER_TYPE_UNGATED_RX) — lines 676–691

Routes to either the refill path (4D) or the consult/intake path:
```python
add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(order.user.id, order.order_number)
```

This function (in `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, line 344):
- Finds or creates a `Consult` (type=TYPE_UNGATED_RX)
- Creates `ConsultIntake.objects.get_or_create(consult=latest_in_progress_consult)`
- Creates `ConsultOrder.objects.get_or_create(consult=..., order=order)`

**Models created:**
- `Consult` (if none exists)
- `ConsultIntake` (`consults/models.py`)
- `ConsultOrder`

---

### Stage 5: OTC Treatment Attachment (`attach_otc_treatments_to_existing_consult`)

Called at the bottom of `_process_shopify_order_impl()` for all order types (line 733):

```python
ConsultOTCTreatment.objects.get_or_create(consult=consult, otctreatment=otc_treatment)
```

**Model created:**
- `ConsultOTCTreatment` (`care/models.py`) — links OTC treatments to a consult

---

### Stage 6: Gift Card Processing (Async, `process_gift_cards` Celery task)

If the order contains Shopify gift card activity:
```python
process_gift_cards.delay(order.id, payload)
```

The `GiftCardRedemptionService.process_order_gift_cards()` in `/Users/albertgwo/Work/evvy/backend/ecomm/services/gift_card_redemption.py` handles:
- Gift card purchases → creates `GiftCard` records
- Gift card redemptions → creates `GiftCardOrderRedemption` records (line 196 of `ecomm/models/product.py`)

**Models created:**
- `GiftCard` (`ecomm/models/product.py`, line 148)
- `GiftCardOrderRedemption` (`ecomm/models/product.py`, line 196)

---

### Stage 7: Fulfillment (Async, `send_order_to_berlin_for_fulfillment` Celery task)

At the very end (line 763):
```python
send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)
```

In `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` (line 685), this calls Berlin API's `create_order()`. On success, sets `order.sent_to_berlin_at` timestamp.

---

### Stage 8: Precision Pharmacy (Async, `send_prescription_refill_request` Celery task)

In `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (line 157), this task:
1. Updates `PrescriptionFill.status` from DRAFT → CREATED
2. Calls `send_create_patient_request_to_precision()` — creates patient record in external Precision system
3. For each prescription: `send_create_prescription_request_to_precision()` — sends Rx to pharmacy
4. For each OTC treatment: `send_create_otc_treatment_request_to_precision()`
5. Calls `send_fill_request_to_precision(prescription_fill.id, ...)` — triggers the actual fill

On error, creates `ConsultTask` records as alerts:
```python
ConsultTask.objects.create(task_type=ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE, task_data={"reason": error_message})
```

---

## Error Handling

**1. Top-level wrapper (`process_shopify_order`):** All exceptions from `_process_shopify_order_impl` are caught, logged to NewRelic with structured error attributes, and re-raised. The exception propagates back to the webhook handler.

**2. Line item atomicity:** Each `OrderLineItem` is created inside `transaction.atomic()` with `select_for_update()` on the Order row (line 1395–1415). This prevents duplicate line items from concurrent webhook deliveries but does NOT wrap the whole order processing.

**3. Provider test order linking:** Wrapped in `try/except` with `logger.warning` — failure is non-fatal (lines 1768–1771).

**4. MPT voucher gift card creation:** Wrapped in `transaction.atomic()`. If the Shopify API call fails, it raises `ValueError` which propagates up and causes the MPT voucher validation to fail loudly (line 1124).

**5. Missing consult for care order:** Creates a `ConsultTask` alert record (`TASK_TYPE_A_LA_CARE_FAILURE`) and logs to NewRelic, but does NOT raise — processing continues.

**6. Treatment refill failures (Precision):** If no prescriptions or OTC treatments found, returns early (line 2184–2189). If state validation fails or no refills remain, creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` and either returns or re-raises.

**7. Berlin fulfillment (async):** If Berlin API returns non-200/201, raises exception inside the Celery task. A retry job (`retry_failed_berlin_order_fulfillments`) periodically re-queues orders where `sent_to_berlin_at` is still null (line 749–774 of `shipping/tasks.py`).

**8. The main `_process_shopify_order_impl` is NOT wrapped in a single transaction.atomic().** This means partial state is possible: an Order + OrderShippingAddress + OrderLineItems may exist in the DB even if later stages (ConsultOrder, PrescriptionFill) fail. The individual stages handle failures independently.

---

## Summary Model Relationship Map

```
Order (ecomm/models/order.py)
├── OrderShippingAddress (1:1, always created)
├── OrderLineItem (1:N, one per Shopify line item)
│   └── GiftCard (if MPT voucher SKU)
├── RelatedOrder (if cross-sell, links parent_order → cross_sell_order)
│
├── [Care orders]
│   ├── ConsultOrder (through table: Consult ↔ Order)
│   ├── SelectedTreatment (updated/finalized per purchased product)
│   └── ConsultTask (on mismatch/failure, no FK to Order)
│
├── [Test orders]
│   └── ProviderTestOrder (providers/models.py, FK to Order)
│
├── [PCR add-on]
│   └── LabTest (test_results/models.py)
│
├── [Urine test orders]
│   └── UrineTest (test_results/models/test.py, FK ecomm_order → Order)
│
├── [OTC products — any order type]
│   ├── OTCTreatment (care/models.py, FK to Order)
│   └── ConsultOTCTreatment (through table: Consult ↔ OTCTreatment)
│
├── [Prescription refill orders]
│   ├── PrescriptionFill (care/models.py, FK to Order)
│   ├── PrescriptionFillOrder (through table: PrescriptionFill ↔ Order)
│   ├── PrescriptionFillPrescriptions (through table: PrescriptionFill ↔ Prescription)
│   └── PrescriptionFillOTCTreatments (through table: PrescriptionFill ↔ OTCTreatment)
│
├── [Ungated RX — no prior consult]
│   ├── Consult (created fresh)
│   ├── ConsultIntake (1:1 with new Consult)
│   └── ConsultOrder (through table)
│
└── [Gift card activity — async]
    ├── GiftCard (ecomm/models/product.py)
    └── GiftCardOrderRedemption (ecomm/models/product.py)
```
