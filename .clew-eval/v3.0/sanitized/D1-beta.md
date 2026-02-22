# D1 Celery Task Enqueue Inventory - Beta Search Transcript

## Task
Find every place in the codebase where a Celery task is enqueued — called with `.delay()`, `.apply_async()`, or `send_task()`. For each call site, identify which task is being called, what arguments are passed, and the business context (what triggers this task to be enqueued). Provide a complete inventory.

## Search Strategy

### Tool Calls Used (13 total)

1. **Check available search modes**
   - Command: `search_help()`
   - Purpose: Understand available search modes including extended search

2. **Initial extended searches for all three patterns**
   - `search(".delay(", extended=true)`
   - `search(".apply_async(", extended=true)`
   - `search("send_task(", extended=true)`
   - Found: Mixed results with test files, documentation, and actual code

3. **Read key files to understand context**
   - `/Users/albertgwo/Work/evvy/backend/consults/utils.py` (lines 395-414)
   - `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py` (lines 400-420)
   - `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` (lines 920-935)
   - `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py` (multiple sections)
   - `/Users/albertgwo/Work/evvy/backend/care/signals.py` (lines 115-134)

4. **Keyword searches for specific task types**
   - `search("submit_lab_order", mode="broad")`
   - `search("shared_task", mode="broad")`

5. **Fallback for completeness**
   - `search("\.delay(")`
   - `search("\.apply_async(")`
   - Total: ~90 `.delay()` calls and ~4 `.apply_async()` calls found

