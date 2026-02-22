# E3: Order Creation Chain — Side Effects, Orchestration, and Failure Handling

## Entry Point

The order creation chain starts with a Shopify webhook payload being processed by:

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`** — `process_shopify_order(payload, is_order_cancellation)`

This is the public wrapper that catches all exceptions, logs them to NewRelic, and re-raises. It delegates to `_process_shopify_order_impl(payload, is_order_cancellation, order_logger)`.

---

## Phase 1: Order Record Creation

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 336–432

```python
order, _ = Order.objects.get_or_create(
    provider=Order.PROVIDER_SHOPIFY,
    provider_id=order_number,
)
```

**Records created:**

1. **`Order`** (`ecomm.Order`) — always created/updated via `get_or_create` on `(provider, provider_id)`.

2. **`OrderShippingAddress`** (`ecomm.OrderShippingAddress`) — created via `get_or_create(order=order)` if `shipping_address` is present in payload. It is a `OneToOneField` on `Order`.

3. **`ProviderTestOrder`** link (optional) — if `provider_test_order_id` is in note attributes, an existing `ProviderTestOrder` record has its `ecomm_order` FK set to the new order (lines 437–452).

---

## Phase 2: Line Item Processing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_order_line_item()`, lines 1322–1597

For **each** line item in the payload, the following records are created or updated:

4. **`OrderLineItem`** (`ecomm.OrderLineItem`) — created via `get_or_create(order=locked_order, shopify_id=shopify_id)` inside a `transaction.atomic()` with `select_for_update()` on the parent Order (prevents race conditions with duplicate webhooks).

5. **`OTCTreatment`** (`care.OTCTreatment`) — if the line item maps to an OTC-regulated `care.Product`, one `OTCTreatment` record is bulk-created per unit of quantity, tied to the order, product, and user (lines 1503–1521).

6. **`UrineTest`** (`test_results.UrineTest`) — if the line item SKU is a urine test SKU, `UrineTest` records are bulk-created with `ecomm_order=order`, `lab=UrineTest.LAB_JUNCTION`, `status=Test.STATUS_ORDERED`. One record per quantity unit, deduplicated against existing records (lines 1526–1558, via `create_urine_tests_for_order_if_needed()`).

7. **`GiftCard`** + Shopify gift card (for MPT voucher SKUs) — if the line item is the MPT voucher SKU, a Shopify gift card is created via `ShopifyAdminAPIClient.create_gift_card()` and a `GiftCard` (`ecomm.models.product.GiftCard`) record is created via `get_or_create` (lines 1118–1123). The `OrderLineItem.gift_card_id` and `gift_card_code` fields are also populated.

---

## Phase 3: Cross-Sell / RelatedOrder Tracking

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 570–575

8. **`RelatedOrder`** (`ecomm.RelatedOrder`) — if `parent_order_number` is in order note attributes, a `RelatedOrder` record is created via `get_or_create(parent_order=parent_order, cross_sell_order=order)` to track cross-sell analytics.

---

## Phase 4: Order-Type-Specific Processing

### For Care Orders (Vaginitis, STI, UTI, A La Carte, Bundle, Mixed, Male Partner)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_care()`, lines 1807–1961

9. **`ConsultOrder`** (`consults.ConsultOrder`) — if a `consult_uid` is in note attributes and matches a `Consult` in the DB, a `ConsultOrder` through-record linking the consult and the order is created via `get_or_create(consult=consult, order=order)` (line 1858).

   The `Consult.order` FK is also set directly (`consult.order = order`) and status may be advanced from `STATUS_OPTED_IN` to `STATUS_ORDERED`.

10. **`ConsultTask`** (error path) — if no valid `consult_uid` is found for a non-staff, non-test-user care order, a `ConsultTask` with `TASK_TYPE_A_LA_CARE_FAILURE` is created (lines 1941–1955). Similarly, a `ConsultTask` is created if ordered products don't match selected treatments (lines 1918–1922).

### For Test Orders (Standard, Expanded, Urine)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_test()`, lines 1600–1786

For vaginal test orders, no new domain records are created during order processing — the `Test` (vaginal microbiome) record is a physical kit that already exists; it gets linked to the order when the patient registers the kit (the `Test.ecomm_order` FK is set at registration time). For urine tests, `UrineTest` records are already created in Phase 2.

