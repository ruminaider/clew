# C2: Stripe API Calls — Search Results

## Summary

After an exhaustive search of the codebase using both search and direct text search across all Python, TypeScript, JavaScript, and configuration files, **the evvy codebase does not contain any direct Stripe API calls**.

The Stripe Python library (`stripe`) is not imported anywhere in the codebase. There are no calls to Stripe API methods such as `stripe.PaymentIntent.create()`, `stripe.Customer.create()`, `stripe.checkout.Session.create()`, `stripe.Subscription.create()`, or any other Stripe SDK methods.

## What Was Found

### 1. "stripe" as a Payment Gateway Name String

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

Stripe appears as a string value in Shopify order payloads under `payment_gateway_names`. This is Shopify's internal identifier for the Stripe payment gateway, not a direct Stripe API call.

**Line 619-622** — Reading payment gateway name from Shopify order payload:
```python
payment_gateway_names = payload.get("payment_gateway_names", [])
if payment_gateway_names and not is_order_cancellation:
    payment_method = payment_gateway_names[0] if payment_gateway_names else "unknown"
    payment_amount = float(total_line_items_price) if total_line_items_price else 0.0
```

**Line 781** — Passing payment method to checkout tracking:
```python
track_checkout_completion(
    order=order,
    session_id=session_id,
    payment_method=payload.get("payment_gateway_names", [None])[0],
)
```

**Line 171-172** — Checking for gift card payment gateway:
```python
payment_gateway_names = payload.get("payment_gateway_names", [])
if "gift_card" in payment_gateway_names:
    return True
```

### 2. "stripe" in Test Assertions

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

The test file uses `"stripe"` as a mock value for `payment_gateway_names` in Shopify webhook payloads to verify that monitoring correctly records the payment method.

**Line 189, 196** — Testing that "stripe" payment method is passed through:
```python
payload_with_session["payment_gateway_names"] = ["stripe"]
# ...
self.assertEqual(call_kwargs["payment_method"], "stripe")
```

**Line 202, 208** — Testing multiple payment gateways (first one wins):
```python
payload["payment_gateway_names"] = ["stripe", "paypal"]
# ...
self.assertEqual(call_kwargs["payment_method"], "stripe")
```

### 3. Shopify utils.py — Payment Gateway Names Extracted from GraphQL

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/utils.py` (line 134)

```python
"payment_gateway_names": order.get("paymentGatewayNames", []),
```

This extracts the `paymentGatewayNames` field from a Shopify GraphQL order response, which may contain `"stripe"` when Stripe is the payment processor — but again this is not a direct Stripe API call.

## Conclusion

The evvy codebase processes payments exclusively through Shopify's checkout flow. When a customer pays via Stripe on Shopify, the only evidence in the backend is the string `"stripe"` appearing in the `payment_gateway_names` field of Shopify order webhook payloads. The backend reads this field to track which payment method was used for analytics/monitoring purposes, but never calls the Stripe API directly.

- The `stripe` Python package is not in `requirements.txt`.
- No `import stripe` or `from stripe import` statements exist anywhere.
- No Stripe API keys are referenced in `settings.py` or `.env.example`.
- No Stripe webhook endpoints exist in any `urls.py`.

The payment integration is: **Customer → Shopify Checkout (uses Stripe) → Shopify sends order webhook → evvy backend processes Shopify webhook**.
