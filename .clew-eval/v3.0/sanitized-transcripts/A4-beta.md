# A4 Beta Transcript: Order Type Determination and Downstream Processing

## Search Strategy

**Tool calls used: 10 (well under the 20 budget)**

1. Initial semantic search for "order type determination subscription refill one-time purchase"
2. Read key functions in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:
   - `_get_overall_order_type_and_sku_from_line_items` (lines 952-1033)
   - `_get_order_type_from_sku` (lines 1036-1056)
   - `_process_shopify_order_impl` (lines 238-790)
   - `process_order_line_item` (lines 1322-1597)
   - Order type routing logic (lines 635-755)
3. Read Order model constants in `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (lines 11-181)
4. Search for specific processing handlers (care, test, subscription)
5. Read downstream processing functions:
   - `process_shopify_order_for_care` (lines 1807+)
   - `process_shopify_order_for_test` (lines 1600+)

## Complete Answer

### Order Type Determination System

The Evvy order processing system determines order types through a **two-stage hierarchical process**: first at the **line-item level** based on SKU, then at the **overall order level** by aggregating and potentially overriding based on custom attributes.

---

## Stage 1: Line-Item Level Classification

When an order arrives from Shopify (via `_process_shopify_order_impl`), each line item is processed individually through `process_order_line_item()`.

### SKU-Based Initial Classification

Each line item's `order_type` is determined by calling `_get_order_type_from_sku(sku)` which uses predefined SKU lists:

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

**Key line item types:**
- **Care orders**: `VAGINITIS_CARE`, `STI_CARE`, `UTI_CARE` (deprecated v0-bundle program)
- **Test orders**: `TEST` (standard vNGS), `EXPANDED_TEST`, `URINE_TEST`, `PCR_ADD_ON`
- **Treatment orders**: `PRESCRIPTION_TREATMENT`
- **Other**: `OTHER`, `GIFT_CARD`

### Line-Item Metadata Extraction

During line item processing, custom properties from Shopify are extracted:

```python
for custom_property in custom_properties:
    if custom_property["name"] == SHOPIFY_LINE_PURCHASE_TYPE:
        purchase_type = custom_property["value"]  # "bundle" or "individual"
    if custom_property["name"] == SHOPIFY_LINE_EVVY_TREATMENT_SLUG:
        evvy_treatment_slug = custom_property["value"]
    if custom_property["name"] == SHOPIFY_EVVY_CONSULT_ID:
        consult_uid = custom_property["value"]
```

This metadata is stored in `line_item.metadata` for later use.

### Subscription Detection (Line-Item Level)

Line items are flagged as subscription-related through two mechanisms:

1. **Selling Plan ID** (from order notes): Sets `line_item.is_subscription = True`
2. **Recharge App ID** (app_id == SHOPIFY_RECHARGE_APP_ID): Sets `line_item.is_recurring_order_item = True`

```python
if line_item_subscription_metadata and line_item_subscription_metadata.selling_plan_id:
    line_item.is_subscription = True

if line_item_subscription_metadata and line_item_subscription_metadata.app_id == SHOPIFY_RECHARGE_APP_ID:
    line_item.is_recurring_order_item = True
```

The distinction is critical:
- `is_subscription`: New subscription order (first purchase)
- `is_recurring_order_item`: **Refill/recurring charge** from existing subscription

---

## Stage 2: Overall Order Classification

After all line items are processed, `_get_overall_order_type_and_sku_from_line_items()` determines the overall order type.

### Single vs. Multi-Line Item Logic

**Single line item**: Order type inherits directly from the line item.

**Multiple line items**: A priority cascade determines the overall type:

```python
# Priority hierarchy (highest to lowest):
if has_vaginitis_care and has_uti_care:
    order_type = Order.ORDER_TYPE_VAGINITIS_CARE  # Error condition
elif has_vaginitis_care:
    order_type = Order.ORDER_TYPE_VAGINITIS_CARE
elif has_uti_care:
    order_type = Order.ORDER_TYPE_UTI_CARE
elif ORDER_TYPE_STI_CARE in line_item_order_types:
    order_type = Order.ORDER_TYPE_STI_CARE
elif ORDER_TYPE_EXPANDED_TEST in line_item_order_types or (
    ORDER_TYPE_TEST and ORDER_TYPE_PCR_ADD_ON both present):
    order_type = Order.ORDER_TYPE_EXPANDED_TEST
