# A2 Exploration Log

## Search 1: Semantic search for "checkout source type"
Searched with clew for "checkout source type". Found highly relevant results:
- `backend/providers/admin.py` — `provider_checkout_source` method (score 0.917)
- `backend/ecomm/utils.py` — `_determine_checkout_source` function with docstring explaining priority logic (score 0.715)
- `backend/scripts/backfill_order_checkout_sources.py` — `_determine_checkout_source_from_payload` (score 0.556)
- `backend/api/v1/serializers/consult.py` — `get_is_checkout_source_health_context` (score 0.438)
- `backend/ecomm/models/order.py` — `Order` class (score 0.427)

## Search 2: Semantic search for "checkout source enum"
Found:
- `backend/analytics/braze/constants.py` — `TestOrderSource` enum (score 1.093) — but this is for Braze analytics, different concept
- `backend/ecomm/utils.py` — `_determine_checkout_source` again
- `backend/scripts/backfill_order_checkout_sources.py` — backfill logic

## Search 3: Semantic search for "CHECKOUT_SOURCE constants"
Confirmed constants live in `backend/ecomm/utils.py` (imported from `ecomm/constants.py`) and backfill script.

## Search 4: Grep for checkout_source in ecomm/constants.py
No matches — the constants are defined as class-level attributes on the `Order` model, not a separate constants file.

## Search 5: List ecomm/ directory
Confirmed structure: `constants.py`, `models/`, `utils.py`, `services/`, `shopify/`, `monitoring/`, `migrations/`.

## Search 6: Read Order model (ecomm/models/order.py lines 1-200)
Found the authoritative definition of all `CHECKOUT_SOURCE_*` constants on the `Order` model:
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

And the `CHECKOUT_SOURCE_CHOICES` tuple + `checkout_source = models.CharField(max_length=50, ...)` field.

## Search 7: Grep all files referencing checkout_source in backend/
Found 41 files total. Key groups:
- Model definition: `ecomm/models/order.py`
- Core logic: `ecomm/utils.py`, `ecomm/services/cart.py`, `ecomm/services/viome.py`
- API views: `api/v1/views/cart.py`, `api/v1/views/consult.py`, `api/v1/views/orders.py`, `api/v1/views/user_tests.py`, `api/v1/views/provider_test_orders.py`
- Serializers: `api/v1/serializers/consult.py`, `api/v1/serializers/order.py`
- Admin: `ecomm/admin.py`, `providers/admin.py`
- Monitoring: `ecomm/monitoring/events.py`, `ecomm/monitoring/metrics.py`, `ecomm/monitoring/utils.py`
- Shopify integration: `ecomm/shopify/shopify.py`
- Scripts: `scripts/backfill_order_checkout_sources.py`, `scripts/backfill_subscription_refill_order_attributes.py`, `scripts/reprocess_subscription_refill_orders.py`, `scripts/backfill_upsell_purchase_types.py`
- Migrations: 7 migration files
- Tests: `ecomm/tests/test_utils.py`, `ecomm/tests/test_tasks.py`, `ecomm/tests/test_service.py`, `ecomm/tests/test_shopify.py`, `api/tests/test_magic_link_flow.py`, `api/tests/test_consults.py`
- Tasks: `ecomm/tasks.py`

## Search 8: Grep ecomm/utils.py for checkout_source
Found:
- Lines 284, 297-299, 332: Parsing `checkout_source` from Shopify order custom attributes in `_process_shopify_order_impl`
- Lines 593-611: Calling `_determine_checkout_source` then optionally overriding with custom attribute
- Lines 810-865: `_determine_checkout_source()` — priority logic using Shopify app IDs
- Lines 1652-1654: Setting `CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK` or `CHECKOUT_SOURCE_PROVIDER` for magic link orders
- Lines 1853: Checking for `CHECKOUT_SOURCE_VAGINITIS_INTAKE` in post-order processing
- Lines 2629-2667: `cart_requires_consult()` uses `checkout_source` to modify consult requirement logic

## Search 9: Grep ecomm/services/cart.py for checkout_source
- Line 422: Reading `checkout_source` from cart custom attributes
- Line 424: Passing to `cart_requires_consult()`
- Lines 597-599: Setting default `checkout_source = CHECKOUT_SOURCE_INTERNAL_SITE` if not already in custom_attributes

