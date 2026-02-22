# How the Order Processing System Determines Order Type

## Overview

The order type determination is a multi-stage process that happens during Shopify webhook processing. The system classifies each incoming order using SKU-based rules, Shopify metadata (app ID, selling plan, order notes), and cart-level custom attributes to assign an `order_type`, set subscription flags, and route to the appropriate downstream processing function.

---

## Stage 1: Line-Item Order Type from SKU

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `_get_order_type_from_sku` (line 1036)

Each line item's order type is determined first by its SKU:

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

The SKU constants driving this are defined in `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`. Key SKU groups include:
- `ALL_TEST_SUBSCRIPTION_SKUS` (e.g., `EM002`, `EMEXP001`) — test membership/subscription SKUs
- `ALL_TREATMENT_REFILL_SKUS` — refill and replacement SKUs with prefixes `RFL` and `RPL` (e.g., `RFLBA001`, `RPLVP001`)
- `ALL_CARE_SKUS` — original consult-gated treatment SKUs (`TRMT001`–`TRMT006`)

---

## Stage 2: Order-Level Type Aggregated from Line Items

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `_get_overall_order_type_and_sku_from_line_items` (line 952)

After all line items are processed, the system rolls up to an overall `order_type`:

- Single-item orders: the order type equals the line item's type.
- Multi-item orders: a priority cascade applies:
  1. Vaginitis + UTI care together → `ORDER_TYPE_VAGINITIS_CARE` (with a warning — this is considered an error condition)
  2. Vaginitis care alone → `ORDER_TYPE_VAGINITIS_CARE`
  3. UTI care → `ORDER_TYPE_UTI_CARE`
  4. STI care → `ORDER_TYPE_STI_CARE`
  5. Expanded test (or test + PCR add-on) → `ORDER_TYPE_EXPANDED_TEST`
  6. Urine test → `ORDER_TYPE_URINE_TEST`
  7. Standard test → `ORDER_TYPE_TEST`
  8. PCR add-on → `ORDER_TYPE_PCR_ADD_ON`
  9. Prescription treatment → `ORDER_TYPE_PRESCRIPTION_TREATMENT`
  10. Fallback → `ORDER_TYPE_OTHER`

**Ungated Rx override** (lines 1001–1013): After this cascade, if any line item is an `ORDER_TYPE_PRESCRIPTION_TREATMENT` with a URX-prefixed SKU, the order type is overridden to `ORDER_TYPE_UNGATED_RX`. Similarly, male partner treatment SKUs override to `ORDER_TYPE_MALE_PARTNER`.

**Purchase type override from custom attributes** (lines 1020–1031): Unless this is a recurring subscription refill order, the `purchase_type` Shopify order attribute can further override the type:
- `a-la-carte` → `ORDER_TYPE_A_LA_CARTE`
- `dynamic-bundle` → `ORDER_TYPE_DYNAMIC_BUNDLE`
- `bundle-a-la-care` → `ORDER_TYPE_MIXED_CARE`

Recurring subscription refill orders deliberately skip this override (line 1020: `if not is_recurring_subscription_order`) to prevent purchase_type metadata copied from the original subscription order from mis-classifying refills.

---

## Stage 3: Subscription vs. One-Time Detection

### 3a. Test Subscription SKU (new subscription)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `_get_is_subscription_sku` (line 1068)

```python
def _get_is_subscription_sku(sku: str) -> bool:
    return sku in ALL_TEST_SUBSCRIPTION_SKUS
```

If the order's primary SKU is in `ALL_TEST_SUBSCRIPTION_SKUS` (the test membership SKUs like `EM002`), `order.is_subscription_order` is set to `True` (line 581–582). This marks the order as the initial setup of a new subscription.

### 3b. Selling Plan ID (new subscription, webflow site)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, function `_extract_subscription_metadata_from_notes` (line 793)

For orders placed on the webflow marketing site, the order `note` field may contain a JSON array of line items with `sellingPlanId` values. If a line item has a `selling_plan_id`, it means the customer signed up for a subscription during checkout:

```python
if line_item_subscription_metadata and line_item_subscription_metadata.selling_plan_id:
    line_item.is_subscription = True
```

### 3c. Cart Line Item Subscription Flag (new subscription, my.evvy.com)

For orders placed through the internal evvy app (my.evvy.com), the order carries a `_evvyCartId` attribute. The system looks up the corresponding `Cart` and `CartLineItem` to retrieve `cart_line_item.is_subscription`, copying it to the `OrderLineItem.is_subscription` field (line 1478).

### 3d. Recharge App ID (recurring refill)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 1487–1491); **constant:** `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` line 324

```python
SHOPIFY_RECHARGE_APP_ID = 294517
```

```python
if (
    line_item_subscription_metadata
    and line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID
):
    line_item.is_recurring_order_item = True
```