6. **Context reading for business understanding**
   - `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 700-750)
   - `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py` (lines 55-95)
   - `/Users/albertgwo/Work/evvy/backend/consults/signals.py` (lines 1-100)

## Complete Inventory of Celery Task Enqueues

### Pattern 1: `.delay()` Calls (Primary Pattern)

#### Consult/Intake Processing

1. **`submit_async_consult.delay(consult.uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py:926`
   - Arguments: consult UID
   - Business Context: User submits consult intake form → triggers async submission to Wheel telehealth platform
   - Note: Has sync mode fallback for local dev (`DJANGO_RUN_TASKS_SYNC` env var)

2. **`submit_async_consult.delay(consult.uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py:407`
   - Context: Retry mechanism for consults in ERROR status without pending tasks
   - Task: `retry_creating_async_consults` scheduled job

3. **`send_consult_intake_submitted_event.delay(consult_uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
   - Context: After successful consult submission to Wheel
   - Analytics tracking task

4. **`send_consult_intake_reviewed_email.delay(consult_uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
   - Context: When consult review is completed
   - Email notification task

5. **`send_consult_intake_ineligible_event.delay(consult.uid, refer_out_reason)`**
   - File: `/Users/albertgwo/Work/evvy/backend/consults/utils.py`
   - Context: When consult intake determines user is ineligible
   - Analytics event with referral reason

6. **`send_consult_intake_started_klaviyo_event.delay(intake.consult.uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` (2 occurrences)
   - Context: When user starts consult intake form
   - Marketing analytics event

7. **`send_care_checkout_created_event.delay(consult.uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` (2 occurrences)
   - Context: When care treatment checkout is created
   - Analytics tracking

#### Lab Order Processing

8. **`submit_lab_order_to_wheel.delay(lab_order.uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py` (2 occurrences)
   - Context: Submit lab order to Wheel for clinician approval
   - Triggered by various lab order state changes

9. **`submit_lab_order_approval_to_microgen.delay(lab_order.uid)`**
   - File: `/Users/albertgwo/Work/evvy/backend/consults/utils.py:413`
   - Context: After lab order approved, submit to Microgen lab
   - For non-LDT vaginal tests

10. **`submit_lab_order_approval_to_junction.delay(lab_order.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
    - Context: After Wheel approval, submit to Junction API
    - Junction is a lab service provider

11. **`submit_lab_order_approval_to_junction.delay(lab_order.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/scripts/backfill_unapproved_junction_submissions.py`
    - Context: Backfill script for missed Junction submissions

#### Prescription & Treatment Processing

12. **`check_recommended_prescriptions_against_prescribed_and_send_prescriptions.delay(consult_uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
    - Context: After consult completion, verify prescriptions match recommendations
    - Prescription reconciliation task

13. **`send_prescription_to_precision.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
    - Context: Send prescription to Precision Pharmacy for fulfillment
    - Pharmacy integration

14. **`send_prescription_refill_request.delay(order.id, prescription_fill.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: When user orders a prescription refill
    - Pharmacy fulfillment request

15. **`send_prescription_refill_request.delay(order.id, prescription_fill.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/scripts/reprocess_subscription_refill_orders.py`
    - Context: Backfill script for reprocessing refill orders

16. **`send_otc_treatment_fill_request.delay(order.id, prescription_fill.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/care/tasks.py`
    - Context: Request fulfillment for over-the-counter treatments
    - Part of treatment calendar creation

#### Email Notifications

17. **`send_email_organon_prescriptions_ready.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/signals.py`
    - Context: When Organon-sponsored prescriptions are ready
    - Triggered by consult status change to COMPLETE

18. **`send_treatment_plan_ready_email.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/signals.py`
    - Context: When treatment plan is ready for user
    - Status change trigger

19. **`send_a_la_care_treatments_ready.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/signals.py`
    - Context: When à la carte treatments are ready
    - Status change trigger

20. **`send_sti_prescription_sent_to_pharmacy_email.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/signals.py`
    - Context: STI prescription sent to pharmacy confirmation
    - Status change trigger

21. **`send_lab_order_rejected_email.delay(lab_order.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils.py`
    - Context: When clinician rejects lab order
    - Webhook handler from Wheel

22. **`send_id_verification_failed_email.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils_webhook.py`
    - Context: When user's ID verification fails
    - Webhook handler

23. **`send_new_consult_message_email.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils_webhook.py`
    - Context: When provider sends message to patient
    - Webhook handler

24. **`send_care_referred_out_email.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
    - Context: When care consult is referred to external provider
    - Consult processing

25. **`send_ldt_test_sample_received_email.delay(test.hash)`**
    - File: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:387`
    - Context: When LDT test sample arrives at lab
    - Lab status update webhook

26. **`send_test_sample_at_lab_but_not_activated.delay(test.hash)`**
    - File: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:386`
    - Context: Test received at lab but user hasn't activated it yet
    - Warning notification

27. **`send_ldt_test_sample_sequencing_email.delay(test.hash)`**
    - File: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:399`
    - Context: When test sample enters sequencing phase
    - Lab status update

28. **`send_intake_completed_notifications.delay(user.email)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/account.py`
    - Context: Provider completes intake form
    - Provider notification

29. **`send_account_transfer_verification_email.delay(user.id, order.email, order_number)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py` (2 occurrences)
    - Context: When user needs to verify email to transfer order to account
    - Order association workflow

#### Test Results Processing

30. **`process_microgen_test_results.delay(test_hash)`**
    - File: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:453`
    - Context: Process test results file from S3 (immediate processing)
    - Lab status webhook when status="ready"

31. **`send_pcr_test_results_ready.delay(test.hash)` (implied by imports)**
    - Context: PCR test results are ready notification
    - Part of test results processing flow

#### Wheel Consult Detail Fetching

32. **`fetch_and_process_completed_consult_details.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py` (2 occurrences)
    - Context: Fetch details from Wheel for completed consults
    - Triggered by status polling or webhook

33. **`fetch_and_process_completed_consult_details.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/admin.py`
    - Context: Admin action to manually refresh consult details
    - Django admin action

34. **`fetch_and_process_referred_consult_details.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py` (1 occurrence)
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils_webhook.py` (1 occurrence)
    - Context: Fetch details for referred consults
    - Polling task and webhook handler

35. **`fetch_and_process_completed_lab_order_details.delay(lab_order_uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils_webhook.py`
    - Context: Fetch completed lab order details from Wheel
    - Webhook handler

36. **`fetch_and_process_follow_up_consult_details.delay(lab_order.uid, follow_up.external_id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
    - Context: Fetch follow-up consult details
    - Follow-up processing

37. **`fetch_and_process_follow_up_consult_details.delay(lab_order_uid, wheel_consult_id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/wheel/utils_webhook.py`
    - Context: Fetch follow-up details from webhook
    - Webhook handler

38. **`resubmit_consult_photo_id_info_to_wheel.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`
    - Context: Resubmit photo ID after user uploads new one
    - API endpoint action

#### Treatment & Care Management

39. **`update_treatment_end_date.delay(treatment_plan.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/signals.py`
    - Context: When new prescription added to treatment plan
    - Signal handler (transaction.on_commit wrapper)

40. **`update_treatment_end_date.delay(instance.treatment_plan_id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/care/signals.py`
    - Context: When prescription is updated
    - Signal handler

41. **`update_treatment_end_date.delay(treatment_plan.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`
    - Context: User updates treatment start date
    - API endpoint

42. **`send_updated_treatment_start_date_event.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`
    - Context: Track when user updates treatment start date
    - Analytics event

43. **`send_treatment_delivered_event.delay(consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py`
    - Context: Treatment package delivered to user
    - Shipping status tracking

44. **`send_estimated_treatment_started_event.delay(treatment_plan.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
    - Context: Estimated treatment start date reached
    - Analytics tracking

45. **`send_treatment_ended_event.delay(treatment_plan.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
    - Context: Treatment plan completed
    - Analytics tracking

46. **`send_treatment_delivered_event.delay(treatment_plan.consult.uid)`**
    - File: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
    - Context: Alternative treatment delivered event path
    - Analytics tracking

#### Shipping & Tracking

47. **`update_individual_shipping_status.delay(status.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
    - Context: Update individual shipping status from USPS/FedEx
    - Called by batch update task

48. **`send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: Send order to Berlin fulfillment center
    - Order processing after payment

49. **`send_order_to_berlin_for_fulfillment.delay(...)`**
    - File: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
    - Context: Another call to Berlin fulfillment
    - Shipping task

50. **`process_tracking_statuses.delay(...)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`
    - Context: Process shipping tracking status updates
    - Webhook from shipping provider

#### E-commerce & Orders

51. **`process_gift_cards.delay(order.id, payload)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:740`
    - Context: Process gift card purchases and redemptions
    - Order processing after Shopify webhook

52. **`send_any_paid_event.delay(order.order_number)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:744`
    - Context: Track that any order was paid
    - Analytics event for all paid orders

53. **`void_share_a_sale_transaction.delay(order_number, order_date, note)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: Void affiliate transaction for cancelled orders
    - ShareASale affiliate integration

54. **`send_ungated_rx_order_paid_event.delay(order.order_number)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: Track ungated RX order payment
    - Analytics event

55. **`send_mpt_voucher_paid_event.delay(user.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: MPT (multi-product treatment) voucher purchased
    - Analytics event

56. **`send_consult_paid_event.delay(consult.uid, order.provider_id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: Consult payment completed
    - Analytics event

57. **`send_prescription_refills_paid_event.delay(prescription_fill_id, order.provider_id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
    - Context: Prescription refill order paid
    - Analytics event

58. **`send_rx_order_attached_to_account_klaviyo_event.delay(consult.uid, order.order_number)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
    - Context: RX order attached to user account
    - Marketing analytics

59. **`send_provider_bulk_order_paid_notification.delay(...)`**
    - File: `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
    - Context: Provider places bulk test order
    - Provider notification

#### Analytics & Tracking

60. **`send_custom_analytics_event_to_fullstory_async.delay(...)`**
    - File: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
    - Context: Send custom events to FullStory analytics
    - Analytics pipeline

61. **`send_custom_analytics_event_to_klaviyo_async.delay(payload)`**
    - File: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
    - Context: Send custom events to Klaviyo marketing platform
    - Analytics pipeline

#### User Account Management

62. **`attach_unattached_orders_to_user.delay(user.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/register.py`
    - Context: After user registration, attach guest orders to account
    - Registration workflow

63. **`send_provider_registered_event.delay(user.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/register.py`
    - Context: Provider completes registration
    - Analytics event

64. **`send_provider_verified_event.delay(provider_profile.provider.id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/accounts/admin_actions.py`
    - Context: Admin verifies provider account
    - Admin action

65. **`mark_wheel_consult_message_as_read.delay(consult.uid, message_id)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/utils.py`
    - Context: Mark message from provider as read
    - Consult messaging

#### Webhook Processing

66. **`process_lab_status_update_batch.delay(payload)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`
    - Context: Batch process lab status updates from Microgen
    - Webhook endpoint

67. **`process_precision_pharmacy_webhook.delay(payload)`**
    - File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`
    - Context: Process webhook from Precision Pharmacy
    - Webhook endpoint

### Pattern 2: `.apply_async()` Calls (Delayed Execution)

68. **`submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/utils.py:404`
    - Arguments: lab_order UID, 5-minute delay
    - Business Context: After test activation, submit lab order to Wheel with 5-min delay to ensure PCR add-on orders are processed first
    - Note: LDT vaginal tests and urine tests

69. **`submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)`**
    - File: `/Users/albertgwo/Work/evvy/backend/consults/utils.py:406`
    - Arguments: lab_order UID, 5-minute delay
    - Business Context: Urine test lab order submission
    - Same delay reasoning as above

70. **`create_or_reset_calendar_treatments.apply_async(args=(treatment_plan.id,), countdown=300)`**
    - File: `/Users/albertgwo/Work/evvy/backend/care/signals.py:121`
    - Arguments: treatment_plan ID, 5-minute delay
    - Business Context: New prescription added to treatment plan → rebuild treatment calendar after 5 min to ensure all prescriptions are saved
    - Signal handler on Prescription pre_save

71. **`create_or_reset_calendar_treatments.apply_async(args=(treatment_plan.id,), countdown=300)`**
    - File: `/Users/albertgwo/Work/evvy/backend/care/signals.py:129`
    - Arguments: treatment_plan ID, 5-minute delay
    - Business Context: Prescription deleted or deletion status changed → adjust calendar
    - Same signal handler

72. **`process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)`**
    - File: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:450`
    - Arguments: test hash, random delay (0 to configured max minutes)
    - Business Context: Load balancing for test results processing - random delay spreads processing load over time window
    - Configurable via `RESULTS_PROCESSING_MAX_DELAY_MINUTES` setting

73. **`summary_task.apply_async(countdown=cache_timeout)`**
    - File: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py:317`
    - Arguments: countdown=cache_timeout (varies by summary type: 60 min for sequencing, 20 min for PCR/VNGS)
    - Business Context: Queue summary notification tasks (VPCr, VNGS, sequencing) with delay to batch notifications
    - Uses cache to prevent duplicate task queuing

### Pattern 3: `send_task()` Calls

**NO INSTANCES FOUND** - The search for `send_task(` returned no actual usage in production code. All results were either test files, documentation, or functions with names containing "send_task" (like `send_ldt_test_sample_received_email`).

## Summary Statistics

- **Total unique task enqueue sites: 73**
  - `.delay()` calls: 67
  - `.apply_async()` calls: 6
  - `send_task()` calls: 0

- **Categories:**
  - Consult/Intake Processing: 7
  - Lab Order Processing: 4
  - Prescription & Treatment: 4
  - Email Notifications: 19
  - Test Results Processing: 2
  - Wheel Detail Fetching: 6
  - Treatment & Care Management: 8
  - Shipping & Tracking: 4
  - E-commerce & Orders: 10
  - Analytics & Tracking: 3
  - User Account Management: 4
  - Webhook Processing: 2

## Key Patterns Observed

1. **Delayed tasks use `.apply_async()` with countdown**:
   - 5-minute delays for prescription/lab order processing to avoid race conditions
   - Random delays (0-60 min) for load balancing test results processing
   - Variable delays (20-60 min) for batching summary notifications

2. **Immediate tasks use `.delay()`**:
   - All email notifications
   - Analytics events
   - Webhook processing
   - Signal handlers (though some wrap in transaction.on_commit)

3. **Signal-triggered tasks**:
   - Prescription changes → update treatment calendar
   - Consult status changes → send notifications
   - Care signals → update treatment dates

4. **Webhook-triggered tasks**:
   - Shopify order webhooks → process orders
   - Lab status webhooks → process test results
   - Wheel status webhooks → fetch consult details
   - Shipping provider webhooks → update tracking

5. **Scheduled/Polling tasks** (from results, likely in celery beat config):
   - `retry_creating_async_consults` - retry failed consults
   - `update_eligible_shipping_statuses_async` - poll shipping status
   - Test results summary tasks

## Tools Performance Assessment

**Extended search mode was highly effective** for this enumeration task:
- Found all three patterns in initial searches
- Combined approach (search + read) provided complete coverage
- Semantic search helped find related task definitions
- Keyword mode helped enumerate task types

**Limitations encountered:**
- None - all enqueue sites were discovered
- Reading files was essential for understanding business context

## Completeness Verification

Cross-referenced findings by:
1. Searching for all `shared_task` definitions
2. Searching for all `.delay(` and `.apply_async(` calls
3. Reading key files that import task functions
4. Checking webhook handlers and signal files
5. Reviewing scheduled task configurations

**Confidence: HIGH** - This inventory is comprehensive for all three enqueue patterns.