## Search 10: Grep API views for checkout_source
- `api/v1/views/cart.py` lines 132, 137, 140-141, 169-170: Reading `checkout_source` from POST request, passing to `cart_requires_consult`, setting in custom attributes
- `api/v1/views/consult.py` lines 409, 502-534: Setting `CHECKOUT_SOURCE_INTERNAL_SITE`, reading from request, routing checkout based on source value
- `api/v1/views/orders.py` lines 128-130: Checking for `CHECKOUT_SOURCE_UNGATED_RX_INTAKE` or `CHECKOUT_SOURCE_VAGINITIS_INTAKE`
- `api/v1/views/user_tests.py` lines 817, 885: Setting `CHECKOUT_SOURCE_HEALTH_HISTORY` and `CHECKOUT_SOURCE_RETEST_UPSELL`
- `api/v1/views/provider_test_orders.py` line 199: Setting `CHECKOUT_SOURCE_PROVIDER`
- `api/v1/serializers/consult.py` lines 491-530: Exposing `is_checkout_source_health_context` field derived from `CHECKOUT_SOURCE_HEALTH_HISTORY`
- `api/v1/serializers/order.py` line 65: Including `checkout_source` in serializer fields

## Search 11: Grep monitoring files for checkout_source
- `ecomm/monitoring/events.py` lines 69, 121-128: Passing `checkout_source` as attribute in order events
- `ecomm/monitoring/metrics.py` lines 61-62, 76-90: Recording metrics per source (e.g., `OrderValue/Source/{checkout_source}` and `Conversions/Source/{checkout_source}`)
- `ecomm/monitoring/utils.py` lines 46, 100: Including `checkout_source` in order monitoring data

## Search 12: Grep Shopify integration + Viome service
- `ecomm/shopify/shopify.py` lines 100-102: Setting default `checkout_source = CHECKOUT_SOURCE_INTERNAL_SITE` in Shopify cart custom attributes
- `ecomm/services/viome.py` line 189: Setting `checkout_source = CHECKOUT_SOURCE_VIOME` as Shopify custom attribute

## Search 13: Grep provider admin
- `providers/admin.py` lines 19, 34-39: `provider_checkout_source` readonly field that displays `ecomm_order.checkout_source`

## Search 14: Read ecomm/utils.py lines 800-865
Confirmed the full `_determine_checkout_source()` function with all 9 priority cases.

## Search 15: Grep frontend for checkout_source
Found frontend files:
- `frontend/src/types/orders.ts` line 27-31: TypeScript union type for `checkout_source` (4 values: `"vaginitis-upsell"`, `"ungated-rx-upsell"`, `"health-history"`, `"male-partner"`)
- `frontend/src/services/cart.ts` lines 86, 98: Including `checkout_source` in cart checkout API request
- `frontend/src/pages/loadingOrder.tsx` lines 58-97: `switch(checkout_source)` routing users to different intake flows
- `frontend/src/utils/analytics/customEventTracking.js` lines 441, 1039-1084, 2072-2104: Tracking `CHECKOUT_SOURCE` in analytics events
- `frontend/src/hooks/useProcessOrder.ts` line 8: Interface field `checkout_source?: string`
- `frontend/src/types/care.ts` line 384: `is_checkout_source_health_context?: boolean` field on care type
- `frontend/src/components/care/consultIntake/upsells/SymptomsUpsell.tsx` lines 50, 102: Reading `is_checkout_source_health_context` and passing `checkout_source`
- `frontend/src/pages/care/intake/ungatedRx/Consent.tsx` line 80: Reading `is_checkout_source_health_context`

## Search 16: Read ecomm/constants.py for Shopify App IDs
Found all Shopify app ID constants at lines 323-342:
- `SHOPIFY_RECHARGE_APP_ID = 294517` → subscription
- `SHOPIFY_EVVY_API_APP_ID = 6687809` → logged-in-cart
- `SHOPIFY_MARKETING_SITE_APP_IDS = [12875497473, 88312, 580111]` → marketing-site
- `SHOPIFY_SHOP_PAY_APP_ID = 3890849` → marketing-site
- `SHOPIFY_SOCIAL_APP_IDS = [2775569, 4383523, 2329312]` → social
- `SHOPIFY_POS_APP_ID = 129785` → pos
- `SHOPIFY_OPS_CREATED_APP_IDS = [1354745, 1251622]` → ops_created
- `SHOPIFY_DISTRIBUTION_PARTNER_APP_ID = 2417604` → distribution_partner
- `SHOPIFY_TESTING_ORDERS_APP_ID = 262131515393` → other

## Search 17: Read the latest migration (0050_alter_order_checkout_source.py)
Confirmed the migration pattern: each time a new source is added to `CHECKOUT_SOURCE_CHOICES`, a new Django migration is required.

