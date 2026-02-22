# A4 Exploration Log

## Search 1: Order type determination - subscription, refill, one-time
Searched: `order type determination subscription refill one-time`

Found the central function `_get_overall_order_type_and_sku_from_line_items` in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 952-1033), plus a parallel backfill script at `/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py`. The core processing entry point `_process_shopify_order_impl` was also identified at line 238. The `_get_order_type_from_sku` helper at line 1036 was flagged as the per-line-item SKU classifier.

## Search 2: Read _get_overall_order_type_and_sku_from_line_items and _get_order_type_from_sku
Read lines 952-1057 of `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`.

Key findings:
- `_get_order_type_from_sku(sku)` maps individual SKUs to type constants using SKU lists (care SKUs, test SKUs, urine test SKUs, expanded test SKUs, PCR add-on SKU, treatment SKUs).
- `_get_overall_order_type_and_sku_from_line_items(created_line_items, custom_attributes, is_recurring_subscription_order)` aggregates line items using a priority cascade: vaginitis care > UTI care > STI care > expanded test > urine test > test > PCR add-on > prescription treatment > other.
- After initial classification, it checks each line item for ungated Rx SKUs (prefix "URX") → upgrades to `ORDER_TYPE_UNGATED_RX`, or male partner treatment SKUs → upgrades to `ORDER_TYPE_MALE_PARTNER`.
- Finally, unless `is_recurring_subscription_order=True`, it checks `custom_attributes` for a `purchase_type` attribute that can further refine to `ORDER_TYPE_A_LA_CARTE`, `ORDER_TYPE_DYNAMIC_BUNDLE`, or `ORDER_TYPE_MIXED_CARE`.

## Search 3: Shopify order processing entry point and checkout source
Searched: `process shopify order checkout source subscription`

Then read `_process_shopify_order_impl` lines 238-614.

Key findings for how the system determines order type:

**Step 1 — Parse note_attributes (custom attributes from Shopify):**
- `checkout_source` — overrides auto-determined source if set (skipped for recurring subscription orders)
- `parent_order_number` — marks cross-sell orders
- `purchase_type` — used later in `_get_overall_order_type_and_sku_from_line_items`

**Step 2 — Extract subscription metadata from order notes:**
- `_extract_subscription_metadata_from_notes(notes)` parses JSON from the order `note` field to extract a `{variantId: sellingPlanId}` map (used by webflow-based subscription orders).

**Step 3 — Process each line item via `process_order_line_item`:**
- Returns `(line_item, line_item_has_subscription, line_item_is_recurring_order_item)`
- If any line item has `is_subscription=True` → `order.is_subscription_order = True`
- If any line item `is_recurring_order_item=True` → `is_recurring_subscription_order = True`

**Step 4 — Determine overall order type:**
- Calls `_get_overall_order_type_and_sku_from_line_items(created_line_items, order_custom_attributes, is_recurring_subscription_order)`
- Sets `order.order_type` and `order.sku`

**Step 5 — Determine checkout source:**
- `_determine_checkout_source(source_name, app_id, cart_id)` applies priority logic
- For recurring subscription orders, the `checkout_source` custom attribute is ignored

## Search 4: Line item subscription/recurring detection
Searched: `process_order_line_item subscription recurring selling_plan`

Read `process_order_line_item` at lines 1322-1597.

Key detection logic:
1. **SKU-based type**: `order_type = _get_order_type_from_sku(sku)` — maps SKU to type constant immediately.
2. **Cart-based subscription**: If the line item has a `cart_id` property, the system fetches the corresponding `Cart` object and reads `cart_line_item.is_subscription` from the cart's line items.
3. **Selling plan (webflow subscriptions)**: If `line_item_subscription_metadata.selling_plan_id` is set (extracted from order notes), `line_item.is_subscription = True`.
4. **Recharge (recurring)**: If `line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID`, `line_item.is_recurring_order_item = True`. This is the primary signal for a subscription refill order.

## Search 5: _determine_checkout_source and SHOPIFY_RECHARGE_APP_ID
Read lines 793-865 of `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`.

`_determine_checkout_source` priority order:
1. Recharge app ID → `CHECKOUT_SOURCE_SUBSCRIPTION` ("subscription")
2. Cart ID present OR Evvy API app ID → `CHECKOUT_SOURCE_INTERNAL_SITE` ("logged-in-cart")
3. No app ID / marketing site app IDs / source_name="web" / Shop Pay → `CHECKOUT_SOURCE_MARKETING_SITE`
4. Social app IDs → social
5. POS → pos
6. Ops created → ops_created
7. Distribution partner → distribution_partner
8. Testing orders → other
9. Fallback → other

## Search 6: Downstream routing by order type
Read lines 635-790 of `_process_shopify_order_impl`.

