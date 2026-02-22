# A2: Adding New Checkout Source Type - Beta Search Transcript

## Task
"We need to add a new checkout source type for a partner integration. What code needs to change? Provide a comprehensive list of files and code locations that reference or depend on the checkout source concept."

## Search Strategy
1. Search for patterns: `checkout.?source`, `CheckoutSource`, `CHECKOUT_SOURCE_`
2. Read model definition to understand the field structure
3. Examine backend usage (views, services, utils, tasks, monitoring)
4. Check frontend TypeScript types and usage
5. Review admin interface configuration
6. Check migrations to understand field evolution

## Tool Calls and Findings

### Search 1-3: Pattern matching across codebase
```bash
# Search 1: Case-insensitive "checkout source" pattern
search("checkout.?source")
# Found 54 files

# Search 2: PascalCase "CheckoutSource"
search("CheckoutSource")
# Found 0 files (no TypeScript enum/type)

# Search 3: Constant pattern "CHECKOUT_SOURCE_"
search("CHECKOUT_SOURCE")
# Found 23 files
```

**Key Finding**: The checkout source is implemented as Django model constants (CHECKOUT_SOURCE_*), not as a separate enum/class.

### Read 1: Model Definition
File: `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (lines 139-175)

**Current Checkout Source Constants:**
```python
CHECKOUT_SOURCE_VAGINITIS_INTAKE = "vaginitis-intake"
CHECKOUT_SOURCE_UNGATED_RX_INTAKE = "ungated-rx-intake"
CHECKOUT_SOURCE_HEALTH_HISTORY = "health-history"
CHECKOUT_SOURCE_MALE_PARTNER = "male-partner"
CHECKOUT_SOURCE_PROVIDER = "provider-portal"
CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK = "provider-magic-link"
CHECKOUT_SOURCE_MARKETING_SITE = "marketing-site"
CHECKOUT_SOURCE_INTERNAL_SITE = "logged-in-cart"
CHECKOUT_SOURCE_VIOME = "viome-webhook"
CHECKOUT_SOURCE_SUBSCRIPTION = "subscription"
CHECKOUT_SOURCE_RETEST_UPSELL = "retest-upsell"
CHECKOUT_SOURCE_SOCIAL = "social"
CHECKOUT_SOURCE_POS = "pos"
CHECKOUT_SOURCE_OPS_CREATED = "ops_created"
CHECKOUT_SOURCE_DISTRIBUTION_PARTNER = "distribution_partner"
CHECKOUT_SOURCE_OTHER = "other"

CHECKOUT_SOURCE_CHOICES = (
    (CHECKOUT_SOURCE_VAGINITIS_INTAKE, "Vaginitis Intake"),
    (CHECKOUT_SOURCE_UNGATED_RX_INTAKE, "Ungated RX Intake"),
    (CHECKOUT_SOURCE_HEALTH_HISTORY, "Health History"),
    (CHECKOUT_SOURCE_MALE_PARTNER, "Male Partner"),
    (CHECKOUT_SOURCE_PROVIDER, "Provider"),
    (CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK, "Provider Magic Link"),
    (CHECKOUT_SOURCE_MARKETING_SITE, "Marketing Site"),
    (CHECKOUT_SOURCE_INTERNAL_SITE, "Internal Site"),
    (CHECKOUT_SOURCE_VIOME, "Viome Webhook"),
    (CHECKOUT_SOURCE_SUBSCRIPTION, "Subscription"),
    (CHECKOUT_SOURCE_RETEST_UPSELL, "Retest Upsell"),
    (CHECKOUT_SOURCE_SOCIAL, "Social"),
    (CHECKOUT_SOURCE_POS, "POS"),
    (CHECKOUT_SOURCE_OPS_CREATED, "Ops Created"),
    (CHECKOUT_SOURCE_DISTRIBUTION_PARTNER, "Distribution Partner"),
    (CHECKOUT_SOURCE_OTHER, "Other"),
)

checkout_source = models.CharField(
    max_length=50, choices=CHECKOUT_SOURCE_CHOICES, null=True, blank=True
)
```

### Backend Usage Analysis

#### 1. Core Utils (`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`)

**Lines 825-865: Shopify checkout source detection**
```python
def _get_checkout_source(
    app_id: str | None,
    cart_id: str | None,
    source_name: str | None,
) -> str:
    """
    Maps Shopify app_id/cart_id to checkout_source field.
    Priority order:
    1. Recharge app ID → subscription
    2. Cart ID exists OR Evvy app ID → logged-in-cart
    3. Marketing site app IDs OR source_name='web' → marketing-site
    4. Social app IDs → social
    5. POS app ID → pos
    6. Ops created app IDs → ops_created
    7. Distribution partner app ID → distribution_partner
    8. Testing orders app ID → other
    9. Fallback → other
    """
