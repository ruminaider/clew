# E3 Exploration Log

## Search 1: Find the Order model
Searched for `class Order` across all Python files in the repo.

Found the Order model at `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`.

Key fields:
- `user` (FK to User, nullable)
- `cart` (FK to Cart, nullable)
- `email`, `evvy_account_email`
- `provider`, `provider_id`, `order_number`, `shopify_order_id`, `shopify_customer_id`
- `checkout_id`, `checkout_token`
- `order_type` (TE/CA/SC/UC/PA/ET/UT/OT/PR/AL/BU/MC/UX/MP/GC)
- `business_verticals` (multiselect: care/test/other)
- `sku`, `status` (AC/CA)
- `shipping_method`, `payload` (JSONField, full Shopify webhook)
- `is_subscription_order`, `is_testing_order`, `is_manual_invoice`
- `total_line_items_price`, `sent_to_berlin_at`, `checkout_source`

Related models in the same file:
- `OrderLineItem` (FK to Order via `line_items` related_name)
- `OrderShippingAddress` (OneToOne to Order)
- `RelatedOrder` (tracks cross-sells: parent_order -> cross_sell_order)
- `PartnerRelationship` (user -> user_partner via gift_card_code)

## Search 2: Find the main order processing entry point
Searched for `_process_shopify_order|process_order|create_order|handle_order` across Python files.

The primary entry point is in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:
- `process_shopify_order()` — public wrapper with error handling
- `_process_shopify_order_impl()` — the actual implementation

## Search 3: Read `_process_shopify_order_impl` (lines 238–791)
This is the orchestrator function. Key steps identified:

1. **Parse payload**: extracts order_number, checkout_id, shopify_order_id, email, line_items, shipping_address, custom_attributes (consult_uid, checkout_source, parent_order_number, bulk_order_id, provider_test_order_id, cart_id, session_id)

2. **Create/get Order**: `Order.objects.get_or_create(provider=SHOPIFY, provider_id=order_number)` — idempotent

3. **Create OrderShippingAddress**: `OrderShippingAddress.objects.get_or_create(order=order)` — created if shipping_address present

4. **Link ProviderTestOrder**: If `provider_test_order_id` is set, links `pto.ecomm_order = order`

5. **Process each line item**: calls `process_order_line_item()` for each — creates `OrderLineItem` records

6. **Create RelatedOrder**: If `parent_order_number` is set, `RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)`

7. **Route by order type**:
   - Care orders (CA/SC/UC/AL/BU/MC/MP): `process_shopify_order_for_care()`
   - Test orders (TE/ET/UT): `process_shopify_order_for_test()`
   - PCR Add-on (PA): `process_shopify_order_for_pcr_add_on()`
   - Unknown: `process_shopify_order_for_unknown_order_sku()`

8. **Treatment refill path**: If order contains prescription treatment line items (outside of AL/MC/BU/UX/MP types): `process_shopify_order_for_treatment_refill()`

9. **Ungated RX routing**: Either routes to refill path or creates a new consult

10. **OTC attachment**: `attach_otc_treatments_to_existing_consult(order)`

11. **Gift card processing**: `process_gift_cards.delay(order.id, payload)` (async)

12. **Analytics events**: `send_any_paid_event.delay()`, `track_event()` (Braze events for test purchases)

13. **Fulfillment**: `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` (async Celery task)

## Search 4: Read `process_order_line_item` (lines 1322–1597)
Creates/updates `OrderLineItem` for each Shopify line item. Additional side effects:

- Resolves `EcommProduct` and `CareProduct` from SKU/variant_id
- Creates `OTCTreatment` records for OTC regulatory category products (bulk_create per quantity)
- For `ORDER_TYPE_URINE_TEST`:
  - Calls `create_urine_tests_for_order_if_needed()` → bulk_creates `UrineTest` records
  - Calls `create_urine_tests_and_unregistered_testkit_orders_for_order()` → queues Junction API calls