elif ORDER_TYPE_URINE_TEST in line_item_order_types:
    order_type = Order.ORDER_TYPE_URINE_TEST
elif ORDER_TYPE_TEST in line_item_order_types:
    order_type = Order.ORDER_TYPE_TEST
elif ORDER_TYPE_PCR_ADD_ON in line_item_order_types:
    order_type = Order.ORDER_TYPE_PCR_ADD_ON
elif ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types:
    order_type = Order.ORDER_TYPE_PRESCRIPTION_TREATMENT
else:
    order_type = Order.ORDER_TYPE_OTHER
```

### Special Care Type Overrides

After the initial cascade, two additional checks can **override** the order type:

#### 1. Ungated RX Detection

```python
for line_item in created_line_items:
    if line_item.order_type == ORDER_TYPE_PRESCRIPTION_TREATMENT and _is_ungated_rx_sku(line_item.sku):
        order_type = Order.ORDER_TYPE_UNGATED_RX
        break
```

#### 2. Male Partner Treatment

```python
if line_item.order_type == ORDER_TYPE_PRESCRIPTION_TREATMENT and _is_male_partner_treatment_sku(line_item.sku):
    order_type = Order.ORDER_TYPE_MALE_PARTNER
    break
```

### Custom Attributes Override (Purchase Type)

**Critical**: This step is **SKIPPED for recurring subscription orders** to prevent incorrect classification:

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

**Why skip for refills?** Subscription refill orders may have inherited custom attributes from the original order (e.g., "dynamic-bundle"), which would incorrectly override the type. Refill orders should be classified as `PRESCRIPTION_TREATMENT` based on their actual line items.

### Final Order Types

The system supports 16 distinct order types:

**Care Orders:**
- `VAGINITIS_CARE` (deprecated)
- `STI_CARE` (deprecated)
- `UTI_CARE` (deprecated)
- `PRESCRIPTION_TREATMENT` (standard Rx treatment)
- `A_LA_CARTE` (transparent care: individual Rx products)
- `DYNAMIC_BUNDLE` (transparent care: bundle of Rx products)
- `MIXED_CARE` (transparent care: bundle + individual mix)
- `UNGATED_RX` (Rx without consult requirement)
- `MALE_PARTNER` (partner treatment)

**Test Orders:**
- `TEST` (standard vaginal test)
- `EXPANDED_TEST` (expanded panel)
- `URINE_TEST` (UTI test)
- `PCR_ADD_ON`

**Other:**
- `OTHER` (swag, etc.)
- `GIFT_CARD`

---

## Downstream Processing Based on Order Type

Once the order type is determined, `_process_shopify_order_impl` routes orders to specialized handlers:

### 1. Care Order Processing

```python
if order.order_type in [
    ORDER_TYPE_VAGINITIS_CARE,
    ORDER_TYPE_STI_CARE,
    ORDER_TYPE_UTI_CARE,
    ORDER_TYPE_A_LA_CARTE,
    ORDER_TYPE_DYNAMIC_BUNDLE,
    ORDER_TYPE_MIXED_CARE,
    ORDER_TYPE_MALE_PARTNER,
]:
    order = process_shopify_order_for_care(order, payload, order_logger)
```

**Care processing (`process_shopify_order_for_care`):**
- Links order to existing `Consult` (if `consult_uid` present in custom attributes)
- Updates consult status from `OPTED_IN` → `ORDERED`
- Sends `send_consult_paid_event` (triggers care workflow)
- Finalizes selected treatments on the consult
- Adds ordered products to consult
- Handles purchase type merging logic (bundle + a la carte)
- Creates `ConsultOrder` association

**Key distinction**: Care orders are **consult-driven** and trigger clinical workflow automation.

### 2. Test Order Processing

```python
elif order.order_type in [
    ORDER_TYPE_TEST,
    ORDER_TYPE_EXPANDED_TEST,
    ORDER_TYPE_URINE_TEST,
]:
    process_shopify_order_for_test(order, payload, bulk_order_id, order_logger)
