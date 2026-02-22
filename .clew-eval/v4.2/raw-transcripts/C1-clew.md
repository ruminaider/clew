# C1: Ecomm-Related Django URL Patterns

## Summary

The ecomm-related URL patterns are primarily located in `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`. There is no standalone `ecomm/urls.py` — ecomm URLs are defined as part of the main API v1 URL configuration. The URL hierarchy is:

```
/api/v1/  (from backend/api/urls.py → api/v1/urls.py)
```

---

## All Ecomm-Related URL Patterns

### File: `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`

#### 1. Ecomm Products (Public Endpoint)

```python
path(
    r"ecomm-products/<str:sku>/",
    views.EcommProductView.as_view(),
    name="ecomm-products",
)
```

- **Full path:** `/api/v1/ecomm-products/<sku>/`
- **View:** `EcommProductView` (class-based, APIView)
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py`
- **Note:** Public endpoint — no authentication required. GET by SKU.

#### 2. Cart (ViewSet — CRUD)

```python
router.register(r"cart", views.CartViewSet, basename="cart")
```

- **Full path:** `/api/v1/cart/` (list/create), `/api/v1/cart/<pk>/` (retrieve/update/delete)
- **View:** `CartViewSet`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`

#### 3. Products (ViewSet — CRUD)

```python
router.register(r"products", views.ProductViewSet, basename="products")
```

- **Full path:** `/api/v1/products/`, `/api/v1/products/<pk>/`
- **View:** `ProductViewSet`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py`

#### 4. Orders (View — Multiple routes)

```python
path(r"orders/", views.OrdersView.as_view(), name="orders"),
path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail"),
path(r"orders/process", views.OrdersView.as_view(), name="orders-process"),
```

- **Full paths:** `/api/v1/orders/`, `/api/v1/orders/attach`, `/api/v1/orders/process`
- **View:** `OrdersView`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`

#### 5. Order Transfer Verification

```python
path(
    r"order-transfer-verification/",
    views.AccountOrderTransferVerification.as_view(),
    name="order-transfer-verification",
),
path(
    r"order-transfer-verification-confirm/",
    views.AccountOrderTransferConfirmVerification.as_view(),
    name="order-transfer-verification-confirm",
),
```

- **Full paths:** `/api/v1/order-transfer-verification/`, `/api/v1/order-transfer-verification-confirm/`
- **Views:** `AccountOrderTransferVerification`, `AccountOrderTransferConfirmVerification`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/account_order_transfer_verification.py`

#### 6. Provider Test Orders (ViewSet)

```python
router.register(
    r"provider-test-orders",
    views.ProviderTestOrderViewSet,
    basename="provider-test-orders",
)
```

- **Full paths:** `/api/v1/provider-test-orders/`, `/api/v1/provider-test-orders/<pk>/`
- **View:** `ProviderTestOrderViewSet`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py`

#### 7. Shopify Webhooks (Ecomm order processing)

```python
path(r"webhooks/shopify", views.shopify_webhook_view, name="shopify-webhook"),
path(
    r"webhooks/shopify-graphql",
    views.shopify_webhook_graphql_view,
    name="shopify-webhook-graphql",
),
path(
    r"webhooks/shopify-fulfillment",
    views.shopify_fulfillment_webhook_view,
    name="shopify-fulfillment-webhook",
),
```

- **Full paths:** `/api/v1/webhooks/shopify`, `/api/v1/webhooks/shopify-graphql`, `/api/v1/webhooks/shopify-fulfillment`
- **Views:** `shopify_webhook_view`, `shopify_webhook_graphql_view`, `shopify_fulfillment_webhook_view`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 82, 150, 175)
- **Note:** These process Shopify order events via `ecomm.utils.process_shopify_order` and `ecomm.utils.process_shopify_subscription_webhook`

#### 8. Recharge Webhook (Subscription/ecomm)

```python
path(r"webhooks/recharge", views.recharge_webhook_view, name="recharge-webhook"),
```

- **Full path:** `/api/v1/webhooks/recharge`
- **View:** `recharge_webhook_view`
- **Source:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (line 369)

#### 9. Subscriptions (ecomm product subscriptions)

```python
path(r"subscription/", views.get_subscription, name="subscription"),
path(r"subscriptions/", views.get_subscriptions, name="subscriptions"),
path(
    r"subscriptions/<str:subscription_id>/",
    views.get_subscription_by_id,
    name="subscription-by-id",
),
path(
    r"subscriptions/sku/<str:sku>/",
    views.get_active_subscription_by_product_sku,
    name="subscription-by-product-sku",
),
path(r"subscription/exists/", views.subscription_exists, name="subscription-exists"),
path(
    r"subscription/next-charge/",
    views.update_next_subscription_charge,
    name="subscription-next-charge",
),
path(
    r"subscription/next-charge-with-discount/",
    views.update_next_subscription_charge_with_discount,
    name="subscription-next-charge-with-discount",
),
path(r"subscription/portal-link/", views.portal_link, name="subscription-portal-link"),
path(r"subscription/swap/", views.swap_subscription, name="subscription-swap"),
```

- **Full paths:** `/api/v1/subscription/`, `/api/v1/subscriptions/`, `/api/v1/subscriptions/<subscription_id>/`, `/api/v1/subscriptions/sku/<sku>/`, `/api/v1/subscription/exists/`, `/api/v1/subscription/next-charge/`, `/api/v1/subscription/next-charge-with-discount/`, `/api/v1/subscription/portal-link/`, `/api/v1/subscription/swap/`
- **Views:** `get_subscription`, `get_subscriptions`, `get_subscription_by_id`, `get_active_subscription_by_product_sku`, `subscription_exists`, `update_next_subscription_charge`, `update_next_subscription_charge_with_discount`, `portal_link`, `swap_subscription`

#### 10. Lab Order Intake (ViewSet)

```python
router.register(r"lab-order-intake", views.LabOrderIntakeViewSet, basename="lab-order-intake")
```

- **Full paths:** `/api/v1/lab-order-intake/`, `/api/v1/lab-order-intake/<pk>/`
- **View:** `LabOrderIntakeViewSet`

---

## Admin URL (ecomm app)

### File: `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py`

The `OrderAdmin` class registers a custom admin URL via `get_urls()`:

```python
def get_urls(self):
    urls = super().get_urls()
    my_urls = [
        path("transfer-order-to-user/", self.attach_order_to_user),
    ]
    return my_urls + urls
```

- **Admin path:** `/admin/ecomm/order/transfer-order-to-user/`
- **View handler:** `OrderAdmin.attach_order_to_user` — attaches an order number to a user account.

---

## URL Routing Chain

```
/                        → backend/app/urls.py
/api/                    → backend/api/urls.py
/api/v1/                 → backend/api/v1/urls.py  (all ecomm patterns above)
/admin/ecomm/order/...   → ecomm/admin.py (OrderAdmin.get_urls)
```
