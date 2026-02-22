# A4 Exploration Log

## Search 1: Find files related to order types, subscriptions, and refills
Searched for files containing keywords "order_type", "subscription", "refill", "one-time" across all Python files.

Key files found:
- `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` — Order and OrderLineItem models
- `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` — SKU constants for all product types
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — Core order processing logic
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — Celery tasks for post-order processing
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` — Webhook entry points

## Search 2: Read the Order model to understand order type taxonomy
Read `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`.

Found the `Order` model defines these order type constants (stored as 2-char codes):
- `ORDER_TYPE_TEST = "TE"` — Standard vaginal test
- `ORDER_TYPE_VAGINITIS_CARE = "CA"` — Vaginitis care (legacy bundle)
- `ORDER_TYPE_STI_CARE = "SC"` — STI care
- `ORDER_TYPE_UTI_CARE = "UC"` — UTI care
- `ORDER_TYPE_PCR_ADD_ON = "PA"` — PCR panel add-on
- `ORDER_TYPE_EXPANDED_TEST = "ET"` — Expanded test
- `ORDER_TYPE_URINE_TEST = "UT"` — Urine/UTI test
- `ORDER_TYPE_OTHER = "OT"` — Other / swag
- `ORDER_TYPE_PRESCRIPTION_TREATMENT = "PR"` — Prescription refill or treatment fill
- `ORDER_TYPE_A_LA_CARTE = "AL"` — A la carte care (individual treatment, no bundle)
- `ORDER_TYPE_DYNAMIC_BUNDLE = "BU"` — Dynamic care bundle
- `ORDER_TYPE_MIXED_CARE = "MC"` — Mixed (bundle + a la carte)
- `ORDER_TYPE_UNGATED_RX = "UX"` — Ungated Rx (no consult required first)
- `ORDER_TYPE_MALE_PARTNER = "MP"` — Male partner treatment
- `ORDER_TYPE_GIFT_CARD = "GC"` — Gift card

Also found `is_subscription_order` (bool) on Order and on OrderLineItem:
- `is_subscription` — line item was part of a subscription
- `is_recurring_order_item` — line item is a recurring/refill from Recharge

## Search 3: Read ecomm/constants.py to understand SKU taxonomy
Read `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`.

Found the SKU naming conventions that drive order type classification:
- All care SKUs: `TRMT001`–`TRMT006` (legacy care bundle products)
- Refill SKUs: named with `RFL` prefix (e.g., `RFLBA001` for boric acid refill)
- Replacement SKUs: named with `RPL` prefix (replacements for refills)
- Test subscription SKUs: `EM001`, `EM002`, `EMEXP001`, `EM004` (membership SKUs)
- Regular test SKUs: `VMT001`, `VMTEXP001`, etc.
- Ungated Rx: `URXBA004`
- Male partner treatment: `MPTCL001`, `MPTMG001`

Also found Shopify app ID constants used to determine checkout source:
- `SHOPIFY_RECHARGE_APP_ID = 294517` — subscription platform
- `SHOPIFY_EVVY_API_APP_ID = 6687809` — internal logged-in cart
- Marketing site, social, POS, ops-created IDs

## Search 4: Find functions that classify/determine order type
Searched for `def.*order_type`, `determine.*order`, `classify.*order`, `get_order_type`.

Found key functions in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:
- `_get_order_type_from_sku()` (line 1036) — determines per-line-item order type from SKU
- `_get_overall_order_type_and_sku_from_line_items()` (line 952) — determines the overall order type from all line items + custom attributes
- `_determine_checkout_source()` (line 810) — determines where order originated from (Recharge, internal cart, marketing site, etc.)
- `process_shopify_order_for_care()` (line 1807) — care-specific downstream logic
- `process_shopify_order_for_test()` (line 1600) — test-specific downstream logic
- `process_shopify_order_for_treatment_refill()` (line 2089) — prescription refill downstream logic
- `can_refill_entire_order()` (line 2732) — check if ungated Rx order can be fulfilled via refill path vs consult path

## Search 5: Read the core order processing orchestration function
Read `_process_shopify_order_impl()` starting at line 238 in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`.

