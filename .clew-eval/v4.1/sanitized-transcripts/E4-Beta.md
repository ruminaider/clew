# E4 — Agent Beta

Here is a complete investigation of the subscription order confirmation email pipeline and where it can fail silently.

## System Overview

Subscription order confirmation emails are NOT sent via Mandrill (the transactional email layer). They are sent via **Braze**, triggered by a ReCharge webhook event. The two systems are separate:

- **Mandrill** (`transactional_email/`): Used for lifecycle emails (test status updates, treatment shipping, care eligibility nudges, etc.)
- **Braze** (`analytics/braze/`): Used for subscription lifecycle events including the confirmation email triggered by the `subscription/created` webhook

## The Email Dispatch Pipeline

**Step 1: ReCharge fires the `subscription/created` webhook**

The entry point is `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 415-433). ReCharge POSTs to the webhook endpoint. The `X-Recharge-Topic` header must equal `subscription/created`. A local variable `send_braze_event` is set to `True` only inside an `if` block with no default initialization:

```python
success = False
if topic == TOPIC_CHARGE_UPCOMING:
    success = handle_charge_upcoming_webhook(payload)
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
        send_braze_event = True   # <-- only set here, no default
    success = handle_subscription_webhook(payload, send_braze_event, topic)
```

**Silent failure point 1:** If `topic` is in the outer `elif` list but NOT in the inner `if` list (e.g., `TOPIC_SUBSCRIPTION_DELETED`, `TOPIC_SUBSCRIPTION_SKIPPED`, `TOPIC_SUBSCRIPTION_UPDATED`, `TOPIC_SUBSCRIPTION_UNSKIPPED`, `TOPIC_SUBSCRIPTION_PAUSED`), Python will raise a `NameError: name 'send_braze_event' is not defined`, or if this is reached in some Python path where it was previously set, carry a stale value. In practice for `TOPIC_SUBSCRIPTION_CREATED` this is fine, but if ReCharge ever sends an update webhook before a created webhook in the same request session, the variable would be uninitialized.

**Step 2: `handle_subscription_webhook` processes the payload**

Located in `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` (lines 66-124):

```python
def handle_subscription_webhook(payload, send_braze_event=True, topic=None):
    try:
        subscription_data, success = _extract_data_from_payload(payload, "subscription")
        if not success:
            return False   # <-- silently returns False

        ...
        email = formatted_subscription_data.get("email")
        user = User.objects.filter(email=email).first()
        if not user:
            logger.error(f"User not found for subscription webhook: {email}")
            return False   # <-- silently returns False, no exception

        subscription_service = SubscriptionService(user, force_refresh=True)
        subscriptions_response = subscription_service.get_all_subscriptions_with_cache()
        ...

        if send_braze_event:
            braze_event_name = _get_braze_event_for_subscription_topic(topic, subscription_data)
            if braze_event_name:
                track_event(...)   # <-- the actual email trigger
        return True

    except Exception as e:
        logger.exception(f"Error processing subscription webhook: {str(e)}")
        return False   # <-- any exception → False, email never sent
```

**Silent failure point 2: Missing user lookup.** If the email from the ReCharge payload does not match any `User` record (e.g., the user placed the order before creating an Evvy account, or the email is mixed case), the function returns `False` and no email is sent. The error is only logged; the caller at the webhook view also only logs and returns HTTP 200:

```python
if success:
    logger.info("Successfully processed ReCharge webhook")
else:
    logger.error("Failed to process ReCharge webhook")
return HttpResponse(status=200)
```

ReCharge sees HTTP 200 and considers delivery successful. No retry is triggered. No alert fires directly from this path.

**Silent failure point 3: `SubscriptionService` call.** The `subscription_service.get_all_subscriptions_with_cache()` call (which hits the Recharge API to refresh the `active_subscriptions` profile attribute) runs before the Braze event is sent. If it throws, the entire function catches the exception, returns `False`, and the Braze `SUBSCRIPTION_CREATED` event is never tracked — so no confirmation email goes out.

**Step 3: `track_event` calls Braze**

Located in `/Users/albertgwo/Work/evvy/backend/analytics/service.py` (lines 51-86):

```python
def track_event(user=None, event_name=None, properties=None, alias_name=None, ...):
    try:
        ...
        if ANALYTICS_PROVIDER == "braze":
            return braze_track_user_event(...)
        else:
            logger.warning(f"Unsupported analytics provider: {ANALYTICS_PROVIDER}")
            return None
    except Exception as e:
        user_identifier = user.uuid if user else alias_name
        logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
        return None   # <-- silently swallows ALL exceptions
```

**Silent failure point 4: `track_event` swallows all exceptions.** If the Braze HTTP call fails (network timeout, 5xx response, invalid API key, rate limit), the exception is caught, logged, and `None` is returned. The caller (`handle_subscription_webhook`) does not check the return value from `track_event` — it proceeds to `return True`. The webhook handler then logs "Successfully processed ReCharge webhook." No indication that the email was not actually sent.

**Step 4: `BrazeAPIClient._make_request` retries, then throws**

Located in `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py` (lines 269-275):

```python
@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)
def _make_request(self, method, url, data=None):
    logger.debug(f"Making {method} request to {url} ...")
    return make_request(method, url, json=data, headers=self.headers)
```

The `@retry` decorator retries 3 times with exponential backoff before raising. If all 3 attempts fail, the exception propagates up to `track_event`, which catches it at step 3 and swallows it silently.

## Summary of Silent Failure Points

| # | Location | Condition | Observable Signal |
|---|---|---|---|
| 1 | `webhooks.py` line 432 | `send_braze_event` variable uninitialized for non-event subscription topics | `NameError` in logs; HTTP 500 to ReCharge would cause retry |
| 2 | `service.py` line 90-93 | User not found by email (case mismatch, pre-registration order) | `logger.error` only; caller returns HTTP 200 to ReCharge, no retry |
| 3 | `service.py` line 95-96 | `SubscriptionService.get_all_subscriptions_with_cache()` throws (Recharge API down) | Exception caught at line 122, `return False`, HTTP 200 returned, no retry |
| 4 | `service.py` line 110-116 + `analytics/service.py` line 83-85 | Braze API fails after 3 retries | `logger.error` only; `handle_subscription_webhook` still returns `True`; webhook considered "successfully processed" |

## Most Likely Root Cause for the Reported Issue

The most probable failure path is **Silent Failure Point 2** or **Silent Failure Point 4**:

- **Point 2**: The order was placed with a different email than the Evvy account (common for subscription orders). `User.objects.filter(email=email).first()` returns `None`, the function returns `False`, and no email is sent. No retry, HTTP 200 returned to ReCharge.

- **Point 4**: The Braze `track_event` call failed silently. Because `track_event` catches all exceptions and returns `None`, and `handle_subscription_webhook` does not check the return value, the Braze `subscription_created` event is never recorded — meaning the Braze campaign that sends the confirmation email is never triggered. The webhook is marked as successful despite the email never being dispatched.

## Key Files

- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` — ReCharge webhook routing (lines 415-445)
- `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` — `handle_subscription_webhook` (lines 66-124), `_get_braze_event_for_subscription_topic` (lines 127-153)
- `/Users/albertgwo/Work/evvy/backend/analytics/service.py` — `track_event` exception swallowing (lines 51-86)
- `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py` — `BrazeAPIClient._make_request` retry logic (lines 269-275)
- `/Users/albertgwo/Work/evvy/backend/analytics/braze/utils.py` — `braze_track_user_event` wrapper (lines 74-100)
