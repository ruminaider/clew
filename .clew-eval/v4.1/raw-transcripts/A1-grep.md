# A1-grep Raw Transcript

**Agent ID:** a4cba575a3a402fed
**Tool:** grep (Grep, Glob, Read)
**Test:** A1 — Subscription renewal → PrescriptionFill creation failure
**Tool calls:** 27
**Tokens:** 87,718

## Final Answer

Now I have a thorough understanding of the full code path. Let me compile the comprehensive answer.

---

## Investigation: Order Webhook to PrescriptionFill Creation

### Entry Point: Shopify Webhook

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 82-145)

The `shopify_webhook_view` function handles `orders/create` and `orders/cancelled` topics. After HMAC signature verification (using `SHOPIFY_WEBHOOK_SECRET`), it calls `process_shopify_order(payload, is_order_cancellation=...)`.

---

### Stage 1: `process_shopify_order` (error-handling wrapper)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 204-234)

This is a thin wrapper around `_process_shopify_order_impl`. All exceptions bubble here, get logged to NewRelic, and are re-raised. **Failure here means the entire order processing is aborted.**

---

### Stage 2: `_process_shopify_order_impl` — Order Creation and Routing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 238-700+)

**Critical steps:**

1. **Line item validation** (lines 262-272): If the payload has no `line_items`, the function returns early with no prescription fill created. No error is raised — it logs a warning and returns `None`.

2. **Order record** is `get_or_create`'d by `(provider=SHOPIFY, provider_id=order_number)`.

3. **User resolution** (line 460): `_update_order_user(order, email)` — if user cannot be found by email, `order.user` remains `None`, which causes downstream failures in the prescription path.

4. **Subscription metadata detection** (lines 469-494): `is_recurring_subscription_order` is set `True` when a line item is a recurring subscription order (ReCharge app ID or `is_recurring_order_item` property).

5. **Order type routing** (lines 636-692): The function routes to different handlers based on `order.order_type`:
   - `ORDER_TYPE_PRESCRIPTION_TREATMENT` ("PR") → goes into the secondary check at lines 661-672
   - `ORDER_TYPE_UNGATED_RX` ("UX") → has its own path via `can_refill_entire_order`
   - Care order types (vaginitis, STI, UTI, etc.) → `process_shopify_order_for_care`

6. **Secondary routing for refill line items** (lines 660-672): Even if the overall order type is something else (e.g., `TEST`), if any line item has type `PRESCRIPTION_TREATMENT`, `process_shopify_order_for_treatment_refill` is called. **However, if the overall order type is `A_LA_CARTE`, `MIXED_CARE`, `DYNAMIC_BUNDLE`, `UNGATED_RX`, or `MALE_PARTNER`, this secondary check is SKIPPED**, and care-type orders go through `process_shopify_order_for_care` which has its own PrescriptionFill logic.

---

### Stage 3: `process_shopify_order_for_treatment_refill` — The Core Refill Path

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 2089-2201)

This is the main function where PrescriptionFill is created for subscription renewals.

**Step-by-step with failure points:**

**Step 1 — Parse order attributes** (lines 2097-2099):
Extracts `prescription_fill_id`, `consult_uid`, `user_account_email`, `prescription_ids` from `note_attributes`.

**Step 2 — Get or create PrescriptionFill** (lines 2102-2108):
```python
if prescription_fill_id and _is_valid_uuid(prescription_fill_id):
    prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)
else:
    lookup_params = {"order": order}
    if order.user:
        lookup_params["user"] = order.user
    prescription_fill, _ = PrescriptionFill.objects.get_or_create(**lookup_params)
```
**Failure point:** If a `prescription_fill_id` is provided but is not a valid UUID or doesn't exist in the DB, this raises an exception. For renewals originating from ReCharge, no `prescription_fill_id` is typically included in `note_attributes`, so the `get_or_create` branch runs. If `order.user` is `None`, the fill is created without a user, causing issues later.

**Step 3 — Resolve user** (lines 2111-2138):
Tries 4 fallbacks:
1. `user_account_email` from note attributes
2. `order.cart.user`
3. `consult.user`
4. `order.email`

**Failure point:** If all 4 fail, the order has no user (`order.user = None`). This propagates to the prescription lookup below.

**Step 4 — Associate order with fill** (lines 2141-2143): Sets `prescription_fill.order = order` and creates `PrescriptionFillOrder` through-table record.

**Step 5 — Find prescriptions and OTC treatments** (lines 2145-2182):
```python
if order_attrs.prescription_ids:
    prescriptions = Prescription.objects.filter(id__in=prescription_id_list)
    # validates user matches
elif order.user:
    prescriptions = Prescription.objects.filter(
        user=order.user, product__in=ordered_products, deleted=False
    ).order_by("product_id", "create_date").distinct("product_id")
else:
    logger.warning("No prescription IDs ... cannot process prescriptions")

otc_treatments = order.otc_treatments.all()

if not prescriptions.exists() and not otc_treatments.exists():
    logger.error("No prescriptions and no otc treatments found ...")
    return  # SILENT ABORT — no PrescriptionFill fill request sent
```