Found the top-level orchestration of order type determination:
1. Extracts `source_name`, `app_id`, `note_attributes`, `line_items` from Shopify payload
2. Loops over each line item calling `process_order_line_item()`, which:
   - Calls `_get_order_type_from_sku(sku)` to get per-line-item order type
   - Detects `selling_plan_id` from order notes (subscription signal from webflow site)
   - Detects `app_id == SHOPIFY_RECHARGE_APP_ID` (subscription signal from Recharge)
   - Sets `is_subscription = True` if from cart with subscription flag or selling_plan_id
   - Sets `is_recurring_order_item = True` if from Recharge app
3. If any line item has `is_recurring_order_item`, sets `is_recurring_subscription_order = True`
4. Calls `_get_overall_order_type_and_sku_from_line_items()` to compute overall order type
5. Sets `order.is_subscription_order = True` if the SKU is a subscription SKU
6. Calls `_determine_checkout_source()` to get origin, with special handling to NOT override checkout_source from custom attributes for recurring subscription orders

## Search 6: Read `_get_order_type_from_sku()` and `_get_overall_order_type_and_sku_from_line_items()`
Read lines 1036–1065 and 952–1034.

`_get_order_type_from_sku(sku)`:
- If SKU in `get_all_care_skus()`:
  - `SHOPIFY_CARE_STI_TREAMENT_SKU` → `ORDER_TYPE_STI_CARE`
  - `SHOPIFY_CARE_UTI_TREAMENT_SKU` → `ORDER_TYPE_UTI_CARE`
  - else → `ORDER_TYPE_VAGINITIS_CARE`
- If SKU in `get_all_test_skus()`:
  - Urine test SKUs → `ORDER_TYPE_URINE_TEST`
  - Expanded test SKUs → `ORDER_TYPE_EXPANDED_TEST`
  - else → `ORDER_TYPE_TEST`
- If SKU == `EXPANDED_PCR_ADD_ON_SKU` → `ORDER_TYPE_PCR_ADD_ON`
- If SKU in `get_all_treatment_skus()` (includes refill SKUs `RFL*` and replacement SKUs `RPL*`) → `ORDER_TYPE_PRESCRIPTION_TREATMENT`
- else → `ORDER_TYPE_OTHER`

`_get_overall_order_type_and_sku_from_line_items()`:
- If single line item → use that line item's order_type directly
- If multiple line items → priority resolution:
  1. Vaginitis+UTI mix → error, default to vaginitis
  2. Vaginitis care wins over other types
  3. UTI care
  4. STI care
  5. Expanded test (or test + PCR add-on together)
  6. Urine test
  7. Standard test
  8. PCR add-on
  9. Prescription treatment
  10. Other
- Then checks each line item for ungated Rx SKU → overrides to `ORDER_TYPE_UNGATED_RX`
- Then checks for male partner treatment SKU → overrides to `ORDER_TYPE_MALE_PARTNER`
- **If NOT a recurring subscription order**, checks `purchase_type` custom attribute:
  - `a_la_carte` → `ORDER_TYPE_A_LA_CARTE`
  - `dynamic_bundle` → `ORDER_TYPE_DYNAMIC_BUNDLE`
  - `bundle_a_la_care` → `ORDER_TYPE_MIXED_CARE`

This is a critical distinction: **recurring subscription orders skip the `purchase_type` attribute check** because that attribute may have been copied from the original order and would incorrectly reclassify a refill order.

## Search 7: Read downstream routing by order type (lines 632–695)
Read lines 632–695 in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`.

Found the order-type dispatch after classification:
```python
if order.order_type in [VAGINITIS_CARE, STI_CARE, UTI_CARE, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, MALE_PARTNER]:
    process_shopify_order_for_care(order, payload, order_logger)
elif order.order_type in [TEST, EXPANDED_TEST, URINE_TEST]:
    process_shopify_order_for_test(order, payload, bulk_order_id, order_logger)
elif order.order_type == PCR_ADD_ON:
    process_shopify_order_for_pcr_add_on(order, payload, order_logger)
else:
    process_shopify_order_for_unknown_order_sku(order, payload, order_logger)
