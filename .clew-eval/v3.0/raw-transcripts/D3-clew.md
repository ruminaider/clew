# Investigation: Subscription Order Email Failure Path (Clew)

## Task

A user reported that their subscription order was processed successfully but no confirmation email was sent. Investigate the email sending pipeline to find where the failure might have occurred. Focus on understanding the specific failure path from order completion to email dispatch — do NOT exhaustively catalog all email-related code in the codebase.

## Tool Calls and Reasoning

### 1. Check available search modes
**Command:** `python3 -m clew search --help`

**Reasoning:** Needed to understand what search modes are available, especially the `--mode` and `--exhaustive` flags mentioned in the hint.

**Findings:** Available modes are `semantic`, `keyword`, and `exhaustive`. The `--exhaustive` flag is a shortcut for `--mode exhaustive`.

### 2. Search for subscription order confirmation email logic
**Command:** `python3 -m clew search "subscription order confirmation email" --project-root /Users/albertgwo/Work/evvy --json --limit 10`

**Reasoning:** Starting broad to find where subscription order confirmation emails are sent.

**Findings:** Found `send_account_email` in `/backend/subscriptions/recharge.py` and references to order processing in `/backend/ecomm/utils.py`.

### 3. Search for email sending after order completion
**Command:** `python3 -m clew search "send confirmation email after order" --project-root /Users/albertgwo/Work/evvy --json --limit 10`

**Reasoning:** Trying to find where emails are triggered after an order completes.

**Findings:** Found `_notify_after_commit` for provider orders and `_process_shopify_order_impl` which appears to be the main order processing function.

### 4. Read the main order processing function
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 238-337)

**Reasoning:** Need to understand the order processing flow to see where email sending should occur.

**Findings:** The function processes Shopify webhooks and creates Order objects but does not appear to send confirmation emails directly.

### 5. Exhaustive search for email notifications
**Command:** `python3 -m clew search "email notification order complete subscription" --project-root /Users/albertgwo/Work/evvy --json --mode exhaustive --limit 15`

**Reasoning:** Using exhaustive mode to ensure I'm not missing any email-related code for subscriptions.

**Findings:** Same results - no clear confirmation email sending after subscription orders.

### 6. Search for transactional email tasks
**Command:** `python3 -m clew search "transactional email subscription order" --project-root /Users/albertgwo/Work/evvy --json --limit 10`

**Reasoning:** Looking for transactional email infrastructure related to subscription orders.

**Findings:** Found transactional email tasks in `/backend/transactional_email/tasks.py`.

### 7. Read transactional email tasks file
**File:** `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py` (lines 1-50)

**Reasoning:** Need to understand the transactional email infrastructure.

**Findings:** File imports `send_templated_email` and `send_transactional_email` utility functions.

### 8. Search for email sending utilities
**Command:** `python3 -m clew search "send_templated_email send_transactional_email" --project-root /Users/albertgwo/Work/evvy --json --limit 10`

**Reasoning:** Need to find the email sending utilities to understand how emails are sent.

**Findings:** Found implementations in `/backend/transactional_email/utils.py` and `/backend/transactional_email/mandrill.py`.

### 9. Search for subscription charge webhook handling
**Command:** `python3 -m clew search "subscription charge success webhook" --project-root /Users/albertgwo/Work/evvy --json --limit 10`

**Reasoning:** Subscription orders likely come through webhooks, so need to find webhook handlers.

**Findings:** Found `handle_charge_upcoming_webhook` in `/backend/subscriptions/service.py` and webhook view in `/backend/api/v1/views/webhooks.py`.

### 10. Read the ReCharge webhook handler
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 369-448)

**Reasoning:** Need to see what webhooks are actually handled for subscriptions.

**Findings:** **Critical discovery** - The webhook handler only processes:
- `charge/upcoming`
- `subscription/created`
- `subscription/cancelled`
- `subscription/activated`
- `subscription/swapped`
- Other subscription lifecycle events

**There is NO handler for `charge/success` or `charge/paid` webhooks!**

### 11. Search for charge success/paid webhook constants
**Command:** `python3 -m clew search "charge/success charge_success TOPIC_CHARGE" --project-root /Users/albertgwo/Work/evvy --json --mode keyword --limit 15`

**Reasoning:** Verify if charge success webhooks are defined anywhere.

**Findings:** Found only `TOPIC_CHARGE_UPCOMING` in `/backend/subscriptions/constants.py`, confirming that charge success webhooks are not implemented.

### 12. Read subscription webhook constants
**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/constants.py`

**Reasoning:** Confirm the list of supported webhook topics.

**Findings:** **Confirmed** - Only these topics are defined:
- `TOPIC_CHARGE_UPCOMING = "charge/upcoming"`
- `TOPIC_SUBSCRIPTION_CREATED = "subscription/created"`
- `TOPIC_SUBSCRIPTION_CANCELLED = "subscription/cancelled"`
- `TOPIC_SUBSCRIPTION_ACTIVATED = "subscription/activated"`
- Plus several other subscription lifecycle topics

**NO `charge/paid` or `charge/success` constant exists.**

### 13. Search for Shopify order webhook processing
**Command:** `python3 -m clew search "order created shopify webhook process" --project-root /Users/albertgwo/Work/evvy --json --limit 10`

**Reasoning:** Maybe confirmation emails come from Shopify webhooks instead of ReCharge webhooks.

**Findings:** Found `shopify_webhook_view` in `/backend/api/v1/views/webhooks.py` and order processing in `_process_shopify_order_impl`.

### 14. Read end of order processing function
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 700-790)

**Reasoning:** Check if confirmation emails are sent at the end of order processing.

**Findings:** **Critical finding** - The order processing function:
- Tracks events to Braze/analytics
- Attaches OTC treatments
- Processes gift cards
- Sends "Any Paid" event
- Sends to fulfillment
- **DOES NOT send confirmation emails**

The function ends without sending any confirmation email to the customer.

### 15. Read subscription architecture documentation
**File:** `/Users/albertgwo/Work/evvy/docs/system-architecture/backend-apps/subscriptions.md`

**Reasoning:** Check if the documentation describes how confirmation emails should work.

**Findings:** **Major discrepancy** - The documentation at line 353 shows:
```python
elif event_type == 'charge/paid':
    process_charge_paid.delay(payload)
