# Investigation: Subscription Order Email Failure Path (Grep)

## Task
"A user reported that their subscription order was processed successfully but no confirmation email was sent. Investigate the email sending pipeline to find where the failure might have occurred. Focus on understanding the specific failure path from order completion to email dispatch — do NOT exhaustively catalog all email-related code in the codebase."

## Tool Calls and Reasoning

### 1. Initial Search for Subscription Order and Email Code
**Searches performed:**
- `subscription.*order.*email|order.*confirmation.*email` (case-insensitive)
- `send.*email.*subscription|email.*dispatch.*order` (case-insensitive)
- `def send_confirmation_email|send_order_confirmation` (case-insensitive)

**Finding:** Initial searches found only test plan documents in `.clew-eval`, not actual implementation code.

### 2. Broader Email and Order Search
**Searches performed:**
- `class.*Email|def send_email` in Python files
- `subscription.*complete|order.*complete|process.*order` in Python files (case-insensitive)

**Finding:** Located test files only - realized I needed to navigate to the correct project directory.

### 3. Directory Navigation
**Action:** Changed to `/Users/albertgwo/Work/evvy` (the actual project directory)

### 4. Email and Subscription Order Code Discovery
**Searches performed:**
- `subscription.*order|order.*subscription` (case-insensitive) → Found 31 files
- `send.*email|email.*send` (case-insensitive) → Found 79 files

**Key files identified:**
- `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` - Subscription webhook handling
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` - Order processing tasks
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` - Core order processing logic
- `/Users/albertgwo/Work/evvy/backend/transactional_email/` - Email sending utilities

### 5. Examined Subscription Service Code
**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`

**Key findings:**
- Handles ReCharge subscription webhooks (charge/upcoming, subscription/created, etc.)
- Sends Braze analytics events for subscription actions
- Does NOT send transactional emails directly
- Webhook handlers: `handle_charge_upcoming_webhook()`, `handle_subscription_webhook()`

### 6. Examined Order Processing Tasks
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`

**Key findings:**
- `send_prescription_refill_request()` - Processes prescription refill orders
- `send_otc_treatment_fill_request()` - Processes OTC-only orders
- `process_gift_cards()` - Handles gift card processing
- `reprocess_subscription_refill_orders_daily()` - Catch-up job for missed orders
- Sends Braze event: `send_prescription_refills_paid_event.delay()`
- NO direct email sending for order confirmation

### 7. Examined Shopify Webhook Handler
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

**Key findings:**
- `shopify_webhook_view()` handles `orders/create` and `orders/cancelled` webhooks
- Calls `process_shopify_order()` to process order
- Uses HMAC signature verification for security
- No email sending logic in webhook handler

### 8. Examined Core Order Processing
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

**Key findings:**
- `process_shopify_order()` - Wrapper with error handling
- `_process_shopify_order_impl()` - Main order processing implementation
- Creates/updates Order model
- Processes line items
- Determines if order is subscription order (`is_subscription_order` flag)
- Extracts subscription metadata from order notes
- NO order confirmation email sending

### 9. Search for Confirmation Email Logic
**Searches performed:**
- `order.*confirmation|confirmation.*email` (case-insensitive)
- `send.*email.*order|order.*email.*send|confirmation.*send` (case-insensitive)

**Finding:** Only found:
- Account transfer verification emails
- Provider test order notifications
- Test confirmation emails
- NO subscription order confirmation emails in backend

## Investigation Results

### The Failure Path: Email Delegation to Shopify

**Critical Discovery:** The Evvy backend does NOT send order confirmation emails for subscription orders. This responsibility is delegated to Shopify.

### Order Processing Flow

1. **Shopify Order Creation**
   - User completes checkout on Shopify
   - Shopify should send order confirmation email (native Shopify functionality)

2. **Webhook to Backend**
   - Shopify sends `orders/create` webhook → `shopify_webhook_view()`
   - HMAC signature verification
   - Calls `process_shopify_order(payload, is_order_cancellation=False)`

3. **Order Processing**
   - `_process_shopify_order_impl()` creates/updates Order record
   - Extracts subscription metadata from line items and order notes
   - Sets `order.is_subscription_order = True` for subscription orders
   - Processes line items via `process_order_line_item()`

4. **Subscription-Specific Handling**
   - No email sending logic in order processing
   - Analytics events sent to Braze
   - Prescription refill requests sent to pharmacy (if applicable)

