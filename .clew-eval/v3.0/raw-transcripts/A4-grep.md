# A4 Grep Transcript: Order Type Determination System

## Task
Explain how the order processing system decides what type of order it is (e.g., new subscription vs. refill vs. one-time purchase) and how that determination affects downstream processing.

## Investigation Process

### Tool Call 1-3: Initial Discovery
Searched for order processing patterns and found:
- 362 files matching "order.type|order_type|subscription|refill|one.time"
- 102 files matching "process.*order|order.*process"
- Key files identified: `/backend/ecomm/utils.py`, `/backend/ecomm/shopify/tasks.py`

### Tool Call 4-5: Core Processing Functions
Read `shopify/tasks.py` and `models/shopify.py` - found that:
- `process_shopify_order_from_api()` is the entry point
- Calls `process_shopify_order()` in `ecomm/utils.py`

### Tool Call 6-11: Deep Dive into Order Type Logic
Read `ecomm/utils.py` (large file, ~2000 lines):
- Main wrapper: `process_shopify_order()` (line 204)
- Implementation: `_process_shopify_order_impl()` (line 238)
- Order type determination: `_get_overall_order_type_and_sku_from_line_items()` (line 952)
- Line item processing: `process_order_line_item()` (line 1322)

### Tool Call 12: Order Model Constants
Found order type constants in `/backend/ecomm/models/order.py`:
- 15 different order types (TEST, CARE variants, PRESCRIPTION_TREATMENT, etc.)
- Subscription flags at both order and line item level

### Tool Call 13: Subscription Detection Logic
Examined how subscriptions are identified:
- `selling_plan_id` presence indicates subscription
- `SHOPIFY_RECHARGE_APP_ID` indicates recurring refill order
- Line items marked with `is_subscription` and `is_recurring_order_item` flags

## Answer

### Order Type Determination Flow

The order processing system determines order types through a **multi-level classification hierarchy** that analyzes line items, SKUs, custom attributes, and subscription metadata.

#### Level 1: Line Item Classification (Bottom-Up)

Each line item is classified individually based on its SKU:

```python
# From _get_order_type_from_sku() in utils.py
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
```

**15 Order Types:**
- **Care Types:** VAGINITIS_CARE, STI_CARE, UTI_CARE, PRESCRIPTION_TREATMENT, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, UNGATED_RX, MALE_PARTNER
- **Test Types:** TEST, EXPANDED_TEST, URINE_TEST, PCR_ADD_ON
- **Other:** OTHER, GIFT_CARD

#### Level 2: Overall Order Classification (Aggregation)

The overall order type is determined from line items in `_get_overall_order_type_and_sku_from_line_items()`:

**Single Line Item:** Order type = line item type

**Multiple Line Items:** Priority-based rollup:
1. Mixed care detection (Vaginitis + UTI = error, defaults to Vaginitis)
2. Specific care types (Vaginitis, UTI, STI)
3. Test combinations (Expanded Test if TEST + PCR_ADD_ON)
4. Test hierarchy (URINE_TEST > TEST > PCR_ADD_ON)
5. PRESCRIPTION_TREATMENT (fallback for Rx items)
6. OTHER (catch-all)

**Example Priority Logic:**
```python
if has_vaginitis_care and has_uti_care:
    order_type = Order.ORDER_TYPE_VAGINITIS_CARE  # Error case, logged
elif has_vaginitis_care:
    order_type = Order.ORDER_TYPE_VAGINITIS_CARE
elif Order.ORDER_TYPE_EXPANDED_TEST in line_item_order_types or (
    Order.ORDER_TYPE_TEST in line_item_order_types
    and Order.ORDER_TYPE_PCR_ADD_ON in line_item_order_types
):
    order_type = Order.ORDER_TYPE_EXPANDED_TEST
```

#### Level 3: Special Overrides

**Ungated Rx Detection:**
```python
for line_item in created_line_items:
    if line_item.order_type == Order.ORDER_TYPE_PRESCRIPTION_TREATMENT and _is_ungated_rx_sku(line_item.sku):
        order_type = Order.ORDER_TYPE_UNGATED_RX
        break
```

**Purchase Type Custom Attributes** (NOT for subscription refills):
```python
if not is_recurring_subscription_order:
    for attribute in custom_attributes:
        if attribute_name == "purchase_type":
            if attribute_value == Consult.PURCHASE_TYPE_A_LA_CARTE:
                order_type = Order.ORDER_TYPE_A_LA_CARTE
            elif attribute_value == Consult.PURCHASE_TYPE_DYNAMIC_BUNDLE:
                order_type = Order.ORDER_TYPE_DYNAMIC_BUNDLE
            elif attribute_value == Consult.PURCHASE_TYPE_BUNDLE_A_LA_CARE:
                order_type = Order.ORDER_TYPE_MIXED_CARE
```

### Subscription vs. One-Time vs. Refill Detection