```

**Lines 1652-1654: Provider source detection**
```python
if is_magic_link:
    order.checkout_source = Order.CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK
else:
    order.checkout_source = Order.CHECKOUT_SOURCE_PROVIDER
```

**Line 1853: Conditional logic based on source**
```python
if order.checkout_source == Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE
```

**Line 2653: Health history check**
```python
if checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
```

#### 2. Services

**Cart Service (`/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py:599`)**
```python
custom_attributes["checkout_source"] = Order.CHECKOUT_SOURCE_INTERNAL_SITE
```

**Viome Service (`/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py:189`)**
```python
ShopifyCustomAttribute(key="checkout_source", value=Order.CHECKOUT_SOURCE_VIOME)
```

#### 3. Shopify Integration (`/Users/albertgwo/Work/evvy/backend/ecomm/shopify/shopify.py:102`)
```python
{"key": "checkout_source", "value": Order.CHECKOUT_SOURCE_INTERNAL_SITE}
```

#### 4. Tasks (`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:409`)
```python
if order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
```

#### 5. API Views

**Consult View (`/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`)**
- Line 409: `"checkout_source": Order.CHECKOUT_SOURCE_INTERNAL_SITE`
- Line 516: Conditional check for vaginitis intake

**User Tests View (`/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py`)**
- Line 817: `"checkout_source": Order.CHECKOUT_SOURCE_HEALTH_HISTORY`
- Line 885: `"checkout_source": Order.CHECKOUT_SOURCE_RETEST_UPSELL`

**Provider Test Orders View (`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py:199`)**
```python
"checkout_source": Order.CHECKOUT_SOURCE_PROVIDER
```

**Orders View (`/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py:129-130`)**
```python
Order.CHECKOUT_SOURCE_UNGATED_RX_INTAKE,
Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE,
```

**Male Partner Utils (`/Users/albertgwo/Work/evvy/backend/api/v1/utils/male_partner.py:99`)**
```python
"checkout_source": Order.CHECKOUT_SOURCE_MALE_PARTNER
```

#### 6. Serializers

**Order Serializer (`/Users/albertgwo/Work/evvy/backend/api/v1/serializers/order.py:65`)**
```python
fields = (
    "id",
    "order_number",
    "checkout_id",
    "create_date",
    "order_type",
    "business_verticals",
    "status",
    "line_items",
    "is_open",
    "country",
    "checkout_source",  # Exposed in API
)
```

**Consult Serializer (`/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py:503`)**
```python
if consult_order.order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
```

#### 7. Monitoring/Observability

**Monitoring Utils (`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/utils.py`)**
- Line 46: `"checkout_source": getattr(order, "checkout_source", None)`
- Line 100: Includes checkout_source in tracking

**Monitoring Events (`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`)**
- Line 69: Includes in event attributes
- Line 121: Function parameter for checkout_source
- Line 128: Passed as additional_attributes

**Monitoring Metrics (`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py`)**
- Lines 61-62: Metric by source: `OrderValue/Source/{order.checkout_source}`
- Lines 76-90: Conversion tracking by source: `Conversions/Source/{checkout_source}`

#### 8. Admin Interface

**Admin (`/Users/albertgwo/Work/evvy/backend/ecomm/admin.py:227`)**
```python
list_filter = ("cross_sell_order__checkout_source",)
```

Admin filter allows filtering RelatedOrder objects by checkout source of the cross-sell order.

#### 9. Scripts

**Backfill Order Checkout Sources (`/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`)**
- Lines 89-117: Duplicate logic for mapping app_id to checkout source
- Lines 166-173: List of care intake sources for backfill filtering

**Subscription Refill Backfill (`/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py`)**
- Line 209: Check if already subscription source
- Line 215: Set to CHECKOUT_SOURCE_SUBSCRIPTION

**Reprocess Subscription Orders (`/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py:104`)**
```python
if order.checkout_source != Order.CHECKOUT_SOURCE_SUBSCRIPTION:
```

**Backfill Upsell Purchase Types (`/Users/albertgwo/Work/evvy/backend/scripts/backfill_upsell_purchase_types.py:15`)**
```python
cross_sell_order__checkout_source=Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE
```

### Frontend Usage Analysis

#### 1. TypeScript Types

**Order Types (`/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts:27-31`)**
```typescript
checkout_source?:
  | "vaginitis-upsell"
  | "ungated-rx-upsell"
  | "health-history"
  | "male-partner";
