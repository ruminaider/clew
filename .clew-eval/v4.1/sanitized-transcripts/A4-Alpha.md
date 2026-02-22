# A4 — Agent Alpha

## How the Order Processing System Determines Order Type and Routes Downstream Processing

### Overview

All Shopify orders flow through a single entry point in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` via `process_shopify_order()` → `_process_shopify_order_impl()`. The system determines order type through a multi-step classification pipeline: per-line-item SKU classification, then order-level aggregation using both line item types and custom attributes from the order payload.

---

### Step 1: Per-Line-Item SKU Classification

`process_order_line_item()` (line 1322) calls `_get_order_type_from_sku(sku)` (line 1036) for each line item. This function checks the SKU against several hardcoded SKU lists defined in `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`:

```python
def _get_order_type_from_sku(sku: str) -> str:
    if sku in get_all_care_skus():          # TRMT001-TRMT006
        if sku == SHOPIFY_CARE_STI_TREAMENT_SKU:
            return Order.ORDER_TYPE_STI_CARE       # "SC"
        elif sku == SHOPIFY_CARE_UTI_TREAMENT_SKU:
            return Order.ORDER_TYPE_UTI_CARE       # "UC"
        else:
            return Order.ORDER_TYPE_VAGINITIS_CARE  # "CA"
    elif sku in get_all_test_skus():        # VMT001, VMTEXPxxx, UTIxxx, EMxxx, etc.
        if sku in URINE_TEST_SKUS:
            return Order.ORDER_TYPE_URINE_TEST     # "UT"
        elif sku in EXPANDED_TEST_SKUS:
            return Order.ORDER_TYPE_EXPANDED_TEST  # "ET"
        else:
            return Order.ORDER_TYPE_TEST            # "TE"
    elif sku == EXPANDED_PCR_ADD_ON_SKU:    # VPCR001
        return Order.ORDER_TYPE_PCR_ADD_ON         # "PA"
    elif sku in get_all_treatment_skus():   # RFLxx/RPLxx SKUs
        return Order.ORDER_TYPE_PRESCRIPTION_TREATMENT  # "PR"
    else:
        return Order.ORDER_TYPE_OTHER              # "OT"
```

The SKU namespaces from `constants.py` encode the distinction:
- `TRMT001-TRMT006` = initial care (consult-gated, new prescription needed)
- `RFLxx001` / `RFLxx002` = prescription refills (e.g., `RFLBA001` = boric acid 7-day refill)
- `RPLxx001` = prescription replacements (physically damaged kits)
- `URXxx` prefix = ungated Rx (prescription without initial consult gate)
- `MPTxx` = male partner treatments
- `EMxxx`, `VMTxxx`, `VMTEXPxxx` = test kits (subscription vs. one-time)

---

### Step 2: Per-Line-Item Subscription vs. Recurring Detection

Still within `process_order_line_item()` (lines 1461–1493), three mechanisms determine whether a line item is a new subscription vs. a recurring charge:

1. **Cart-based flag** (line 1463–1480): If the order has an `_evvyCartId`, the cart's `CartLineItem.is_subscription` is copied to the `OrderLineItem.is_subscription` field. This covers new subscriptions placed via `my.evvy.com`.

2. **Selling plan ID in order notes** (lines 1482–1484): For webflow-site subscription orders, selling plan IDs are embedded in the order notes (JSON). If a selling plan ID is present for the line item's variant, `OrderLineItem.is_subscription = True`.

3. **Recharge app ID = recurring** (lines 1486–1492): If `payload["app_id"] == SHOPIFY_RECHARGE_APP_ID` (294517), then `OrderLineItem.is_recurring_order_item = True`. This is the definitive signal that this is a subscription **refill** (an auto-charged renewal), not a new subscription.

```python
if line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID:
    line_item.is_recurring_order_item = True
