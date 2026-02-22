# A2 Exploration Log

## Search 1: Find all files referencing checkout_source
search("checkout_source|checkout_sources|CheckoutSource|CHECKOUT_SOURCE")

Key file groups identified:
- **Core model**: `backend/ecomm/models/order.py`
- **Order processing logic**: `backend/ecomm/utils.py`
- **Cart services**: `backend/ecomm/services/cart.py`, `backend/ecomm/shopify/shopify.py`
- **API views**: `backend/api/v1/views/cart.py`, `backend/api/v1/views/orders.py`, `backend/api/v1/views/user_tests.py`, `backend/api/v1/views/consult.py`, `backend/api/v1/views/provider_test_orders.py`
- **Serializers**: `backend/api/v1/serializers/order.py`, `backend/api/v1/serializers/consult.py`
- **Admin**: `backend/ecomm/admin.py`, `backend/providers/admin.py`
- **Monitoring**: `backend/ecomm/monitoring/utils.py`, `backend/ecomm/monitoring/events.py`, `backend/ecomm/monitoring/metrics.py`
- **Partner services**: `backend/ecomm/services/viome.py`
- **Migrations**: Several migration files (0025, 0035, 0039, 0041, 0042, 0050)
- **Scripts**: `backend/scripts/backfill_order_checkout_sources.py`, `backend/scripts/backfill_subscription_refill_order_attributes.py`, `backend/scripts/reprocess_subscription_refill_orders.py`, `backend/scripts/backfill_upsell_purchase_types.py`
- **Tests**: Multiple test files
- **Frontend**: `frontend/src/types/orders.ts`, `frontend/src/pages/loadingOrder.tsx`, `frontend/src/services/cart.ts`, `frontend/src/hooks/useProcessOrder.ts`, `frontend/src/components/care/consultIntake/upsells/SymptomsUpsell.tsx`, `frontend/src/pages/care/intake/ungatedRx/Consent.tsx`, `frontend/src/utils/analytics/customEventTracking.js`

## Search 2: Read the Order model
Read `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` in full.

Found the canonical definition of checkout source values. The `Order` model defines 16 constants and a `CHECKOUT_SOURCE_CHOICES` tuple:
- `CHECKOUT_SOURCE_VAGINITIS_INTAKE = "vaginitis-intake"`
- `CHECKOUT_SOURCE_UNGATED_RX_INTAKE = "ungated-rx-intake"`
- `CHECKOUT_SOURCE_HEALTH_HISTORY = "health-history"`
- `CHECKOUT_SOURCE_MALE_PARTNER = "male-partner"`
- `CHECKOUT_SOURCE_PROVIDER = "provider-portal"`
- `CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK = "provider-magic-link"`
- `CHECKOUT_SOURCE_MARKETING_SITE = "marketing-site"`
- `CHECKOUT_SOURCE_INTERNAL_SITE = "logged-in-cart"`
- `CHECKOUT_SOURCE_VIOME = "viome-webhook"`
- `CHECKOUT_SOURCE_SUBSCRIPTION = "subscription"`
- `CHECKOUT_SOURCE_RETEST_UPSELL = "retest-upsell"`
- `CHECKOUT_SOURCE_SOCIAL = "social"`
- `CHECKOUT_SOURCE_POS = "pos"`
- `CHECKOUT_SOURCE_OPS_CREATED = "ops_created"`
- `CHECKOUT_SOURCE_DISTRIBUTION_PARTNER = "distribution_partner"`
- `CHECKOUT_SOURCE_OTHER = "other"`

The field: `checkout_source = models.CharField(max_length=50, choices=CHECKOUT_SOURCE_CHOICES, null=True, blank=True)`

## Search 3: Grep checkout_source in ecomm/utils.py
Found the `_determine_checkout_source()` function (lines 810-865) and `cart_requires_consult()` function (lines 2629-2667). These are the two key business logic functions that use checkout_source:

- `_determine_checkout_source(source_name, app_id, cart_id)` maps Shopify app IDs to checkout source values
- `cart_requires_consult(cart, purchase_type, checkout_source)` has special logic for `CHECKOUT_SOURCE_HEALTH_HISTORY`
- The main order processing logic at line 593 calls `_determine_checkout_source` and then allows custom attribute override (lines 596-609)

## Search 4: Grep checkout_source in ecomm/services/cart.py
Found that `CartCheckoutService` reads `checkout_source` from Shopify custom attributes (line 422) and uses it to determine if a consult is required (line 424). Also sets default `checkout_source` to `CHECKOUT_SOURCE_INTERNAL_SITE` if not already set (lines 597-599).