When the Shopify order's `app_id` equals `294517` (the Recharge subscription management app), every line item is flagged as `is_recurring_order_item = True`. This is the canonical signal that an order is a **subscription refill** (not the initial purchase). This also sets `is_recurring_subscription_order = True` at the order level, which triggers the special handling described in Stage 2.

---

## Stage 4: Downstream Processing Routing

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 637–692)

After order type and subscription flags are resolved, the system dispatches to type-specific handlers:

```python
if order.order_type in [
    Order.ORDER_TYPE_VAGINITIS_CARE,
    Order.ORDER_TYPE_STI_CARE,
    Order.ORDER_TYPE_UTI_CARE,
    Order.ORDER_TYPE_A_LA_CARTE,
    Order.ORDER_TYPE_DYNAMIC_BUNDLE,
    Order.ORDER_TYPE_MIXED_CARE,
    Order.ORDER_TYPE_MALE_PARTNER,
]:
    order = process_shopify_order_for_care(order, payload, order_logger)
elif order.order_type in [
    Order.ORDER_TYPE_TEST,
    Order.ORDER_TYPE_EXPANDED_TEST,
    Order.ORDER_TYPE_URINE_TEST,
]:
    process_shopify_order_for_test(order, payload, bulk_order_id, order_logger)
elif order.order_type == Order.ORDER_TYPE_PCR_ADD_ON:
    process_shopify_order_for_pcr_add_on(order, payload, order_logger)
else:
    process_shopify_order_for_unknown_order_sku(order, payload, order_logger)
```

After this block, a **secondary check** fires for treatment refills (lines 661–672):
```python
if (
    order.order_type not in [
        Order.ORDER_TYPE_A_LA_CARTE, Order.ORDER_TYPE_MIXED_CARE,
        Order.ORDER_TYPE_DYNAMIC_BUNDLE, Order.ORDER_TYPE_UNGATED_RX,
        Order.ORDER_TYPE_MALE_PARTNER,
    ]
    and Order.ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
):
    process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

This handles the case where a test-type order also contains treatment refill line items (a combo order).

For `ORDER_TYPE_UNGATED_RX` specifically (lines 676–691), the system calls `can_refill_entire_order()` to branch between:
- **Refill path** (`process_shopify_order_for_treatment_refill`) — if all Rx products already have valid prescriptions.
- **New consult/intake path** (`add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`) — if any Rx product lacks a valid prescription, triggering a new consult.

---

## What Happens in Each Downstream Function

### Care Orders (`process_shopify_order_for_care`, line 1807)
- Extracts `consult_uid` and `purchase_type` from order note attributes.
- Links the order to an existing `Consult` object; updates consult status to `STATUS_ORDERED`.
- Fires the `send_consult_paid_event` analytics event.
- Calls `add_ordered_products_to_consult` to finalize selected treatments.

### Test Orders (`process_shopify_order_for_test`, line 1600)
- Links the order to a `Test` record via test kit hash or email.
- For urine tests: creates `UrineTest` records and queues creation of unregistered testkit orders in the Junction lab system.
- Provider-ordered tests trigger `send_patient_ordered_provider_test_notification`.

### Treatment Refill Orders (`process_shopify_order_for_treatment_refill`, line 2089)
- Parses note attributes for a `prescription_fill_id`, `consult_uid`, and `prescription_ids`.
- Creates or retrieves a `PrescriptionFill` object linking order to prescriptions.
- For subscription refills (from Recharge), the user and prescription are identified from the order email or consult.
- Validates that all prescriptions have remaining refills (`get_all_prescriptions_have_remaining_refills`).
- Queues `send_prescription_refill_request` Celery task, which:
  - Checks prescription refill counts and state/jurisdictional validity.
  - Sends patient, prescription, and fill requests to the Precision pharmacy fulfillment API.

---

## Summary of Key Signals

| Signal | Location | Indicates |
|---|---|---|
| SKU in `ALL_TEST_SUBSCRIPTION_SKUS` | `_get_is_subscription_sku` | New test subscription |
| `selling_plan_id` in order notes | `_extract_subscription_metadata_from_notes` | New subscription (webflow) |
| `cart_line_item.is_subscription = True` | Cart lookup in `process_order_line_item` | New subscription (my.evvy.com) |
| `app_id == 294517` (Recharge) | `process_order_line_item` line 1487 | **Recurring refill** |
| `checkout_source == "subscription"` | `_determine_checkout_source` | Subscription-originated order |
| SKU prefix `RFL` / `RPL` | `ALL_TREATMENT_REFILL_SKUS` in constants | Refill/replacement treatment |
| `purchase_type` attribute | `_get_overall_order_type_and_sku_from_line_items` | A la carte vs. bundle distinction |
| `can_refill_entire_order()` result | Ungated Rx routing block | New prescription vs. evergreen refill |
