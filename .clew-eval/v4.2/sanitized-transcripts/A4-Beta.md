# A4: Order Processing Type Determination

## Summary

The order processing system determines order type through a multi-signal pipeline applied when Shopify webhooks are received. The determination uses SKU lookup (product-based), line item properties (purchase_type, selling_plan_id), order-level custom attributes (purchase_type, checkout_source), and the originating app_id (Recharge vs. Evvy vs. marketing site). The resolved `order_type` then forks into type-specific downstream handlers.

---

## Step 1: Entry Point — `_process_shopify_order_impl`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 238–790

All Shopify order webhooks go through `_process_shopify_order_impl`. This function:

1. Parses `note_attributes` (custom order attributes) to extract `checkout_source`, `parent_order_number`, `_evvyCartId`, `_evvySessionId`, and `_evvyAccountEmail`.
2. Parses `note` (order notes) to extract subscription metadata for webflow-origin subscription orders via `_extract_subscription_metadata_from_notes`.
3. Processes each line item via `process_order_line_item`, accumulating:
   - `line_item_has_subscription` (is this item a subscription opt-in?)
   - `line_item_is_recurring_order_item` (is this a recurring charge from Recharge?)
4. If any line item `is_recurring_order_item`, sets `is_recurring_subscription_order = True` (line 494).

```python
is_recurring_subscription_order = False
for line_item_payload in line_items:
    ...
    line_item, line_item_has_subscription, line_item_is_recurring_order_item = (
        process_order_line_item(order, line_item_payload, line_item_subscription_metadata, order_logger)
    )
    if line_item_has_subscription or line_item_is_recurring_order_item:
        order.is_subscription_order = True
    if line_item_is_recurring_order_item:
        is_recurring_subscription_order = True
```

---

## Step 2: Per-Line-Item Classification — `process_order_line_item`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 1322–1597

For each line item:

### 2a. SKU-based order_type

`_get_order_type_from_sku(sku)` maps SKU to one of:
- `ORDER_TYPE_TEST` ("TE") — standard vNGS test
- `ORDER_TYPE_EXPANDED_TEST` ("ET")
- `ORDER_TYPE_URINE_TEST` ("UT")
- `ORDER_TYPE_PCR_ADD_ON` ("PA")
- `ORDER_TYPE_VAGINITIS_CARE` ("CA")
- `ORDER_TYPE_STI_CARE` ("SC")
- `ORDER_TYPE_UTI_CARE` ("UC")
- `ORDER_TYPE_PRESCRIPTION_TREATMENT` ("PR")
- `ORDER_TYPE_OTHER` ("OT")

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 1036–1056

### 2b. Subscription detection (two mechanisms)

**Webflow/my.evvy.com subscription** — selling plan in order notes:
```python
if line_item_subscription_metadata and line_item_subscription_metadata.selling_plan_id:
    line_item.is_subscription = True
```
(line 1483–1484)

**Recharge recurring subscription** — app_id check:
```python
if line_item_subscription_metadata and line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID:
    line_item.is_recurring_order_item = True
```
(lines 1487–1491)

`SHOPIFY_RECHARGE_APP_ID = 294517` (defined in `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`, line 324).

The function returns `(line_item, line_item.is_subscription, line_item.is_recurring_order_item)`. Only `is_recurring_order_item` (Recharge) sets `is_recurring_subscription_order = True` at the order level — the distinction between a new subscription signup vs. an ongoing refill from Recharge.

### 2c. Line item purchase_type

For prescription treatment line items, custom properties are read:
- `_purchase_type` property → `PURCHASE_TYPE_INDIVIDUAL` ("individual") or `PURCHASE_TYPE_BUNDLE` ("bundle")
- Default for `ORDER_TYPE_PRESCRIPTION_TREATMENT` is `PURCHASE_TYPE_INDIVIDUAL`

---

## Step 3: Overall Order Type — `_get_overall_order_type_and_sku_from_line_items`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 952–1033

Called at line 565–567 with:
```python
order_type, order_sku = _get_overall_order_type_and_sku_from_line_items(
    created_line_items, order_custom_attributes, is_recurring_subscription_order
)
```

The function applies a priority hierarchy:

**Single-item orders:** the one line item's `order_type` is used directly.