11. **`ProviderTestOrder`** (conditional, for provider-initiated orders) — if a `provider_magic` note attribute is present, either an existing `ProviderTestOrder` is linked (`pto.ecomm_order = order`, line 1713) or a new one is created (lines 1724–1729):

```python
pto = ProviderTestOrder.objects.create(
    provider=provider,
    patient_email=patient_email_candidate,
    order_method=ProviderTestOrder.PATIENT_PAID,
    ecomm_order=order,
)
```

### For PCR Add-On Orders

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_pcr_add_on()`, lines 1964–2009

The function calls `add_expanded_vpcr_panel_to_test_kit(test_kit, order)` which adds lab test panels to the existing Test record. No new `Test` record is created; instead, `LabTest` records for the expanded PCR panel are added.

### For Treatment Refill Orders (Prescription, OTC, Ungated RX)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `process_shopify_order_for_treatment_refill()`, lines 2089–2201

12. **`PrescriptionFill`** (`care.PrescriptionFill`) — retrieved by `prescription_fill_id` from note attributes if valid, otherwise created via `get_or_create(order=order, user=user)` (lines 2102–2108).

13. **`PrescriptionFillOrder`** (`care.PrescriptionFillOrder`) — through table linking `PrescriptionFill` and `Order`, created via `get_or_create(prescription_fill=prescription_fill, order=order)` (line 2143).

14. **`PrescriptionFillPrescriptions`** (`care.PrescriptionFillPrescriptions`) — through table linking `PrescriptionFill` to each `Prescription` in the fill, created via `get_or_create` in `create_prescription_fill_prescriptions()` (file: `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py`, lines 836–843).

15. **`PrescriptionFillOTCTreatments`** (`care.PrescriptionFillOTCTreatments`) — through table linking `PrescriptionFill` to each `OTCTreatment`, created via `get_or_create` in `create_prescription_fill_otc_treatments()` (same file, lines 867–873).

### For Ungated RX Orders (routing to consult path)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 676–692; task in `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, lines 344–461

If the user has no existing in-progress consult, a **new `Consult`** and **`ConsultIntake`** are created:

```python
latest_in_progress_consult, created = Consult.objects.get_or_create(
    user=user,
    type=Consult.TYPE_UNGATED_RX,
    purchase_type=Consult.PURCHASE_TYPE_A_LA_CARTE,
    provider=Consult.PROVIDER_WHEEL,
    status=Consult.STATUS_ORDERED,
    defaults={"order": order, "pharmacy_type": Consult.PHARMACY_TYPE_PRECISION},
)
consult_intake, _ = ConsultIntake.objects.get_or_create(consult=latest_in_progress_consult)
```

16. **`Consult`** (`consults.Consult`) — ungated RX intake consult
17. **`ConsultIntake`** (`consults.ConsultIntake`) — associated intake record
18. **`ConsultOrder`** (`consults.ConsultOrder`) — linking consult to the order (line 449)

---

## Phase 5: OTC Treatment Attachment to Consult

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, `attach_otc_treatments_to_existing_consult()`, lines 479–522

19. **`ConsultOTCTreatment`** (`care.ConsultOTCTreatment`) — through table linking each `OTCTreatment` to the user's latest active consult, created via `get_or_create(consult=consult, otctreatment=otc_treatment)` (line 510).

---

## Phase 6: Asynchronous Tasks Queued

The following Celery tasks are dispatched (`.delay()`) during order processing:

| Task | File | Trigger condition |
|---|---|---|
| `send_order_to_berlin_for_fulfillment` | `shipping/tasks.py` line 685 | Every order (creates `order.sent_to_berlin_at`) |
| `send_prescription_refill_request` | `ecomm/tasks.py` line 157 | Treatment refill orders |
| `process_gift_cards` | `ecomm/tasks.py` line 552 | Orders with gift cards |
| `send_any_paid_event` | `analytics/tasks.py` | All non-cancelled orders with user |
| `void_share_a_sale_transaction` | `ecomm/tasks.py` line 94 | Cancellations only |
| `send_consult_paid_event` | `analytics/tasks.py` | Care orders with consult |
| `send_additional_tests_paid_event` | `analytics/tasks.py` | PCR add-on orders |
| `send_ungated_rx_order_paid_event` | `analytics/tasks.py` | Ungated RX orders |
| `create_unregistered_testkit_order_for_urine_test` | `test_results/lab_services/providers/junction/tasks.py` | Urine test orders |