```

Then, **additional refill routing** runs on top:
- If order type is NOT in [A_LA_CARTE, MIXED_CARE, DYNAMIC_BUNDLE, UNGATED_RX, MALE_PARTNER] AND any line item has `ORDER_TYPE_PRESCRIPTION_TREATMENT` → also runs `process_shopify_order_for_treatment_refill()`
- For UNGATED_RX orders with a known user: checks `can_refill_entire_order()` to decide between:
  - Refill path (`process_shopify_order_for_treatment_refill()`) — all Rx products have valid prescriptions
  - Consult path (`add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()`) — new consult needed

## Search 8: Read `process_shopify_order_for_treatment_refill()` to understand refill downstream logic
Read lines 2089–2203.

Found the prescription refill path:
1. Parses order notes for `prescription_fill_id`, `replacement_fill_id`, `consult_uid`, `prescription_ids`
2. Finds or creates a `PrescriptionFill` object keyed to order+user
3. Looks up existing prescriptions by `prescription_ids` or (for evergreen prescriptions) by user + products
4. Validates prescriptions (state restrictions, refills remaining)
5. Creates `PrescriptionFillPrescriptions` linking fill to prescriptions
6. Sends async Celery task `send_prescription_refill_request` to dispatch to Precision pharmacy

## Search 9: Read webhook entry points to understand how orders enter the system
Read `shopify_webhook_view()` and `recharge_webhook_view()` in `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`.

Found two entry paths:
- **Shopify webhooks** (`orders/create` and `orders/cancelled`) → `process_shopify_order(payload, is_order_cancellation)`
  - Covers: new purchases, subscription first orders (with `selling_plan_id` in notes), Recharge recurring orders (detected by `app_id == SHOPIFY_RECHARGE_APP_ID`)
- **ReCharge webhooks** (subscription lifecycle events) → `handle_subscription_webhook()` or `handle_charge_upcoming_webhook()`
  - These handle subscription management events (create, cancel, activate, pause, skip) separately from the actual order fulfillment

## Search 10: Understand subscription first-order vs recurring distinction
From reading lines 462–494 in `ecomm/utils.py`:

For webflow/my.evvy.com site orders:
- Order notes contain a JSON list of line items with `variantId` and `sellingPlanId` — parsed by `_extract_subscription_metadata_from_notes()`
- If a line item has a `selling_plan_id`, it is a **new subscription** → `is_subscription = True`

For Recharge-originated orders:
- `app_id == SHOPIFY_RECHARGE_APP_ID` → `is_recurring_order_item = True` on every line item
- This makes `is_recurring_subscription_order = True` on the overall order

Additionally, if the cart had `is_subscription = True` on a CartLineItem (set during checkout), the OrderLineItem inherits it.

`_get_is_subscription_sku()` checks if the SKU is in `ALL_TEST_SUBSCRIPTION_SKUS` (membership SKUs: EM001, EM002, EMEXP001, EM004) → sets `order.is_subscription_order = True`.

---

## Final Answer

### How the Order Processing System Determines Order Type

The order type determination is a multi-stage process triggered by Shopify webhooks and implemented primarily in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`.

---

### Stage 1: Entry Point and Raw Signal Extraction

Orders enter via `shopify_webhook_view()` in `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (line 82), which calls `process_shopify_order()` for both `orders/create` and `orders/cancelled` Shopify topics.

Inside `_process_shopify_order_impl()` (line 238), the system extracts raw signals from the Shopify payload:
- `line_items` — the products purchased
- `note_attributes` — custom attributes from the cart (including `purchase_type`, `consult_uid`, `checkout_source`, subscription metadata)
- `source_name` — Shopify order source
- `app_id` — the Shopify app that created the order (critical for subscription detection)
- `notes` — free-form notes that may contain JSON subscription selling plan data

---

### Stage 2: Per-Line-Item Order Type via SKU

`process_order_line_item()` (line 1322) calls `_get_order_type_from_sku(sku)` (line 1036) on each line item. This function classifies each individual product by SKU pattern:

```python
# /Users/albertgwo/Work/evvy/backend/ecomm/utils.py, lines 1036–1056
def _get_order_type_from_sku(sku: str) -> str:
    if sku in get_all_care_skus():      # TRMT001–TRMT006
        if sku == SHOPIFY_CARE_STI_TREAMENT_SKU:    return Order.ORDER_TYPE_STI_CARE
        elif sku == SHOPIFY_CARE_UTI_TREAMENT_SKU:  return Order.ORDER_TYPE_UTI_CARE
        else:                                        return Order.ORDER_TYPE_VAGINITIS_CARE
    elif sku in get_all_test_skus():    # VMT*, VMTEXP*, EM*, UTI*, etc.
        if sku in URINE_TEST_SKUS:       return Order.ORDER_TYPE_URINE_TEST
        elif sku in EXPANDED_TEST_SKUS:  return Order.ORDER_TYPE_EXPANDED_TEST
        else:                            return Order.ORDER_TYPE_TEST
    elif sku == EXPANDED_PCR_ADD_ON_SKU:             return Order.ORDER_TYPE_PCR_ADD_ON
    elif sku in get_all_treatment_skus():  # RFL*, RPL* refill/replacement SKUs
        return Order.ORDER_TYPE_PRESCRIPTION_TREATMENT
    else:
        return Order.ORDER_TYPE_OTHER