- Validates/processes MPT (Male Partner Treatment) voucher line items: creates gift card and `GiftCard` object, updates `PartnerRelationship`
- Checks Cart for subscription metadata

## Search 5: Read `process_shopify_order_for_care` (lines 1807–1961)
Care-order specific processing:

1. Looks up the `Consult` by `consult_uid` from note_attributes
2. If consult found:
   - `order.user = consult.user`
   - `consult.order = order`
   - **Creates `ConsultOrder`**: `ConsultOrder.objects.get_or_create(consult=consult, order=order)`
   - Updates `consult.status` to `STATUS_ORDERED` if still in `STATUS_OPTED_IN`
   - Fires `send_consult_paid_event.delay(consult.uid, order.provider_id)` (async)
   - If consult has selected treatments purchase type: calls `add_ordered_products_to_consult(consult, order)` and may create `ConsultTask` alert on mismatch
3. If consult NOT found (and not staff/test user/MPT): creates `ConsultTask` with `TASK_TYPE_A_LA_CARE_FAILURE`
4. Marks cart as purchased: `mark_order_cart_as_purchased()`

## Search 6: Read `process_shopify_order_for_treatment_refill` (lines 2089–2201)
Prescription refill processing:

1. **Get or create `PrescriptionFill`**: `PrescriptionFill.objects.get_or_create(order=order)` or retrieves existing by `prescription_fill_id`
2. Links consult to fill: `prescription_fill.consult = consult`
3. Sets user on order
4. **Creates `PrescriptionFillOrder`**: `PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)` through table
5. Fetches ordered products, resolves `Prescription` objects
6. **Creates `PrescriptionFillPrescriptions`** (via `create_prescription_fill_prescriptions`): through table linking PrescriptionFill <-> Prescription with fill_quantity
7. **Creates `PrescriptionFillOTCTreatments`** (via `create_prescription_fill_otc_treatments`): through table linking PrescriptionFill <-> OTCTreatment
8. Queues async task: `send_prescription_refill_request.delay(order.id, prescription_fill.id)`
9. Marks cart as purchased

## Search 7: Read `send_prescription_refill_request` Celery task (ecomm/tasks.py lines 157–267)
Async task that:

1. Validates shipping state against `VALID_STATES` (creates `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` if invalid)
2. Validates prescriptions have remaining refills (raises + creates `ConsultTask` if not)
3. Updates `PrescriptionFill.status` from DRAFT → CREATED
4. Fires `send_prescription_refills_paid_event.delay()` (Braze event)
5. Calls `send_create_patient_request_to_precision()` → Precision pharmacy API
6. Calls `send_create_prescription_request_to_precision()` for each prescription → Precision API
7. Calls `send_create_otc_treatment_request_to_precision()` for each OTC treatment → Precision API
8. Calls `send_fill_request_to_precision()` → dispatches fill to pharmacy

On cancellation: calls `send_cancel_fill_request_to_precision()`, creates `ConsultTask` on failure.

## Search 8: Read `send_order_to_berlin_for_fulfillment` Celery task (shipping/tasks.py lines 684–746)
Async task that:

1. Calls `BerlinAPIClient().create_order(shopify_payload)` (or `cancel_order` for cancellations)
2. On success (200/201): sets `order.sent_to_berlin_at = timezone.now()` and saves
3. On failure: logs error, raises exception (can be retried via `retry_failed_berlin_order_fulfillments` periodic task)

## Search 9: Identify `create_prescription_fill_prescriptions` / `create_prescription_fill_otc_treatments` (shipping/precision/utils.py lines 821–874)
- `create_prescription_fill_prescriptions`: creates `PrescriptionFillPrescriptions` through-table rows via `get_or_create`
- `create_prescription_fill_otc_treatments`: creates `PrescriptionFillOTCTreatments` through-table rows via `get_or_create`, avoids duplicates

