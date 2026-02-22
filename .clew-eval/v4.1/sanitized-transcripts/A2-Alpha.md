# A2 — Agent Alpha

## Comprehensive Checkout Source Change Guide

Adding a new checkout source type for a partner integration requires changes across the following files:

---

### 1. Core Model Definition (REQUIRED — primary source of truth)

**`/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`** (lines 139-175)

This is where all source constants and the `CHECKOUT_SOURCE_CHOICES` tuple live. You must:
- Add a new constant, e.g. `CHECKOUT_SOURCE_PARTNER_X = "partner-x"`
- Add it to `CHECKOUT_SOURCE_CHOICES` with a human-readable label
- The `checkout_source` field itself (`max_length=50`) does not need changes unless the new slug exceeds 50 characters

```python
CHECKOUT_SOURCE_PARTNER_X = "partner-x"   # add here
CHECKOUT_SOURCE_CHOICES = (
    ...
    (CHECKOUT_SOURCE_PARTNER_X, "Partner X"),  # add here
)
```

---

### 2. Django Database Migration (REQUIRED)

**`/Users/albertgwo/Work/evvy/backend/ecomm/migrations/`**

Each time `CHECKOUT_SOURCE_CHOICES` changes, Django requires an `AlterField` migration. The most recent one is `0050_alter_order_checkout_source.py`. You must generate a new migration:

```bash
python manage.py makemigrations ecomm
```

This produces a new file mirroring the pattern in `0050_alter_order_checkout_source.py` — an `AlterField` operation on `order.checkout_source` listing all choices.

---

### 3. Shopify App ID Constants (REQUIRED if source is Shopify-app-based)

**`/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`** (lines 323-332)

If the partner integration routes through a specific Shopify App ID, add a constant here alongside the existing ones:

```python
SHOPIFY_PARTNER_X_APP_ID = 1234567  # new entry
```

---

### 4. Order Source Determination Logic (REQUIRED)

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`** — `_determine_checkout_source()` function (lines 810-865)

This function maps Shopify `app_id`, `cart_id`, and `source_name` to a checkout source. Add a new branch in priority order:

```python
if app_id == SHOPIFY_PARTNER_X_APP_ID:
    return Order.CHECKOUT_SOURCE_PARTNER_X
```

Also update the import at the top of the file (lines 59-77) to import the new constant from `ecomm.constants`.

---

### 5. Shopify Checkout Custom Attribute Fallback (CONDITIONAL)

**`/Users/albertgwo/Work/evvy/backend/ecomm/shopify/shopify.py`** (lines 96-103)

If the partner creates Shopify orders and you want to set the source via a custom attribute (as opposed to app ID detection), ensure the `checkout_source` key is included in `custom_attributes` before calling Shopify's draft order API. The existing fallback to `CHECKOUT_SOURCE_INTERNAL_SITE` at line 102 applies when no source is set.

---

### 6. Cart Service — Default Source Override (CONDITIONAL)

**`/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py`** (lines 597-599)

If the partner uses the internal cart checkout flow:

```python
if "checkout_source" not in custom_attributes:
    custom_attributes["checkout_source"] = Order.CHECKOUT_SOURCE_INTERNAL_SITE  # replace or condition
```

If the new source should apply in specific contexts, this default may need adjusting.

---

### 7. Cart Checkout API View (CONDITIONAL)

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`** (lines 132-171)

The cart checkout view passes `checkout_source` from the request body through to `custom_attributes`. If the partner integration triggers checkout from a specific frontend path, review whether a new source value needs to be forwarded here. No structural change needed if the partner sends `checkout_source` in the request body — it flows through automatically.

---

### 8. Order Processing Logic — Business Logic Branches (REVIEW for new behavior)

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`** (line 1853):
```python
is_vaginitis_upsell_order = (
    order.checkout_source == Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE ...
)
```

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`** (line 2653):
```python
if checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
```