### Berlin Fulfillment Task (line 763)

`send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` calls `BerlinAPIClient().create_order(shopify_payload)`. On success, it sets `order.sent_to_berlin_at = timezone.now()`. On failure (non-200 response), it raises an exception.

### Prescription Refill Task (`send_prescription_refill_request`, lines 156–267)

This task creates records at the **Precision pharmacy** level:
- Sets `PrescriptionFill.status` from `DRAFT` to `CREATED`
- Calls `send_create_patient_request_to_precision()`
- For each prescription: calls `send_create_prescription_request_to_precision()`
- For each OTC treatment: calls `send_create_otc_treatment_request_to_precision()`
- Finally calls `send_fill_request_to_precision()`

If the state is invalid or prescriptions lack refills, it creates a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` and returns/raises.

### Urine Test Junction Task (`create_unregistered_testkit_order_for_urine_test`, lines 214–330)

For each `UrineTest`:
20. **`LabOrder`** (`consults.LabOrder`) — created via `get_or_create(urine_test=urine_test)` with `external_order_id` from Junction API response (line 273).
21. **`LabOrderIntake`** — created via `get_or_create(lab_order=lab_order)`, then pre-populated with address from `OrderShippingAddress` (lines 285–303).

---

## Complete Record Creation Chain (Summary)

```
Order.objects.get_or_create()
  └── OrderShippingAddress.objects.get_or_create()       [if shipping address]
  └── ProviderTestOrder.ecomm_order = order (update)    [if provider_test_order_id]

  For each line item:
  └── OrderLineItem.objects.get_or_create()              [always, atomic + select_for_update]
      └── OTCTreatment.objects.bulk_create()             [if OTC care product]
      └── UrineTest.objects.bulk_create()                [if UTI test SKU]
      └── GiftCard.objects.get_or_create()               [if MPT voucher SKU]
          └── ShopifyAdminAPIClient.create_gift_card()   [Shopify API call]

  └── RelatedOrder.objects.get_or_create()               [if cross-sell order]

  [care orders]
  └── ConsultOrder.objects.get_or_create()
  └── ConsultTask.objects.get_or_create()                [on failure: missing consult]

  [treatment refill orders]
  └── PrescriptionFill.objects.get_or_create()
  └── PrescriptionFillOrder.objects.get_or_create()
  └── PrescriptionFillPrescriptions.objects.get_or_create()
  └── PrescriptionFillOTCTreatments.objects.get_or_create()

  [ungated RX, no existing consult]
  └── Consult.objects.get_or_create()
  └── ConsultIntake.objects.get_or_create()
  └── ConsultOrder.objects.get_or_create()

  [OTC treatment attachment]
  └── ConsultOTCTreatment.objects.get_or_create()

  [async tasks]
  └── send_order_to_berlin_for_fulfillment.delay()
      └── BerlinAPIClient.create_order()
          └── order.sent_to_berlin_at = now()
  └── send_prescription_refill_request.delay()
      └── PrescriptionFill.status = CREATED
      └── Precision pharmacy API calls (patient, prescriptions, OTC, fill)
  └── create_unregistered_testkit_order_for_urine_test.delay()
      └── LabOrder.objects.get_or_create()
      └── LabOrderIntake.objects.get_or_create()
```

---

## Failure Handling

### Synchronous failures

- **`process_shopify_order`** wraps `_process_shopify_order_impl` in `try/except Exception`. All exceptions are logged to NewRelic via `order_logger.log_processing_error()` and then re-raised. The caller (Shopify webhook handler) receives the exception.

- **Line item processing** (`process_order_line_item`) uses `transaction.atomic()` with `select_for_update()` for the `OrderLineItem` creation. If an MPT voucher gift card creation fails, the exception is re-raised after logging (line 1578), which propagates up to the webhook handler.

- **Care order without consult:** Instead of raising, the function creates a `ConsultTask` to flag the issue for manual remediation (lines 1941–1955). This is a soft failure — the order is saved but unlinked from a consult.

- **Treatment refill without prescriptions/OTC treatments:** Returns early without calling the pharmacy API (lines 2184–2189). No exception raised.

- **Treatment refill with invalid state code:** Creates a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` and returns (lines 202–210).