## Search 18: Read cart_requires_consult function (ecomm/utils.py lines 2625-2667)
Confirmed this function has specific logic branching on `CHECKOUT_SOURCE_HEALTH_HISTORY`.

---

## Final Answer

Adding a new checkout source type for a partner integration requires changes across **5 distinct layers**. Here is a comprehensive list of every file and location that must change:

---

### Layer 1: Core Model — Canonical Definition

**`/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`** (lines 139-175)

This is the single source of truth. You must:
1. Add a new class-level constant:
   ```python
   CHECKOUT_SOURCE_NEW_PARTNER = "new-partner"
   ```
2. Add it to `CHECKOUT_SOURCE_CHOICES`:
   ```python
   (CHECKOUT_SOURCE_NEW_PARTNER, "New Partner"),
   ```
The `checkout_source` field is a `CharField` with `max_length=50`, so the string value must be ≤50 characters.

---

### Layer 2: Source Detection Logic

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`**

Two functions need updating:

**`_determine_checkout_source()` (lines 810-865)**
This is the primary runtime detection function. If the partner integration comes through a distinct Shopify app ID, add a new branch before the `return Order.CHECKOUT_SOURCE_OTHER` fallback:
```python
if app_id == SHOPIFY_NEW_PARTNER_APP_ID:
    return Order.CHECKOUT_SOURCE_NEW_PARTNER
```
If it arrives via a Shopify custom attribute (like `viome-webhook` or `provider-portal`), you don't modify this function — detection happens via the custom attribute override at lines 598-601.

**`/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`** (lines 323-342)

If the partner has a distinct Shopify app ID, add a new constant:
```python
SHOPIFY_NEW_PARTNER_APP_ID = <app_id_integer>
```
Then import it in `ecomm/utils.py` (around lines 61-76 where other app ID constants are imported).

---

### Layer 3: Application-Specific Source Injection Points

These are the places in business logic where the new `checkout_source` value would be set if the partner sends it as a Shopify custom attribute or if your application sets it programmatically:

**`/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py`** (line 189)
Reference pattern — Viome sets `checkout_source` as a Shopify custom attribute:
```python
ShopifyCustomAttribute(key="checkout_source", value=Order.CHECKOUT_SOURCE_VIOME)
```
If the new partner integration sets this custom attribute similarly, you would add analogous code in the partner's service file.

**`/Users/albertgwo/Work/evvy/backend/ecomm/shopify/shopify.py`** (lines 100-102)
Sets a default `CHECKOUT_SOURCE_INTERNAL_SITE` if no `checkout_source` attribute is present — no changes needed but be aware the default could override partner attributes if the partner attribute key is missing.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py`** (line 199)
Reference pattern for provider integration — sets `checkout_source` in the custom attributes dict sent to Shopify.

---

### Layer 4: Downstream Business Logic That Branches on Source

Any new partner-specific routing or behavior requires reviewing these locations:

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`**
- `cart_requires_consult()` (lines 2629-2667): Currently branches only on `CHECKOUT_SOURCE_HEALTH_HISTORY`. If the new partner checkout should skip or require a consult under special conditions, add a branch here.
- `_process_shopify_order_impl()` (lines 1851-1854): Checks `CHECKOUT_SOURCE_VAGINITIS_INTAKE` to flag cross-sell orders. If the new partner source should also trigger such logic, add a check.
- Lines 1652-1654: Magic link / provider-portal assignment. Reference for pattern.

**`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`** (line 409)
Checks `CHECKOUT_SOURCE_HEALTH_HISTORY` in task processing — review if the new source requires analogous task-level handling.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`** (lines 502-534)
Routes consult creation logic based on `checkout_source` value (`vaginitis-intake`, `ungated-rx-intake`). If the new partner checkout creates consults differently, update routing here.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`** (lines 128-130)
Checks `CHECKOUT_SOURCE_UNGATED_RX_INTAKE` and `CHECKOUT_SOURCE_VAGINITIS_INTAKE` for order display logic.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py`** (lines 817, 885)
Sets `CHECKOUT_SOURCE_HEALTH_HISTORY` and `CHECKOUT_SOURCE_RETEST_UPSELL` in checkout payloads from specific user flows.

**`/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py`** (lines 491-530)
Exposes `is_checkout_source_health_context` — a derived boolean. If the new partner source needs a similar derived flag, add it here.

**`/Users/albertgwo/Work/evvy/backend/api/v1/serializers/order.py`** (line 65)
Includes `checkout_source` as a serialized field — no change needed, it will surface automatically.

---

### Layer 5: Backfill Script (if applicable)

