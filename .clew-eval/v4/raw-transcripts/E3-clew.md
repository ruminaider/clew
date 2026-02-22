# E3 Exploration Log

## Search 1: Order model definition
Searched for "Order model django" using clew.

Found the `Order` model at `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (lines 11-181). Key fields:
- `user` (ForeignKey to User, nullable)
- `email`, `evvy_account_email` - customer contact
- `provider_id`, `order_number`, `shopify_order_id` - Shopify identifiers
- `order_type` - choices: TEST, VAGINITIS_CARE, STI_CARE, UTI_CARE, PCR_ADD_ON, EXPANDED_TEST, URINE_TEST, PRESCRIPTION_TREATMENT, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, UNGATED_RX, MALE_PARTNER, GIFT_CARD, OTHER
- `status` - ACTIVE or CANCELLED
- `payload` (JSONField) - stores full Shopify webhook payload
- `checkout_source` - tracks origin of checkout

Also found related models in the same file:
- `OrderLineItem` (lines 184-260) - individual items in an order
- `OrderShippingAddress` (lines 262-292) - one-to-one with Order
- `RelatedOrder` (lines 294-313) - analytics cross-sell tracking
- `PartnerRelationship` (lines 316-338) - male partner treatment vouchers

## Search 2: Order creation signals and side effects
Searched for "order creation side effects post save signal".

Found `_process_shopify_order_impl` as the primary orchestrator in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`. Also found `prescription_fill_post_save` signal in `care/signals.py` and `lab_order_status_changed` in `consults/signals.py`.

## Search 3: Main orchestration function
Searched for process_shopify_order create test event.

Found the call chain:
- `process_shopify_order()` at line 204 - wrapper with error handling
- `_process_shopify_order_impl()` at line 238 - main orchestrator
- `process_order_line_item()` at line 1322 - per-line-item processing
- `process_shopify_order_for_care()` at line 1807 - care order branch
- `process_shopify_order_for_test()` at line 1600 - test kit branch
- `process_shopify_order_for_treatment_refill()` at line 2089 - prescription refill branch
- `process_shopify_order_for_pcr_add_on()` at line 1964 - PCR add-on branch

## Search 4: Reading the main orchestrator (_process_shopify_order_impl)
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 238-790.

Key records created during orchestration:
1. **Order** - `Order.objects.get_or_create(provider=PROVIDER_SHOPIFY, provider_id=order_number)` at line 336
2. **OrderShippingAddress** - `OrderShippingAddress.objects.get_or_create(order=order)` at line 382
3. **OrderLineItem** - created for each line item via `process_order_line_item()`
4. **RelatedOrder** - `RelatedOrder.objects.get_or_create(parent_order, cross_sell_order)` at line 573 (for cross-sell orders)

Async tasks queued at the end:
- `void_share_a_sale_transaction.delay()` (on cancellation)
- `attach_otc_treatments_to_existing_consult(order)`
- `process_gift_cards.delay(order.id, payload)` (if gift cards involved)
- `send_any_paid_event.delay(order.order_number)`
- `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)`

## Search 5: Line item processing (process_order_line_item)
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 1322-1597.

Records created per line item:
1. **OrderLineItem** - `OrderLineItem.objects.get_or_create(order, shopify_id, ...)` at line 1401
2. **OTCTreatment** - `OTCTreatment.objects.bulk_create(...)` at line 1512 (for OTC care products)
3. **UrineTest** - `create_urine_tests_for_order_if_needed()` at line 1541 (for urine test orders)
   - Then queues `create_unregistered_testkit_order_for_urine_test.delay()` via Junction

The line item processing uses `transaction.atomic()` with `select_for_update()` on the Order to prevent race conditions.

## Search 6: Care order branch (process_shopify_order_for_care)
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 1807-1961.

