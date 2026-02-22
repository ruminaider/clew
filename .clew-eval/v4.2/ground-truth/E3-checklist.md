# E3 Ground Truth Checklist: Order Model Dependency Chain

Scenario: Starting from the Order model, trace how creating an order triggers the creation of
related records. Map the full chain: which models are created as side effects of order processing,
what service functions orchestrate this creation, and what happens if any step in the chain fails.

---

## E3 Ground Truth Checklist

### Core Order Records (always created)

- [ ] Artifact 1: `Order` (`backend/ecomm/models/order.py`) - created/fetched via `Order.objects.get_or_create()` at the top of `_process_shopify_order_impl`; primary entry point for all downstream creation

- [ ] Artifact 2: `OrderLineItem` (`backend/ecomm/models/order.py`) - created per Shopify line item inside `process_order_line_item()` within a `transaction.atomic()` block using `OrderLineItem.objects.get_or_create(order=locked_order, shopify_id=shopify_id)`; uses `select_for_update()` on Order to prevent race conditions from duplicate webhooks

- [ ] Artifact 3: `OrderShippingAddress` (`backend/ecomm/models/order.py`) - created via `OrderShippingAddress.objects.get_or_create(order=order)` when a shipping address is present in the Shopify payload; one-to-one with Order

- [ ] Artifact 4: `RelatedOrder` (`backend/ecomm/models/order.py`) - created via `RelatedOrder.objects.get_or_create(parent_order=parent_order, cross_sell_order=order)` when the order payload contains a `parent_order_number` note attribute (cross-sell analytics)

### Care Pathway Records (care order types: vaginitis, STI, UTI, a la carte, dynamic bundle, mixed care, male partner)

- [ ] Artifact 5: `ConsultOrder` (`backend/consults/models.py`) - created via `ConsultOrder.objects.get_or_create(consult=consult, order=order)` inside `process_shopify_order_for_care()` when a valid `consult_uid` is found in the order note attributes; links the Consult to the Order

- [ ] Artifact 6: `ConsultTask` (`backend/consults/models.py`) - created via `ConsultTask.objects.get_or_create()` or `ConsultTask.objects.create()` in two error scenarios: (a) when a care order is missing or has an invalid `consult_uid`, task type `a-la-care-failure`; (b) when ordered products don't match selected treatments on the consult, task type `a-la-care-failure`

- [ ] Artifact 7: `ConsultStatusChange` (`backend/consults/models.py`) - created inside the `on_change` pre_save signal handler (`backend/consults/signals.py`) whenever the Consult's `status` field changes (e.g., `STATUS_OPTED_IN` → `STATUS_ORDERED`); logs every status transition

### Prescription Refill Pathway Records (prescription treatment / ungated RX / subscription refill order types)

- [ ] Artifact 8: `PrescriptionFill` (`backend/care/models.py`) - created or fetched inside `process_shopify_order_for_treatment_refill()`: if a valid `prescription_fill_id` UUID is present in note attributes it fetches the existing record; otherwise `PrescriptionFill.objects.get_or_create(order=order, user=user)`; transitions status from `draft` → `created` inside `send_prescription_refill_request` task

- [ ] Artifact 9: `PrescriptionFillOrder` (`backend/care/models.py`) - created via `PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)` immediately after setting the order on the PrescriptionFill; through-table linking PrescriptionFill to Order

- [ ] Artifact 10: `PrescriptionFillPrescriptions` (`backend/care/models.py`) - created by `create_prescription_fill_prescriptions()` (`backend/shipping/precision/utils.py`) via `PrescriptionFillPrescriptions.objects.get_or_create(prescriptionfill=..., prescription=...)` for each Prescription in the fill; records fill quantity and precision pharmacy reference ID

- [ ] Artifact 11: `PrescriptionFillOTCTreatments` (`backend/care/models.py`) - created by `create_prescription_fill_otc_treatments()` (`backend/shipping/precision/utils.py`) for each OTC treatment associated with the prescription fill

### OTC Treatment Records

- [ ] Artifact 12: `OTCTreatment` (`backend/care/models.py`) - created via `OTCTreatment.objects.bulk_create()` inside `process_order_line_item()` when the line item's care product has `regulatory_category == OVER_THE_COUNTER`; one record per quantity unit; then `attach_otc_treatments_to_existing_consult()` links them to an active Consult via `ConsultOTCTreatment.objects.get_or_create()`

### Test Kit Records