After `order.order_type` is set, the system dispatches to type-specific handlers:
- **Care types** (vaginitis, STI, UTI, a la carte, dynamic bundle, mixed care, male partner) → `process_shopify_order_for_care()`
- **Test types** (test, expanded test, urine test) → `process_shopify_order_for_test()`
- **PCR add-on** → `process_shopify_order_for_pcr_add_on()`
- **Unknown/other** → `process_shopify_order_for_unknown_order_sku()`

Additionally:
- If order type is NOT a la carte/mixed care/dynamic bundle/ungated RX/male partner AND any line item is `ORDER_TYPE_PRESCRIPTION_TREATMENT` → also calls `process_shopify_order_for_treatment_refill()` (handles refill orders that contain prescription treatments alongside tests).
- For ungated Rx orders: calls `can_refill_entire_order(user, order)` → if True, routes to `process_shopify_order_for_treatment_refill()`; if False, routes to `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()`.

## Search 7: process_shopify_order_for_care downstream
Read lines 1807-1961.

For care orders:
- Parses `consult_uid` and `purchase_type` from note_attributes
- Links consult to order via `ConsultOrder`
- Updates consult status from `STATUS_OPTED_IN` → `STATUS_ORDERED` (if not already progressed)
- Calls `send_consult_paid_event.delay()` to trigger analytics
- If `has_selected_treatments_purchase_type`, calls `add_ordered_products_to_consult()` to finalize treatment selection

## Search 8: process_shopify_order_for_treatment_refill downstream
Read lines 2089-2201.

For prescription refill orders:
1. Parses `prescription_fill_id`, `consult_uid`, `user_account_email`, `prescription_ids` from order note attributes
2. Finds or creates a `PrescriptionFill` record
3. Resolves user from account email, cart, consult, or order email
4. Links prescription fill to order
5. Gets ordered products and looks up matching `Prescription` objects
6. Calls `create_prescription_fill_prescriptions()` and `create_prescription_fill_otc_treatments()`
7. Calls `send_prescription_refill_request.delay()` → sends to Precision pharmacy

## Search 9: send_prescription_refill_request task
Read lines 157-267 of `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`.

The task:
- For cancelled orders: attempts to cancel the fill in Precision pharmacy
- For active orders with prescriptions: validates shipping address for state restrictions, checks refill availability
- Creates patient in Precision, submits each prescription to Precision, submits OTC treatments
- Calls `send_fill_request_to_precision()` to dispatch to pharmacy

## Search 10: can_refill_entire_order for ungated Rx routing
Read lines 2732-2791 of `ecomm/utils.py`.

For ungated Rx orders specifically, this function determines whether to route to the refill path or the new-consult path:
- Gets care products from order line items
- Filters to Rx-only products (excludes OTC)
- Looks up active prescriptions for the user matching those products
- Returns True only if every Rx product has a valid, non-expired prescription with remaining refills

---

## Final Answer

### How the Order Processing System Determines Order Type

The order type determination pipeline is implemented in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, triggered via the `_process_shopify_order_impl()` function (line 238) which is called from the Shopify webhook handler.

---

### Stage 1: Per-Line-Item Type Classification

Every line item in the Shopify order is classified individually by `_get_order_type_from_sku(sku)` (line 1036):

```python
def _get_order_type_from_sku(sku: str) -> str:
    if sku in get_all_care_skus():
        if sku == SHOPIFY_CARE_STI_TREAMENT_SKU:
            return Order.ORDER_TYPE_STI_CARE
        elif sku == SHOPIFY_CARE_UTI_TREAMENT_SKU:
            return Order.ORDER_TYPE_UTI_CARE
        else:
            return Order.ORDER_TYPE_VAGINITIS_CARE
    elif sku in get_all_test_skus():
        if sku in URINE_TEST_SKUS:
            return Order.ORDER_TYPE_URINE_TEST
        elif sku in EXPANDED_TEST_SKUS:
            return Order.ORDER_TYPE_EXPANDED_TEST
        else:
            return Order.ORDER_TYPE_TEST
    elif sku == EXPANDED_PCR_ADD_ON_SKU:
        return Order.ORDER_TYPE_PCR_ADD_ON
    elif sku in get_all_treatment_skus():
        return Order.ORDER_TYPE_PRESCRIPTION_TREATMENT
    else:
        return Order.ORDER_TYPE_OTHER
```

This runs for each line item inside `process_order_line_item()` at line 1338.

---

### Stage 2: New Subscription vs. Refill vs. One-Time Detection (per line item)

Still within `process_order_line_item()` (lines 1460-1492), three signals determine whether a line item is a subscription or recurring refill:

**Signal 1 — Cart-based subscription (my.evvy.com orders):**
```python
if cart_id:
    cart_line_item = cart.line_items.filter(...)
    line_item.is_subscription = cart_line_item.is_subscription  # True = new subscription
```

