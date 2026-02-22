# A2 Test - Search Transcript

**Task:** "We need to add a new checkout source type for a partner integration. What code needs to change? Provide a comprehensive list of files and code locations that reference or depend on the checkout source concept."

## Tool Calls Made

### Call 1-2: Initial Search
```bash
search("checkout source type")
search("CheckoutSource")
```

**Key findings:**
- Found `_determine_checkout_source()` function in `backend/ecomm/utils.py`
- Found `Order` model in `backend/ecomm/models/order.py`
- Found backfill scripts in `backend/scripts/backfill_order_checkout_sources.py`
- Found serializer usage in `backend/api/v1/serializers/consult.py`

### Call 3: Search for Constants
```bash
search("checkout source constants enum")
```

**Key findings:**
- Found `TestOrderSource` enum in `backend/analytics/braze/constants.py`

### Call 4-5: Read Core Files
```bash
read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (lines 810-865)
read("/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py") (lines 11-210)
```

**Key findings:**
- Found all CHECKOUT_SOURCE constants in Order model (lines 139-175)
- Found `_determine_checkout_source()` logic that maps app_ids to checkout sources
- 16 existing checkout source types defined

### Call 6-7: Search for Field Usage
```bash
search("order.checkout_source =")
search("checkout_source serializer")
```

**Key findings:**
- Found checkout_source assignment in `_process_shopify_order_impl()`
- Found serializer method `get_is_checkout_source_health_context()` in consult serializers

### Call 8-9: Read Implementation Details
```bash
read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (lines 238-337)
read("/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py") (lines 499-518)
```

**Key findings:**
- Custom attributes can override determined checkout_source (line 297-299, 598-599)
- Subscription refill orders ignore custom attribute overrides (line 603-606)
- Order processing logs checkout_source for tracking

### Call 10: Search for App ID Constants
```bash
search("shopify app id constants")
```

### Call 11: Find App ID Constants
```bash
search("SHOPIFY.*APP_ID")
```

**Key findings:**
- Found all Shopify app ID constants in `backend/ecomm/constants.py` (lines 324-332)
- 8 app ID constants that map to checkout sources:
  - SHOPIFY_RECHARGE_APP_ID
  - SHOPIFY_EVVY_API_APP_ID
  - SHOPIFY_MARKETING_SITE_APP_IDS
  - SHOPIFY_SHOP_PAY_APP_ID
  - SHOPIFY_SOCIAL_APP_IDS
  - SHOPIFY_POS_APP_ID
  - SHOPIFY_OPS_CREATED_APP_IDS
  - SHOPIFY_DISTRIBUTION_PARTNER_APP_ID
  - SHOPIFY_TESTING_ORDERS_APP_ID

### Call 12-13: Read More Implementation
```bash
search("SHOPIFY_DISTRIBUTION_PARTNER_APP_ID SHOPIFY_RECHARGE")
read("/Users/albertgwo/Work/evvy/backend/ecomm/utils.py") (lines 590-669)
```

**Key findings:**
- Checkout source assignment at line 609: `order.checkout_source = determined_checkout_source`
- Logic for overriding with custom attributes vs determined value

### Call 14: Read Constants File
```bash
read("/Users/albertgwo/Work/evvy/backend/ecomm/constants.py") (lines 1-150)
```

### Call 15: Read Backfill Script
```bash
read("/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py") (lines 68-147)
```

**Key findings:**
- Backfill script mirrors the logic from `_determine_checkout_source()`
- Must be kept in sync with main determination logic

### Call 16-17: Search for Analytics/Admin Usage
```bash
search("checkout_source analytics braze segment")
search("admin checkout_source display")
```

**Key findings:**
- Admin panel displays checkout_source in provider admin
- No direct Braze/analytics integration found (only general TestOrderSource enum)

### Call 18-19: Read Admin Files
```bash
read("/Users/albertgwo/Work/evvy/backend/providers/admin.py") (full file)
read("/Users/albertgwo/Work/evvy/backend/ecomm/admin.py") (lines 96-155)
```

