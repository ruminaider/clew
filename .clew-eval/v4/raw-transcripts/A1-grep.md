# A1 Exploration Log

## Search 1: Find all files referencing PrescriptionFill and webhook files
Searched for all Python files (glob) and all files referencing `PrescriptionFill` (grep).

Found 75 files touching `PrescriptionFill`, with the most important being:
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — core order processing
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — async tasks including `send_prescription_refill_request`
- `/Users/albertgwo/Work/evvy/backend/care/models.py` — PrescriptionFill model definition
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` — webhook entry points
- `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py` — known bug remediation script
- `/Users/albertgwo/Work/evvy/backend/scripts/remediate_unfilled_orders.py` — historical bug remediation

## Search 2: Read ecomm/tasks.py
Found the primary task `send_prescription_refill_request` (line 156). This task:
- Receives `order_id` and `prescription_fill_id`
- Handles cancellations via `send_cancel_fill_request_to_precision`
- Validates state code restrictions for prescriptions
- Calls `get_all_prescriptions_have_remaining_refills()` to check refill eligibility
- Transitions fill status from DRAFT to CREATED
- Calls `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_create_otc_treatment_request_to_precision`, and `send_fill_request_to_precision`

Failure points found in this task:
1. Invalid/unsupported state code → logs error, creates ConsultTask, returns early (no fill)
2. No remaining refills on prescription → logs error, creates ConsultTask, raises exception
3. Exceptions from Precision API calls → propagate up

## Search 3: Read api/v1/views/webhooks.py (Shopify webhook entry point)
Found `shopify_webhook_view` (line 82). For `orders/create` and `orders/cancelled` topics, it calls `process_shopify_order(payload, is_order_cancellation=...)` synchronously in the request/response cycle. Errors are logged but the view still returns 200 on success.

Also found `recharge_webhook_view` (line 369) for subscription-specific webhooks, handling topics like `charge/upcoming`, `subscription/created`, etc. — but the actual order creation for renewals comes through Shopify's `orders/create`.

## Search 4: Read the wrapper and implementation of process_shopify_order
`process_shopify_order` (line 204) wraps `_process_shopify_order_impl` with error handling and NewRelic logging. If any exception escapes `_process_shopify_order_impl`, it is caught, logged to NewRelic, and re-raised.

`_process_shopify_order_impl` (line 238) is the large orchestrating function. It:
1. Parses order payload (line items, email, shipping address, note attributes)
2. Determines `is_recurring_subscription_order` by checking if any line item has `is_recurring_order_item=True`
3. Gets or creates an `Order` record
4. Processes each line item via `process_order_line_item`
5. Determines overall `order_type` via `_get_overall_order_type_and_sku_from_line_items`
6. Routes to the appropriate handler based on `order_type`

The key routing for subscription renewals (lines 660-692):
- If `order_type` is NOT in `[A_LA_CARTE, MIXED_CARE, DYNAMIC_BUNDLE, UNGATED_RX, MALE_PARTNER]` AND `ORDER_TYPE_PRESCRIPTION_TREATMENT` appears in line item types → calls `process_shopify_order_for_treatment_refill`
- If `order_type == ORDER_TYPE_UNGATED_RX` → routes to refill OR consult path based on `can_refill_entire_order`

## Search 5: Find process_shopify_order_for_treatment_refill
Read lines 2089–2201. This function:
1. Parses `prescription_fill_id` from note attributes or order note
2. Gets or creates a `PrescriptionFill` object (line 2102–2108)
3. Resolves `consult` from `consult_uid` attribute
4. Resolves `user` from email, cart, consult, or order email (fallback chain)
5. Associates order with fill and creates `PrescriptionFillOrder`
6. Finds prescriptions: either via explicit `prescription_ids` attribute, or via `Prescription.objects.filter(user=order.user, product__in=ordered_products, deleted=False)`
7. Finds OTC treatments from `order.otc_treatments.all()`
8. If neither prescriptions NOR OTC treatments found → logs error and returns early (NO FILL created)
9. Calls `create_prescription_fill_prescriptions` and `create_prescription_fill_otc_treatments`
10. Enqueues `send_prescription_refill_request.delay(order.id, prescription_fill.id)`

## Search 6: Understand order type routing for subscription renewals
Read `_get_overall_order_type_and_sku_from_line_items` (lines 952–1054). For subscription renewal orders, `is_recurring_subscription_order=True` is passed, which causes the `purchase_type` custom attribute to be ignored — preventing the order from being reclassified as `A_LA_CARTE` or `DYNAMIC_BUNDLE`. Without this protection, recurring orders could get wrongly routed to `process_shopify_order_for_care` instead of `process_shopify_order_for_treatment_refill`.

Also found `_determine_checkout_source` (line 836): recharge app_id → `CHECKOUT_SOURCE_SUBSCRIPTION`. This is how subscription renewal orders are identified.

## Search 7: Check line item subscription detection
Found in `process_order_line_item` (around line 1487):
- If `app_id == SHOPIFY_RECHARGE_APP_ID` → sets `line_item.is_recurring_order_item = True`
- This is then propagated to `is_recurring_subscription_order` at the order level

## Search 8: Read reprocess_subscription_refill_orders.py
This script (referenced by `reprocess_subscription_refill_orders_daily` task in `ecomm/tasks.py`) reveals a past bug: recurring subscription orders were being routed to `process_shopify_order_for_care` instead of `process_shopify_order_for_treatment_refill`. Orders affected had their `checkout_source` set to `subscription` but `order_type` set to a "care" type (A_LA_CARTE, DYNAMIC_BUNDLE, etc.). The daily healing job re-processes orders from the last 24 hours.

## Search 9: Read care/models.py PrescriptionFill and Prescription definitions
Found:
- `Prescription.refills_remaining` property (line 646): returns 0 if expired; otherwise `num_allowed_refills - fill_count + 1`, capped by `product.max_allowed_refills` if set
- `Prescription.can_refill` property (line 659): requires `refills_remaining > 0`, `is_refillable_product`, `expiration_date > today`, `not product.is_disabled_for_refill`, `not product.is_deprecated`
- `Prescription.fill_count` (line 604): counts non-draft, non-cancelled `PrescriptionFillPrescriptions` records
- `PrescriptionFill` model (line 721): has statuses `draft`, `created`, `shipped`, `delivered`, `warning`, `cancelled`, `failed`; default is `created`

## Search 10: Read create_prescription_fill_prescriptions and create_prescription_fill_otc_treatments
In `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` (lines 821–878):
- `create_prescription_fill_prescriptions`: loops prescriptions, creates `PrescriptionFillPrescriptions` records with fill quantity and precision reference ID
- `create_prescription_fill_otc_treatments`: similarly for OTC treatments, skips duplicates

## Search 11: Read remediate_unfilled_orders.py docstring
Confirms that "a bug in the subscription fulfillment pipeline caused ~302 orders (June 2025 – Feb 2026) to never receive fills." Root causes categorized as `no_fill_unknown`, `fill_failed`, `multiple_orders_ambiguity`, `consult_missing_products`, `no_user_subscription_renewal`.

## Search 12: Search for subscription-related failures in code
Found `_should_skip_order` in the reprocess script checks:
- `checkout_source != CHECKOUT_SOURCE_SUBSCRIPTION` → skips (not a subscription renewal)
- `existing_fill and existing_fill.prescriptions.exists()` → skips (already processed)

---

## Final Answer

### Code Path: Subscription Renewal Order → PrescriptionFill Creation

#### Step 1: Webhook Entry Point
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`, line 82 (`shopify_webhook_view`)