**Signal 2 — Selling plan ID (webflow site subscriptions):**
```python
if line_item_subscription_metadata.selling_plan_id:
    line_item.is_subscription = True  # new subscription with a selling plan
```

**Signal 3 — Recharge app ID (subscription refill/recurring):**
```python
if line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID:
    line_item.is_recurring_order_item = True  # THIS is a recurring refill
```

The `app_id` is read from the Shopify payload and `SHOPIFY_RECHARGE_APP_ID` identifies orders that originated from Recharge (the subscription management platform), meaning the customer's subscription timer fired and Recharge generated a refill order automatically.

Back in `_process_shopify_order_impl()` (lines 491-494):
```python
if line_item_has_subscription or line_item_is_recurring_order_item:
    order.is_subscription_order = True
if line_item_is_recurring_order_item:
    is_recurring_subscription_order = True  # used throughout rest of processing
```

---

### Stage 3: Overall Order Type Aggregation

`_get_overall_order_type_and_sku_from_line_items(created_line_items, order_custom_attributes, is_recurring_subscription_order)` (line 952) combines all line item types into a single order type using a **priority cascade** for multi-item orders:

1. Vaginitis care beats UTI care (error-logged if both present)
2. STI care
3. Expanded test (or test + PCR add-on combo)
4. Urine test
5. Standard test
6. PCR add-on
7. Prescription treatment
8. Other

**Ungated Rx upgrade** (lines 1001-1013): After initial classification, if any line item is `ORDER_TYPE_PRESCRIPTION_TREATMENT` AND its SKU starts with "URX", the order type becomes `ORDER_TYPE_UNGATED_RX`. If it's a male partner treatment SKU, it becomes `ORDER_TYPE_MALE_PARTNER`.

**Purchase type refinement** (lines 1020-1031): Unless this is a recurring subscription order (`is_recurring_subscription_order=True`), the `purchase_type` custom attribute on the order overrides the type:
```python
if not is_recurring_subscription_order:
    for attribute in custom_attributes:
        if attribute["name"] == "purchase_type":
            if attribute_value == Consult.PURCHASE_TYPE_A_LA_CARTE:
                order_type = Order.ORDER_TYPE_A_LA_CARTE
            elif attribute_value == Consult.PURCHASE_TYPE_DYNAMIC_BUNDLE:
                order_type = Order.ORDER_TYPE_DYNAMIC_BUNDLE
            elif attribute_value == Consult.PURCHASE_TYPE_BUNDLE_A_LA_CARE:
                order_type = Order.ORDER_TYPE_MIXED_CARE
```

**Critical design note**: For recurring subscription orders (`is_recurring_subscription_order=True`), the `purchase_type` custom attribute is deliberately ignored. This is because Recharge copies the original order's attributes (which may say "dynamic-bundle") onto the refill order, but a refill is always just `ORDER_TYPE_PRESCRIPTION_TREATMENT`. The checkout source custom attribute is similarly ignored for recurring orders.

---

### Stage 4: Checkout Source Determination

`_determine_checkout_source(source_name, app_id, cart_id)` (line 810) identifies where the order originated, using the same priority logic as the dbt data warehouse models:

1. Recharge app ID → `"subscription"` (recurring refill)
2. Cart ID or Evvy API app → `"logged-in-cart"` (new subscription from my.evvy.com)
3. Marketing site app IDs / source_name="web" → `"marketing-site"` (one-time purchase)
4. Social, POS, ops, distribution partner, etc.

For recurring subscription orders, any `checkout_source` custom attribute from the Shopify payload is ignored (lines 598-607).

---

### Stage 5: Downstream Processing Based on Order Type

After `order.order_type` is set, `_process_shopify_order_impl()` dispatches to type-specific handlers (lines 637-658):

| Order Type | Handler | What It Does |
|---|---|---|
| `VAGINITIS_CARE`, `STI_CARE`, `UTI_CARE`, `A_LA_CARTE`, `DYNAMIC_BUNDLE`, `MIXED_CARE`, `MALE_PARTNER` | `process_shopify_order_for_care()` | Links consult, updates consult status to `ORDERED`, fires `send_consult_paid_event`, finalizes selected treatments |
| `TEST`, `EXPANDED_TEST`, `URINE_TEST` | `process_shopify_order_for_test()` | Handles provider portal linking (magic links, PTOs), creates urine test records for Junction lab |
| `PCR_ADD_ON` | `process_shopify_order_for_pcr_add_on()` | Fetches test kit by hash, calls `add_expanded_vpcr_panel_to_test_kit()` |
| `OTHER` (and unknown SKUs) | `process_shopify_order_for_unknown_order_sku()` | Minimal: just attempts user lookup from email |