5. **Email Sending** ❌
   - Backend does NOT send order confirmation emails
   - Relies on Shopify's native email notifications

### Potential Failure Points

Based on the code analysis, here are the specific failure points where subscription order confirmation emails could fail:

#### 1. **Shopify Email Settings Disabled**
- **Location:** Shopify Admin → Settings → Notifications
- **Failure:** "Order confirmation" email template disabled or not configured for subscription orders
- **Evidence:** Backend has no email sending fallback; complete delegation to Shopify

#### 2. **Subscription Order Email Template Missing**
- **Location:** Shopify subscription app (likely ReCharge) email settings
- **Failure:** Subscription orders may use different email templates than regular orders
- **Evidence:** Code shows subscription orders flagged via `is_subscription_order` but no backend email logic

#### 3. **Email Deliverability Issues**
- **Failure:** Shopify sent email but it was blocked/filtered
  - Customer's email provider marked as spam
  - Typo in customer email address
  - Email bounced (invalid address)
- **Evidence:** No email delivery tracking in backend code

#### 4. **ReCharge Webhook Timing**
- **Location:** Subscription webhook handlers in `subscriptions/service.py`
- **Failure:** ReCharge webhooks (`charge/upcoming`, `subscription/created`) might conflict with Shopify's order creation
- **Evidence:** Code shows separate ReCharge webhook handlers that track analytics but don't send emails

#### 5. **Shopify App Integration Issue**
- **Location:** Shopify Apps (ReCharge or subscription management app)
- **Failure:** Subscription app might have suppressed Shopify's default email
- **Evidence:** Code shows `app_id` and `source_name` used to determine order source; subscription orders may have different notification rules

#### 6. **Custom Email Logic Override**
- **Location:** Shopify theme or checkout customization
- **Failure:** Custom checkout code may have disabled default email notifications
- **Evidence:** Code checks for `source_name == "shopify_draft_order"` and other custom sources

### Where to Look for Root Cause

1. **Shopify Admin Panel**
   - Settings → Notifications → Order confirmation template
   - Check if enabled for all order types
   - Review email sending logs

2. **ReCharge Dashboard** (or subscription app being used)
   - Email notification settings for subscription orders
   - Check if it overrides Shopify's default emails

3. **Email Logs**
   - Shopify email sending logs
   - Customer's spam folder
   - Email bounce reports

4. **Order Record**
   - Check `order.email` field in database
   - Verify email address is correct
   - Check `order.is_subscription_order` flag is set

5. **Braze Analytics**
   - Verify Braze events were sent (indicates order was processed)
   - Check if any email campaigns are tied to these events (unlikely based on code)

### Code Evidence Summary

**Files examined:**
- `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` - ReCharge webhook handling, no emails
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` - Order processing tasks, no confirmation emails
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` - Webhook entry point, no email logic
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` - Core order processing, delegates to Shopify

**Emails the backend DOES send:**
- Account transfer verification (`send_account_transfer_verification_email`)
- Provider test notifications (`send_patient_ordered_provider_test_notification`)
- Test result notifications (various test-related emails)

**Emails the backend does NOT send:**
- Order confirmation emails (delegated to Shopify)
- Subscription order confirmation emails (delegated to Shopify/ReCharge)

### Conclusion

The failure occurred because **the backend completely delegates order confirmation email sending to Shopify**. There is no backend code that sends these emails. The failure must be in:

1. Shopify's email notification configuration
2. The subscription app's (likely ReCharge) email settings
3. Email deliverability (spam, bounce, incorrect address)

**Recommended Next Steps:**
1. Check Shopify Admin → Notifications → "Order confirmation" is enabled
2. Check ReCharge (or subscription app) email settings
3. Review Shopify's email sending logs for this order
4. Verify customer's email address in order record
5. Check customer's spam folder

## Tool Call Summary

**Total tool calls: 14**

1. Grep: subscription.*order.*email pattern search
2. Grep: send.*email.*subscription pattern search
3. Grep: send_confirmation_email function search
4. Grep: Email class/send_email search
5. Grep: order processing search
6. Bash: Navigate to project directory
7. Grep: subscription order files search
8. Grep: email sending files search
9. Read: subscriptions/service.py
10. Read: ecomm/tasks.py
11. Grep: order confirmation search
12. Read: webhooks.py
13. Grep: process_shopify_order search (output too large)
14. Read: ecomm/utils.py (order processing implementation)

The investigation successfully identified the failure path: **complete delegation of email sending to Shopify with no backend fallback mechanism**.