- **Treatment refill without remaining refills:** Creates a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` and **raises an exception** (lines 218–223), causing the Celery task to retry.

### Asynchronous failures

- **`send_order_to_berlin_for_fulfillment`:** If `BerlinAPIClient.create_order()` returns a non-200 status, it raises `Exception("Failed to send order to Berlin")`. A periodic retry task `retry_failed_berlin_order_fulfillments` in `shipping/tasks.py` (line 749) re-queues any orders where `sent_to_berlin_at` is still null.

- **`send_prescription_refill_request`:** State validation failures create a `ConsultTask` and return. Refill count failures create a `ConsultTask` and raise (causing Celery retry). Cancellation of precision fills that cannot be cancelled is caught and also creates a `ConsultTask`.

- **`create_unregistered_testkit_order_for_urine_test`:** Individual per-test failures are caught and counted; the task logs success/failure counts. If the overall task fails, it will be retried by Celery's default retry mechanism.

---

## Key Relationships Between Created Records

```
Order (ecomm.Order)
├── OrderLineItem[] (FK: order)                      — one per Shopify line item
├── OrderShippingAddress (OneToOne: order)           — one per order
├── RelatedOrder (FK: cross_sell_order)              — if cross-sell
├── ConsultOrder (FK: order)                         — links order to consult(s)
├── PrescriptionFill (FK: order)                     — for treatment orders
│   ├── PrescriptionFillOrder (FKs: prescription_fill + order)
│   ├── PrescriptionFillPrescriptions[] (through)   — rx medications
│   └── PrescriptionFillOTCTreatments[] (through)   — OTC treatments
├── OTCTreatment[] (FK: order)                       — for OTC care products
├── UrineTest[] (FK: ecomm_order)                    — for UTI test orders
│   └── LabOrder (FK: urine_test)
│       └── LabOrderIntake (FK: lab_order)
└── ProviderTestOrder (FK: ecomm_order)              — for provider-ordered tests

Consult (consults.Consult)
├── ConsultOrder (FK: consult)                       — links to Order
├── ConsultOTCTreatment[] (through)                  — links to OTCTreatments
└── ConsultIntake (OneToOne: consult)                — for ungated RX path
```

---

## Source Files

- **Main orchestrator:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
  - `process_shopify_order()` — line 204
  - `_process_shopify_order_impl()` — line 238
  - `process_order_line_item()` — line 1322
  - `process_shopify_order_for_care()` — line 1807
  - `process_shopify_order_for_test()` — line 1600
  - `process_shopify_order_for_pcr_add_on()` — line 1964
  - `process_shopify_order_for_treatment_refill()` — line 2089
  - `create_urine_tests_for_order_if_needed()` — line 1141
  - `create_urine_tests_and_unregistered_testkit_orders_for_order()` — line 1194
  - `mark_order_cart_as_purchased()` — line 2816

- **Async tasks:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
  - `send_prescription_refill_request()` — line 157
  - `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()` — line 344
  - `attach_otc_treatments_to_existing_consult()` — line 479
  - `process_gift_cards()` — line 552

- **Fulfillment:** `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
  - `send_order_to_berlin_for_fulfillment()` — line 685

- **Junction (UTI lab):** `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`
  - `create_unregistered_testkit_order_for_urine_test()` — line 214

- **Precision pharmacy utils:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py`
  - `create_prescription_fill_prescriptions()` — line 821
  - `create_prescription_fill_otc_treatments()` — line 846

- **Models:**
  - `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` — Order, OrderLineItem, OrderShippingAddress, RelatedOrder
  - `/Users/albertgwo/Work/evvy/backend/care/models.py` — PrescriptionFill (line 721), PrescriptionFillOrder (line 831), PrescriptionFillPrescriptions (line 864), PrescriptionFillOTCTreatments (line 927), OTCTreatment (line 895)
  - `/Users/albertgwo/Work/evvy/backend/consults/models.py` — ConsultOrder (line 742), ConsultTask (line 1995)
  - `/Users/albertgwo/Work/evvy/backend/test_results/models/test.py` — Test (line 263), UrineTest