When Shopify (via Recharge) processes a subscription renewal, it sends an `orders/create` webhook. The view verifies the HMAC signature and calls `process_shopify_order(payload, is_order_cancellation=False)` synchronously.

#### Step 2: Order Processing Wrapper
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, line 204 (`process_shopify_order`)

Wraps `_process_shopify_order_impl` with error catching + NewRelic reporting. Exceptions propagate after logging.

#### Step 3: Main Order Processing Orchestrator
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, line 238 (`_process_shopify_order_impl`)

Key steps for a subscription renewal:

1. **Identify as a recurring order:** Each line item is processed via `process_order_line_item`. If `app_id == SHOPIFY_RECHARGE_APP_ID` (line 1487), the line item gets `is_recurring_order_item = True`. If any line item has this flag, `is_recurring_subscription_order = True` at the order level (line 493).

2. **Determine order type:** `_get_overall_order_type_and_sku_from_line_items` is called with `is_recurring_subscription_order=True`. This prevents `purchase_type` custom attributes (which may be copied from the original subscription order) from overriding the order type. Subscription renewal orders containing prescription treatment SKUs resolve to `ORDER_TYPE_PRESCRIPTION_TREATMENT`.

3. **Set checkout source:** `_determine_checkout_source` returns `CHECKOUT_SOURCE_SUBSCRIPTION` for Recharge app IDs (line 836). For recurring orders, the custom attribute `checkout_source` is ignored to prevent stale values from polluting the field (lines 603-607).