## Search 10: Identify `UrineTest` creation path
In `create_urine_tests_for_order_if_needed` (ecomm/utils.py lines 1141–1191):
- `UrineTest.objects.bulk_create([UrineTest(ecomm_order=order, lab=LAB_JUNCTION, status=STATUS_ORDERED) ...])` — one per quantity

## Search 11: Identify `GiftCard` object creation for MPT voucher
In `_validate_mpt_voucher_line_item` (called from `process_order_line_item`):
- `GiftCard.objects.get_or_create(order=..., shopify_id=..., gift_card_code=..., value=...)`
- Updates `OrderLineItem.gift_card_id` and `gift_card_code`
- Updates `PartnerRelationship` Braze attributes

---

## Final Answer

### Entry Point

Order creation begins when a Shopify webhook is received by the Django API. The webhook view calls:

```
/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py
  → process_shopify_order(payload, is_order_cancellation)       [ecomm/utils.py:204]
    → _process_shopify_order_impl(payload, is_order_cancellation, order_logger)  [ecomm/utils.py:238]
```

`process_shopify_order` is a thin wrapper that catches all exceptions, logs them to NewRelic, and re-raises.

---

### Phase 1: Core Order and Address Records

**File**: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

**Order (get_or_create)**
```python
order, _ = Order.objects.get_or_create(
    provider=Order.PROVIDER_SHOPIFY,
    provider_id=order_number,
)
```
The Order is created idempotently. Fields then updated include: `checkout_id`, `checkout_token`, `order_number`, `shopify_order_id`, `shopify_customer_id`, `email`, `total_line_items_price`, `is_testing_order`, `is_manual_invoice`, `payload`, `status`, `shipping_method`, `checkout_source`, `order_type`, `sku`, `business_verticals`.

**OrderShippingAddress (get_or_create)**
```python
shipping_address_record, _ = OrderShippingAddress.objects.get_or_create(order=order)
```
Created only if the Shopify payload includes a `shipping_address` block (lines 378–394). OneToOne to Order.

**RelatedOrder (get_or_create, conditional)**
```python
RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)
```
Created only when `parent_order_number` is in Shopify note attributes (cross-sell flow). Line 573.

---

### Phase 2: Line Item Processing

**File**: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `process_order_line_item` (line 1322)

For each Shopify line item, the following records may be created:

**OrderLineItem (get_or_create)**
```python
line_item, created = OrderLineItem.objects.get_or_create(
    order=locked_order,
    shopify_id=shopify_id,
    defaults={...}
)
```
Created inside a `transaction.atomic()` with `select_for_update()` on the Order row to prevent race conditions. Stores SKU, product_id, variant_id, order_type, quantity, price, business_vertical, purchase_type, metadata.

**OTCTreatment (bulk_create, conditional)**
```python
OTCTreatment.objects.bulk_create([
    OTCTreatment(order=order, product=care_product, user=user)
    for _ in range(quantity - existing_count)
])
```
Created when the line item's care product has `regulatory_category == OTC`. One record per quantity unit ordered (lines 1504–1521).

**UrineTest (bulk_create, conditional)**
```python
UrineTest.objects.bulk_create([
    UrineTest(ecomm_order=order, lab=LAB_JUNCTION, status=STATUS_ORDERED)
    for _ in range(tests_to_create)
])
```
Created when `order_type == ORDER_TYPE_URINE_TEST`. One per quantity. Created early in line item processing so Junction (external lab) can store sample IDs on them (lines 1526–1558, helper at lines 1141–1191).

**GiftCard (get_or_create, conditional)**
```python
GiftCard.objects.get_or_create(
    order=line_item.order,
    shopify_id=line_item.gift_card_id,
    gift_card_code=line_item.gift_card_code,
    value=line_item.price,
)
```
Created for Male Partner Treatment (MPT) voucher SKUs. Also sets `OrderLineItem.gift_card_id` and `gift_card_code` (lines 1111–1123).

---

### Phase 3: Order-Type-Specific Processing

