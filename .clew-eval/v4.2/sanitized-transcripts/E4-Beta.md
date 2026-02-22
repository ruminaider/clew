# Investigation: Subscription Order Confirmation Email Failure Path

## Summary

A subscription order can be processed successfully (payment captured, order created) but the confirmation email never reaches the user. The failure is **not a single point** but a pipeline with **three distinct silent-failure zones**. Here is the exact path and where it can fail silently.

---

## The Email Delivery Architecture

Subscription order confirmation emails are **not sent by the Django application directly**. They are triggered indirectly via a **ReCharge webhook → Braze event** chain. There is no Mandrill/transactional email call for "order confirmation" in the codebase. Confirmation emails are owned entirely by Braze (the marketing automation platform), which listens for events fired from the backend.

---

## The Full Pipeline

### Step 1: Shopify/ReCharge Order Created

When a subscription order is placed, Shopify fires a webhook to the backend. The order is processed in:

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`** (the main order processing function, around line 460–790)

The order gets `is_subscription_order = True` set, and then various post-processing tasks fire. Notably, **no confirmation email is sent here** — this entire file has no call to `send_templated_email` or any email-sending function for the order itself.

### Step 2: ReCharge Fires a `subscription/created` Webhook

ReCharge (the subscription billing platform) separately fires a webhook to:

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`** (lines 415–433)

```python
elif topic in [
    TOPIC_SUBSCRIPTION_ACTIVATED,
    TOPIC_SUBSCRIPTION_CANCELLED,
    TOPIC_SUBSCRIPTION_CREATED,
    ...
]:
    if topic in [
        TOPIC_SUBSCRIPTION_CREATED,
        TOPIC_SUBSCRIPTION_CANCELLED,
        TOPIC_SUBSCRIPTION_ACTIVATED,
        TOPIC_SUBSCRIPTION_SWAPPED,
    ]:
        send_braze_event = True
    success = handle_subscription_webhook(payload, send_braze_event, topic)
```

### Step 3: `handle_subscription_webhook` Fires a Braze Event

**`/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`** (lines 66–124)

```python
def handle_subscription_webhook(
    payload: Dict[Any, Any], send_braze_event: bool = True, topic: str | None = None
) -> bool:
    try:
        ...
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
    except Exception as e:
        logger.exception(f"Error processing subscription webhook: {str(e)}")
        return False
```

The `track_event` call routes to Braze via:

**`/Users/albertgwo/Work/evvy/backend/analytics/service.py`** (line 65–86):
```python
def track_event(...) -> Dict[str, Any] | None:
    try:
        ...
        if ANALYTICS_PROVIDER == "braze":
            return braze_track_user_event(...)
        ...
    except Exception as e:
        user_identifier = user.uuid if user else alias_name
        logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
        return None   # <-- SILENT FAILURE: returns None, caller never knows
```

Braze then triggers the "subscription confirmation" email campaign based on receiving the `subscription_created` event.

---

## The Three Silent Failure Points

### Failure Point 1: ReCharge Webhook Never Arrives (or is silently acknowledged)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 440–445)

```python
if success:
    logger.info("Successfully processed ReCharge webhook")
else:
    logger.error("Failed to process ReCharge webhook")

return HttpResponse(status=200)   # <-- Always returns 200 regardless of success
```

The webhook view **always returns HTTP 200** whether `handle_subscription_webhook` succeeded or not. If processing failed, ReCharge has no reason to retry because it received a 200 OK. The failure is logged as an error but the email is never sent and no retry occurs.

### Failure Point 2: `track_event` / Braze API Call Fails Silently

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/service.py` (lines 83–86)

```python
    except Exception as e:
        user_identifier = user.uuid if user else alias_name
        logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
        return None
```

If the Braze API call fails (network error, API key issue, rate limit, Braze outage), `track_event` returns `None`. The caller in `handle_subscription_webhook` does not check this return value at all — it just proceeds and returns `True` (success). The subscription webhook is marked as "processed successfully" but Braze never received the event, so no email is triggered.

The Braze client itself does have retry logic (`@retry(stop_max_attempt_number=3)` in `BrazeAPIClient._make_request`), but after 3 failures it raises, which is caught by `track_event`'s except block and swallowed.

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py` (lines 269–275)
```python
@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)
def _make_request(self, method: str, url: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    ...
    return make_request(method, url, json=data, headers=self.headers)
```

### Failure Point 3: User Not Found in the System

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` (lines 89–93)

```python
email = formatted_subscription_data.get("email")
user = User.objects.filter(email=email).first()
if not user:
    logger.error(f"User not found for subscription webhook: {email}")
    return False
```

If the email on the ReCharge subscription does not match any `User` record (e.g., the user signed up with a different email, or the account doesn't exist yet), the entire webhook handler returns `False` and nothing happens. No email is sent, and the webhook endpoint still returns 200 to ReCharge.

This can happen when:
- A user places a subscription order as a guest (no Evvy account yet)
- The user has changed their email address in Evvy but not in ReCharge
- There is a case-sensitivity mismatch (`User.objects.filter(email=email)` — note: NOT `email__iexact`)

---

## Key Architecture Observation

There is **no Mandrill/transactional email template for subscription order confirmation** in the codebase. Looking at:

- `/Users/albertgwo/Work/evvy/backend/transactional_email/constants.py` — no `TEMPLATE_SUBSCRIPTION_CONFIRMATION` or similar
- `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py` — no subscription order confirmation task

The confirmation email is entirely owned by Braze as a campaign triggered by the `subscription_created` event. This means **the backend has no visibility into whether the email was actually sent** — it can only confirm whether it fired the event to Braze.

---

## Most Likely Failure Path for the Reported Bug

Given "order processed successfully but no confirmation email," the most likely failure path is:

1. The Shopify order is created correctly (payment succeeds, `Order` record created).
2. ReCharge fires the `subscription/created` webhook to the backend.
3. **`track_event` call to Braze returns `None` due to a transient API error**, but `handle_subscription_webhook` returns `True` anyway (line 120 in `service.py`). No exception is raised, no retry is triggered, the webhook returns 200.
4. Braze never receives the `subscription_created` event, so its email campaign never fires.

The second most likely path is: the user's email in ReCharge does not match any `User` record (line 90–93 in `service.py`), causing an early `return False`. The webhook endpoint still returns 200 to ReCharge.

---

## Files Referenced

| File | Relevant Lines | Issue |
|------|---------------|-------|
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` | 415–445 | Always returns HTTP 200 even on failure; no retry from ReCharge |
| `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` | 66–124 | `track_event` return value not checked; user-not-found returns False but 200 |
| `/Users/albertgwo/Work/evvy/backend/analytics/service.py` | 51–86 | `track_event` catches all exceptions and returns `None` silently |
| `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py` | 269–275 | 3 retries then raises; exception caught upstream and swallowed |
| `/Users/albertgwo/Work/evvy/backend/transactional_email/constants.py` | 1–155 | No subscription order confirmation template exists in Mandrill layer |
