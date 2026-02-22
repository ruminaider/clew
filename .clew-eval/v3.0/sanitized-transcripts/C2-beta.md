# Stripe API Call Search - Complete Transcript

## Task
Find all Stripe API calls in the codebase. List each call site with the Stripe API method being called and the context in which it's used.

## Search Process

### Step 1: Initial Broad Search for "stripe"
**Command:** `search("stripe")`

**Result:** Found 1 file:
- `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

### Step 2: Search for Stripe Import Statements
**Commands:**
- `search("import stripe")`
- `search("from stripe")`

**Result:** No matches found in the codebase.

### Step 3: Examine the One File Containing "stripe"
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

**Findings:**
The word "stripe" appears only as a test data value for payment methods:
- Line 189: `payload_with_session["payment_gateway_names"] = ["stripe"]`
- Line 196: `self.assertEqual(call_kwargs["payment_method"], "stripe")`
- Line 202: `payload["payment_gateway_names"] = ["stripe", "paypal"]`
- Line 208: `self.assertEqual(call_kwargs["payment_method"], "stripe")`

These are NOT actual Stripe API calls - they are test fixtures simulating payment gateway names from Shopify webhooks.

### Step 4: Search for Stripe API Method Patterns
**Command:** `search("\.Customer\.|\.PaymentIntent\.|\.Charge\.|\.Subscription\.|\.Invoice\.|\.Refund\.|\.PaymentMethod\.")`

**Result:** No matches found.

### Step 5: Search for Stripe Environment Variables
**Command:** `search("STRIPE_SECRET|STRIPE_PUBLIC|STRIPE_API")`

**Result:** No matches found.

### Step 6: Check Package Dependencies
**Files checked:**
- `/Users/albertgwo/Work/evvy/frontend/package.json` - No Stripe packages
- `/Users/albertgwo/Work/evvy/internal-frontend/package.json` - No Stripe packages

**Python packages:** No evidence of `stripe` package in any requirements files.

### Step 7: Search for Alternative Payment Processing
**Command:** `search("payment\|billing\|charge\|refund")`

**Findings:** The codebase uses **Recharge** (a subscription billing platform), not Stripe:
- `subscriptions/service.py` - Contains `handle_charge_upcoming_webhook` and `_format_charge_upcoming_payload`
- `subscriptions/subscription_service.py` - Contains Recharge-related methods
- `subscriptions/tests/test_recharge.py` - Tests for Recharge API client
- Multiple references to Recharge customer management, webhooks, and portal links

### Step 8: Search in Documentation Files
**Command:** `search("stripe")`

**Result:** References to "stripe" found only in project documentation files (not part of evvy codebase):
- Documentation examples mentioning Stripe as a hypothetical search scenario
- Test plans and ADR documents

## Final Answer

**No Stripe API calls were found in the evvy codebase.**

### Summary of Findings:

1. **No Stripe SDK Integration:** The codebase does not import or use the Stripe Python library or Stripe.js.

2. **No Stripe API Environment Variables:** No configuration for Stripe API keys (STRIPE_SECRET_KEY, STRIPE_PUBLIC_KEY, etc.).

3. **String References Only:** The word "stripe" appears exactly 4 times, all in a single test file (`backend/ecomm/tests/test_order_monitoring.py`), where it's used as a string literal to simulate payment gateway names in test data.

4. **Alternative Payment System:** The codebase uses **Recharge** for subscription billing and payment processing, not Stripe. Evidence includes:
   - Recharge API client implementation
   - Recharge webhook handlers
   - Recharge customer management functionality
   - References to charge upcoming webhooks, customer portals, and subscription management

5. **Payment Gateway Integration:** The application appears to integrate with **Shopify** for e-commerce functionality, which handles payment processing. The payment gateway names (including "stripe") come from Shopify webhook payloads, indicating that Shopify (not the evvy backend) handles the actual payment processing with various gateways.

### Conclusion

There are **zero Stripe API calls** in the evvy codebase. The application uses Shopify for e-commerce checkout and Recharge for subscription management. Any Stripe payments that occur are processed entirely through Shopify's platform, with the evvy backend only receiving payment gateway names as metadata in webhook payloads.
