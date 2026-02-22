# C1 — Agent Alpha

Here is a complete list of all Django URL patterns that involve ecomm-related views in the Evvy codebase. The URL patterns are defined across the URL files at `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, `/Users/albertgwo/Work/evvy/backend/api/urls.py`, and `/Users/albertgwo/Work/evvy/backend/app/urls.py`. All `api/v1/` routes are rooted under the full path prefix `api/v1/`.

---

## Router-Registered ViewSets (via `SimpleRouter`)

These generate standard CRUD URL patterns automatically.

### 1. `CartViewSet` — `/api/v1/cart/`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`

| URL Pattern | Method | Action |
|---|---|---|
| `api/v1/cart/` | GET | list active carts |
| `api/v1/cart/` | POST | create or return existing active cart |
| `api/v1/cart/<pk>/` | GET | retrieve cart |
| `api/v1/cart/<pk>/items/` | POST, DELETE | add/remove items from cart |
| `api/v1/cart/<pk>/items/delete/` | POST | delete items from cart (alternative to DELETE) |
| `api/v1/cart/<pk>/checkout/` | POST | create Shopify checkout URL from cart |

The `CartViewSet` is deeply ecomm-integrated — it imports from `ecomm.models.cart`, `ecomm.services.cart`, `ecomm.monitoring`, and `ecomm.utils`.

### 2. `ProductViewSet` — `/api/v1/products/`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py`

| URL Pattern | Method | Action |
|---|---|---|
| `api/v1/products/` | GET | list care products |
| `api/v1/products/<slug>/` | GET | retrieve care product by slug |
| `api/v1/products/all-products/` | GET | returns both ecomm test products (by SKU) and all care products |

The `all-products` action explicitly queries `ecomm.models.product.Product` for standard test SKUs (`VHT_TEST_SKU`, `EXPANDED_TEST_SKU`, `UTI_TEST_SKU`, etc.) and serializes them as `EcommProductSerializer`.

### 3. `PDPConfigurationViewSet` — `/api/v1/pdp-configurations/`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py`

`PDPConfiguration` is an ecomm model imported directly from `ecomm.models`.

| URL Pattern | Method | Action |
|---|---|---|
| `api/v1/pdp-configurations/` | GET | list all active PDP configurations |
| `api/v1/pdp-configurations/<pk>/` | GET | retrieve single PDP configuration |
| `api/v1/pdp-configurations/by-care-product/<care_product_slug>/` | GET | get PDP config by care product slug |
| `api/v1/pdp-configurations/by-ecomm-product/<ecomm_product_sku>/` | GET | get PDP config by ecomm product SKU |
| `api/v1/pdp-configurations/by-slug/<slug>/` | GET | get PDP config by slug |
| `api/v1/pdp-configurations/featured/` | GET | get featured PDP configurations |

---

## Explicit `path()` URL Patterns

### 4. `EcommProductView` — `/api/v1/ecomm-products/<str:sku>/`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py`

```python
path(r"ecomm-products/<str:sku>/", views.EcommProductView.as_view(), name="ecomm-products")
```

| URL Pattern | Method | Description |
|---|---|---|
| `api/v1/ecomm-products/<sku>/` | GET | Fetch a single `ecomm.models.product.Product` by SKU. Public endpoint — no authentication required. |

### 5. `OrdersView` — `/api/v1/orders/`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`

Imports `ecomm.models.order.Order`, `ecomm.models.order.RelatedOrder`, `ecomm.services.cart`, and `ecomm.shopify.tasks`.

```python
path(r"orders/", views.OrdersView.as_view(), name="orders"),
path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail"),
path(r"orders/process", views.OrdersView.as_view(), name="orders-process"),
```

| URL Pattern | Method | Description |
|---|---|---|
| `api/v1/orders/` | GET | Get user's orders |
| `api/v1/orders/attach` | PUT | Attach order to user |
| `api/v1/orders/process` | POST | Process an order |

### 6. Shopify Webhook Views — `/api/v1/webhooks/shopify*`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

These are core ecomm ingestion endpoints for Shopify events.