#### A. Care Orders (Vaginitis, STI, UTI, A La Carte, Dynamic Bundle, Mixed Care, Male Partner)

**File**: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `process_shopify_order_for_care` (line 1807)

**ConsultOrder (get_or_create)**
```python
ConsultOrder.objects.get_or_create(consult=consult, order=order)
```
Through-table linking the pre-existing `Consult` (identified by `consult_uid` in order note_attributes) to this Order (line 1858). The Consult is NOT created here; it must pre-exist from the care intake flow.

Also updates `consult.order = order`, advances `consult.status` to `STATUS_ORDERED` if still in `STATUS_OPTED_IN`, and fires the `send_consult_paid_event` async task.

**ConsultTask (get_or_create / create, on failure)**
```python
ConsultTask.objects.get_or_create(
    task_type=ConsultTask.TASK_TYPE_A_LA_CARE_FAILURE,
    task_data={"reason": error_message},
)
```
Created when consult_uid is missing/invalid, or when ordered products don't match consult's selected treatments (lines 1918–1922, 1952–1954).

#### B. Test Kit Orders (Standard vNGS, Expanded Test)

**File**: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `process_shopify_order_for_test` (line 1600)

Primarily links the order to a user by email match. For provider-initiated orders (magic link), creates or links a `ProviderTestOrder` record. No new test records are created in this path (the physical test kits are created after lab registration).

For bulk provider orders, routes to `_process_bulk_provider_order()`.

#### C. Prescription Treatment Refill Orders

**File**: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `process_shopify_order_for_treatment_refill` (line 2089)

**PrescriptionFill (get_or_create)**
```python
prescription_fill, _ = PrescriptionFill.objects.get_or_create(order=order, user=user)
```
Or retrieved by explicit `prescription_fill_id` from note_attributes. Represents one dispensing event to the pharmacy (lines 2102–2108).

**PrescriptionFillOrder (get_or_create)**
```python
PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
```
Through-table linking a fill event to its order(s) (line 2143).

**PrescriptionFillPrescriptions (get_or_create, per prescription)**
```python
PrescriptionFillPrescriptions.objects.get_or_create(
    prescriptionfill=prescription_fill,
    prescription=prescription,
    defaults={"fill_quantity": ..., "precision_reference_id": ...},
)
```
Through-table linking the fill event to each `Prescription` in the order. Created in `create_prescription_fill_prescriptions()` in `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` (line 836).

**PrescriptionFillOTCTreatments (get_or_create, per OTC treatment)**
```python
PrescriptionFillOTCTreatments.objects.get_or_create(
    prescriptionfill=prescription_fill,
    otctreatment=otc_treatment,
    defaults={"fill_quantity": ..., "precision_reference_id": ...},
)
```
Through-table linking the fill event to each OTC treatment. Created in `create_prescription_fill_otc_treatments()` (line 867).

#### D. PCR Add-on Orders

Retrieves the existing `Test` by `test_kit_hash` and calls `add_expanded_vpcr_panel_to_test_kit()` to attach expanded PCR panels. May update `ProviderTestOrder.add_expanded_pcr = True`.

---

### Phase 4: Async Fulfillment Tasks (Celery)

#### Berlin Fulfillment (all non-UTI orders)