```

Both refill SKUs (prefix `RFL`) and replacement SKUs (prefix `RPL`) map to `ORDER_TYPE_PRESCRIPTION_TREATMENT` — the system does not distinguish refill from replacement at the SKU classification level; that distinction is handled in the prescription fill logic downstream.

---

### Stage 3: Subscription vs. Recurring Detection (per line item)

During `process_order_line_item()` (lines 1460–1492), three signals determine whether a line item is part of a subscription or a recurring order:

1. **Cart subscription flag**: If the Shopify cart (linked via `_evvyCartId`) had `is_subscription = True` on the CartLineItem, that is inherited onto the OrderLineItem.

2. **Selling plan ID in order notes** (new subscriptions on webflow/my.evvy.com):
   ```python
   # lines 1482–1484
   if line_item_subscription_metadata and line_item_subscription_metadata.selling_plan_id:
       line_item.is_subscription = True
   ```
   The `selling_plan_id` is extracted from the order `note` field by `_extract_subscription_metadata_from_notes()` (line 793), which parses a JSON blob embedded in the notes by the frontend.

3. **Recharge app ID** (recurring/refill subscription orders):
   ```python
   # lines 1486–1491
   if line_item_subscription_metadata and line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID:
       line_item.is_recurring_order_item = True
   ```
   `SHOPIFY_RECHARGE_APP_ID = 294517` (defined in `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`, line 324).

If any line item has `is_recurring_order_item = True`, the overall flag `is_recurring_subscription_order = True` is set (line 494). This flag is **the primary distinguisher between a new subscription purchase and a recurring subscription refill at the order level**.

---

### Stage 4: Overall Order Type Resolution

`_get_overall_order_type_and_sku_from_line_items()` (line 952) resolves the single overall order type from all line item types using a priority hierarchy:

```python
# lines 959–994 (simplified priority order)
if single line item:
    order_type = that line item's type
else:
    # Priority hierarchy for multi-item orders:
    has_vaginitis_care → ORDER_TYPE_VAGINITIS_CARE  (or error if also has UTI care)
    has_uti_care → ORDER_TYPE_UTI_CARE
    STI_CARE in items → ORDER_TYPE_STI_CARE
    EXPANDED_TEST or (TEST + PCR_ADD_ON) → ORDER_TYPE_EXPANDED_TEST
    URINE_TEST in items → ORDER_TYPE_URINE_TEST
    TEST in items → ORDER_TYPE_TEST
    PCR_ADD_ON → ORDER_TYPE_PCR_ADD_ON
    PRESCRIPTION_TREATMENT → ORDER_TYPE_PRESCRIPTION_TREATMENT
    else → ORDER_TYPE_OTHER
```

Then special-case overrides (lines 1001–1013):
- Any line item with an ungated Rx SKU (`URXBA004`) → overrides to `ORDER_TYPE_UNGATED_RX`
- Any line item with a male partner treatment SKU (`MPTCL001`, `MPTMG001`) → overrides to `ORDER_TYPE_MALE_PARTNER`

Then the **purchase_type** attribute from cart custom attributes (lines 1020–1031):
```python
# ONLY if NOT a recurring subscription order
if not is_recurring_subscription_order:
    for attribute in custom_attributes:
        if attribute["name"] == "purchase_type":
            if value == "a_la_carte":      order_type = ORDER_TYPE_A_LA_CARTE
            elif value == "dynamic_bundle": order_type = ORDER_TYPE_DYNAMIC_BUNDLE
            elif value == "bundle_a_la_care": order_type = ORDER_TYPE_MIXED_CARE