```python
path(r"webhooks/shopify", views.shopify_webhook_view, name="shopify-webhook"),
path(r"webhooks/shopify-graphql", views.shopify_webhook_graphql_view, name="shopify-webhook-graphql"),
path(r"webhooks/shopify-fulfillment", views.shopify_fulfillment_webhook_view, name="shopify-fulfillment-webhook"),
```

| URL Pattern | Method | View Function | Description |
|---|---|---|---|
| `api/v1/webhooks/shopify` | POST | `shopify_webhook_view` | Receives Shopify order webhooks |
| `api/v1/webhooks/shopify-graphql` | POST | `shopify_webhook_graphql_view` | Receives Shopify GraphQL webhooks |
| `api/v1/webhooks/shopify-fulfillment` | POST | `shopify_fulfillment_webhook_view` | Receives Shopify fulfillment webhooks |

### 7. Recharge Webhook View — `/api/v1/webhooks/recharge`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

```python
path(r"webhooks/recharge", views.recharge_webhook_view, name="recharge-webhook"),
```

| URL Pattern | Method | View Function | Description |
|---|---|---|---|
| `api/v1/webhooks/recharge` | POST | `recharge_webhook_view` | Receives Recharge subscription billing webhooks |

### 8. Subscription Views — `/api/v1/subscription*` and `/api/v1/subscriptions*`

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/subscription.py`

Imports `ecomm.constants.RETEST_DISCOUNT_CODE`; manages Recharge subscription state.

```python
path(r"subscription/", views.get_subscription, name="subscription"),
path(r"subscriptions/", views.get_subscriptions, name="subscriptions"),
path(r"subscriptions/<str:subscription_id>/", views.get_subscription_by_id, name="subscription-by-id"),
path(r"subscriptions/sku/<str:sku>/", views.get_active_subscription_by_product_sku, name="subscription-by-product-sku"),
path(r"subscription/exists/", views.subscription_exists, name="subscription-exists"),
path(r"subscription/next-charge/", views.update_next_subscription_charge, name="subscription-next-charge"),
path(r"subscription/next-charge-with-discount/", views.update_next_subscription_charge_with_discount, name="subscription-next-charge-with-discount"),
path(r"subscription/portal-link/", views.portal_link, name="subscription-portal-link"),
path(r"subscription/swap/", views.swap_subscription, name="subscription-swap"),
```

| URL Pattern | Method | View | Description |
|---|---|---|---|
| `api/v1/subscription/` | GET | `get_subscription` | Get user's current subscription |
| `api/v1/subscriptions/` | GET | `get_subscriptions` | Get all subscriptions for user |
| `api/v1/subscriptions/<subscription_id>/` | GET | `get_subscription_by_id` | Get subscription by Recharge ID |
| `api/v1/subscriptions/sku/<sku>/` | GET | `get_active_subscription_by_product_sku` | Get active subscription by ecomm product SKU |
| `api/v1/subscription/exists/` | GET | `subscription_exists` | Check if user has a subscription |
| `api/v1/subscription/next-charge/` | POST/PUT | `update_next_subscription_charge` | Update next subscription charge date |
| `api/v1/subscription/next-charge-with-discount/` | POST/PUT | `update_next_subscription_charge_with_discount` | Update next charge with discount code |
| `api/v1/subscription/portal-link/` | GET | `portal_link` | Get Recharge customer portal URL |
| `api/v1/subscription/swap/` | POST | `swap_subscription` | Swap subscription product |

---

## Summary by Ecomm Concern

| Ecomm Domain | URL Prefix | View File |
|---|---|---|
| Ecomm products (by SKU) | `api/v1/ecomm-products/<sku>/` | `views/ecomm_products.py` |
| PDP configurations | `api/v1/pdp-configurations/` | `views/pdp_configuration.py` |
| Cart + checkout | `api/v1/cart/` | `views/cart.py` |
| Orders (Shopify) | `api/v1/orders/` | `views/orders.py` |
| All products (care + ecomm) | `api/v1/products/all-products/` | `views/products.py` |
| Shopify webhooks | `api/v1/webhooks/shopify*` | `views/webhooks.py` |
| Recharge webhooks | `api/v1/webhooks/recharge` | `views/webhooks.py` |
| Subscriptions (Recharge) | `api/v1/subscription*/` | `views/subscription.py` |