```

Back in `_process_shopify_order_impl()` (lines 469–494):

```python
is_recurring_subscription_order = False
for line_item_payload in line_items:
    ...
    line_item, line_item_has_subscription, line_item_is_recurring_order_item = process_order_line_item(...)
    if line_item_has_subscription or line_item_is_recurring_order_item:
        order.is_subscription_order = True
    if line_item_is_recurring_order_item:
        is_recurring_subscription_order = True
```

The boolean `is_recurring_subscription_order` is the system's internal flag for "this is a Recharge refill".

---

### Step 3: Order-Level Type Determination

`_get_overall_order_type_and_sku_from_line_items()` (line 952) rolls up line item types to a single order type using priority rules:

- Single-line-item orders: inherit the line item's order type directly.
- Multi-line-item priority (descending): vaginitis care > UTI care > STI care > expanded test > urine test > test > PCR add-on > prescription treatment > other.
- **Ungated Rx override** (lines 1001–1006): If any treatment line item has a URX-prefixed SKU, the whole order becomes `ORDER_TYPE_UNGATED_RX`.
- **Male Partner override**: If any treatment line item has an MPT-prefixed SKU, the order becomes `ORDER_TYPE_MALE_PARTNER`.
- **`purchase_type` custom attribute override** (lines 1020–1031): The Shopify `note_attributes` field carries a `purchase_type` attribute set by the frontend at checkout:
  - `a-la-carte` → `ORDER_TYPE_A_LA_CARTE` ("AL")
  - `dynamic-bundle` → `ORDER_TYPE_DYNAMIC_BUNDLE` ("BU")
  - `bundle-a-la-care` → `ORDER_TYPE_MIXED_CARE` ("MC")

  Critically, this override is **skipped for recurring subscription refills** (`is_recurring_subscription_order=True`) to prevent old purchase_type metadata from misclassifying refill orders.

Additionally, `Order.is_subscription_order` is set to `True` if the primary SKU is in `ALL_TEST_SUBSCRIPTION_SKUS` (EM001, EM002, EMEXP001, EM004 — membership/subscription test SKUs):

```python
if order_sku and _get_is_subscription_sku(order_sku):
    order.is_subscription_order = True
```

---

### Step 4: Checkout Source Determination

`_determine_checkout_source()` (line 810) maps `app_id` + `cart_id` + `source_name` to one of the `CHECKOUT_SOURCE_*` constants. The most important signal:

- `app_id == SHOPIFY_RECHARGE_APP_ID` → `CHECKOUT_SOURCE_SUBSCRIPTION` (overrides everything else, first priority)
- This means recurring subscription refills always get `checkout_source = "subscription"`, independent of any custom attribute that may have been copied from the original order.

---

### Step 5: Downstream Processing Routing (the "if/elif" dispatcher)

Lines 637–691 of `_process_shopify_order_impl()` route to type-specific handlers:

| Order Type | Handler | What it does |
|---|---|---|
| `VAGINITIS_CARE`, `STI_CARE`, `UTI_CARE`, `A_LA_CARTE`, `DYNAMIC_BUNDLE`, `MIXED_CARE`, `MALE_PARTNER` | `process_shopify_order_for_care()` | Links order to a `Consult`, updates consult status, fires `send_consult_paid_event`, validates selected treatments against ordered products |
| `TEST`, `EXPANDED_TEST`, `URINE_TEST` | `process_shopify_order_for_test()` | Links to user or provider test order, handles provider magic-link orders, creates `UrineTest` records and Junction lab orders |
| `PCR_ADD_ON` | `process_shopify_order_for_pcr_add_on()` | Looks up test kit by hash, calls `add_expanded_vpcr_panel_to_test_kit()` |
| `OTHER`, `GIFT_CARD`, etc. | `process_shopify_order_for_unknown_order_sku()` | Logs warning only |

**Prescription refill / treatment path** (lines 660–672): Any order whose line items include `ORDER_TYPE_PRESCRIPTION_TREATMENT` SKUs (but is not an a-la-carte, mixed care, dynamic bundle, ungated RX, or male partner order) also runs `process_shopify_order_for_treatment_refill()`. This is how subscription refill orders (which come in as `ORDER_TYPE_PRESCRIPTION_TREATMENT` from the Recharge app) get processed:

```python
if (
    order.order_type not in [A_LA_CARTE, MIXED_CARE, DYNAMIC_BUNDLE, UNGATED_RX, MALE_PARTNER]
    and ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
):
    process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

