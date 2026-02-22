# C1 — Agent Beta

## Django URL Patterns Involving Ecomm-Related Views

The primary URL file for these patterns is `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, registered under the prefix `api/v1/`. The full URL paths are `api/v1/<pattern>`. There is one dedicated ecomm-app view file at `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py`.

---

### Router-Registered ViewSets (ecomm-backed)

These are registered via `routers.SimpleRouter()` in `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` and generate standard REST CRUD URLs:

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/cart/` | `CartViewSet` | `api/v1/views/cart.py` |
| `api/v1/cart/<pk>/` | `CartViewSet` | `api/v1/views/cart.py` |
| `api/v1/products/` | `ProductViewSet` | `api/v1/views/products.py` |
| `api/v1/products/<pk>/` | `ProductViewSet` | `api/v1/views/products.py` |
| `api/v1/provider-test-orders/` | `ProviderTestOrderViewSet` | `api/v1/views/provider_test_orders.py` |
| `api/v1/provider-test-orders/<pk>/` | `ProviderTestOrderViewSet` | `api/v1/views/provider_test_orders.py` |
| `api/v1/pdp-configurations/` | `PDPConfigurationViewSet` | `api/v1/views/pdp_configuration.py` |
| `api/v1/pdp-configurations/<pk>/` | `PDPConfigurationViewSet` | `api/v1/views/pdp_configuration.py` |

---

### Explicit One-Off URL Patterns (ecomm-backed)

**Ecomm Products**

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/ecomm-products/<str:sku>/` | `EcommProductView` | `api/v1/views/ecomm_products.py` |

**Orders**

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/orders/` | `OrdersView` | `api/v1/views/orders.py` |
| `api/v1/orders/attach` | `OrdersView` | `api/v1/views/orders.py` |
| `api/v1/orders/process` | `OrdersView` | `api/v1/views/orders.py` |

**Order Transfer Verification**

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/order-transfer-verification/` | `AccountOrderTransferVerification` | `api/v1/views/account_order_transfer_verification.py` |
| `api/v1/order-transfer-verification-confirm/` | `AccountOrderTransferConfirmVerification` | `api/v1/views/account_order_transfer_verification.py` |

**Subscriptions (Recharge/ecomm-integrated)**

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/subscription/` | `get_subscription` | `api/v1/views/subscription.py` |
| `api/v1/subscriptions/` | `get_subscriptions` | `api/v1/views/subscription.py` |
| `api/v1/subscriptions/<str:subscription_id>/` | `get_subscription_by_id` | `api/v1/views/subscription.py` |
| `api/v1/subscriptions/sku/<str:sku>/` | `get_active_subscription_by_product_sku` | `api/v1/views/subscription.py` |
| `api/v1/subscription/exists/` | `subscription_exists` | `api/v1/views/subscription.py` |
| `api/v1/subscription/next-charge/` | `update_next_subscription_charge` | `api/v1/views/subscription.py` |
| `api/v1/subscription/next-charge-with-discount/` | `update_next_subscription_charge_with_discount` | `api/v1/views/subscription.py` |
| `api/v1/subscription/portal-link/` | `portal_link` | `api/v1/views/subscription.py` |
| `api/v1/subscription/swap/` | `swap_subscription` | `api/v1/views/subscription.py` |

**Webhooks (Shopify/ecomm)**

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/webhook/` | `webhook_view` | `api/v1/views/webhooks.py` |
| `api/v1/webhooks/shopify` | `shopify_webhook_view` | `api/v1/views/webhooks.py` |
| `api/v1/webhooks/shopify-graphql` | `shopify_webhook_graphql_view` | `api/v1/views/webhooks.py` |
| `api/v1/webhooks/shopify-fulfillment` | `shopify_fulfillment_webhook_view` | `api/v1/views/webhooks.py` |
| `api/v1/webhooks/recharge` | `recharge_webhook_view` | `api/v1/views/webhooks.py` |
| `api/v1/webhooks/viome` | `viome_webhook_view` | `api/v1/views/webhooks.py` |

**Checkout / Provider Magic Link**

| URL Pattern | View | View File |
|---|---|---|
| `api/v1/male-partner-checkout/` | `MalePartnerCheckoutView` | `api/v1/views/userconfig.py` |
| `api/v1/provider-test/<slug>/` (re_path) | `PublicProviderMagicLinkCheckout` | `api/v1/views/views.py` |

---

### Summary

There is exactly **one URL pattern explicitly named "ecomm"**: `api/v1/ecomm-products/<str:sku>/` -> `EcommProductView`. However, a much broader set of URL patterns involve ecomm-related views:

- **Cart**: `api/v1/cart/`
- **Products**: `api/v1/products/`, `api/v1/ecomm-products/<str:sku>/`, `api/v1/pdp-configurations/`
- **Orders**: `api/v1/orders/`, `api/v1/orders/attach`, `api/v1/orders/process`, `api/v1/order-transfer-verification/`, `api/v1/order-transfer-verification-confirm/`
- **Provider test orders**: `api/v1/provider-test-orders/`, `api/v1/provider-test/<slug>/`
- **Subscriptions**: 9 URL patterns under `api/v1/subscription(s)/...`
- **Webhooks**: `api/v1/webhooks/shopify`, `api/v1/webhooks/shopify-graphql`, `api/v1/webhooks/shopify-fulfillment`, `api/v1/webhooks/recharge`, `api/v1/webhooks/viome`, `api/v1/webhook/`
- **Checkout**: `api/v1/male-partner-checkout/`