```

**Test processing (`process_shopify_order_for_test`):**
- Links order to user based on email
- Processes **provider-initiated orders** (via provider portal/magic link)
  - Links to `ProviderTestOrder` records
  - Sets `checkout_source` to `PROVIDER` or `PROVIDER_MAGIC_LINK`
- Handles **bulk orders** (quantity >= 3)
- For **URINE_TEST**: Creates `UrineTest` records and triggers Junction integration

**Key distinction**: Test orders are **fulfillment-focused** and may route through provider workflows.

### 3. PCR Add-On Processing

```python
elif order.order_type == ORDER_TYPE_PCR_ADD_ON:
    process_shopify_order_for_pcr_add_on(order, payload, order_logger)
```

Separate handler for PCR add-ons (typically associated with existing tests).

### 4. Treatment Refill Processing

**Critical routing logic**: Even if the order type is `TEST`, if prescription treatments are present in line items, the order is **also** routed to refill processing:

```python
if (
    order.order_type not in [
        ORDER_TYPE_A_LA_CARTE,
        ORDER_TYPE_MIXED_CARE,
        ORDER_TYPE_DYNAMIC_BUNDLE,
        ORDER_TYPE_UNGATED_RX,
        ORDER_TYPE_MALE_PARTNER,
    ]
    and ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
):
    process_shopify_order_for_treatment_refill(order, payload, order_logger)
```

This handles **combo orders** (test + treatment refill) correctly.

### 5. Ungated RX Conditional Routing

Ungated RX orders have **dynamic routing** based on prescription availability:

```python
if order.order_type == ORDER_TYPE_UNGATED_RX and order.user:
    if can_refill_entire_order(order.user, order):
        # User has valid prescriptions → route to refill path
        process_shopify_order_for_treatment_refill(order, payload, order_logger)
    else:
        # No valid prescriptions → route to consult/intake path
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(
            order.user.id, order.order_number
        )
    send_ungated_rx_order_paid_event.delay(order.order_number)
```

**This is a key business rule**: Ungated RX can be either a refill OR a new consult depending on the user's prescription history.

### 6. Subscription-Specific Behavior

Orders flagged as `is_recurring_order_item = True` receive special treatment:

1. **Order type determination** skips `purchase_type` custom attribute override
2. **Checkout source determination** skips custom attribute override
3. Likely routed to `process_shopify_order_for_treatment_refill` (based on line items containing `PRESCRIPTION_TREATMENT`)

**Refill processing creates:**
- `PrescriptionFill` records
- `PrescriptionFillOrder` associations
- Triggers fulfillment via `send_prescription_refill_request`

---

## Summary: Order Type Flow

```
Shopify Webhook Payload
    ↓
For each line item:
    - Extract SKU → _get_order_type_from_sku() → line_item.order_type
    - Extract subscription metadata (selling_plan_id, app_id)
    - Set line_item.is_subscription / is_recurring_order_item
    - Store custom properties in metadata
    ↓
Aggregate line items:
    - If single item → inherit order_type
    - If multiple items → apply priority cascade
    - Check for ungated RX / male partner SKUs → override
    - If NOT recurring order → check purchase_type custom attribute → final override
    ↓
Route to handler:
    - Care types → process_shopify_order_for_care (consult workflow)
    - Test types → process_shopify_order_for_test (fulfillment + provider linking)
    - PCR add-on → process_shopify_order_for_pcr_add_on
    - Ungated RX → conditional (refill if prescriptions exist, else consult)
    - Mixed (test + Rx) → both test handler AND refill handler
    ↓
Downstream effects:
    - Care: Consult creation/linking, status updates, clinical workflow triggers
    - Test: Provider linking, bulk order detection, Junction integration (UTI)
    - Refill: PrescriptionFill creation, fulfillment requests
    - Subscription refills: Skip attribute overrides, route to refill path
```

---

## Key Insights

1. **Two-stage classification**: Line-item SKU-based → Overall aggregation with overrides
2. **Subscription vs. Refill distinction**: `is_subscription` (new) vs. `is_recurring_order_item` (refill)
3. **Refill protection**: Recurring orders skip custom attribute checks to prevent misclassification
4. **Dynamic routing**: Ungated RX orders route differently based on prescription availability
5. **Multi-handler support**: Combo orders (test + treatment) invoke multiple handlers
6. **Consult-driven vs. fulfillment-driven**: Care orders integrate with clinical workflows; test orders focus on fulfillment and provider relationships

The system is designed to handle complex real-world scenarios: combo orders, subscription refills, provider-initiated purchases, and transparent care bundles—all while maintaining data integrity through careful order type determination.