#### New Subscription (First Order)
**Indicators:**
- Line item has `selling_plan_id` in metadata
- `is_subscription = True` on line item
- `is_recurring_order_item = False`

**Detection Logic:**
```python
if line_item_subscription_metadata and line_item_subscription_metadata.selling_plan_id:
    line_item.is_subscription = True
```

#### Refill (Recurring Subscription Order)
**Indicators:**
- Order comes from Recharge app (`app_id == SHOPIFY_RECHARGE_APP_ID`)
- `is_recurring_order_item = True` on line item
- `is_recurring_subscription_order = True` at order level

**Detection Logic:**
```python
if (line_item_subscription_metadata
    and line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID):
    line_item.is_recurring_order_item = True
```

**Critical Behavior:** Refill orders SKIP custom attribute overrides to prevent incorrect metadata from being copied from original orders.

#### One-Time Purchase
**Indicators:**
- No `selling_plan_id`
- `is_subscription = False`
- `is_recurring_order_item = False`

### Downstream Processing Impact

#### 1. Order-Type-Specific Processing (Lines 637-673)

**Care Orders** → `process_shopify_order_for_care()`:
- Types: VAGINITIS_CARE, STI_CARE, UTI_CARE, A_LA_CARTE, DYNAMIC_BUNDLE, MIXED_CARE, MALE_PARTNER
- Actions:
  - Link to Consult via `consult_uid`
  - Check for UTI treatment orders
  - Handle vaginitis upsell orders
  - Create prescription fills
  - Generate intake forms

**Test Orders** → `process_shopify_order_for_test()`:
- Types: TEST, EXPANDED_TEST, URINE_TEST
- Actions:
  - Match user by email
  - Process provider-initiated orders
  - Handle bulk orders
  - Link to ProviderTestOrder

**PCR Add-On** → `process_shopify_order_for_pcr_add_on()`:
- Extract test kit hash
- Link to existing test
- Add expanded PCR panel

**Unknown** → `process_shopify_order_for_unknown_order_sku()`:
- Match user by email only

#### 2. Prescription Refill Processing (Lines 660-692)

Orders are routed to `process_shopify_order_for_treatment_refill()` if:
1. Line items contain `ORDER_TYPE_PRESCRIPTION_TREATMENT` AND
2. Order type is NOT already a care type (prevents double processing)

**OR**

3. Order type is `UNGATED_RX` AND user can refill entire order

**Refill Processing Logic:**
```python
if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        # Route to refill path
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        # Route to consult/intake path
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(
            order.user.id, order.order_number
        )
```

#### 3. Event Tracking (Lines 694-727)

**Line-item-level events** fire regardless of overall order type:
- `UTI_PURCHASE` event if `ORDER_TYPE_URINE_TEST` in line items
- `VAGINAL_TEST_PURCHASE` event if TEST/EXPANDED_TEST in line items
- Includes `isSubscription` flag in properties

#### 4. Fulfillment Routing (Line 763)

All non-cancelled orders → `send_order_to_berlin_for_fulfillment.delay()`

#### 5. Checkout Source Determination (Lines 592-613)

Different source detection for:
- Logged-in cart (has cart_id or Evvy app_id)
- Marketing site (web source or Shop Pay)
- Subscription (Recharge app)
- Provider portal, Viome webhook, etc. (custom attributes)

**Refill Override Prevention:**
```python
if checkout_source and not is_recurring_subscription_order:
    determined_checkout_source = checkout_source
elif checkout_source and is_recurring_subscription_order:
    logger.info(f"Order {order_number} is a subscription refill order, ignoring checkout_source custom attribute")
```

### Key Design Patterns

1. **SKU-First Classification:** Product SKU determines base order type
2. **Line Item Aggregation:** Multi-item orders use priority-based rollup
3. **Custom Attribute Refinement:** Purchase type attributes provide fine-grained classification (A La Carte vs. Bundle)
4. **Subscription Separation:** Refill orders bypass custom attribute overrides to prevent data pollution
5. **Defensive Logging:** Mixed care types trigger warnings for error detection
6. **Line-Item Granularity:** Events track at line-item level to handle combo orders (care + test)

### Critical Edge Cases

1. **Vaginitis + UTI combo:** Logs error, defaults to Vaginitis
2. **Ungated Rx routing:** Checks prescription validity to decide refill vs. consult path
3. **Refill metadata isolation:** `is_recurring_subscription_order` flag prevents inherited custom attributes
4. **TEST + PCR_ADD_ON:** Automatically becomes EXPANDED_TEST
5. **Combo orders:** Overall type may be CARE, but test purchase events still fire from line items

## Files Referenced

1. `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py` - Entry points
2. `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` - Core processing logic
3. `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` - Order type constants
4. `/Users/albertgwo/Work/evvy/backend/ecomm/models/shopify.py` - Shopify data models