For care orders:
1. Links the order to an existing **Consult** via `consult_uid` attribute
2. Creates **ConsultOrder** - `ConsultOrder.objects.get_or_create(consult=consult, order=order)` at line 1858
3. Updates Consult status to `STATUS_ORDERED`
4. Calls `add_ordered_products_to_consult(consult, order)` for selected-treatment orders
5. Creates **ConsultTask** (failure alert) if consult_uid is missing/invalid (line 1952)
6. Queues `send_consult_paid_event.delay(consult.uid, order.provider_id)`

## Search 7: Treatment refill branch (process_shopify_order_for_treatment_refill)
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 2089-2201.

For prescription refill/treatment orders:
1. Gets or creates **PrescriptionFill** - `PrescriptionFill.objects.get_or_create(order=order)` at line 2108
2. Creates **PrescriptionFillOrder** - `PrescriptionFillOrder.objects.get_or_create(prescription_fill, order)` at line 2143
3. Calls `create_prescription_fill_prescriptions()` to link Prescription records
4. Calls `create_prescription_fill_otc_treatments()` for OTC items
5. Queues `send_prescription_refill_request.delay(order.id, prescription_fill.id)` to send to Precision pharmacy

## Search 8: Ungated RX consult creation task
Read `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` lines 344-461.

For ungated RX orders without an existing consult:
1. Creates new **Consult** - `Consult.objects.get_or_create(user, type=TYPE_UNGATED_RX, ...)` at line 400
2. Creates **ConsultIntake** - `ConsultIntake.objects.get_or_create(consult=...)` at line 408
3. Creates **ConsultOrder** link at line 449

## Search 9: Prescription refill request task (send_prescription_refill_request)
Read `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` lines 157-267.

When prescription fill request is processed:
1. Updates `PrescriptionFill.status` from DRAFT to CREATED
2. Calls `send_create_patient_request_to_precision()` - creates patient in Precision pharmacy
3. Calls `send_create_prescription_request_to_precision()` per prescription
4. Calls `send_create_otc_treatment_request_to_precision()` per OTC treatment
5. Calls `send_fill_request_to_precision()` - sends fill request
6. Creates **ConsultTask** if shipping state is invalid or no refills remain

## Search 10: OTC treatment attachment
Read `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` lines 479-522.

`attach_otc_treatments_to_existing_consult()`:
1. Creates **ConsultOTCTreatment** junction records linking OTC treatments to active consult

## Search 11: Models with ecomm_order FK
Searched for `ecomm_order = models.ForeignKey`.

Found:
- `test_results/models/lab_test.py:19` - LabTest has `ecomm_order` FK
- `test_results/models/test.py:120` - Test (vaginal test) has `ecomm_order` FK
- `providers/models.py:43` - ProviderTestOrder has `ecomm_order` FK
- `accounts/models.py:255` - (another model) has `ecomm_order` FK

## Search 12: Berlin fulfillment and Test association
Read `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` lines 685-746 and 380-460.

`send_order_to_berlin_for_fulfillment()`:
- Sends the Shopify payload to Berlin (fulfillment provider) for physical shipping
- On 200/201 response, sets `order.sent_to_berlin_at`

`process_tracking_statuses()` (triggered later via webhooks):
- Associates existing `Test` with `order` via `test.ecomm_order = order` at line 400
- For provider test orders: links `ProviderTestOrder.test = test`
- For expanded test orders: calls `add_expanded_vpcr_panel_to_test_kit()` to add `LabTest` records

## Search 13: Urine test (UTI) creation
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 1141-1257.

`create_urine_tests_for_order_if_needed()`:
- Creates **UrineTest** records via `UrineTest.objects.bulk_create()` (one per quantity)
- Status set to `STATUS_ORDERED`, lab to `LAB_JUNCTION`

`create_urine_tests_and_unregistered_testkit_orders_for_order()`:
- After creating UrineTests, queues `create_unregistered_testkit_order_for_urine_test.delay()` to create order in Junction lab system