**`/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`** (lines 68-117, 165-173)

The `APPLICATION_SPECIFIC_SOURCES` list (lines 165-173) controls which sources the backfill preserves vs. recalculates. If the new partner source is set via a Shopify custom attribute (not app_id), add it to `APPLICATION_SPECIFIC_SOURCES` so the backfill does not overwrite it:
```python
APPLICATION_SPECIFIC_SOURCES = [
    ...
    Order.CHECKOUT_SOURCE_NEW_PARTNER,
]
```

The mirror function `_determine_checkout_source_from_payload()` (lines 68-117) must be updated in parallel with `ecomm/utils._determine_checkout_source()` if the new source is app_id-based.

**`/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py`**
References `checkout_source` in the context of subscription refill backfilling — review if the new partner source could appear on subscription orders.

---

### Layer 6: Django Migration

**`/Users/albertgwo/Work/evvy/backend/ecomm/migrations/`**

A new migration file must be created (following the pattern of `0050_alter_order_checkout_source.py`). Django's `AlterField` migration adds the new choice to the database-level field definition. The migration will be auto-generated by running:
```bash
python manage.py makemigrations ecomm
```

Previous migration files that altered this field: `0025`, `0035`, `0039`, `0041`, `0042`, `0050`.

---

### Layer 7: Frontend

**`/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts`** (lines 27-31)

The TypeScript union type for `checkout_source` only lists 4 values. If the new partner checkout source will be surfaced to the frontend, add it:
```typescript
checkout_source?:
  | "vaginitis-upsell"
  | "ungated-rx-upsell"
  | "health-history"
  | "male-partner"
  | "new-partner";
```

**`/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx`** (lines 56-97)

The `switch(checkout_source)` block routes users to different intake flows post-purchase. If the new partner checkout requires a specific post-purchase redirect, add a `case "new-partner":` here.

**`/Users/albertgwo/Work/evvy/frontend/src/services/cart.ts`** (lines 86, 98)
Passes `checkout_source` to the cart checkout API — no type-level change needed if `checkout_source?: string`.

**`/Users/albertgwo/Work/evvy/frontend/src/utils/analytics/customEventTracking.js`** (lines 441, 1039-1104, 2072-2104)
Tracks `CHECKOUT_SOURCE` in analytics events. No code change required — it passes the value dynamically. However, verify that downstream analytics dashboards (Braze, etc.) account for the new value.

---

### Layer 8: Monitoring

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py`** (lines 61-62, 76-90)
Automatically records CloudWatch metrics `OrderValue/Source/{checkout_source}` and `Conversions/Source/{checkout_source}` — no code change needed, metrics will appear automatically for the new source value.

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`** (lines 69, 121-128)
Passes `checkout_source` as an event attribute — no change needed.

---

### Summary: Mandatory Changes Checklist

| File | Change Required |
|---|---|
| `backend/ecomm/models/order.py` | Add `CHECKOUT_SOURCE_NEW_PARTNER` constant + add to `CHECKOUT_SOURCE_CHOICES` |
| `backend/ecomm/constants.py` | Add `SHOPIFY_NEW_PARTNER_APP_ID` (if app_id-based detection) |
| `backend/ecomm/utils.py` | Add branch in `_determine_checkout_source()` (if app_id-based) |
| `backend/ecomm/migrations/` | Create new `AlterField` migration via `makemigrations` |
| `backend/scripts/backfill_order_checkout_sources.py` | Add to `APPLICATION_SPECIFIC_SOURCES` + update `_determine_checkout_source_from_payload()` |
| `frontend/src/types/orders.ts` | Add new value to `checkout_source` union type (if frontend-visible) |
| `frontend/src/pages/loadingOrder.tsx` | Add `case` in post-purchase routing switch (if partner needs specific redirect) |

### Conditional / Review-Required Locations

| File | Review If |
|---|---|
| `backend/ecomm/utils.py::cart_requires_consult()` | Partner checkout has special consult requirements |
| `backend/api/v1/views/consult.py` | Partner consult creation follows a different path |
| `backend/api/v1/views/orders.py` | Partner orders need different display logic |
| `backend/ecomm/tasks.py` | Partner orders need task-level special handling |
| `backend/api/v1/serializers/consult.py` | A new derived boolean flag is needed for the partner source |
| New partner service file (e.g., `ecomm/services/new_partner.py`) | Partner integration sends `checkout_source` as Shopify custom attribute |
| `backend/ecomm/admin.py` | Admin filtering on the new source (currently filters on `cross_sell_order__checkout_source`) |
