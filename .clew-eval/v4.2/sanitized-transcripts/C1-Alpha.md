# C1: Django URL Patterns Involving Ecomm-Related Views

## Summary

All ecomm-related URL patterns live in a single file: `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`. The base URL is mounted at `api/v1/` (see `api/urls.py` → `app/urls.py`). Full URL prefix: `/api/v1/`.

---

## URL Patterns with Ecomm-Related Views

### 1. `EcommProductView` — Direct Ecomm Product Lookup

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, lines 86–90

```python
path(
    r"ecomm-products/<str:sku>/",
    views.EcommProductView.as_view(),
    name="ecomm-products",
),
```

- **Full URL:** `GET /api/v1/ecomm-products/<sku>/`
- **View:** `EcommProductView` (in `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py`)
- **Description:** Public endpoint (no auth required). Fetches an `ecomm.models.product.Product` by SKU and returns serialized data via `EcommProductSerializer`.

---

### 2. `CartViewSet` — Ecomm Cart Management

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, line 19

```python
router.register(r"cart", views.CartViewSet, basename="cart")
```

- **View:** `CartViewSet` (in `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`)
- **Description:** Manages ecommerce carts using `ecomm.models.cart.Cart` and `ecomm.services.cart.CartService`. Supports creating carts, adding/removing items, and initiating checkout.

Generated routes (SimpleRouter):

| URL Pattern | Method | Action |
|---|---|---|
| `/api/v1/cart/` | GET | list |
| `/api/v1/cart/` | POST | create (get/create active cart) |
| `/api/v1/cart/<pk>/` | GET | retrieve |
| `/api/v1/cart/<pk>/items/` | POST | add items to cart |
| `/api/v1/cart/<pk>/items/` | DELETE | remove items from cart |
| `/api/v1/cart/<pk>/items/delete/` | POST | remove items (POST-based delete) |
| `/api/v1/cart/<pk>/checkout/` | POST | create Shopify checkout URL |

---

### 3. `ProductViewSet` — Care Products with Ecomm Product Data

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, line 28

```python
router.register(r"products", views.ProductViewSet, basename="products")
```

- **View:** `ProductViewSet` (in `/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py`)
- **Description:** Returns `care.models.Product` records but includes ecomm product data (`ecomm.models.product.Product`) in the `all-products` action, serialized via `EcommProductSerializer`.

Generated routes:

| URL Pattern | Method | Action |
|---|---|---|
| `/api/v1/products/` | GET | list (care products) |
| `/api/v1/products/<slug>/` | GET | retrieve (care product by slug) |
| `/api/v1/products/all-products/` | GET | returns all ecomm test products + care products |

---

### 4. `PDPConfigurationViewSet` — Product Detail Page Configs (Ecomm-Linked)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, lines 39–43

```python
router.register(
    r"pdp-configurations",
    views.PDPConfigurationViewSet,
    basename="pdp-configurations",
)
```

- **View:** `PDPConfigurationViewSet` (in `/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py`)
- **Description:** ReadOnly viewset for `ecomm.models.PDPConfiguration`. Supports filtering by `ecomm_product_sku` query param and has a dedicated `by-ecomm-product/<sku>` action.

Generated routes:

| URL Pattern | Method | Action |
|---|---|---|
| `/api/v1/pdp-configurations/` | GET | list (filterable by `ecomm_product_sku` query param) |
| `/api/v1/pdp-configurations/<pk>/` | GET | retrieve |
| `/api/v1/pdp-configurations/by-ecomm-product/<ecomm_product_sku>/` | GET | get PDP config by ecomm product SKU |
| `/api/v1/pdp-configurations/by-care-product/<care_product_slug>/` | GET | get PDP config by care product slug |
| `/api/v1/pdp-configurations/by-slug/<slug>/` | GET | get PDP config by slug |
| `/api/v1/pdp-configurations/featured/` | GET | get featured PDP configs |

---

### 5. `OrdersView` — Ecomm Order Management

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, lines 76–78

```python
path(r"orders/", views.OrdersView.as_view(), name="orders"),
path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail"),
path(r"orders/process", views.OrdersView.as_view(), name="orders-process"),
```

- **View:** `OrdersView` (in `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`)
- **Description:** Uses `ecomm.models.order.Order` and `ecomm.services.cart` utilities. Handles fetching user orders, attaching orders to users, and processing unprocessed Shopify orders.

| URL Pattern | Method | Action |
|---|---|---|
| `/api/v1/orders/` | GET | list orders for authenticated user |
| `/api/v1/orders/attach` | PUT | attach order to current user (by checkout_id or order_number) |
| `/api/v1/orders/process` | POST | process unprocessed Shopify order synchronously |

---

## URL Mounting Chain

```
app/urls.py        path("api/", include("api.urls"))
api/urls.py        path("v1/", include(("api.v1.urls", "v1"), namespace="v1"))
api/v1/urls.py     All patterns above
```

All ecomm-related URLs are thus reachable under `/api/v1/`.

---

## Source Files Referenced

- `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` — URL registration
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py` — `EcommProductView`
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py` — `CartViewSet`
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py` — `ProductViewSet`
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py` — `PDPConfigurationViewSet`
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py` — `OrdersView`
- `/Users/albertgwo/Work/evvy/backend/api/urls.py` — API URL mounting
- `/Users/albertgwo/Work/evvy/backend/app/urls.py` — Root URL conf