## Search 14: Gift card processing
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 1094-1140.

For MPT (Male Partner Treatment) voucher line items:
1. Creates Shopify gift card via admin API
2. Creates **GiftCard** - `GiftCard.objects.get_or_create(order, shopify_id, gift_card_code, value)` at line 1118
3. Stores gift card code in `OrderLineItem.gift_card_code`

## Search 15: PCR add-on branch
Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 1964-2010.

For PCR add-on orders:
1. Looks up existing **Test** by hash from order note attributes
2. Calls `add_expanded_vpcr_panel_to_test_kit(test, order)` - adds a `LabTest` record for vPCR panel
3. Updates `ProviderTestOrder.add_expanded_pcr = True` if provider-ordered

## Search 16: ConsultTask error records
Searched for ConsultTask creation patterns.

ConsultTask is created as a failure/alerting mechanism when:
- Care order is missing/invalid `consult_uid` (line 1952 in utils.py - `TASK_TYPE_A_LA_CARE_FAILURE`)
- Treatment refill has invalid shipping state (tasks.py line 205 - `TASK_TYPE_TREATMENT_REFILL_FAILURE`)
- Prescription has no remaining refills (tasks.py line 218 - `TASK_TYPE_TREATMENT_REFILL_FAILURE`)
- Ordered products don't match consult selected treatments (line 1918 - `TASK_TYPE_A_LA_CARE_FAILURE`)
- Missing cart attributes with transparent care line items (line 519)

---

## Final Answer

### Order Creation: Full Chain of Record Creation

The entry point for order creation is a Shopify webhook that calls `process_shopify_order()` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`. This is a thin wrapper that delegates to `_process_shopify_order_impl()` and catches all exceptions for NewRelic logging.

---

### Step 1: Core Order Records (always created)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 336-432

```python
# 1. Order - idempotent get_or_create
order, _ = Order.objects.get_or_create(
    provider=Order.PROVIDER_SHOPIFY,
    provider_id=order_number,
)

# 2. OrderShippingAddress - one-to-one with Order
shipping_address_record, _ = OrderShippingAddress.objects.get_or_create(order=order)
```

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 1401-1415

```python
# 3. OrderLineItem - one per Shopify line item, inside transaction.atomic()
with transaction.atomic():
    locked_order = Order.objects.select_for_update().get(id=order.id)
    line_item, created = OrderLineItem.objects.get_or_create(
        order=locked_order,
        shopify_id=shopify_id,
        defaults={...}
    )
```

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 570-575

```python
# 4. RelatedOrder - only if order has parent_order_number attribute (cross-sell)
RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)
```

---

### Step 2: Order-Type-Specific Records

The orchestrator branches based on `order.order_type`:

#### Branch A: Care Orders (Vaginitis, STI, UTI Care, A La Carte, Dynamic Bundle, Mixed Care, Male Partner)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_care()` (line 1807)

1. **ConsultOrder** - links the Order to the pre-existing Consult
   ```python
   ConsultOrder.objects.get_or_create(consult=consult, order=order)
   ```
   Model at: `/Users/albertgwo/Work/evvy/backend/consults/models.py`, line 742

2. **Consult** status updated to `STATUS_ORDERED` (if previously `STATUS_OPTED_IN`)

3. **ConsultTask** (failure record) - created if `consult_uid` is missing or no matching Consult found
   ```python
   ConsultTask.objects.create(
       task_type=ConsultTask.TASK_TYPE_A_LA_CARE_FAILURE,
       task_data={"reason": error_message},
   )
   ```

#### Branch B: Test Kit Orders (Standard, Expanded, Urine Test)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_test()` (line 1600)

For urine test orders, created during `process_order_line_item()`:
1. **UrineTest** - one per quantity unit ordered
   ```python
   UrineTest.objects.bulk_create([
       UrineTest(ecomm_order=order, lab=UrineTest.LAB_JUNCTION, status=Test.STATUS_ORDERED)
       for _ in range(tests_to_create)
   ])
   ```
   File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, line 1171
   Model at: `/Users/albertgwo/Work/evvy/backend/test_results/models/test.py`