```

**WARNING**: Frontend type is incomplete! Only includes 4 values, backend has 16.

**Care Types (`/Users/albertgwo/Work/evvy/frontend/src/types/care.ts:384`)**
```typescript
is_checkout_source_health_context?: boolean;
```

#### 2. Services

**Cart Service (`/Users/albertgwo/Work/evvy/frontend/src/services/cart.ts`)**
- Line 80: Function parameter `checkoutSource?: string`
- Line 86: Request type `checkout_source?: string`
- Lines 97-98: Conditionally add to request

#### 3. Hooks

**usePanelCart (`/Users/albertgwo/Work/evvy/frontend/src/hooks/cart/usePanelCart.tsx:151`)**
```typescript
const checkoutOnCart = async (consultId: string, checkoutSource?: string)
```

**useProcessOrder (`/Users/albertgwo/Work/evvy/frontend/src/hooks/useProcessOrder.ts:8`)**
```typescript
checkout_source?: string;
```

**useOrderTracking (`/Users/albertgwo/Work/evvy/frontend/src/hooks/useOrderTracking.ts:71`)**
```typescript
(cartValue: number, itemCount: number, checkoutSource: string) => {
```

#### 4. Pages/Components

**Loading Order (`/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx`)**
- Lines 22-29: JSDoc describing redirect logic based on checkout_source
- Line 58: Destructure `checkout_source` from order
- Line 60: Switch statement routing based on checkout_source
- Lines 177-181: Set source and track

**Ungated RX Pages (`/Users/albertgwo/Work/evvy/frontend/src/pages/care/intake/ungatedRx/`)**
- Loading.tsx lines 43, 60, 120, 148: Pass checkoutSource to tracking
- Consent.tsx lines 79-87: Check for health history source

**Symptoms Upsell (`/Users/albertgwo/Work/evvy/frontend/src/components/care/consultIntake/upsells/SymptomsUpsell.tsx`)**
- Lines 49-50: Check for health history source
- Line 102: Pass checkout_source to cart
- Lines 162, 191, 275, 371, 396: Pass to tracking
- Line 241: Conditional logic based on source

#### 5. Analytics

**Custom Event Tracking (`/Users/albertgwo/Work/evvy/frontend/src/utils/analytics/customEventTracking.js`)**
- Line 441: Property name constant `CHECKOUT_SOURCE: "checkoutSource_str"`
- Lines 1034-1039, 1048-1053, 1065-1070, 1079-1084: Multiple event tracking functions
- Lines 2065-2072, 2081-2088, 2097-2104: More tracking events

**New Relic Helpers (`/Users/albertgwo/Work/evvy/frontend/src/utils/newrelicHelpers.js`)**
- Line 141: JSDoc parameter
- Line 143: logCheckoutStarted function parameter
- Line 148: Include in event attributes

### Test Files

**Backend Tests:**
1. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py:1387-1391`
2. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_service.py:230,360,445`
3. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_tasks.py:486`
4. `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_shopify.py`
5. `/Users/albertgwo/Work/evvy/backend/api/tests/test_consults.py:452,548,557`
6. `/Users/albertgwo/Work/evvy/backend/api/tests/test_magic_link_flow.py:159,240,374`

### Migrations

**Initial Addition (`0025_order_checkout_source.py`)**
- Added with only 3 choices: vaginitis-intake, ungated-rx-intake, health-history
- Field: CharField(max_length=50, null=True, blank=True)

**Subsequent Migrations Adding Sources:**
- `0035_alter_order_checkout_source.py`
- `0039_alter_order_checkout_source.py`
- `0040_orderlineitem_care_product_and_more.py`
- `0041_alter_order_checkout_source.py`
- `0042_alter_order_checkout_source.py`
- `0050_alter_order_checkout_source.py`

### Documentation

**ADR (`/Users/albertgwo/Work/evvy/docs/adr/00052-subscription-refill-order-custom-attributes.md`)**
- References checkout_source in subscription refill context

## Comprehensive Change List

To add a new checkout source type (e.g., `CHECKOUT_SOURCE_PARTNER_INTEGRATION = "partner-integration"`), you need to modify:

### 1. REQUIRED CHANGES (Core Model & Database)

**A. Model Definition**
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`
- **Lines**: 139-175
- **Changes**:
  1. Add new constant: `CHECKOUT_SOURCE_PARTNER_INTEGRATION = "partner-integration"`
  2. Add to `CHECKOUT_SOURCE_CHOICES` tuple: `(CHECKOUT_SOURCE_PARTNER_INTEGRATION, "Partner Integration")`

**B. Database Migration**
- **Action**: Create new migration with `python manage.py makemigrations`
- **Pattern**: Follow existing migration pattern (see `0025_order_checkout_source.py`)

**C. Frontend TypeScript Types**
- **File**: `/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts`
- **Lines**: 27-31
- **Changes**: Add `"partner-integration"` to union type
- **CRITICAL**: Current type only has 4 values vs 16 in backend - should synchronize all values

### 2. INTEGRATION POINTS (Where Source is Set)

**A. Shopify Integration Logic**
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- **Function**: `_get_checkout_source()` (lines 825-865)
- **Action**: Add logic to detect partner integration (likely via app_id or custom attribute)

**B. Order Creation Entry Points**
Choose relevant locations based on how partner orders are created:
- **Cart Service**: `/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py:599`
- **Viome Service**: `/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py:189` (example pattern)
- **Shopify Custom Attributes**: `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/shopify.py:102`
- **API Views**:
  - `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py:409,516`
  - `/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py:817,885`
  - `/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py:199`
  - `/Users/albertgwo/Work/evvy/backend/api/v1/utils/male_partner.py:99`

### 3. CONDITIONAL LOGIC (Business Rules by Source)

Review and update if partner integration needs special handling:

**A. Backend Logic**
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:1853` - Intake-specific logic
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2653` - Health history check
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:409` - Task-based processing
- `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py:503` - Serialization logic
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py:129-130` - View filtering

**B. Frontend Routing/UI**
- `/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx:60` - Switch statement for post-order routing
- `/Users/albertgwo/Work/evvy/frontend/src/components/care/consultIntake/upsells/SymptomsUpsell.tsx:241` - Conditional UI

### 4. OBSERVABILITY & ANALYTICS

**A. Backend Monitoring**
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py`
- **Lines**: 61-62, 89-90
- **Action**: No code change needed - metrics auto-generate by source
- **Verify**: CloudWatch metrics for `OrderValue/Source/partner-integration` and `Conversions/Source/partner-integration`

**B. Frontend Analytics**
- **File**: `/Users/albertgwo/Work/evvy/frontend/src/utils/analytics/customEventTracking.js`
- **Action**: No code change needed - source is passed through
- **Verify**: Segment/analytics events include correct checkoutSource

**C. New Relic**
- **File**: `/Users/albertgwo/Work/evvy/frontend/src/utils/newrelicHelpers.js`
- **Action**: No code change needed - generic implementation

### 5. ADMIN INTERFACE

**A. Django Admin Filters**
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py:227`
- **Action**: No code change needed - auto-populates from model choices
- **Verify**: Filter dropdown shows new source in RelatedOrder admin

### 6. SCRIPTS & BACKFILLS (If Needed)

**A. Backfill Script Pattern**
- **Reference**: `/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`
- **Action**: Create similar script if need to backfill historical partner orders
- **Pattern**: Lines 89-117 show detection logic, 166-173 show filtering

**B. Existing Script Updates**
Only if partner integration relates to subscriptions or specific filtering:
- `/Users/albertgwo/Work/evvy/backend/scripts/backfill_upsell_purchase_types.py:15`

### 7. TESTING

**A. Backend Tests to Update/Add**
- `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_utils.py` - Test checkout source detection
- `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_service.py` - Test cart/service layer
- `/Users/albertgwo/Work/evvy/backend/api/tests/` - Test API endpoints that set source

**B. Test Pattern**
```python
# Example from test_utils.py:1387-1391
order.checkout_source = Order.CHECKOUT_SOURCE_PARTNER_INTEGRATION
order.save()
self.assertEqual(order.checkout_source, Order.CHECKOUT_SOURCE_PARTNER_INTEGRATION)
```

### 8. DOCUMENTATION

**A. Code Documentation**
- Update JSDoc in `/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx:22-29`
- Update function docstrings that enumerate sources

**B. ADR/Design Docs**
- Consider adding to `/Users/albertgwo/Work/evvy/docs/adr/` if significant business logic

## Summary Statistics

- **Total files referencing checkout_source**: 54
- **Backend Python files**: 31
- **Frontend TypeScript/JavaScript files**: 13
- **Migration files**: 7
- **Test files**: 6
- **Documentation files**: 1

## Key Architectural Insights

1. **Centralized Definition**: All source constants defined in `Order` model - single source of truth
2. **Auto-Detection**: Primary source assignment via `_get_checkout_source()` in utils.py based on Shopify metadata
3. **Explicit Override**: Some sources set explicitly in API views (provider, male-partner, health-history)
4. **Frontend Subset**: TypeScript type only includes 4 sources - out of sync with backend's 16
5. **Metrics by Source**: Monitoring automatically creates per-source metrics without code changes
6. **Migration History**: Field evolved from 3 sources to 16 over multiple migrations

## Critical Gaps to Address

1. **Frontend Type Sync**: TypeScript `Order.checkout_source` type only has 4 values, should have all 16
2. **Documentation**: No central mapping of what each source means or when it's used
3. **Test Coverage**: Not all sources have corresponding test cases

## Recommended Implementation Order

1. Add constant to `Order` model + update `CHECKOUT_SOURCE_CHOICES`
2. Create and run Django migration
3. Update frontend TypeScript types (fix all 16 sources while you're there)
4. Add detection logic to `_get_checkout_source()` or explicit assignment point
5. Add/update tests
6. Verify monitoring dashboards after deployment
7. Document the new source and its business meaning