**File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`, function `send_order_to_berlin_for_fulfillment` (line 685)

Queued with: `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` (utils.py line 763)

- Calls `BerlinAPIClient().create_order(shopify_payload)` or `cancel_order`
- On success: sets `order.sent_to_berlin_at = timezone.now()` (no new records created)
- On failure: raises exception; retried by `retry_failed_berlin_order_fulfillments` periodic task

#### Precision Pharmacy Fulfillment (prescription refill orders)

**File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, function `send_prescription_refill_request` (line 157)

Queued with: `send_prescription_refill_request.delay(order.id, prescription_fill.id)` (utils.py line 2198)

1. **Validates shipping state** — creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` and returns early if state invalid
2. **Validates refill count** — creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` and raises if no remaining refills
3. **Updates PrescriptionFill.status** to CREATED
4. **Precision API calls**: `send_create_patient_request_to_precision()`, `send_create_prescription_request_to_precision()` (per Rx), `send_create_otc_treatment_request_to_precision()` (per OTC)
5. `send_fill_request_to_precision()` — dispatches the fill to the pharmacy

#### Gift Card Processing

`process_gift_cards.delay(order.id, payload)` — async task, processes gift card redemptions. Creates or updates `GiftCard` records.

---

### Failure Handling

| Failure Point | Behavior |
|---|---|
| Missing line items in payload | Logs warning, returns early (no Order created/updated) |
| Invalid `evvy_account_email` format | Logs error, continues without setting field |
| `consult_uid` missing/invalid on care order | Creates `ConsultTask(TASK_TYPE_A_LA_CARE_FAILURE)`, order saved without consult link |
| Ordered products vs selected treatments mismatch | Creates `ConsultTask(TASK_TYPE_A_LA_CARE_FAILURE)` |
| `ProviderTestOrder` link failure | Logs error, continues (soft fail) |
| MPT voucher validation failure | Raises exception (propagates up), logged |
| `UrineTest` creation failure | Logs error, exception caught in `process_order_line_item`, logged |
| Berlin API failure | Raises; Celery retries; periodic `retry_failed_berlin_order_fulfillments` task retries |
| Invalid state for prescription refill | Creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)`, returns early |
| No remaining refills | Creates `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)`, raises |
| Precision API failure during fill | Exception propagates from Celery task |
| Gift card processing failure | `ValueError` raised inside `_validate_mpt_voucher_line_item`, propagates |

The top-level `process_shopify_order` catches ALL exceptions, logs them to NewRelic/OrderLogger, and re-raises. This ensures no order processing failure is silent but also does not swallow exceptions that should signal webhook retry.

---

### Model Relationship Map

```
Order
├── OrderLineItem (FK, related_name="line_items") — one per Shopify line item
│   ├── care_product → CareProduct (FK, nullable)
│   └── ecomm_product → EcommProduct (FK, nullable)
├── OrderShippingAddress (OneToOne) — shipping address from webhook
├── RelatedOrder (FK as cross_sell_order or parent_order) — cross-sell analytics
├── ConsultOrder (FK via consult+order) — links to Consult (care orders)
├── PrescriptionFillOrder (FK via prescriptionfill+order) — links to PrescriptionFill
├── OTCTreatment (FK via order) — one per OTC unit ordered
├── UrineTest (FK via ecomm_order) — one per UTI test unit ordered
└── GiftCard (FK via order) — MPT voucher gift cards

PrescriptionFill (created on refill path)
├── PrescriptionFillOrder → Order (through table)
├── PrescriptionFillPrescriptions → Prescription (through table, per Rx)
└── PrescriptionFillOTCTreatments → OTCTreatment (through table, per OTC)

ConsultOrder
├── consult → Consult (FK)
└── order → Order (FK)
```

---

### Key Files

- `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` — Order, OrderLineItem, OrderShippingAddress, RelatedOrder, PartnerRelationship models
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — Main orchestration: `process_shopify_order`, `_process_shopify_order_impl`, `process_order_line_item`, `process_shopify_order_for_care`, `process_shopify_order_for_test`, `process_shopify_order_for_treatment_refill`, `create_urine_tests_for_order_if_needed`
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — `send_prescription_refill_request` Celery task
- `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` — `send_order_to_berlin_for_fulfillment` Celery task
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` — `create_prescription_fill_prescriptions`, `create_prescription_fill_otc_treatments`
- `/Users/albertgwo/Work/evvy/backend/care/models.py` — PrescriptionFill, PrescriptionFillOrder, PrescriptionFillPrescriptions, PrescriptionFillOTCTreatments, OTCTreatment models
- `/Users/albertgwo/Work/evvy/backend/consults/models.py` — ConsultOrder, ConsultTask models