## Search 5: Check Shopify constants for app IDs
Read `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` (lines 310-350). Found all Shopify app ID constants used in `_determine_checkout_source`:
- `SHOPIFY_RECHARGE_APP_ID = 294517`
- `SHOPIFY_EVVY_API_APP_ID = 6687809`
- `SHOPIFY_MARKETING_SITE_APP_IDS = [12875497473, 88312, 580111]`
- `SHOPIFY_SHOP_PAY_APP_ID = 3890849`
- `SHOPIFY_SOCIAL_APP_IDS = [2775569, 4383523, 2329312]`
- `SHOPIFY_POS_APP_ID = 129785`
- `SHOPIFY_OPS_CREATED_APP_IDS = [1354745, 1251622]`
- `SHOPIFY_DISTRIBUTION_PARTNER_APP_ID = 2417604`
- `SHOPIFY_TESTING_ORDERS_APP_ID = 262131515393`

## Search 6: Grep checkout_source in API views
Found all API views that set or use checkout_source:

- `api/v1/views/cart.py` lines 132, 137, 140-141, 169-170: reads `checkout_source` from request data and passes it along
- `api/v1/views/orders.py` lines 128-131: branches logic based on whether `checkout_source` is in `[CHECKOUT_SOURCE_UNGATED_RX_INTAKE, CHECKOUT_SOURCE_VAGINITIS_INTAKE]`
- `api/v1/views/user_tests.py` line 817: sets `checkout_source: CHECKOUT_SOURCE_HEALTH_HISTORY`, line 885: sets `checkout_source: CHECKOUT_SOURCE_RETEST_UPSELL`
- `api/v1/views/consult.py` lines 409, 502, 516, 523, 532, 534: reads and uses checkout_source for consult creation
- `api/v1/views/provider_test_orders.py` line 199: sets `checkout_source: CHECKOUT_SOURCE_PROVIDER`

## Search 7: Grep checkout_source in serializers
- `api/v1/serializers/order.py` line 65: includes `checkout_source` in serialized fields
- `api/v1/serializers/consult.py` lines 417, 491-503, 530: exposes `is_checkout_source_health_context` computed field that checks if `order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY`

## Search 8: Grep checkout_source in monitoring
Found 3 monitoring files that track checkout_source for metrics/events:
- `ecomm/monitoring/utils.py` lines 46, 100: includes `checkout_source` in order attributes dict
- `ecomm/monitoring/events.py` lines 69, 121, 128: passes `checkout_source` as an additional event attribute
- `ecomm/monitoring/metrics.py` lines 61-62, 76-90: records CloudWatch metrics keyed by `checkout_source` (e.g., `OrderValue/Source/<checkout_source>`, `Conversions/Source/<checkout_source>`)

## Search 9: Grep checkout_source in partner service
- `ecomm/services/viome.py` line 189: hardcodes `ShopifyCustomAttribute(key="checkout_source", value=Order.CHECKOUT_SOURCE_VIOME)` when creating a Viome-originated order

## Search 10: Read the latest migration
Read `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0050_alter_order_checkout_source.py`. Confirmed this is the authoritative migration reflecting the current list of valid choices for the `checkout_source` field.

## Search 11: Grep checkout_source in admin
- `ecomm/admin.py` line 227: uses `cross_sell_order__checkout_source` as a list_filter field
- `providers/admin.py` lines 19, 34-39: displays `checkout_source` from ecomm order in the provider admin interface

## Search 12: Read frontend types/orders.ts
Found the TypeScript `Order` type (lines 27-31) which has a typed `checkout_source` union:
```typescript
checkout_source?: "vaginitis-upsell" | "ungated-rx-upsell" | "health-history" | "male-partner";
```
Note: this only covers the subset of checkout sources relevant to frontend routing.

## Search 13: Read frontend loadingOrder.tsx routing switch
Found `getCareConsultRedirect()` function (lines 56-98) which switches on `checkout_source` to route users to different intake flows after purchase:
- `"vaginitis-upsell"` → vaginitis RX intake
- `"ungated-rx-upsell"` → ungated RX intake (with boric acid branch)
- `"health-history"` → ungated RX consent
- `"male-partner"` → male partner intake
- default → UTI, STI, or general care intake

## Search 14: Grep checkout_source in frontend analytics
Found `customEventTracking.js` which defines `CHECKOUT_SOURCE: "checkoutSource_str"` as a tracked property name and uses it in several analytics event functions (lines 1034-1084, 2065-2104).