- [ ] Artifact 13: `UrineTest` (`backend/test_results/models/test.py`) - created via `UrineTest.objects.bulk_create()` inside `create_urine_tests_for_order_if_needed()` when the line item has `order_type == ORDER_TYPE_URINE_TEST`; one record per quantity unit; status set to `Test.STATUS_ORDERED`; Junction lab platform is notified asynchronously via `create_unregistered_testkit_order_for_urine_test.delay()`

### Gift Card Records (male partner treatment voucher / MPT orders)

- [ ] Artifact 14: `GiftCard` (`backend/ecomm/models/product.py`) - created via `GiftCard.objects.get_or_create()` inside `_validate_mpt_voucher_line_item()` when the line item SKU matches `MPT_VOUCHER_SKU`; the Shopify gift card is first created via `ShopifyAdminAPIClient.create_gift_card()` inside a `transaction.atomic()` block with `select_for_update()` to prevent duplicate creation

### Ungated RX / New Consult Creation

- [ ] Artifact 15: `Consult` (ungated RX path) (`backend/consults/models.py`) - created via `Consult.objects.get_or_create(user=user, type=Consult.TYPE_UNGATED_RX, ...)` inside the Celery task `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()` when no existing in-progress consult is found for the user

- [ ] Artifact 16: `ConsultIntake` (`backend/consults/models.py`) - created via `ConsultIntake.objects.get_or_create(consult=latest_in_progress_consult)` immediately after ungated RX consult creation; may be pre-populated with symptoms from a parent order's HealthContext if the checkout source is `health-history`

### Provider Test Order Records

- [ ] Artifact 17: `ProviderTestOrder` (`backend/providers/models.py`) - created via `ProviderTestOrder.objects.create(provider=provider, patient_email=..., order_method=PATIENT_PAID, ecomm_order=order)` inside `process_shopify_order_for_test()` when `provider_magic` note attribute is present and no existing matching PTO is found

---

## Service Functions Orchestrating Creation

| Function | File | Role |
|---|---|---|
| `process_shopify_order()` | `backend/ecomm/utils.py:204` | Top-level wrapper; catches all exceptions and logs to NewRelic |
| `_process_shopify_order_impl()` | `backend/ecomm/utils.py:238` | Core orchestrator; creates Order, OrderShippingAddress, RelatedOrder; dispatches to type-specific processors |
| `process_order_line_item()` | `backend/ecomm/utils.py:1322` | Per-line-item processor; creates OrderLineItem, OTCTreatment, UrineTest, GiftCard records |
| `process_shopify_order_for_care()` | `backend/ecomm/utils.py:1807` | Care path orchestrator; links Consult to Order, creates ConsultOrder, fires `ConsultTask` on errors |
| `process_shopify_order_for_treatment_refill()` | `backend/ecomm/utils.py:2089` | Refill orchestrator; creates/fetches PrescriptionFill, PrescriptionFillOrder, calls pharmacy creation utils |
| `process_shopify_order_for_test()` | `backend/ecomm/utils.py:1600` | Test kit path orchestrator; links ProviderTestOrder if magic-link |
| `create_prescription_fill_prescriptions()` | `backend/shipping/precision/utils.py:821` | Creates PrescriptionFillPrescriptions records for each Prescription |
| `create_prescription_fill_otc_treatments()` | `backend/shipping/precision/utils.py:846` | Creates PrescriptionFillOTCTreatments records for each OTC treatment |
| `create_urine_tests_for_order_if_needed()` | `backend/ecomm/utils.py:1141` | Creates UrineTest records; deduplicates against existing count |
| `send_prescription_refill_request()` | `backend/ecomm/tasks.py:157` | Celery task; transitions PrescriptionFill to CREATED, sends patient/prescription/OTC to Precision pharmacy, sends fill request |
| `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()` | `backend/ecomm/tasks.py:344` | Celery task; creates Consult + ConsultIntake for ungated RX path if none exists |
| `attach_otc_treatments_to_existing_consult()` | `backend/ecomm/tasks.py:479` | Links OTCTreatment records to user's latest active Consult via ConsultOTCTreatment |
| `process_gift_cards()` | `backend/ecomm/tasks.py:552` | Celery task; handles gift card purchases and redemptions |
| `send_order_to_berlin_for_fulfillment()` | `backend/shipping/tasks.py:685` | Celery task; sends order to Berlin fulfillment API; sets `Order.sent_to_berlin_at` on success |

---

## Creation Chain