**`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`** (line 409):
```python
if order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
```

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`** (lines 128-131):
```python
if order.checkout_source in [
    Order.CHECKOUT_SOURCE_UNGATED_RX_INTAKE,
    Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE,
]:
```

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`** (lines 516, 532-534) — multiple branch points on source value.

Determine whether the new partner source requires any special downstream order processing behavior (consult creation, prescription routing, etc.) and add branches accordingly.

---

### 9. Backfill Script — Application-Specific Sources List (REQUIRED)

**`/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`** (lines 163-169)

The `APPLICATION_SPECIFIC_SOURCES` list controls which checkout sources are preserved and not overwritten when reprocessing orders. If the new partner source is set via a custom attribute (not app ID), add it here:

```python
APPLICATION_SPECIFIC_SOURCES = [
    Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE,
    ...
    Order.CHECKOUT_SOURCE_PARTNER_X,  # add here
]
```

Also update `_determine_checkout_source_from_payload()` (line 68) to handle the new app ID if applicable.

---

### 10. Frontend TypeScript Type (REQUIRED if frontend-facing)

**`/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts`** (lines 27-31)

The `Order` type has a `checkout_source` union type literal. Add the new value:

```typescript
checkout_source?:
  | "vaginitis-upsell"
  | "ungated-rx-upsell"
  | "health-history"
  | "male-partner"
  | "partner-x";  // add here
```

---

### 11. Frontend Cart Service (REVIEW)

**`/Users/albertgwo/Work/evvy/frontend/src/services/cart.ts`** (lines 82-99)

The `checkoutSource` parameter is passed through to the backend API. If the partner integration triggers checkout from a new frontend page or hook, ensure the correct source string is passed. No structural change needed if using the existing parameter pattern.

---

### 12. Monitoring and Metrics (AUTOMATIC — no changes needed)

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py`** (lines 61-62, 89-90)
**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/utils.py`** (lines 46, 100)
**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`** (lines 69, 121-128)

These use `getattr(order, "checkout_source", None)` and pass the string value directly to New Relic metrics. No code changes are needed — the new source value will automatically produce metrics under `OrderValue/Source/partner-x` and `Conversions/Source/partner-x`.

---

### 13. Admin Interface (OPTIONAL)

**`/Users/albertgwo/Work/evvy/backend/ecomm/admin.py`** (line 227)
`list_filter = ("cross_sell_order__checkout_source",)` — automatically includes the new value since it uses the field's choices.

**`/Users/albertgwo/Work/evvy/backend/providers/admin.py`** (lines 34-40) — the `provider_checkout_source` display method reads directly from the order; no changes needed.

---

### Summary Checklist

| File | Change Type | Required? |
|---|---|---|
| `backend/ecomm/models/order.py` | Add constant + tuple entry | Yes |
| `backend/ecomm/migrations/` | New `AlterField` migration | Yes |
| `backend/ecomm/constants.py` | Add Shopify App ID constant | If app-ID based |
| `backend/ecomm/utils.py` (`_determine_checkout_source`) | Add branch + import | If app-ID based |
| `backend/ecomm/utils.py` (business logic branches) | Add/review conditional branches | If special behavior |
| `backend/ecomm/shopify/shopify.py` | Review custom attribute fallback | If attribute-based |
| `backend/ecomm/services/cart.py` | Review default source logic | If using cart flow |
| `backend/api/v1/views/cart.py` | Review passthrough | Likely no change |
| `backend/api/v1/views/consult.py` | Review conditional branches | If new behavior needed |
| `backend/api/v1/views/orders.py` | Review routing logic | If new behavior needed |
| `backend/ecomm/tasks.py` | Review order processing branches | If new behavior needed |
| `backend/scripts/backfill_order_checkout_sources.py` | Add to preserved sources list | If attribute-based |
| `frontend/src/types/orders.ts` | Add to union type | If frontend-facing |
| `frontend/src/services/cart.ts` | Pass correct source string | If frontend-facing |