```

And at line 361-389, it shows a `process_charge_paid` task that should:
1. Create billing cycle records
2. **Trigger service delivery** via `deliver_subscription_benefits.delay()`

However, at line 250, the documentation shows:
```
Billing->>Customer: Confirmation email
```

**But this is NOT implemented in the actual code!**

### 16. Search for charge/paid webhook implementation
**Command:** `python3 -m clew search "charge/paid charge_paid" --project-root /Users/albertgwo/Work/evvy --json --mode keyword --limit 10`

**Reasoning:** Verify if charge/paid webhook exists anywhere in the codebase.

**Findings:** No results for `charge/paid` webhook handling. The documentation is aspirational but not implemented.

### 17. Search for Shopify confirmation emails
**Command:** `python3 -m clew search "Shopify confirmation email order_confirmation" --project-root /Users/albertgwo/Work/evvy --json --mode keyword --limit 10`

**Reasoning:** Maybe Shopify sends confirmation emails directly?

**Findings:** No code in the backend sends confirmation emails. Shopify might handle this at the platform level.

## Investigation Results

### Root Cause: Missing Webhook Handler

The subscription order confirmation email failure occurs because **the system does not handle the ReCharge `charge/paid` or `charge/success` webhook**, which is the event that fires when a subscription payment is successfully processed.

### Evidence:

1. **Missing Webhook Topic Constants** (`/backend/subscriptions/constants.py`):
   - Only defines `TOPIC_CHARGE_UPCOMING`
   - No `TOPIC_CHARGE_PAID` or `TOPIC_CHARGE_SUCCESS` constants exist

2. **Incomplete Webhook Handler** (`/backend/api/v1/views/webhooks.py`, line 413-434):
   - Only handles `charge/upcoming` webhook
   - Does not handle `charge/paid` or `charge/success` webhooks
   - When a subscription charge succeeds, the webhook is received but not processed

3. **Order Processing Doesn't Send Emails** (`/backend/ecomm/utils.py`, line 763-790):
   - The `_process_shopify_order_impl` function completes without sending confirmation emails
   - It only sends analytics events and triggers fulfillment
   - No call to any email sending function

4. **Documentation-Code Mismatch** (`/docs/system-architecture/backend-apps/subscriptions.md`):
   - Documentation shows a `process_charge_paid` task (line 361-389) that should exist
   - Documentation shows "Confirmation email" in the flow diagram (line 250)
   - **Neither of these are implemented in the actual codebase**

### The Failure Path:

1. Customer's subscription payment is processed successfully by ReCharge
2. ReCharge sends a `charge/paid` or `charge/success` webhook to Evvy's backend
3. The webhook arrives at `/webhooks/recharge/` endpoint
4. The `recharge_webhook_view` function checks the topic
5. **The topic is not in the handled list, so it returns 200 but does nothing** (line 435-438)
6. No confirmation email is triggered
7. The order may be processed when Shopify creates an order, but that flow also doesn't send emails
8. Customer never receives confirmation

### Recommendation:

To fix this issue, the system needs:

1. Add `TOPIC_CHARGE_PAID = "charge/paid"` or `TOPIC_CHARGE_SUCCESS = "charge/success"` to `/backend/subscriptions/constants.py`

2. Implement a `handle_charge_paid_webhook` function in `/backend/subscriptions/service.py` that:
   - Creates/updates the billing cycle record
   - Triggers the confirmation email
   - Initiates fulfillment if needed

3. Add the webhook topic to the handler in `/backend/api/v1/views/webhooks.py`:
   ```python
   elif topic == TOPIC_CHARGE_PAID:
       success = handle_charge_paid_webhook(payload)
   ```

4. Create or wire up a confirmation email task in `/backend/transactional_email/tasks.py` that sends the order confirmation to the customer

The system relies on Shopify's native confirmation emails OR expects ReCharge to handle this, but there's no explicit code path that guarantees a confirmation email is sent when a subscription charge succeeds.

## Tool Call Summary

**Total tool calls:** 17

**Breakdown:**
1. `clew search --help` (1 call)
2. `clew search` semantic/keyword/exhaustive modes (10 calls)
3. `Read` file operations (6 calls)

**Key files examined:**
- `/backend/api/v1/views/webhooks.py` - Webhook handling
- `/backend/subscriptions/constants.py` - Webhook topic constants
- `/backend/subscriptions/service.py` - Webhook processors
- `/backend/ecomm/utils.py` - Order processing
- `/backend/transactional_email/tasks.py` - Email infrastructure
- `/docs/system-architecture/backend-apps/subscriptions.md` - Architecture documentation (revealed the gap)
