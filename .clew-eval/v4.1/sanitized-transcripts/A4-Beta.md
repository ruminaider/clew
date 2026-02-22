# A4 — Agent Beta

## How the Order Processing System Determines Order Type

The determination happens across two files primarily: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (the core logic) and `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (the type constants).

---

### Step 1: Per-Line-Item Classification by SKU

The entry point is `process_order_line_item()` (line 1322 of `utils.py`). For each Shopify line item, it immediately calls `_get_order_type_from_sku(sku)` (line 1036) which maps a SKU to one of the defined order types:

```python
def _get_order_type_from_sku(sku: str) -> str:
    if sku in get_all_care_skus():
        if sku == SHOPIFY_CARE_STI_TREAMENT_SKU:
            return Order.ORDER_TYPE_STI_CARE       # "SC"
        elif sku == SHOPIFY_CARE_UTI_TREAMENT_SKU:
            return Order.ORDER_TYPE_UTI_CARE        # "UC"
        else:
            return Order.ORDER_TYPE_VAGINITIS_CARE  # "CA"
    elif sku in get_all_test_skus():
        if sku in URINE_TEST_SKUS:
            return Order.ORDER_TYPE_URINE_TEST      # "UT"
        elif sku in EXPANDED_TEST_SKUS:
            return Order.ORDER_TYPE_EXPANDED_TEST   # "ET"
        else:
            return Order.ORDER_TYPE_TEST            # "TE"
    elif sku == EXPANDED_PCR_ADD_ON_SKU:
        return Order.ORDER_TYPE_PCR_ADD_ON          # "PA"
    elif sku in get_all_treatment_skus():
        return Order.ORDER_TYPE_PRESCRIPTION_TREATMENT  # "PR"
    else:
        return Order.ORDER_TYPE_OTHER               # "OT"
```

Additionally, if `line_item_payload.get("gift_card", False)` is True, the line item's order type is overridden to `ORDER_TYPE_GIFT_CARD` ("GC").

---

### Step 2: Detecting Subscription vs. One-Time Purchase (Per Line Item)

Also inside `process_order_line_item()`, three signals determine whether a line item is a recurring subscription:

1. **Cart-based subscription** (line 1460–1479): If a `_evvyCartId` custom property is present on the line item, the system looks up the `Cart` model and checks `cart_line_item.is_subscription` — set at time of cart creation on my.evvy.com.

2. **Webflow selling plan ID** (line 1483–1484): If `line_item_subscription_metadata.selling_plan_id` is populated (extracted from the order `note` field via `_extract_subscription_metadata_from_notes()`), the line item is marked `is_subscription = True`.

3. **Recharge app ID = recurring charge** (line 1487–1491): If the Shopify `app_id` matches `SHOPIFY_RECHARGE_APP_ID`, all line items in the order are marked `is_recurring_order_item = True`. This is the key signal for subscription refill orders — Recharge generates recurring charges through this app ID.

The caller in `_process_shopify_order_impl()` then aggregates:
```python
if line_item_has_subscription or line_item_is_recurring_order_item:
    order.is_subscription_order = True
if line_item_is_recurring_order_item:
    is_recurring_subscription_order = True
```

---

### Step 3: Rolling Up to the Overall Order Type

After all line items are processed, `_get_overall_order_type_and_sku_from_line_items()` (line 952) determines the order-level type using a priority cascade:

**Single line item:** order type = that item's type.

**Multiple line items** (priority order):
1. Vaginitis + UTI together → `VAGINITIS_CARE` (error condition, logged as warning)
2. Any vaginitis care → `VAGINITIS_CARE`
3. Any UTI care → `UTI_CARE`
4. Any STI care → `STI_CARE`
5. Expanded test OR (test + PCR add-on) → `EXPANDED_TEST`
6. Any urine test → `URINE_TEST`
7. Any standard test → `TEST`
8. Any PCR add-on → `PCR_ADD_ON`
9. Any prescription treatment → `PRESCRIPTION_TREATMENT`
10. Otherwise → `OTHER`

**Then two overrides** (lines 996–1031):

- **Ungated Rx override**: If any line item has `order_type == PRESCRIPTION_TREATMENT` AND its SKU is an ungated Rx SKU → order becomes `ORDER_TYPE_UNGATED_RX` ("UX"). Similarly, if it's a male partner treatment SKU → `ORDER_TYPE_MALE_PARTNER` ("MP").

- **Purchase type override from cart attributes** (only if NOT a recurring subscription order): The `note_attributes` field `purchase_type` can override the type to:
  - `a-la-carte` → `ORDER_TYPE_A_LA_CARTE` ("AL")
  - `dynamic-bundle` → `ORDER_TYPE_DYNAMIC_BUNDLE` ("BU")
  - `bundle-a-la-care` → `ORDER_TYPE_MIXED_CARE` ("MC")

The `is_recurring_subscription_order` flag explicitly blocks this override to prevent Recharge-copied attributes from polluting refill orders:
```python
# Skip purchase_type check for subscription refill orders
if not is_recurring_subscription_order:
    for attribute in custom_attributes:
        if attribute_name == "purchase_type":
            ...