**Key findings:**
- `ProviderTestOrderAdmin` has `provider_checkout_source` readonly field (line 19, 34-40)
- Admin displays checkout_source for provider test orders
- Main OrderAdmin doesn't include checkout_source in list_display

## Answer

To add a new checkout source type for a partner integration, you need to modify the following files and code locations:

### 1. **Order Model - Define the New Constant**
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`
- **Lines 139-175:** Add new checkout source constant and choice tuple
  - Add constant like `CHECKOUT_SOURCE_PARTNER_NAME = "partner-name"`
  - Add to `CHECKOUT_SOURCE_CHOICES` tuple with display name

### 2. **App ID Constants (if app-based routing)**
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`
- **Lines 324-332:** Add Shopify app ID constant if the partner has a dedicated Shopify app
  - Example: `SHOPIFY_PARTNER_NAME_APP_ID = 123456`

### 3. **Checkout Source Determination Logic**
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- **Lines 810-865:** Update `_determine_checkout_source()` function
  - Add logic to detect the new partner based on `app_id`, `cart_id`, or `source_name`
  - Follow the priority order documented in the function docstring
  - Example:
    ```python
    if app_id == SHOPIFY_PARTNER_NAME_APP_ID:
        return Order.CHECKOUT_SOURCE_PARTNER_NAME
    ```
- **Lines 297-299:** If using custom attributes, the function already handles overrides
- **Lines 592-614:** The main order processing flow already calls this function

### 4. **Backfill Script (Keep in Sync)**
**File:** `/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`
- **Lines 68-117:** Update `_determine_checkout_source_from_payload()` function
  - Mirror the exact logic added to `ecomm/utils._determine_checkout_source()`
  - This ensures historical orders can be backfilled correctly
  - The comment at line 73 states this "mirrors the logic in ecomm.utils._determine_checkout_source"

### 5. **Database Migration**
**Action Required:** Create Django migration
- The new constant in `CHECKOUT_SOURCE_CHOICES` will need a migration to update the field's choices
- Run: `python manage.py makemigrations ecomm`

### 6. **Admin Panel (Optional - for visibility)**
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py`
- **Lines 96-107:** Consider adding `checkout_source` to `OrderAdmin.list_display` if needed
- **Line 107:** Consider adding to `list_filter` for filtering by checkout source

**File:** `/Users/albertgwo/Work/evvy/backend/providers/admin.py`
- Already displays checkout_source in readonly_fields (line 19) and has display method (lines 34-40)

### 7. **Documentation & Data Warehouse**
**Note from code (line 818-819):**
- The logic "matches the dbt-models stg_ecomm_orders.sql logic for consistency across the data warehouse and application code"
- **Action Required:** Update the corresponding dbt model at `dbt-models/stg_ecomm_orders.sql` to mirror the new logic

### 8. **Testing Considerations**
**Files to check for test coverage:**
- Tests for `_determine_checkout_source()` function
- Tests for `_determine_checkout_source_from_payload()` function
- Integration tests for order processing with the new checkout source

### 9. **Conditional Logic Dependencies (Check These)**
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py`
- **Lines 499-506:** `get_is_checkout_source_health_context()` checks for specific checkout sources
  - Determine if your new partner source should be included in similar checks

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- **Lines 820-823:** Custom checkout source attributes note mentions application-specific sources
  - If the partner integration needs to override via custom attributes, this is already supported

### Summary of Required Changes

**Minimal viable changes:**
1. Add constant to `Order` model (`ecomm/models/order.py`)
2. Add app ID constant (if applicable) to `ecomm/constants.py`
3. Update `_determine_checkout_source()` in `ecomm/utils.py`
4. Update `_determine_checkout_source_from_payload()` in `scripts/backfill_order_checkout_sources.py`
5. Create database migration
6. Update dbt model in data warehouse

**Optional but recommended:**
7. Add to admin panel filters/display
8. Update any conditional logic that checks specific checkout sources
9. Add test coverage for the new source type

### Custom Attribute Alternative

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- **Lines 297-299, 598-599:** If the partner integration can set a custom attribute named `checkout_source` in the order payload, it will automatically override the determined value
- This approach requires no code changes, just configuration in the partner integration
- Note: This override is skipped for subscription refill orders (lines 603-606)