**Multi-item orders:** priority cascade (highest to lowest):
1. Vaginitis care + UTI care mixed → `ORDER_TYPE_VAGINITIS_CARE` (with warning; deprecated)
2. Vaginitis care → `ORDER_TYPE_VAGINITIS_CARE`
3. UTI care → `ORDER_TYPE_UTI_CARE`
4. STI care → `ORDER_TYPE_STI_CARE`
5. Expanded test OR test + PCR add-on → `ORDER_TYPE_EXPANDED_TEST`
6. Urine test → `ORDER_TYPE_URINE_TEST`
7. Test → `ORDER_TYPE_TEST`
8. PCR add-on → `ORDER_TYPE_PCR_ADD_ON`
9. Prescription treatment → `ORDER_TYPE_PRESCRIPTION_TREATMENT`
10. Otherwise → `ORDER_TYPE_OTHER`

**Ungated RX override** (lines 1001–1013): If any `ORDER_TYPE_PRESCRIPTION_TREATMENT` line item has an ungated RX SKU, overrides to `ORDER_TYPE_UNGATED_RX` ("UX"). If any has a male partner treatment SKU, overrides to `ORDER_TYPE_MALE_PARTNER` ("MP").

**Care bundle type refinement via `purchase_type`** (lines 1020–1031):
This step only runs for **non-recurring subscription orders** (`not is_recurring_subscription_order`). It reads the `purchase_type` custom attribute from the order:
```python
if not is_recurring_subscription_order:
    for attribute in custom_attributes:
        if attribute["name"] == "purchase_type":
            if attribute_value == Consult.PURCHASE_TYPE_A_LA_CARTE:
                order_type = Order.ORDER_TYPE_A_LA_CARTE       # "AL"
            elif attribute_value == Consult.PURCHASE_TYPE_DYNAMIC_BUNDLE:
                order_type = Order.ORDER_TYPE_DYNAMIC_BUNDLE   # "BU"
            elif attribute_value == Consult.PURCHASE_TYPE_BUNDLE_A_LA_CARE:
                order_type = Order.ORDER_TYPE_MIXED_CARE       # "MC"
            break
```

**Key design decision:** For subscription refill orders (`is_recurring_subscription_order = True`), this `purchase_type` check is explicitly **skipped**. This prevents stale `purchase_type` attributes copied from the original order from contaminating refill order classification. Refill orders should remain `ORDER_TYPE_PRESCRIPTION_TREATMENT` based solely on their SKUs.

---

## Step 4: Checkout Source Determination

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 592–613

Checkout source is computed by `_determine_checkout_source(source_name, app_id, cart_id)` (lines 810–865):

Priority:
1. `app_id == SHOPIFY_RECHARGE_APP_ID` → `CHECKOUT_SOURCE_SUBSCRIPTION`
2. `cart_id` exists or `app_id == SHOPIFY_EVVY_API_APP_ID` → `CHECKOUT_SOURCE_INTERNAL_SITE` ("logged-in-cart")
3. Marketing site app IDs / `source_name='web'` / Shop Pay → `CHECKOUT_SOURCE_MARKETING_SITE`
4. Social app IDs → `CHECKOUT_SOURCE_SOCIAL`
5. POS → `CHECKOUT_SOURCE_POS`
6. Ops-created → `CHECKOUT_SOURCE_OPS_CREATED`
7. Distribution partner → `CHECKOUT_SOURCE_DISTRIBUTION_PARTNER`
8. Fallback → `CHECKOUT_SOURCE_OTHER`

For non-recurring subscription orders, a `checkout_source` custom attribute can **override** this determined value. For recurring subscription orders, the override is **skipped** and the determined source is used (ensuring consistent "subscription" labeling).

---

## Step 5: Downstream Routing Based on Resolved `order_type`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, lines 637–791

```python
if order.order_type in [VAGINITIS_CARE, STI_CARE, UTI_CARE, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, MALE_PARTNER]:
    order = process_shopify_order_for_care(order, payload, order_logger)

elif order.order_type in [TEST, EXPANDED_TEST, URINE_TEST]:
    process_shopify_order_for_test(order, payload, bulk_order_id, order_logger)

elif order.order_type == ORDER_TYPE_PCR_ADD_ON:
    process_shopify_order_for_pcr_add_on(order, payload, order_logger)

else:
    process_shopify_order_for_unknown_order_sku(order, payload, order_logger)
```

**Additional cross-cutting check for prescription treatment line items** (lines 660–672):
Even if the overall `order_type` is something other than treatment bundle types, if any line item is `ORDER_TYPE_PRESCRIPTION_TREATMENT`, `process_shopify_order_for_treatment_refill` is also called:

```python
if (
    order.order_type not in [A_LA_CARTE, MIXED_CARE, DYNAMIC_BUNDLE, UNGATED_RX, MALE_PARTNER]
    and ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
):
    process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

**Ungated RX routing** (lines 676–691): If `ORDER_TYPE_UNGATED_RX` and user exists:
- `can_refill_entire_order(user, order)` checks that every Rx product has a valid, refillable prescription
- If yes → `process_shopify_order_for_treatment_refill` (refill path)
- If no → `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult` (intake/consult path)

---

## What Each Handler Does

### `process_shopify_order_for_care` (lines 1807–)
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

- Looks up `consult_uid` from order note attributes and links the `Consult` to the order
- Updates consult status to `STATUS_ORDERED` if appropriate
- Sets the user on the order from the consult
- Fires `send_consult_paid_event` Celery task
- Updates `consult.purchase_type` if it changed
- Finalizes selected treatments via `add_ordered_products_to_consult`
- Handles care-specific downstream flows (UTI treatment orders, vaginitis upsell orders)

### `process_shopify_order_for_test` (lines 1600–)
- Matches user by email
- Handles provider-initiated orders (magic link checkout URLs)
- Creates test kit records

### `process_shopify_order_for_treatment_refill` (lines 2089–2201)
- Parses prescription fill ID, replacement fill ID from order attributes
- Gets or creates a `PrescriptionFill` record
- Resolves user via: `user_account_email` → cart user → consult user → order email fallback
- Fetches prescriptions (by explicit `prescription_ids` attribute, or by user+product lookup for evergreen prescriptions)
- Creates `PrescriptionFillPrescription` and `PrescriptionFillOTCTreatment` records
- Fires `send_prescription_refill_request.delay(order.id, prescription_fill.id)` Celery task to Precision pharmacy

---

## Order Type Constants (from `Order` model)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`, lines 42–77

| Constant | Code | Description |
|---|---|---|
| `ORDER_TYPE_TEST` | "TE" | Standard vNGS test |
| `ORDER_TYPE_VAGINITIS_CARE` | "CA" | Vaginitis care bundle |
| `ORDER_TYPE_STI_CARE` | "SC" | STI care |
| `ORDER_TYPE_UTI_CARE` | "UC" | UTI care |
| `ORDER_TYPE_PCR_ADD_ON` | "PA" | PCR add-on |
| `ORDER_TYPE_EXPANDED_TEST` | "ET" | Expanded test |
| `ORDER_TYPE_URINE_TEST` | "UT" | Urine test |
| `ORDER_TYPE_OTHER` | "OT" | Other/swag |
| `ORDER_TYPE_PRESCRIPTION_TREATMENT` | "PR" | Prescription treatment (refill) |
| `ORDER_TYPE_A_LA_CARTE` | "AL" | A la carte care |
| `ORDER_TYPE_DYNAMIC_BUNDLE` | "BU" | Dynamic care bundle |
| `ORDER_TYPE_MIXED_CARE` | "MC" | Mixed bundle + a la carte |
| `ORDER_TYPE_UNGATED_RX` | "UX" | Ungated Rx |
| `ORDER_TYPE_MALE_PARTNER` | "MP" | Male partner treatment |
| `ORDER_TYPE_GIFT_CARD` | "GC" | Gift card |

The model also tracks:
- `is_subscription_order` (bool) — order involved a subscription SKU or subscription line item
- `checkout_source` — where the order originated (subscription, vaginitis-intake, health-history, logged-in-cart, marketing-site, provider-portal, etc.)

---

## New Subscription vs. Refill vs. One-Time: Decision Summary

| Signal | Meaning |
|---|---|
| `is_recurring_order_item = True` (Recharge app_id=294517) | **Subscription refill** — recurring charge from Recharge. `is_recurring_subscription_order = True`, `purchase_type` custom attribute ignored. |
| `is_subscription = True` (selling_plan_id in notes or cart.is_subscription) | **New subscription signup** — first-time subscription purchase from webflow or my.evvy.com cart. `is_subscription_order = True`. |
| `purchase_type = "a-la-carte"` on a care treatment order | **One-time a la carte care** → `ORDER_TYPE_A_LA_CARTE`. Routed to care handler. |
| `purchase_type = "dynamic-bundle"` | **New bundle subscription** → `ORDER_TYPE_DYNAMIC_BUNDLE`. Routed to care handler. |
| `ORDER_TYPE_PRESCRIPTION_TREATMENT` line item without bundle purchase_type | **Treatment refill** → `process_shopify_order_for_treatment_refill` (creates PrescriptionFill, sends to Precision pharmacy). |
| `ORDER_TYPE_TEST/EXPANDED_TEST/URINE_TEST` | **Test kit order** → `process_shopify_order_for_test`. |
| `ORDER_TYPE_UNGATED_RX` + valid refillable prescriptions | Routed to **refill path** (`process_shopify_order_for_treatment_refill`). |
| `ORDER_TYPE_UNGATED_RX` + no valid prescriptions | Routed to **new intake/consult path**. |