**Ungated Rx split** (lines 676–692): If the order is `ORDER_TYPE_UNGATED_RX`, `can_refill_entire_order()` checks if the user has a valid, non-expired, refills-remaining prescription for every Rx product in the order:
- **All Rx have valid prescriptions** → routes to `process_shopify_order_for_treatment_refill()` (refill path)
- **Missing or expired prescriptions** → routes to `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()` (new consult / intake path)

---

### `process_shopify_order_for_treatment_refill()` — New vs. Refill Within the Refill Path

This function (line 2089) handles both first-time prescription fills and recurring refills:

1. Checks order `note_attributes` for a `prescription_fill_id` (for orders initiated from the frontend that already have a fill record) or a `replacement-` prefix in the order note (for replacement orders). If neither exists, it `get_or_create`s a `PrescriptionFill` for the order.
2. Looks up prescriptions either by explicit `prescription_ids` in the order attributes or by querying the user's active prescriptions matching the ordered products.
3. Calls `create_prescription_fill_prescriptions()` and `create_prescription_fill_otc_treatments()` to assemble the fill record.
4. Fires `send_prescription_refill_request.delay(order.id, prescription_fill.id)` to dispatch fulfillment to Precision pharmacy.

The function doesn't explicitly label orders as "new fill" vs. "refill" — both go through the same `PrescriptionFill` creation/lookup logic. The distinction is captured implicitly by whether a `PrescriptionFill` already existed for the user and product.

---

### Summary of the Full Classification Decision Tree

```
Shopify webhook arrives
    │
    ├─ Cancellation? → cancel order, void ShareASale commission, sever test associations
    │
    ├─ Per line item:
    │     SKU → _get_order_type_from_sku() [TRMT=care, RFL/RPL=treatment, VMT/EM=test, URX=ungated_rx, MPT=male_partner]
    │     app_id == 294517 (Recharge)? → is_recurring_order_item=True → is_recurring_subscription_order=True
    │     cart.is_subscription? → is_subscription=True (new subscription)
    │     selling_plan_id in notes? → is_subscription=True (webflow subscription)
    │
    ├─ Aggregate line item types → order_type (priority: care > test > treatment > other)
    ├─ URX SKU in any treatment line? → order_type = UNGATED_RX
    ├─ MPT SKU in any treatment line? → order_type = MALE_PARTNER
    ├─ purchase_type attr (if NOT is_recurring) → override to A_LA_CARTE / DYNAMIC_BUNDLE / MIXED_CARE
    │
    └─ Route by order_type:
          CARE types → process_shopify_order_for_care() [consult linking, status update]
          TEST types → process_shopify_order_for_test() [user/provider linking, urine test creation]
          PCR_ADD_ON → process_shopify_order_for_pcr_add_on() [attach to test kit]
          +PRESCRIPTION_TREATMENT in line items → process_shopify_order_for_treatment_refill() [PrescriptionFill, pharmacy dispatch]
          UNGATED_RX + has valid Rx → refill path
          UNGATED_RX + no valid Rx → new consult/intake path
```

### Key Files

- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` — central processing logic (`_process_shopify_order_impl`, `process_order_line_item`, `_get_overall_order_type_and_sku_from_line_items`, `_get_order_type_from_sku`, `process_shopify_order_for_care`, `process_shopify_order_for_treatment_refill`, `can_refill_entire_order`)
- `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` — `Order.ORDER_TYPE_*` and `OrderLineItem.is_subscription` / `is_recurring_order_item` field definitions
- `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` — SKU lists (`ALL_CARE_SKUS`, `ALL_TREATMENT_REFILL_SKUS`, `ALL_TEST_SUBSCRIPTION_SKUS`, `SHOPIFY_RECHARGE_APP_ID`, etc.)
- `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py` — entry point for Shopify webhook processing