```

**This is a key design decision**: recurring subscription refill orders skip the `purchase_type` check because the `purchase_type` attribute may have been copied from the original subscription order (which might have been a `dynamic_bundle`) and would incorrectly reclassify a refill order.

---

### Stage 5: Subscription SKU Check for Test Memberships

After overall type is resolved, the system checks whether the primary SKU is a test membership SKU (lines 581–582):
```python
if _get_is_subscription_sku(order_sku):
    order.is_subscription_order = True
```
This covers: `EM001`, `EM002`, `EMEXP001`, `EM004` — the test subscription membership SKUs. These orders set `is_subscription_order = True` on the Order itself regardless of whether they came from Recharge or a direct purchase.

---

### Stage 6: Downstream Processing by Order Type

After classification, order type determines which handler runs (lines 637–658):

| Order Type | Handler |
|---|---|
| `VAGINITIS_CARE`, `STI_CARE`, `UTI_CARE`, `A_LA_CARTE`, `DYNAMIC_BUNDLE`, `MIXED_CARE`, `MALE_PARTNER` | `process_shopify_order_for_care()` |
| `TEST`, `EXPANDED_TEST`, `URINE_TEST` | `process_shopify_order_for_test()` |
| `PCR_ADD_ON` | `process_shopify_order_for_pcr_add_on()` |
| anything else | `process_shopify_order_for_unknown_order_sku()` |

**Prescription treatment refill routing** runs as a second pass (lines 660–695):
- If order type is NOT in `[A_LA_CARTE, MIXED_CARE, DYNAMIC_BUNDLE, UNGATED_RX, MALE_PARTNER]` AND any line item has `PRESCRIPTION_TREATMENT` type → `process_shopify_order_for_treatment_refill()` also runs
- For `UNGATED_RX` orders with a known user: `can_refill_entire_order()` (line 2732) decides the path:
  - If all Rx products have valid, non-expired prescriptions with remaining refills → **refill path** (`process_shopify_order_for_treatment_refill()`)
  - Otherwise → **new consult path** (`add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()`)

---

### Summary of Order Type Determination Logic

```
Shopify webhook received (orders/create)
         │
         ▼
Extract line_items, note_attributes, app_id, source_name
         │
         ▼
For each line item:
  └─ _get_order_type_from_sku(sku)     ← SKU prefix/membership determines type
  └─ Check selling_plan_id in notes    ← new subscription on webflow
  └─ Check app_id == Recharge app      ← recurring refill order
         │
         ▼ is_recurring_subscription_order?
    YES: Skip purchase_type attribute check (prevents refill misclassification)
    NO:  Apply purchase_type from cart attributes (a_la_carte / dynamic_bundle / mixed)
         │
         ▼
_get_overall_order_type_and_sku_from_line_items()
  Priority: vaginitis_care > uti_care > sti_care > expanded_test > ...
  Override: ungated_rx SKU → UNGATED_RX, male partner SKU → MALE_PARTNER
         │
         ▼
Dispatch to handler:
  CARE types → process_shopify_order_for_care()    (attaches to consult)
  TEST types → process_shopify_order_for_test()    (creates test kit records)
  PCR_ADD_ON → process_shopify_order_for_pcr_add_on()
  +
  If any PRESCRIPTION_TREATMENT line item exists (not certain care types):
    → process_shopify_order_for_treatment_refill()  (fills prescription via pharmacy)
  If UNGATED_RX + user exists:
    → can_refill_entire_order()? YES → refill path
                                 NO  → new consult path
```

---

### Key Files for Order Type Logic

| File | Purpose |
|---|---|
| `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` | `Order` model with order type constants and `is_subscription_order`, `is_recurring_order_item` flags |
| `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` | All SKU constants and Shopify app ID constants used in classification |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | Core logic: `_get_order_type_from_sku()`, `_get_overall_order_type_and_sku_from_line_items()`, `process_order_line_item()`, `_process_shopify_order_impl()`, all type-specific handlers |
| `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` | Celery tasks: `send_prescription_refill_request()` dispatches to Precision pharmacy |
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` | Entry points: `shopify_webhook_view()` (Shopify), `recharge_webhook_view()` (ReCharge subscription events) |
