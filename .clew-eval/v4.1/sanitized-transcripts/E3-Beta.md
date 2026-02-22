# E3 — Agent Beta

I now have all the key pieces to provide a comprehensive answer. Here is the full chain:

---

## Order Creation Chain in Evvy

### Entry Point: Shopify Webhook

All order creation is triggered by Shopify webhook payloads. The entry point is:

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`**

```python
# Line 204 - Public wrapper with error monitoring
def process_shopify_order(payload: dict[str, Any], is_order_cancellation: bool):
    try:
        return _process_shopify_order_impl(payload, is_order_cancellation, order_logger)
    except Exception as e:
        # Logs to NewRelic, re-raises
        raise

# Line 238 - The actual orchestrator
def _process_shopify_order_impl(payload, is_order_cancellation, order_logger):
    ...
```

The wrapper at line 204 catches all exceptions, logs them to NewRelic with structured metadata, and re-raises. There is **no swallowing of errors** at the top level.

---

### Stage 1: Order Record Creation

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 336–432

```python
order, _ = Order.objects.get_or_create(
    provider=Order.PROVIDER_SHOPIFY,
    provider_id=order_number,
)
```

The `Order` is created idempotently (get-or-create). Immediately after:

**`OrderShippingAddress`** (line 382):
```python
shipping_address_record, _ = OrderShippingAddress.objects.get_or_create(order=order)
```
Created with all address fields from the Shopify payload. OneToOne with `Order`.

---

### Stage 2: Line Item Processing

**Function:** `process_order_line_item()` (line 1322)

For each Shopify line item, inside `with transaction.atomic()` (line 1395):

**`OrderLineItem`** (line 1401):
```python
line_item, created = OrderLineItem.objects.get_or_create(
    order=locked_order,
    shopify_id=shopify_id,
    defaults={ sku, product_id, variant_id, order_type, quantity, price, ... }
)
```
The `select_for_update()` lock on the Order row prevents race conditions from duplicate webhook deliveries.

**Side effects per line item type:**

- **OTC treatment products** (line 1512): Creates one `OTCTreatment` record per unit quantity:
  ```python
  OTCTreatment.objects.bulk_create([OTCTreatment(order, product, user) for _ in range(quantity)])
  ```

- **Urine test orders** (line 1541–1553): Creates one `UrineTest` per unit quantity:
  ```python
  UrineTest.objects.bulk_create([UrineTest(ecomm_order=order, lab=LAB_JUNCTION, status=STATUS_ORDERED)])
  ```
  Then immediately queues `create_urine_tests_and_unregistered_testkit_orders_for_order()` to send to Junction (the UTI lab partner).

---

### Stage 3: Cross-Sell Analytics

If the payload contains a `parent_order_number` (line 569–575):

**`RelatedOrder`**:
```python
RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)
```
Links the current order to its parent as a cross-sell for analytics.

---

### Stage 4: Order-Type-Specific Processing

Branching on `order.order_type` (lines 637–658):

#### Care Orders (Vaginitis, STI, UTI, A La Carte, Dynamic Bundle, etc.)

**Function:** `process_shopify_order_for_care()` (line 1807)

**`ConsultOrder`** (line 1858) - links Consult to Order:
```python
ConsultOrder.objects.get_or_create(consult=consult, order=order)
```
Updates `Consult.status` to `STATUS_ORDERED` and fires `send_consult_paid_event` Celery task.

**`ConsultTask`** (line 1918/1952) - created on error conditions:
- If ordered products don't match selected treatments in the consult
- If no consult was found at all (signals ops to investigate)

#### Test Orders (Vaginal NGS, Expanded, Urine)

**Function:** `process_shopify_order_for_test()` (line 1600)

- For provider magic link orders: creates or links a **`ProviderTestOrder`** record (line 1724)
- For bulk orders: `_process_bulk_provider_order()` is called

#### PCR Add-On Orders

**Function:** `process_shopify_order_for_pcr_add_on()` (line 1964)

Calls `add_expanded_vpcr_panel_to_test_kit(test_kit, order)` to add lab tests. If linked to a `ProviderTestOrder`, sets `add_expanded_pcr = True`.

#### Prescription Refill Orders

**Function:** `process_shopify_order_for_treatment_refill()` (line 2089)

Creates the richest chain of records:

**`PrescriptionFill`** (line 2108):
```python
prescription_fill, _ = PrescriptionFill.objects.get_or_create(order=order, user=user)
```

**`PrescriptionFillOrder`** (line 2143) - through table linking PrescriptionFill to Order:
```python
PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
```

**`PrescriptionFillPrescriptions`** (in `create_prescription_fill_prescriptions()`, `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` line 836) - one per Prescription:
```python
PrescriptionFillPrescriptions.objects.get_or_create(
    prescriptionfill=prescription_fill,
    prescription=prescription,
    defaults={"fill_quantity": ..., "precision_reference_id": ...}
)
```

**`PrescriptionFillOTCTreatments`** (line 867) - one per OTC treatment:
```python
PrescriptionFillOTCTreatments.objects.get_or_create(
    prescriptionfill=prescription_fill,
    otctreatment=otc_treatment,
    defaults={"fill_quantity": ..., "precision_reference_id": ...}
)
```

#### Ungated RX Orders

**Function:** `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()` (`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` line 344)

- If no in-progress consult exists, creates a **`Consult`** of type `TYPE_UNGATED_RX` plus **`ConsultIntake`** (line 408)
- Creates **`ConsultOrder`** (line 449) linking the new or found consult to the order
- If `checkout_source == CHECKOUT_SOURCE_HEALTH_HISTORY`, pre-populates `ConsultIntake` with symptom data from the prior test's `HealthContext`

---

### Stage 5: OTC Treatment Attachment

**Function:** `attach_otc_treatments_to_existing_consult()` (`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` line 479)

Called at the end of the main pipeline for all orders. If OTC treatments exist and the user has a consult with an active treatment window:

**`ConsultOTCTreatment`** (line 510):
```python
ConsultOTCTreatment.objects.get_or_create(consult=consult, otctreatment=otc_treatment)
```

---

### Stage 6: Async Fulfillment Tasks

Two main Celery tasks are queued at the end of `_process_shopify_order_impl()`:

1. **`send_order_to_berlin_for_fulfillment.delay(payload, is_cancellation, order.id)`** (line 763, task at `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` line 685): Sends the Shopify payload to Berlin (the physical fulfillment partner) via `BerlinAPIClient`. Sets `order.sent_to_berlin_at` on success.

2. **`send_prescription_refill_request.delay(order.id, prescription_fill.id)`** (queued from `process_shopify_order_for_treatment_refill()` line 2198, task at `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` line 157):
   - Validates shipping address against state restrictions
   - Verifies prescriptions still have remaining refills
   - Sets `PrescriptionFill.status = PRESCRIPTION_FILL_STATUS_CREATED`
   - Calls `send_create_patient_request_to_precision()` (patient record at pharmacy)
   - Calls `send_create_prescription_request_to_precision()` for each `PrescriptionFillPrescriptions`
   - Calls `send_create_otc_treatment_request_to_precision()` for each `PrescriptionFillOTCTreatments`
   - Finally calls `send_fill_request_to_precision()` to actually dispense

---

### Error Handling

| Failure Point | Behavior |
|---|---|
| Top-level exception | Caught by `process_shopify_order()`, logged to NewRelic with structured attributes, then **re-raised** (no silent failure) |
| Line item processing | `transaction.atomic()` block wraps `OrderLineItem` get-or-create; failure rolls back only that line item |
| Missing consult for care order | `ConsultTask.TASK_TYPE_A_LA_CARE_FAILURE` created for ops team to investigate; no exception raised |
| ProviderTestOrder creation | `try/except` logs warning and continues (non-fatal) |
| Prescription refill request | If invalid state: `ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE` created; if no refills remaining: same task created + exception raised to Celery retry |
| Berlin fulfillment failure | `log_fulfillment_failed()` called, exception re-raised to trigger Celery retry |
| Prescription fill cancellation failure | `ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE` created, exception re-raised |

---

### Full Chain Summary (Record Creation)

```
Shopify Webhook
  └── Order (get_or_create)
        ├── OrderShippingAddress (get_or_create) [always]
        ├── RelatedOrder (get_or_create) [if cross-sell]
        └── [for each line item]
              ├── OrderLineItem (get_or_create, atomic + select_for_update)
              ├── OTCTreatment (bulk_create) [if OTC regulatory category]
              └── UrineTest (bulk_create) [if ORDER_TYPE_URINE_TEST]

  [Care orders] → process_shopify_order_for_care
        ├── ConsultOrder (get_or_create) [links Consult ↔ Order]
        └── ConsultTask (create) [on mismatch/missing consult - error path]

  [Test orders] → process_shopify_order_for_test
        └── ProviderTestOrder (create or link) [if provider magic link]

  [Refill/Rx orders] → process_shopify_order_for_treatment_refill
        ├── PrescriptionFill (get_or_create)
        ├── PrescriptionFillOrder (get_or_create) [PrescriptionFill ↔ Order]
        ├── PrescriptionFillPrescriptions (get_or_create, one per Rx)
        └── PrescriptionFillOTCTreatments (get_or_create, one per OTC)

  [Ungated RX] → add_order_treatments_to_latest_existing_consult...
        ├── Consult (get_or_create, TYPE_UNGATED_RX)
        ├── ConsultIntake (get_or_create)
        └── ConsultOrder (get_or_create)

  [All orders, post-processing] → attach_otc_treatments_to_existing_consult
        └── ConsultOTCTreatment (get_or_create, one per OTC treatment)

  [Async Celery tasks]
        ├── send_order_to_berlin_for_fulfillment → updates Order.sent_to_berlin_at
        └── send_prescription_refill_request
              └── [sends to Precision pharmacy API, creates ConsultTask on failure]
```