4. **Route to treatment refill path:** At line 660-672:
   ```python
   if (
       order.order_type not in [ORDER_TYPE_A_LA_CARTE, ORDER_TYPE_MIXED_CARE,
                                 ORDER_TYPE_DYNAMIC_BUNDLE, ORDER_TYPE_UNGATED_RX,
                                 ORDER_TYPE_MALE_PARTNER]
       and Order.ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
   ):
       process_shopify_order_for_treatment_refill(order, payload, order_logger)
   ```

#### Step 4: Treatment Refill Processing
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, line 2089 (`process_shopify_order_for_treatment_refill`)

1. **Parse `prescription_fill_id`** from `note_attributes` (key `prescription_fill_id`) or from the order `note` field (for manual replacements). If provided and a valid UUID, fetches the specific `PrescriptionFill`. Otherwise, does `get_or_create(order=order, user=order.user)`.

2. **Resolve user** via (in order): `user_account_email` attribute → cart user → consult user → order email lookup.

3. **Find prescriptions:** If `prescription_ids` attribute present, uses those IDs. Otherwise, queries:
   ```python
   Prescription.objects.filter(user=order.user, product__in=ordered_products, deleted=False)
       .order_by("product_id", "create_date").distinct("product_id")
   ```

4. **Guard against empty results** (line 2184-2189): If no prescriptions AND no OTC treatments found, logs an error and **returns early without creating a fill or sending to pharmacy**.

5. **Create PrescriptionFill associations:**
   - `create_prescription_fill_prescriptions` → creates `PrescriptionFillPrescriptions` records
   - `create_prescription_fill_otc_treatments` → creates `PrescriptionFillOTCTreatments` records

6. **Enqueue async task:** `send_prescription_refill_request.delay(order.id, prescription_fill.id)`