2. Junction lab order queued via Celery:
   ```python
   create_unregistered_testkit_order_for_urine_test.delay(urine_test_ids=..., ecomm_order_id=...)
   ```
   Task at: `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`, line 213

For provider-initiated test orders, the function creates or links a **ProviderTestOrder**:
```python
pto = ProviderTestOrder.objects.create(
    provider=provider,
    patient_email=patient_email_candidate,
    order_method=ProviderTestOrder.PATIENT_PAID,
    ecomm_order=order,
)
```
Model at: `/Users/albertgwo/Work/evvy/backend/providers/models.py`, line 43

#### Branch C: Prescription Refill Orders (and Ungated RX routed to refill path)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_treatment_refill()` (line 2089)

1. **PrescriptionFill** - created or fetched:
   ```python
   prescription_fill, _ = PrescriptionFill.objects.get_or_create(order=order)
   ```

2. **PrescriptionFillOrder** - through-table linking PrescriptionFill and Order:
   ```python
   PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
   ```
   Model at: `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 831

3. Via `create_prescription_fill_prescriptions()` called from `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` - links existing `Prescription` records to the fill

4. Via `create_prescription_fill_otc_treatments()` - links `OTCTreatment` records to the fill

5. **Celery task** `send_prescription_refill_request.delay(order.id, prescription_fill.id)` queued. This task (line 157 in `tasks.py`):
   - Updates `PrescriptionFill.status` to `PRESCRIPTION_FILL_STATUS_CREATED`
   - Sends create-patient, create-prescription, and fill requests to Precision pharmacy
   - Creates **ConsultTask** on failure (`TASK_TYPE_TREATMENT_REFILL_FAILURE`)

#### Branch D: Ungated RX Orders (routed to consult/intake path)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 683-692; task in `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, line 344

When `can_refill_entire_order()` returns False:
1. **Consult** - created if no in-progress consult exists:
   ```python
   Consult.objects.get_or_create(
       user=user, type=Consult.TYPE_UNGATED_RX,
       purchase_type=Consult.PURCHASE_TYPE_A_LA_CARTE,
       status=Consult.STATUS_ORDERED,
       defaults={"order": order, "pharmacy_type": Consult.PHARMACY_TYPE_PRECISION},
   )
   ```

2. **ConsultIntake** - created alongside the Consult:
   ```python
   ConsultIntake.objects.get_or_create(consult=latest_in_progress_consult)
   ```

3. **ConsultOrder** - links Consult and Order:
   ```python
   ConsultOrder.objects.get_or_create(consult=latest_in_progress_consult, order=order)
   ```

#### Branch E: PCR Add-On Orders
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_pcr_add_on()` (line 1964)

1. Finds existing **Test** by hash from order note attributes
2. Calls `add_expanded_vpcr_panel_to_test_kit(test, order)` which creates a **LabTest** record for the vPCR panel
3. Updates `ProviderTestOrder.add_expanded_pcr = True` if provider-ordered

---

### Step 3: Line-Item-Level Side Effects (OTC Treatments and Gift Cards)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_order_line_item()` lines 1498-1525