**Cross-cutting: Prescription refill path** (lines 660-672):
If the order type is NOT a la carte/mixed care/dynamic bundle/ungated RX/male partner, but any line item is `ORDER_TYPE_PRESCRIPTION_TREATMENT`, `process_shopify_order_for_treatment_refill()` is also called. This handles test-plus-refill combo orders.

**Ungated Rx routing** (lines 676-691):
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        # Route to REFILL path — user already has valid prescriptions
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        # Route to NEW CONSULT path — user needs a new prescription
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(...)
```

`can_refill_entire_order()` (line 2732) checks that every Rx product in the order has a non-expired, non-depleted `Prescription` record for the user.

---

### Treatment Refill Path (`process_shopify_order_for_treatment_refill`, line 2089)

This handles both recurring subscription refills and one-time prescription refill orders:

1. Parses `prescription_fill_id`, `consult_uid`, `user_account_email`, `prescription_ids` from order note attributes
2. Finds or creates a `PrescriptionFill` record
3. Resolves user from multiple fallback sources (account email → cart → consult → order email)
4. Calls `create_prescription_fill_prescriptions()` and `create_prescription_fill_otc_treatments()`
5. Dispatches `send_prescription_refill_request.delay()` which:
   - Validates shipping address for state restrictions
   - Verifies prescriptions have remaining refills (`get_all_prescriptions_have_remaining_refills`)
   - Creates/updates patient record in Precision pharmacy
   - Submits each prescription to Precision
   - Calls `send_fill_request_to_precision()` to trigger actual dispensing

---

### Summary of the Full Decision Tree

```
Shopify webhook arrives
        |
        v
Parse note_attributes (custom attributes):
  checkout_source, purchase_type, parent_order_number, consult_uid, etc.
        |
        v
For each line item:
  1. Map SKU → line_item.order_type (via _get_order_type_from_sku)
  2. Check app_id == SHOPIFY_RECHARGE_APP_ID → is_recurring_order_item = True
  3. Check selling_plan_id in notes OR cart.is_subscription → is_subscription = True
        |
        v
Aggregate to order level:
  - is_recurring_subscription_order = any(is_recurring_order_item)
  - order.is_subscription_order = any(is_subscription OR is_recurring)
        |
        v
_get_overall_order_type_and_sku_from_line_items():
  Priority cascade (care > test > pcr > treatment > other)
  + Ungated Rx upgrade (SKU prefix "URX")
  + Male partner upgrade (SKU in MALE_PARTNER_TREATMENT_SKUS)
  + purchase_type override (ONLY if NOT recurring subscription)
        |
        v
_determine_checkout_source(source_name, app_id, cart_id):
  Recharge app_id → "subscription"
  cart_id or Evvy app → "logged-in-cart"
  marketing site → "marketing-site"
  (custom attribute checkout_source ONLY applied if NOT recurring)
        |
        v
Dispatch by order.order_type:
  Care types → process_shopify_order_for_care()
    - Links consult, STATUS_ORDERED, send_consult_paid_event
  Test types → process_shopify_order_for_test()
    - Provider portal linking, urine test creation
  PCR add-on → process_shopify_order_for_pcr_add_on()
    - Attaches expanded panel to test kit
  Unknown → process_shopify_order_for_unknown_order_sku()
  + If any line item is Rx treatment AND not a care bundle type:
    → process_shopify_order_for_treatment_refill()
        - PrescriptionFill, Precision pharmacy submission
  + If UNGATED_RX:
    → can_refill_entire_order() ?
        True  → process_shopify_order_for_treatment_refill()
        False → create/attach new consult
        |
        v
Universal:
  send_order_to_berlin_for_fulfillment.delay() (physical fulfillment for all orders)
  send_any_paid_event.delay() (analytics for all non-cancelled orders)
```

### Key Files

- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — Central orchestrator: `_process_shopify_order_impl` (line 238), `process_order_line_item` (line 1322), `_get_overall_order_type_and_sku_from_line_items` (line 952), `_get_order_type_from_sku` (line 1036), `_determine_checkout_source` (line 810), `_extract_subscription_metadata_from_notes` (line 793), `process_shopify_order_for_care` (line 1807), `process_shopify_order_for_test` (line 1600), `process_shopify_order_for_treatment_refill` (line 2089), `can_refill_entire_order` (line 2732)
- `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` — `Order` model with all type constants (`ORDER_TYPE_*`, `CHECKOUT_SOURCE_*`) at lines 42-175
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — `send_prescription_refill_request` (line 157), `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult` (line 344)
- `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` — `send_order_to_berlin_for_fulfillment` (line 685)
- `/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py` — Documents the Recharge-specific bug (incorrect purchase_type copied from original order) that motivated the `is_recurring_subscription_order` bypass