#### Step 5: Async Fill Request Task
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`, line 156 (`send_prescription_refill_request`)

This Celery task:
1. Checks if order is cancelled → attempts `send_cancel_fill_request_to_precision` if fill `can_cancel`
2. If prescriptions exist, validates state code (line 199): if shipping state is unsupported, logs error, creates `ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE`, **returns early without filling**
3. Validates refills remaining (line 212): calls `get_all_prescriptions_have_remaining_refills`. If any prescription has no refills left (and it's not a manual invoice), creates ConsultTask and **raises an exception**
4. Updates fill status to `PRESCRIPTION_FILL_STATUS_CREATED`
5. Calls `send_create_patient_request_to_precision`
6. For each prescription: `send_create_prescription_request_to_precision`
7. For each OTC treatment: `send_create_otc_treatment_request_to_precision`
8. Calls `send_fill_request_to_precision` — the actual pharmacy fill request

---

### Where Failures Can Occur

#### Failure Point 1: Order Misrouting (historical bug, still possible)
**Location:** `_process_shopify_order_impl`, line 637-672 and `_get_overall_order_type_and_sku_from_line_items`, lines 1017-1030

If `is_recurring_subscription_order` is incorrectly determined to be `False` (e.g., the Recharge `app_id` is not recognized, or the order comes via an unexpected path), `purchase_type` custom attributes from the original order can override the type. The order gets classified as `ORDER_TYPE_A_LA_CARTE` or `ORDER_TYPE_DYNAMIC_BUNDLE`, which routes it to `process_shopify_order_for_care` instead of `process_shopify_order_for_treatment_refill`. No prescription fill is created. This was the root cause of the ~302 missed fills documented in `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py`.

A daily healing task (`reprocess_subscription_refill_orders_daily` in `ecomm/tasks.py`, line 587) retries orders from the last 24 hours.

#### Failure Point 2: No User on Order
**Location:** `process_shopify_order_for_treatment_refill`, line 2136 and `_reprocess_order`, line 169

If no user can be resolved (no matching email, no cart, no consult), `order.user` is `None`. The prescription lookup falls into the `else` branch at line 2177 (logs a warning, `prescriptions` stays as `Prescription.objects.none()`). Combined with no OTC treatments, the function returns early at line 2189.

#### Failure Point 3: No Matching Prescriptions for User
**Location:** `process_shopify_order_for_treatment_refill`, line 2168-2189

The query `Prescription.objects.filter(user=order.user, product__in=ordered_products, deleted=False)` returns nothing if:
- The user has no prescriptions on file for those products
- All matching prescriptions have `deleted=True`
- The care product lookup fails (line items don't have associated care products)

Result: logs `"No prescriptions and no otc treatments found"` and returns without creating a fill.

#### Failure Point 4: Prescription Has No Refills Remaining
**Location:** `send_prescription_refill_request` task, lines 212-223

Even after the fill is associated, if `get_all_prescriptions_have_remaining_refills` returns `False` (prescription expired, `refills_remaining <= 0`, or `can_refill` is False), the task creates a `ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE` and raises an exception. No fill is sent to the pharmacy.

The `can_refill` property on `Prescription` (`care/models.py`, line 659) requires ALL of:
- `refills_remaining > 0`
- `is_refillable_product` (not antibiotic or antifungal)
- `expiration_date > today`
- `not product.is_disabled_for_refill`
- `not product.is_deprecated`

#### Failure Point 5: Invalid/Unsupported Shipping State
**Location:** `send_prescription_refill_request` task, lines 196-210; `verify_shipping_address_for_prescription_refill`, lines 144-153

If the order's shipping address `province_code` is not in `VALID_STATES` (imported from `consults.constants`), and there are any prescriptions (RX products), a `ConsultTask.TASK_TYPE_TREATMENT_REFILL_FAILURE` is created and the function returns without filling.

#### Failure Point 6: Missing or Corrupted Prescription Fill ID in Note Attributes
**Location:** `process_shopify_order_for_treatment_refill`, lines 2096-2108

For subscription renewal orders, a `prescription_fill_id` is expected in `note_attributes`. If this UUID is missing or invalid (`_is_valid_uuid` check fails), the code falls back to `PrescriptionFill.objects.get_or_create(order=order, user=order.user)`. This creates a new (empty) fill instead of using a pre-existing one, potentially leading to duplicate fills or orphaned fills.

If `prescription_fill_id` is set but the referenced fill doesn't exist in the DB, `PrescriptionFill.objects.get(id=prescription_fill_id)` raises `DoesNotExist`, which propagates up as an uncaught exception.

#### Failure Point 7: Precision API Failures
**Location:** `send_prescription_refill_request` task (ecomm/tasks.py), calls to `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_create_otc_treatment_request_to_precision`, `send_fill_request_to_precision`

Any exception from these Precision pharmacy API calls propagates and the Celery task fails. Celery retry behavior depends on task configuration. If the task does not have retry logic configured, the fill is never sent.

#### Failure Point 8: OTC-Only Subscription Renewal
**Location:** `send_prescription_refill_request` vs `send_otc_treatment_fill_request`

`send_prescription_refill_request` is always used by `process_shopify_order_for_treatment_refill`. The separate `send_otc_treatment_fill_request` task is for OTC-only orders. For subscription renewals that are OTC-only, `prescriptions.exists()` is False but `otc_treatments.exists()` should be True — the logic at line 2194 skips attaching OTC treatments if the order is cancelled, but for active orders this should work.

---

### Summary of the Full Code Path

```
Shopify webhook (orders/create)
  └─ shopify_webhook_view [api/v1/views/webhooks.py:82]
       └─ process_shopify_order [ecomm/utils.py:204]
            └─ _process_shopify_order_impl [ecomm/utils.py:238]
                 ├─ process_order_line_item [per line item]
                 │    └─ sets is_recurring_order_item=True for Recharge app_id
                 ├─ _get_overall_order_type_and_sku_from_line_items
                 │    └─ returns ORDER_TYPE_PRESCRIPTION_TREATMENT for subscription refill
                 ├─ _determine_checkout_source → CHECKOUT_SOURCE_SUBSCRIPTION
                 └─ process_shopify_order_for_treatment_refill [ecomm/utils.py:2089]
                      ├─ get or create PrescriptionFill
                      ├─ resolve user (email/cart/consult fallback chain)
                      ├─ find Prescriptions for user+products
                      ├─ EARLY EXIT if no prescriptions and no OTC treatments
                      ├─ create_prescription_fill_prescriptions [shipping/precision/utils.py:821]
                      ├─ create_prescription_fill_otc_treatments [shipping/precision/utils.py:846]
                      └─ send_prescription_refill_request.delay [ecomm/tasks.py:156]
                           ├─ validate state code → EARLY EXIT if invalid
                           ├─ validate refills_remaining → RAISE if none left
                           ├─ update fill status to CREATED
                           ├─ send_create_patient_request_to_precision
                           ├─ send_create_prescription_request_to_precision (per Rx)
                           ├─ send_create_otc_treatment_request_to_precision (per OTC)
                           └─ send_fill_request_to_precision (final pharmacy request)
```