## Search 15: Grep checkout_source in scripts
Found three backfill/reprocessing scripts:
- `backfill_order_checkout_sources.py`: Applies `_determine_checkout_source` logic to all historical orders. Defines `APPLICATION_SPECIFIC_SOURCES` list (lines 165-173) — sources set via custom attributes that should NOT be overridden by app_id logic.
- `backfill_subscription_refill_order_attributes.py`: Specifically backfills subscription refill orders to have `CHECKOUT_SOURCE_SUBSCRIPTION`.
- `reprocess_subscription_refill_orders.py`: Reprocesses orders; filters on `checkout_source != CHECKOUT_SOURCE_SUBSCRIPTION`.
- `backfill_upsell_purchase_types.py` line 15: Queries by `cross_sell_order__checkout_source=Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE`.

## Search 16: Read cart_requires_consult function
Read `ecomm/utils.py` lines 2620-2668. Confirmed that `cart_requires_consult` has special branching for `CHECKOUT_SOURCE_HEALTH_HISTORY` that bypasses the normal consult requirement for ungated RX eligible products.

---

## Final Answer

### What Code Needs to Change to Add a New Checkout Source Type for a Partner Integration

Adding a new checkout source type requires changes across backend model, business logic, migrations, API, monitoring, admin, frontend types, routing logic, analytics, and backfill scripts. Here is the comprehensive list:

---

### 1. Core Model Definition (REQUIRED)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`
- Lines 139-174: Add a new `CHECKOUT_SOURCE_<NEW_PARTNER> = "<new-partner-slug>"` constant to the `Order` class
- Add the new tuple `(CHECKOUT_SOURCE_<NEW_PARTNER>, "<Human Label>")` to `CHECKOUT_SOURCE_CHOICES`
- The `checkout_source` field at line 173 uses `CHECKOUT_SOURCE_CHOICES`, so it automatically picks up new entries

---

### 2. Django Migration (REQUIRED)

**File (create new):** `backend/ecomm/migrations/0051_alter_order_checkout_source.py` (next in sequence)
- Run `python manage.py makemigrations ecomm` after updating the model
- The migration must `AlterField` the `checkout_source` CharField's `choices` list to include the new value
- See existing pattern in `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0050_alter_order_checkout_source.py`

---

### 3. Shopify Constants (conditional — if partner has a dedicated Shopify app ID)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`
- Lines 323-332: Add `SHOPIFY_<NEW_PARTNER>_APP_ID = <app_id>` alongside the existing app ID constants

---

### 4. Order Source Determination Logic (REQUIRED)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- Function `_determine_checkout_source()` at lines 810-865: Add a new `if app_id == SHOPIFY_<NEW_PARTNER>_APP_ID: return Order.CHECKOUT_SOURCE_<NEW_PARTNER>` branch in the priority chain
- OR, if this partner sets `checkout_source` via a Shopify custom attribute (like Viome, provider portal, etc.), document that at line 821-823 comment and ensure the override logic at lines 596-601 covers it

---

### 5. Partner-Specific Service (conditional — if the partner has a webhook/integration flow)

**File (example pattern):** `/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py`
- Line 189: If the new partner integration creates orders programmatically (like Viome), add a `ShopifyCustomAttribute(key="checkout_source", value=Order.CHECKOUT_SOURCE_<NEW_PARTNER>)` in the order creation call

---

### 6. Cart Service (if the partner uses the cart checkout flow)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py`
- Lines 420-424: The `CartCheckoutService` already reads `checkout_source` from custom attributes generically — no changes needed here unless the new source requires special consult logic
- Lines 597-599: Default fallback assigns `CHECKOUT_SOURCE_INTERNAL_SITE` — verify this is still correct for the new partner

---

### 7. Cart Requires Consult Logic (if the new source has special consult rules)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
- Function `cart_requires_consult()` at lines 2629-2667: Currently has special logic for `CHECKOUT_SOURCE_HEALTH_HISTORY` (line 2653). Add analogous logic for the new partner source if they require different consult behavior.

---

### 8. API Views (if the new source has specific routing or behavior)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`
- Lines 128-131: If the new partner source requires different post-purchase consult routing (like `CHECKOUT_SOURCE_UNGATED_RX_INTAKE` and `CHECKOUT_SOURCE_VAGINITIS_INTAKE`), add the new constant to the list

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`
- Lines 502-534: If the new source affects which Shopify variant is used for consult checkout, add a branch here

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py`
- Line 199: If the new partner integration creates provider-type orders, this may need updating

---