### Care Order Path (vaginitis, STI, UTI care, a la carte, dynamic bundle, mixed care)

```
Shopify webhook (orders/create)
  → shopify_webhook_view() [backend/api/v1/views/webhooks.py]
  → process_shopify_order() [backend/ecomm/utils.py:204]
  → _process_shopify_order_impl() [backend/ecomm/utils.py:238]
    → Order.objects.get_or_create()                        [creates Order]
    → OrderShippingAddress.objects.get_or_create()         [creates OrderShippingAddress]
    → process_order_line_item() per line item
        → OrderLineItem.objects.get_or_create()            [creates OrderLineItem, inside transaction.atomic]
        → OTCTreatment.objects.bulk_create()               [creates OTCTreatment if OTC product]
    → process_shopify_order_for_care()
        → ConsultOrder.objects.get_or_create()             [creates ConsultOrder]
        → consult.status = STATUS_ORDERED → consult.save()
            → on_change signal fires
                → ConsultStatusChange.objects.create()     [creates ConsultStatusChange]
        → ConsultTask.objects.create/get_or_create()       [creates ConsultTask on error]
    → RelatedOrder.objects.get_or_create()                 [creates RelatedOrder if cross-sell]
    → attach_otc_treatments_to_existing_consult()
        → ConsultOTCTreatment.objects.get_or_create()
    → process_gift_cards.delay()                           [async: GiftCard creation]
    → send_order_to_berlin_for_fulfillment.delay()         [async: sets Order.sent_to_berlin_at]
```

### Prescription Refill / Treatment Order Path

```
Shopify webhook (orders/create) with ORDER_TYPE_PRESCRIPTION_TREATMENT line items
  → _process_shopify_order_impl()
    → [same Order + OrderLineItem + OrderShippingAddress creation as above]
    → process_shopify_order_for_treatment_refill()         [backend/ecomm/utils.py:2089]
        → PrescriptionFill.objects.get_or_create()         [creates PrescriptionFill]
        → PrescriptionFillOrder.objects.get_or_create()    [creates PrescriptionFillOrder]
        → create_prescription_fill_prescriptions()
            → PrescriptionFillPrescriptions.objects.get_or_create() [per Prescription]
        → create_prescription_fill_otc_treatments()
            → PrescriptionFillOTCTreatments.objects.get_or_create() [per OTC treatment]
        → send_prescription_refill_request.delay()         [Celery task]
            → PrescriptionFill.status = CREATED → save()
            → send_create_patient_request_to_precision()
            → send_create_prescription_request_to_precision() [per prescription]
            → send_create_otc_treatment_request_to_precision() [per OTC]
            → send_fill_request_to_precision()             [submits to pharmacy]
```

### Urine Test / UTI Order Path

```
Shopify webhook (orders/create) with ORDER_TYPE_URINE_TEST line items
  → _process_shopify_order_impl()
    → process_order_line_item()
        → create_urine_tests_for_order_if_needed()
            → UrineTest.objects.bulk_create()              [creates UrineTest per quantity]
        → create_unregistered_testkit_order_for_urine_test.delay() [async → Junction lab]
    → process_shopify_order_for_test()                     [user resolution, ProviderTestOrder]
    → send_order_to_berlin_for_fulfillment.delay()
```

### Ungated RX (new prescription, no existing consult) Path

```
Shopify webhook with ORDER_TYPE_UNGATED_RX
  → _process_shopify_order_impl()
    → [Order + OrderLineItem + OrderShippingAddress creation]
    → can_refill_entire_order() check:
        TRUE  → process_shopify_order_for_treatment_refill() [refill path, see above]
        FALSE → add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay()
                  → Consult.objects.get_or_create()         [creates Consult of TYPE_UNGATED_RX]
                  → ConsultIntake.objects.get_or_create()   [creates ConsultIntake]
                  → ConsultOrder.objects.get_or_create()    [links Order to Consult]
```

---

## Error Handling

### Transaction Boundaries

- **`process_order_line_item()`** — `transaction.atomic()` wraps the `OrderLineItem.objects.get_or_create()` call with `Order.objects.select_for_update()`. Race condition protection: if two concurrent webhooks process the same line item (duplicate Shopify webhook), only one `OrderLineItem` is created.

- **`_validate_mpt_voucher_line_item()`** — `transaction.atomic()` wraps the Shopify gift card creation API call and the subsequent `GiftCard.objects.get_or_create()`. `select_for_update()` on `OrderLineItem` prevents double gift card creation.

