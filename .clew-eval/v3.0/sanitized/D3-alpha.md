# D3 Alpha Transcript: Subscription Order Email Failure Investigation

**Task:** A user reported that their subscription order was processed successfully but no confirmation email was sent. Investigate the email sending pipeline to find where the failure might have occurred.

## Investigation Process

### 1. Initial Search - Subscription Order Email Handling

**Query:** `search("subscription order confirmation email")`

**Results:**
- Found `send_account_email()` in `/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py` (lines 93-101)
- This function calls ReCharge API to send account access emails
- Also found various order processing functions

### 2. Understanding send_account_email Function

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py:93-101`

```python
def send_account_email(self, recharge_customer_id: str) -> None:
    url = f"{self.BASE_URL}customers/{recharge_customer_id}/notifications"
    post_data = {"type": "email", "template_type": "get_account_access"}
    self._make_request(
        "POST",
        url,
        data=post_data,
        extra_headers={"Content-Type": "application/json"},
    )
```

**Key finding:** This function triggers ReCharge to send an account access email, but it's designed for account management, not order confirmations.

### 3. Traced Calls to send_account_email

**Query:** `search("code related to backend/subscriptions/recharge.py::RechargeAPIClient.send_account_email")`

**Result:** Only found class containment relationship - no actual callers in the codebase.

**Query:** `search("send_account_email(", mode="broad")`

**Finding:** The function appears ONLY in tests, not in production code. This suggests it's not being called during the normal subscription order flow.

### 4. Investigated Subscription Order Processing

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:369-445`

Found the `recharge_webhook_view()` function that handles subscription webhooks:
- Supports topics: subscription/created, subscription/cancelled, charge/upcoming
- Routes to `handle_subscription_webhook()` for subscription events

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py:66-124`

The `handle_subscription_webhook()` function:
```python
def handle_subscription_webhook(
    payload: Dict[Any, Any], send_braze_event: bool = True, topic: str | None = None
) -> bool:
    # ... extracts subscription data ...

    # Updates user profile attributes
    update_user_profile(
        user=user,
        alias_name=email,
        attributes={ACTIVE_SUBSCRIPTIONS: ",".join(active_skus) if active_skus else ""},
    )

    # Sends Braze event for analytics
    if send_braze_event:
        braze_event_name = _get_braze_event_for_subscription_topic(topic, subscription_data)
        if braze_event_name:
            track_event(
                user=user,
                event_name=braze_event_name,
                alias_name=email,
                properties=formatted_subscription_data,
            )
    return True
```

**Critical Finding:** This webhook handler ONLY:
1. Updates user profile attributes in Braze
2. Tracks analytics events to Braze
3. Does NOT send any confirmation emails

### 5. Investigated Charge Processing

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py:26-63`

The `handle_charge_upcoming_webhook()` function:
```python
def handle_charge_upcoming_webhook(payload: Dict[Any, Any]) -> bool:
    # ... extracts charge data ...

    track_event(
        user=user,
        event_name=BrazeEventName.SUBSCRIPTION_NEXT_CHARGE_UPCOMING,
        alias_name=email,
        properties=formatted_charge_data,
    )

    return True
```

**Finding:** This also ONLY tracks events to Braze - no email sending.

### 6. Searched for Email Configuration

**Query:** `search("shopify confirmation email notification")`

Found that Shopify has a `send_gift_card_notification()` function and references to `notify_customer` parameters, but nothing specific to subscription order confirmations.

## Root Cause Analysis

### The Failure Path

The subscription order email failure path can be traced as follows:

1. **Order Processing:**
   - Customer completes subscription purchase through Shopify/ReCharge
   - ReCharge sends webhook to backend (`/webhooks/recharge/`)
   - Webhook is verified and routed based on topic

2. **Webhook Handling:**
   - For `subscription/created`: Routes to `handle_subscription_webhook()`
   - For `charge/upcoming`: Routes to `handle_charge_upcoming_webhook()`

3. **Missing Email Step:**
   - **CRITICAL GAP:** Neither webhook handler calls any email sending function
   - They only update Braze analytics and user profiles
   - No call to `send_account_email()` or any transactional email system

4. **Expected Email Source:**
   - The system appears to rely on **Shopify or ReCharge** to send confirmation emails
   - The backend does NOT implement its own confirmation email logic for subscriptions

### Potential Failure Points

1. **ReCharge Email Configuration:**
   - ReCharge may not be configured to send order confirmation emails
   - Email template `get_account_access` may not be set up or enabled
   - ReCharge customer notification settings may be disabled

2. **Shopify Email Settings:**
   - Shopify confirmation emails may be disabled for subscription orders
   - Email templates may not be configured for the subscription product type

3. **Missing Integration:**
   - The backend SHOULD call `send_account_email()` after successful webhook processing
   - Currently, `send_account_email()` exists but is never invoked in production code
   - This is a **missing implementation** rather than a bug in existing code

4. **Event-Driven Email Dependency:**
   - The system may rely on Braze to trigger emails based on events
   - If Braze integration is broken or email campaigns are not set up, no emails will be sent

## Recommendations

### Immediate Fix Options

1. **Call send_account_email() in webhook handlers:**
   ```python
   # In handle_subscription_webhook() after successful processing:
   if topic == TOPIC_SUBSCRIPTION_CREATED:
       recharge_client = RechargeAPIClient()
       recharge_customer_id = subscription_data.get('customer_id')
       if recharge_customer_id:
           recharge_client.send_account_email(recharge_customer_id)
   ```

2. **Verify ReCharge Settings:**
   - Check ReCharge dashboard for email notification settings
   - Ensure "Order Confirmation" emails are enabled
   - Verify email templates are configured

3. **Check Braze Campaign Configuration:**
   - Verify that Braze has campaigns set up to send emails on `SUBSCRIPTION_CREATED` events
   - Check that email delivery is not blocked or failing

### Architecture Concerns

The current architecture has a **separation of concerns issue:**
- Analytics tracking is in the backend (Braze events)
- Email sending is delegated to external systems (ReCharge/Shopify)
- There's no explicit email sending in the subscription flow
- `send_account_email()` exists but is orphaned (no callers)

This creates fragility - if ReCharge or Shopify fail to send emails, there's no fallback.

## Summary

**The email failure occurred because:**
1. The subscription webhook handlers (`handle_subscription_webhook`, `handle_charge_upcoming_webhook`) only track analytics events to Braze
2. They do NOT call any email sending functions
3. The system relies entirely on ReCharge or Shopify to send confirmation emails
4. If those external systems fail to send emails (misconfiguration, API issues), there's no backup mechanism

**The specific failure path:**
```
Subscription Order Placed
    ↓
ReCharge Webhook Received
    ↓
handle_subscription_webhook() called
    ↓
Braze event tracked ✓
User profile updated ✓
Email sent ✗ (NOT IMPLEMENTED)
    ↓
No confirmation email received by customer
```

**The fix requires:**
- Either: Integrate `send_account_email()` into the webhook handlers
- Or: Verify and fix ReCharge/Shopify email configuration
- Or: Set up Braze email campaigns to trigger on subscription events