### 9. Serializers (if the new source requires frontend-visible computed fields)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py`
- Lines 491-530: The `is_checkout_source_health_context` field is specific to `CHECKOUT_SOURCE_HEALTH_HISTORY`. Add a similar computed field if the new partner source needs to be surfaced to the frontend differently.

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/order.py`
- Line 65: `checkout_source` is already included in the serialized `Order` fields — no change needed.

---

### 10. Monitoring and Metrics (REQUIRED — automatic for new sources)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py`
- Lines 61-62, 89-90: CloudWatch metrics `OrderValue/Source/<checkout_source>` and `Conversions/Source/<checkout_source>` are dynamically computed from the string value, so a new source will automatically get its own metric namespace. No code change needed, but alert dashboards may need updating.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`
- Lines 121-128: `checkout_source` is passed as an additional attribute generically — no change needed.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/utils.py`
- Lines 46, 100: `checkout_source` is included in order attribute dicts generically — no change needed.

---

### 11. Admin (optional)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py`
- Line 227: `list_filter = ("cross_sell_order__checkout_source",)` — Django will automatically include the new value in the filter dropdown once it's in `CHECKOUT_SOURCE_CHOICES`. No change required.

**File:** `/Users/albertgwo/Work/evvy/backend/providers/admin.py`
- Lines 34-39: `provider_checkout_source` displays the `checkout_source` value from the associated order — no change needed.

---

### 12. Frontend TypeScript Types (REQUIRED if frontend routes on this source)

**File:** `/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts`
- Lines 27-31: The `Order.checkout_source` union type is currently `"vaginitis-upsell" | "ungated-rx-upsell" | "health-history" | "male-partner"`. Add the new partner source string if the frontend needs to route on it.

---

### 13. Frontend Routing Logic (REQUIRED if the new source needs a post-purchase redirect)

**File:** `/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx`
- Lines 60-97: The `getCareConsultRedirect()` switch statement handles post-purchase routing based on `checkout_source`. Add a new `case "<new-partner-slug>":` branch with the appropriate redirect path.

---

### 14. Frontend Cart Service (if the frontend sends checkout_source for the new partner)

**File:** `/Users/albertgwo/Work/evvy/frontend/src/services/cart.ts`
- Lines 86-98: The cart service already handles a generic `checkoutSource` param — no structural change needed, but callers need to pass the correct new source string.

---

### 15. Frontend Analytics (if the new source should appear in analytics events)

**File:** `/Users/albertgwo/Work/evvy/frontend/src/utils/analytics/customEventTracking.js`
- Line 441: `CHECKOUT_SOURCE: "checkoutSource_str"` is the analytics property key. The value is passed dynamically, so no code change is required unless new event types are introduced for the new partner.

---

### 16. Backfill Script: APPLICATION_SPECIFIC_SOURCES (REQUIRED if set via custom attribute)

**File:** `/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`
- Lines 165-173: `APPLICATION_SPECIFIC_SOURCES` is the list of checkout sources set via Shopify custom attributes that should NOT be overridden by app_id-based logic. If the new partner source is set via custom attribute (rather than app_id detection), add `Order.CHECKOUT_SOURCE_<NEW_PARTNER>` to this list.

---

### Summary Table

| Location | File | Lines | Change Required |
|---|---|---|---|
| Model constant + choices | `backend/ecomm/models/order.py` | 139-172 | Add new constant and choice tuple |
| Migration | `backend/ecomm/migrations/005X_alter_order_checkout_source.py` | new file | AlterField with new choices |
| Shopify app ID constant | `backend/ecomm/constants.py` | 323-332 | Add app ID if partner has one |
| Source determination | `backend/ecomm/utils.py` | 810-865 | Add detection branch |
| Partner service (if webhook) | `backend/ecomm/services/<partner>.py` | new/existing | Set custom attribute |
| Consult logic (if special rules) | `backend/ecomm/utils.py` | 2629-2667 | Add branch for new source |
| Orders API view (if routing) | `backend/api/v1/views/orders.py` | 128-131 | Add to routing list |
| Consult API view (if variant) | `backend/api/v1/views/consult.py` | 502-534 | Add variant selection branch |
| Consult serializer (if computed) | `backend/api/v1/serializers/consult.py` | 491-530 | Add computed field if needed |
| Backfill script preserved list | `backend/scripts/backfill_order_checkout_sources.py` | 165-173 | Add to APPLICATION_SPECIFIC_SOURCES |
| Frontend type union | `frontend/src/types/orders.ts` | 27-31 | Add to union type |
| Frontend routing switch | `frontend/src/pages/loadingOrder.tsx` | 60-97 | Add case to switch |