- No top-level `transaction.atomic()` wraps `_process_shopify_order_impl()` — the function is NOT fully atomic. Partial failures can leave the database in an intermediate state.

### Failure Modes and Consequences

| Failure Point | What Breaks | Recovery |
|---|---|---|
| Consult not found for care order | `ConsultOrder` not created; `ConsultTask(TASK_TYPE_A_LA_CARE_FAILURE)` created as alert | Manual ops review via admin; `ConsultTask` queue |
| `prescription_fill_id` missing or invalid UUID | Falls back to `PrescriptionFill.objects.get_or_create(order=order)` — creates new fill | Usually recovers automatically |
| State restriction on refill | `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` created; `send_prescription_refill_request` returns early | Manual ops intervention |
| Prescriptions have no remaining refills | `ConsultTask(TASK_TYPE_TREATMENT_REFILL_FAILURE)` created; exception raised in Celery task | Celery retries; manual intervention |
| No prescriptions AND no OTC treatments for refill | Early return from `process_shopify_order_for_treatment_refill()`; pharmacy not contacted | `error` logged; no task created |
| Berlin fulfillment API failure | `Order.sent_to_berlin_at` left null; exception raised in Celery task | `retry_failed_berlin_order_fulfillments` periodic task retries orders with null `sent_to_berlin_at` |
| Order cancellation | `Order.status = STATUS_CANCELLED`; `sever_test_order_associations_for_cancelled_order()` called; `void_share_a_sale_transaction.delay()`; for UTI: `cancel_uti_order_in_junction()` | PrescriptionFill.can_cancel check gates pharmacy cancellation |
| Top-level unhandled exception in `_process_shopify_order_impl` | Caught by `process_shopify_order()` wrapper; logged to NewRelic with order context; re-raised (returns 500 to Shopify) | Shopify retries webhook; `retry_failed_shopify_orders` Celery task catches orders missing from DB |
| Order has line items but no cart attributes on a care order | `ConsultTask(TASK_TYPE_A_LA_CARE_FAILURE)` created; function attempts to reconstruct attributes from line item metadata | Partial recovery via metadata reconstruction |
| Consult pre_save signal failure | Caught inside `on_change` with broad `except Exception`; logged but not re-raised | Status change proceeds; `ConsultStatusChange` creation may fail silently |

### Monitoring

- All errors logged to NewRelic via `OrderEventLogger.log_processing_error()` with structured `OrderErrorCategory` classification (`VALIDATION`, `SYSTEM`, `PROVIDER_API`)
- `OrderProcessingMonitor` tracks stage-level timing: `order_validation`, `address_processing`, `line_item_processing`, `payment_processing`, `order_type_processing`, `fulfillment_processing`
- `retry_failed_shopify_orders` Celery beat task re-processes orders missing from the database within the past 3 days

---

## Key Files

| File | Purpose |
|---|---|
| `backend/ecomm/models/order.py` | Order, OrderLineItem, OrderShippingAddress, RelatedOrder, PartnerRelationship |
| `backend/ecomm/utils.py` | All order processing logic (`process_shopify_order`, `_process_shopify_order_impl`, `process_order_line_item`, `process_shopify_order_for_*`) |
| `backend/ecomm/tasks.py` | Celery tasks: `send_prescription_refill_request`, `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`, `attach_otc_treatments_to_existing_consult`, `process_gift_cards` |
| `backend/api/v1/views/webhooks.py` | Webhook entrypoints: `shopify_webhook_view` dispatches to `process_shopify_order` |
| `backend/care/models.py` | PrescriptionFill, PrescriptionFillOrder, PrescriptionFillPrescriptions, OTCTreatment, PrescriptionFillOTCTreatments, Prescription |
| `backend/consults/models.py` | Consult, ConsultOrder, ConsultIntake, ConsultTask, ConsultStatusChange |
| `backend/consults/signals.py` | `on_change` pre_save signal → ConsultStatusChange creation |
| `backend/shipping/tasks.py` | `send_order_to_berlin_for_fulfillment` Celery task |
| `backend/shipping/precision/utils.py` | `create_prescription_fill_prescriptions`, `create_prescription_fill_otc_treatments` |
| `backend/test_results/models/test.py` | Test (vaginal), UrineTest — `ecomm_order` FK on BaseTest |
| `backend/ecomm/models/product.py` | GiftCard model |
| `backend/ecomm/shopify/tasks.py` | `retry_failed_shopify_orders` periodic task, `process_shopify_order_from_api` |
