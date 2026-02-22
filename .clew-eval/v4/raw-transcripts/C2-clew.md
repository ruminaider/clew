# C2 Exploration Log

## Search 1: clew semantic search for "stripe API calls payment"
Searched with: `clew search "stripe API calls payment" --project-root /Users/albertgwo/Work/evvy --json`

Results returned checkout/payment-related code but nothing Stripe-SDK specific:
- `backend/api/tests/test_user_tests.py` - test_create_checkout (mocked, no Stripe SDK)
- `backend/ecomm/services/cart.py` - create_checkout (Shopify-based checkout)
- `backend/ecomm/monitoring/metrics.py` - log_payment_metrics (payment method logging)
- `backend/api/v1/views/consult.py` - checkout_url (consult checkout)
- `backend/api/v1/views/cart.py` - checkout (Shopify cart checkout)

None showed direct Stripe SDK usage.

## Search 2: grep for Python files importing stripe
Searched: `find /Users/albertgwo/Work/evvy/backend -name "*.py" | xargs grep -li "stripe"` (excluding venv and .worktrees)

**Result:** Only one file matched:
- `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

And that file only contains the string `"stripe"` as a string literal value in test payloads, not as an import or SDK call.

## Search 3: Case-insensitive grep for "stripe" across all Python files (excluding venv/worktrees/migrations)

```
find /Users/albertgwo/Work/evvy/backend -name "*.py" -not -path "*/venv/*" -not -path "*/.worktrees/*" | xargs grep -li "stripe\|Stripe\|STRIPE"
```

**Result:** Only `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

## Search 4: Search frontend TypeScript/JavaScript files for Stripe
Searched `grep -r "stripe\|Stripe" /Users/albertgwo/Work/evvy/frontend/src -l`

**Result:** No matches. Checked `package.json` — no Stripe npm package in frontend dependencies.

## Search 5: Check Python requirements for stripe package
Checked `backend/requirements.txt` and `backend/requirements.in`

**Result:** No `stripe` package in Python dependencies.

## Search 6: Check render.yaml for STRIPE environment variables
**Result:** No STRIPE_* environment variables defined.

## Search 7: Search all source files (Python + TS/JS) across entire project for "stripe"
```
grep -rn "stripe" /Users/albertgwo/Work/evvy --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" | grep -v venv | grep -v .worktrees | grep -v node_modules | grep -v migrations | grep -v static
```

**Result:** Only the 4 lines in `test_order_monitoring.py`:
- Line 189: `payload_with_session["payment_gateway_names"] = ["stripe"]`
- Line 196: `self.assertEqual(call_kwargs["payment_method"], "stripe")`
- Line 202: `payload["payment_gateway_names"] = ["stripe", "paypal"]`
- Line 208: `self.assertEqual(call_kwargs["payment_method"], "stripe")`

## Search 8: Inspect test_order_monitoring.py context (lines 180-219)

The "stripe" occurrences are in test assertions for `process_shopify_order()`. Stripe appears as a string value in `payment_gateway_names` — a field returned by the Shopify API indicating which payment processor handled the transaction. There is no Stripe SDK call here; Shopify handles the actual Stripe payment processing on its platform.

## Search 9: clew search for "stripe checkout payment method webhook"
Searched: `clew search "stripe payment intent webhook"`

Results pointed to Shopify and ReCharge webhooks, but nothing Stripe-specific.

## Search 10: Search for payment module / Stripe-specific patterns
Searched for `payment_intent`, `PaymentIntent`, `PaymentMethod`, and Stripe SDK patterns across backend Python files.

**Result:** No Stripe SDK usage found. All payment processing routes through Shopify (which internally may use Stripe as a payment gateway) and ReCharge (for subscriptions).

## Search 11: Search app settings and config files for STRIPE env vars
Checked `backend/app/settings.py`, `render.yaml`, `.env` patterns, YAML/TOML configs.

**Result:** No STRIPE_KEY, STRIPE_SECRET, or similar configuration found anywhere.

## Search 12: Search documentation for Stripe mentions
`grep -rn -i "stripe" /Users/albertgwo/Work/evvy/docs`

**Result:** No documentation references Stripe.

---

## Final Answer

**There are no Stripe API calls in the Evvy codebase.**

After an exhaustive search across all Python, TypeScript, and JavaScript source files (excluding venv, node_modules, .worktrees, and static assets), the word "stripe" appears in exactly one file, and not as an API call:

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

```python
# Line 189
payload_with_session["payment_gateway_names"] = ["stripe"]

# Line 196
self.assertEqual(call_kwargs["payment_method"], "stripe")

# Line 202
payload["payment_gateway_names"] = ["stripe", "paypal"]

# Line 208
self.assertEqual(call_kwargs["payment_method"], "stripe")
```

These are **test fixtures and assertions** — not Stripe API calls. They simulate a Shopify webhook payload where `payment_gateway_names` contains `"stripe"` as a string value, because Shopify's Orders API returns the payment processor name in that field. The actual Stripe transaction is processed invisibly by Shopify's payment infrastructure before the webhook fires.

### How payment processing actually works in this codebase

The Evvy backend does not integrate with Stripe directly. Instead:

1. **Shopify handles checkout and payment collection** — The `CartService.create_checkout()` method in `/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py` calls `shopify_client.get_checkout_url()` to create a Shopify-hosted checkout, which then handles payment (potentially via Stripe as a gateway on Shopify's side).

2. **Shopify webhooks report the payment gateway** — When an order is paid, Shopify sends a webhook to `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`. The `process_shopify_order()` function in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` reads `payment_gateway_names` (which may contain `"stripe"`, `"shopify_payments"`, `"paypal"`, etc.) purely for analytics/monitoring purposes via `log_payment_metrics()`.

3. **ReCharge handles subscriptions** — Recurring billing is managed by ReCharge (a Shopify app), not Stripe directly. The ReCharge client in `/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py` makes HTTP calls to the ReCharge API.

The `stripe` Python package is not in `backend/requirements.txt` or `backend/requirements.in`, there is no `import stripe` anywhere in the codebase, and there are no `STRIPE_API_KEY` or `STRIPE_SECRET_KEY` environment variables defined in `render.yaml` or `backend/app/settings.py`.

**Conclusion:** Stripe is used as an underlying payment network by Shopify, but Evvy does not make direct Stripe API calls. All payment processing is delegated to Shopify's checkout infrastructure and ReCharge's subscription management platform.