```

---

### Step 4: Downstream Routing Based on Order Type

The order type drives a branching dispatch at line 637 of `_process_shopify_order_impl()`:

```python
if order.order_type in [VAGINITIS_CARE, STI_CARE, UTI_CARE, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, MALE_PARTNER]:
    order = process_shopify_order_for_care(order, payload, order_logger)
elif order.order_type in [TEST, EXPANDED_TEST, URINE_TEST]:
    process_shopify_order_for_test(order, payload, bulk_order_id, order_logger)
elif order.order_type == PCR_ADD_ON:
    process_shopify_order_for_pcr_add_on(order, payload, order_logger)
else:
    process_shopify_order_for_unknown_order_sku(order, payload, order_logger)
```

**After the primary dispatch**, additional supplementary steps run:

- **Treatment refill path** (line 661–672): If the order type is NOT a_la_carte, mixed_care, dynamic_bundle, ungated_rx, or male_partner, AND any line item is `PRESCRIPTION_TREATMENT`, then `process_shopify_order_for_treatment_refill()` also runs. This handles subscription refill orders that may be labeled with "Test" type but contain treatment line items.

- **Ungated Rx routing** (line 676–692): For `ORDER_TYPE_UNGATED_RX` orders with a known user, `can_refill_entire_order()` checks whether every Rx product in the order has a valid, non-expired, refillable prescription. If yes → routed to `process_shopify_order_for_treatment_refill()` (the refill path). If no → routed to `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()` (the new consult/intake path). This is the key fork between a "new prescription" vs "prescription refill" for ungated Rx.

---

### What Each Downstream Path Does

| Path | Key Actions |
|------|-------------|
| **Care** (`process_shopify_order_for_care`) | Looks up `consult_uid` from `note_attributes`, links order to consult, advances consult status to `ORDERED`, fires `send_consult_paid_event`, updates `purchase_type` on consult, reconciles selected treatments |
| **Test** (`process_shopify_order_for_test`) | Matches user by email, handles provider magic-link orders (links `ProviderTestOrder`), fires Braze events for provider/patient test purchase |
| **Treatment Refill** (`process_shopify_order_for_treatment_refill`) | Creates/finds `PrescriptionFill`, resolves prescriptions either from explicit `prescription_ids` in note attributes or from user's evergreen prescriptions, calls `send_prescription_refill_request.delay()` to send to fulfillment |
| **PCR Add-On** (`process_shopify_order_for_pcr_add_on`) | Specialized handling for PCR expansion tests |
| **Unknown SKU** | Minimal: just resolves user from email |

**All order types** additionally run these after the primary dispatch:
- Per-line-item Braze events (`VAGINAL_TEST_PURCHASE`, `UTI_PURCHASE`) at lines 696–727
- OTC treatment attachment (`attach_otc_treatments_to_existing_consult`)
- Gift card processing if applicable
- `send_any_paid_event` analytics event
- `send_order_to_berlin_for_fulfillment.delay()` — every order goes to Berlin regardless of type

---

### Summary of Decision Tree

```
Shopify webhook received
  ├── Parse line items → classify each by SKU (test/care/treatment/pcr/other)
  ├── Detect subscription signals:
  │     ├── Cart.is_subscription → is_subscription = True
  │     ├── selling_plan_id in notes → is_subscription = True
  │     └── app_id == RECHARGE → is_recurring_order_item = True (refill)
  ├── Roll up to order-level type (priority cascade of line item types)
  ├── Override with ungated-rx or male-partner SKU check
  ├── Override with purchase_type cart attribute (BLOCKED for Recharge refills)
  └── Dispatch:
        ├── Care types → process_shopify_order_for_care (consult linking, intake)
        ├── Test types → process_shopify_order_for_test (provider linking)
        ├── PCR Add-On → process_shopify_order_for_pcr_add_on
        ├── Unknown → process_shopify_order_for_unknown_order_sku
        ├── + Treatment refill (if any line item is PRESCRIPTION_TREATMENT and not a-la-care type)
        │       → create PrescriptionFill, send to pharmacy
        └── Ungated Rx:
              ├── can_refill_entire_order? → Yes → refill path
              └── No → new consult/intake path
```