**Critical failure point:** If `order.user` is `None` AND no `prescription_ids` note attribute is present (which is typical for ReCharge renewals), `prescriptions` stays empty. If there are also no OTC treatments, the function **returns silently** at line 2189. **The PrescriptionFill object was already created (step 2), but it stays in DRAFT/CREATED status with no prescriptions linked and no pharmacy request is ever sent.**

**Step 6 — Create fill prescriptions/OTC treatments** (lines 2191-2195):
Calls `create_prescription_fill_prescriptions` and `create_prescription_fill_otc_treatments` from `shipping/precision/utils.py`.

**Step 7 — Dispatch Celery task** (line 2198):
```python
send_prescription_refill_request.delay(order.id, prescription_fill.id)
```
This is asynchronous. If Celery is down or the task is dropped, no fill request ever reaches the pharmacy.

---

### Stage 4: `send_prescription_refill_request` Celery Task

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (lines 156-267)

This task does the actual pharmacy integration work. **Multiple failure points here:**

**Failure 1 — Cancellation check** (lines 173-190):
If `order.status == Order.STATUS_CANCELLED`, it attempts to cancel the fill. If the fill has already been shipped/delivered, it returns without action.

**Failure 2 — Invalid shipping state** (lines 196-210):
```python
if prescriptions.exists():
    invalid_state_code, shipping_address = verify_shipping_address_for_prescription_refill(order, consult_intake)
    if invalid_state_code:
        # Creates ConsultTask TASK_TYPE_TREATMENT_REFILL_FAILURE, returns (no exception raised)
        return
```
If the customer's shipping state is not in `VALID_STATES` (restricted states), the function returns silently. **No exception is raised, so Celery does not retry.**

**Failure 3 — No remaining refills** (lines 212-223):
```python
if not order.is_manual_invoice and not get_all_prescriptions_have_remaining_refills(prescriptions):
    # raises Exception
    raise Exception(error_message)
```
`get_all_prescriptions_have_remaining_refills` returns `False` if `prescription.num_allowed_refills - prescription.fill_count < 0`. Note: the condition checks `< 0` not `<= 0`, so a prescription with exactly 0 remaining refills still passes this check. **However, if refill count goes negative, a `ConsultTask` with `TASK_TYPE_TREATMENT_REFILL_FAILURE` is created and the exception propagates, causing Celery to retry** (the task has `@retry(stop_max_attempt_number=3)`).

**Failure 4 — Prescription fill status update** (lines 225-227):
```python
prescription_fill.status = PrescriptionFill.PRESCRIPTION_FILL_STATUS_CREATED
prescription_fill.save()
```
This updates status from `DRAFT` to `CREATED` before attempting pharmacy calls. If a prior exception occurred before this line, the fill stays in `DRAFT`.

**Failure 5 — Pharmacy API calls** (lines 232-266):
Calls `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_create_otc_treatment_request_to_precision`, and `send_fill_request_to_precision`. Each is synchronous in the task. If Precision API is down or returns an error, the exception propagates and Celery retries up to 3 times with exponential backoff.

---

### Summary of Failure Modes for Subscription Renewals

| Failure Point | Location | Symptom | PrescriptionFill state |
|---|---|---|---|
| Missing HMAC secret | `webhooks.py:94` | 403 response, no order processed | Not created |
| No line items in payload | `utils.py:262` | Warning log, early return | Not created |
| Order user not resolved | `utils.py:460`, `2111-2138` | No user on order | Fill created, no prescriptions |
| No prescriptions/OTCs found | `utils.py:2184-2189` | Error log, silent return | Fill created (no prescriptions linked), no pharmacy request |
| Invalid shipping state | `tasks.py:200-210` | ConsultTask created, silent return | Fill in CREATED, no pharmacy request |
| No remaining refills | `tasks.py:212-223` | ConsultTask + exception, Celery retries | Fill in CREATED, no pharmacy request |
| Celery task dropped | — | No log visible, fill in DRAFT | Fill in DRAFT/CREATED |
| Precision API failure | `tasks.py:247-266` | Exception, up to 3 Celery retries | Fill in CREATED, pharmacy never received request |
| Prescription user mismatch | `utils.py:2157-2162` | Exception raised | Fill created, exception propagates |

### The Most Likely Root Cause for a Subscription Renewal

For a subscription renewal (ReCharge-generated Shopify order), the most common failure path is:

1. ReCharge fires `orders/create` for a recurring charge — this order typically has **no `_evvyAccountEmail`, no `consult_uid`, no `prescription_fill_id`, no `prescription_ids` in `note_attributes`**.
2. `_update_order_user` cannot find a user if the email is new, changed, or missing.
3. In `process_shopify_order_for_treatment_refill`, since `order.user is None` and no `prescription_ids` were passed, `prescriptions` is empty.
4. If there are also no OTC treatments, the function exits silently at line 2189 — **a PrescriptionFill object is created but permanently stuck with no prescriptions, no pharmacy request, and the renewal is lost**.

The daily remediation task (`reprocess_subscription_refill_orders_daily` in `ecomm/tasks.py`, line 587) exists specifically to catch these missed renewals.