For care products with `RegulatoryCategory.OVER_THE_COUNTER`:
```python
OTCTreatment.objects.bulk_create([
    OTCTreatment(order=order, product=care_product, user=user)
    for _ in range(quantity - existing_otc_treatments_count)
])
```
Model at: `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 895

For MPT voucher SKUs, inside `transaction.atomic()`:
```python
GiftCard.objects.get_or_create(
    order=locked_line_item.order,
    shopify_id=locked_line_item.gift_card_id,
    gift_card_code=locked_line_item.gift_card_code,
    value=locked_line_item.price,
)
```

---

### Step 4: Post-Processing (always runs at the end)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 732-763

1. `attach_otc_treatments_to_existing_consult(order)` - creates **ConsultOTCTreatment** junction records
2. `process_gift_cards.delay(order.id, payload)` - processes gift card purchases/redemptions
3. `send_any_paid_event.delay(order.order_number)` - analytics event
4. `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` - physical fulfillment

---

### Step 5: Deferred Test-Order Association (via Berlin webhook)

**File:** `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`, `process_tracking_statuses()` lines 380-455

When Berlin sends a tracking webhook (test kit scanned/shipped):
1. Associates existing **Test** (vaginal test kit, pre-registered by Berlin) with the Order: `test.ecomm_order = order`
2. For provider test orders: links **ProviderTestOrder.test = test**
3. For expanded test orders: calls `add_expanded_vpcr_panel_to_test_kit()` to add **LabTest** record if missing

---

### Full Record Creation Map

```
Order (always created)
├── OrderShippingAddress (always created, one-to-one)
├── OrderLineItem[] (one per Shopify line item)
│   ├── OTCTreatment[] (for OTC care product SKUs)
│   └── UrineTest[] (for urine test SKUs, one per quantity)
│       └── Junction LabOrder (via Celery, external lab system)
├── RelatedOrder (only for cross-sell orders with parent_order_number)
│
├── [CARE ORDER BRANCH]
│   └── ConsultOrder (links to pre-existing Consult)
│       └── Consult.status → STATUS_ORDERED
│
├── [TEST KIT BRANCH - provider-initiated]
│   └── ProviderTestOrder (created or linked)
│
├── [PRESCRIPTION REFILL BRANCH]
│   ├── PrescriptionFill (created or fetched)
│   │   ├── PrescriptionFillOrder (through-table, via Celery)
│   │   ├── PrescriptionFillPrescriptions[] (via Celery, links Prescription records)
│   │   └── PrescriptionFillOTCTreatments[] (via Celery, links OTCTreatment records)
│   └── ConsultTask (TREATMENT_REFILL_FAILURE, only on error)
│
├── [UNGATED RX - NEW CONSULT PATH]
│   ├── Consult (newly created)
│   ├── ConsultIntake (created alongside Consult)
│   └── ConsultOrder (links new Consult to Order)
│
├── [MPT VOUCHER BRANCH]
│   └── GiftCard (Shopify gift card purchase)
│
└── [DEFERRED - via Berlin webhook]
    └── Test.ecomm_order = order (association, no new record)
        └── LabTest (for expanded panel, if missing)
```

---

### Failure Handling

1. **No transaction wrapping at orchestrator level** - `_process_shopify_order_impl` does not run inside a single `transaction.atomic()`. Only `process_order_line_item` wraps the OrderLineItem creation in an atomic block with row-level locking.

2. **Idempotency** - The function is designed to be idempotent. `get_or_create` is used for most records, so re-running on a duplicate webhook is safe.

3. **ConsultTask alerts** - When a step fails in a way that requires human intervention (missing consult UID, invalid shipping state, no refills remaining), a `ConsultTask` record is created. These are visible to the ops team.

4. **Exception propagation** - `process_shopify_order()` catches all exceptions, logs to NewRelic with context (order number, error category, processing time), then re-raises so the caller (usually a Celery task or webhook handler) can handle retry logic.

5. **Celery task failures** - Steps delegated to Celery (Berlin fulfillment, prescription refill requests, analytics events) can fail independently. Berlin fulfillment failures raise exceptions which Celery retries. Precision pharmacy requests create `ConsultTask` alerts on failure.

6. **Partial state risk** - Because there is no outer transaction, a failure midway through `_process_shopify_order_impl` (e.g., after creating `ConsultOrder` but before queuing `send_prescription_refill_request`) will leave the database in a partially-processed state. Idempotency via `get_or_create` mitigates this by allowing safe re-processing on retry.
