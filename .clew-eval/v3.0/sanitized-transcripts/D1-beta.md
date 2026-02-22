# D1 Task Enqueueing Inventory - Search Approach

## Search Strategy

1. Searched for `.delay(`, `.apply_async(`, and `send_task(` patterns across the codebase
2. Excluded venv, .worktrees, and test files to focus on production code
3. Found 116 `.delay()` calls and 6 `.apply_async()` calls in non-test code
4. Read key orchestration files to understand business context

## Tool Calls

### Initial Pattern Searches
```bash
# Searched for basic patterns
search("\.delay\(")  # No matches
search("\.apply_async\(")  # No matches
search("send_task\(")  # No matches
```

### Broader Searches
```bash
# Searched without escaping to find any occurrences
search("delay(")  # No matches
search("apply_async(")  # No matches
search("@task")  # No matches (looking for task definitions)
```

### Celery Infrastructure Discovery
```bash
# Found celery imports and configuration
search("from celery")  # No files
search("import celery")  # No files
find_files("**/celery.py")  # Found multiple celery.py files
```

### Task File Discovery
```bash
find_files("**/tasks.py")  # Found 20+ task files across modules
```

### Complete Inventory Collection
```bash
# Found 116 .delay() calls in production code
search("\.delay(")

# Found 6 .apply_async() calls in production code
search("\.apply_async(")
```

### Context Gathering
```bash
# Read key files to understand business context
read("/Users/albertgwo/Work/evvy/backend/app/celery.py")
read("/Users/albertgwo/Work/evvy/backend/app/tasks.py")
read("/Users/albertgwo/Work/evvy/backend/consults/signals.py")
read("/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py")
```

## Complete Inventory of Celery Task Enqueueing

### 1. Consult Workflow Tasks (consults/signals.py)

**Trigger:** Consult status changes to STATUS_COMPLETE

- `update_treatment_end_date.delay(treatment_plan.id)`
  - **Task:** Updates the treatment end date for a treatment plan
  - **Arguments:** treatment_plan.id (int)
  - **Context:** When a non-STI consult is completed, initially sets treatment_end_date. Gets overwritten later when treatments are delivered or user sets treatment start date.
  - **Wrapped in:** transaction.on_commit() to ensure DB transaction completes first

- `send_email_organon_prescriptions_ready.delay(consult.uid)`
  - **Task:** Sends email notifying patient that organon prescriptions are ready
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered when consult is complete AND pharmacy_type is PATIENT_LOCAL_PICKUP (local pharmacy pickup)

- `send_treatment_plan_ready_email.delay(consult.uid)`
  - **Task:** Sends email notifying patient their treatment plan is ready
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered when consult is complete AND has full treatment plan purchase type

- `send_a_la_care_treatments_ready.delay(consult.uid)`
  - **Task:** Sends email for a-la-carte treatment purchases
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered when consult is complete AND purchase_type is A_LA_CARTE

- `send_sti_prescription_sent_to_pharmacy_email.delay(consult.uid)`
  - **Task:** Sends email notifying STI prescription was sent to pharmacy
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered when STI consult (TYPE_STI) status changes to COMPLETE

### 2. Wheel Integration Tasks (consults/wheel/tasks.py)

**These tasks handle integration with Wheel (telehealth platform):**

- `send_consult_intake_submitted_event.delay(consult_uid)`
  - **Task:** Sends analytics event for consult intake submission
  - **Arguments:** consult_uid (str)
  - **Context:** Called after successfully submitting consult intake to Wheel

- `send_consult_intake_reviewed_email.delay(consult_uid)`
  - **Task:** Sends email notifying patient their intake was reviewed
  - **Arguments:** consult_uid (str)
  - **Context:** Called after submitting consult intake to Wheel

- `check_recommended_prescriptions_against_prescribed_and_send_prescriptions.delay(consult_uid)`
  - **Task:** Validates recommended vs prescribed medications and sends prescriptions
  - **Arguments:** consult_uid (str)
  - **Context:** Called after submitting consult intake to Wheel

- `submit_lab_order_approval_to_junction.delay(lab_order.uid)`
  - **Task:** Submits lab order approval to Junction (lab partner)
  - **Arguments:** lab_order.uid (str)
  - **Context:** Called when lab order needs to be submitted to Junction for processing

- `fetch_and_process_completed_consult_details.delay(consult.uid)`
  - **Task:** Fetches and processes details for a completed consult
  - **Arguments:** consult.uid (str)
  - **Context:** Called when consult reaches completion status from Wheel

- `fetch_and_process_referred_consult_details.delay(consult.uid)`
  - **Task:** Fetches and processes details for a referred consult
  - **Arguments:** consult.uid (str)
  - **Context:** Called when consult is referred out to another provider

- `submit_async_consult.delay(consult.uid)` (called twice in tasks.py)
  - **Task:** Prepares and submits consult to Wheel asynchronously
  - **Arguments:** consult.uid (str)
  - **Context:** Called in two scenarios:
    1. When marking consult as ready for submission
    2. When retrying consult submission after manual review

- `send_care_referred_out_email.delay(consult.uid)`
  - **Task:** Sends email when patient is referred to external care
  - **Arguments:** consult.uid (str)
  - **Context:** Called when consult is marked as referred out

- `submit_lab_order_to_wheel.delay(lab_order.uid)` (called twice in tasks.py)
  - **Task:** Submits lab order to Wheel platform
  - **Arguments:** lab_order.uid (str)
  - **Context:** Called when lab order needs to be submitted to Wheel

- `fetch_and_process_follow_up_consult_details.delay(lab_order.uid, follow_up.external_id)`
  - **Task:** Fetches and processes follow-up consult details
  - **Arguments:** lab_order.uid (str), external_id (str)
  - **Context:** Called when there's a follow-up consult from lab results

### 3. Wheel Webhook Handlers (consults/wheel/utils_webhook.py)

**These handle incoming webhooks from Wheel:**

- `fetch_and_process_follow_up_consult_details.delay(lab_order_uid, wheel_consult_id)`
  - **Task:** Processes follow-up consult from webhook
  - **Arguments:** lab_order_uid (str), wheel_consult_id (str)
  - **Context:** Triggered by Wheel webhook when follow-up is created

- `fetch_and_process_completed_lab_order_details.delay(lab_order_uid)`
  - **Task:** Processes completed lab order details
  - **Arguments:** lab_order_uid (str)
  - **Context:** Triggered by Wheel webhook when lab order is completed

- `fetch_and_process_referred_consult_details.delay(consult_uid)`
  - **Task:** Processes referred consult details from webhook
  - **Arguments:** consult_uid (str)
  - **Context:** Triggered by Wheel webhook when consult is referred

- `fetch_and_process_completed_consult_details.delay(consult.uid)`
  - **Task:** Processes completed consult from webhook
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered by Wheel webhook when consult is completed

- `send_id_verification_failed_email.delay(consult.uid)`
  - **Task:** Sends email when ID verification fails
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered by Wheel webhook on ID verification failure

- `send_new_consult_message_email.delay(consult.uid)`
  - **Task:** Sends email when new consult message arrives
  - **Arguments:** consult.uid (str)
  - **Context:** Triggered by Wheel webhook on new message

### 4. Wheel Admin & Utils (consults/)

- `fetch_and_process_completed_consult_details.delay(obj.uid)` (consults/admin.py)
  - **Task:** Admin action to manually fetch completed consult details
  - **Arguments:** consult uid (str)
  - **Context:** Called from Django admin action

- `send_consult_intake_ineligible_event.delay(consult.uid, refer_out_reason)` (consults/utils.py)
  - **Task:** Sends analytics event for ineligible consult
  - **Arguments:** consult.uid (str), refer_out_reason (str)
  - **Context:** Called when consult is determined to be ineligible

- `submit_lab_order_approval_to_microgen.delay(lab_order.uid)` (consults/utils.py)
  - **Task:** Submits lab order approval to Microgen (lab partner)
  - **Arguments:** lab_order.uid (str)
  - **Context:** Called when lab order is approved for Microgen processing

- `mark_wheel_consult_message_as_read.delay(consult.uid, message_id)` (consults/utils.py)
  - **Task:** Marks a Wheel consult message as read
  - **Arguments:** consult.uid (str), message_id (str)
  - **Context:** Called after displaying message to patient

- `submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)` (consults/utils.py, 2 occurrences)
  - **Task:** Submits lab order to Wheel with 5-minute delay
  - **Arguments:** lab_order.uid (str)
  - **Delay:** 300 seconds (5 minutes)
  - **Context:** Called with countdown to allow time for order processing before submission

- `send_lab_order_rejected_email.delay(lab_order.uid)` (consults/wheel/utils.py)
  - **Task:** Sends email when lab order is rejected
  - **Arguments:** lab_order.uid (str)
  - **Context:** Called when Wheel rejects a lab order

### 5. Care/Treatment Tasks (care/)

- `update_treatment_end_date.delay(instance.treatment_plan_id)` (care/signals.py)
  - **Task:** Updates treatment end date when treatment plan changes
  - **Arguments:** treatment_plan_id (int)
  - **Context:** Signal triggered when treatment plan is modified

- `send_otc_treatment_fill_request.delay(order.id, prescription_fill.id)` (care/tasks.py)
  - **Task:** Sends OTC treatment fill request
  - **Arguments:** order.id (int), prescription_fill.id (int)
  - **Context:** Called when OTC treatment needs to be fulfilled

- `create_or_reset_calendar_treatments.apply_async(...)` (care/signals.py, 2 occurrences)
  - **Task:** Creates or resets calendar treatments
  - **Arguments:** (args=(instance.treatment_plan_id,), countdown=30)
  - **Delay:** 30 seconds
  - **Context:** Delayed to allow multiple rapid updates to settle before regenerating calendar

### 6. Studies/Research (studies/, scripts/)

- `submit_research_sample_lab_order_to_microgen.delay(cohort_test.test.hash)` (studies/admin.py)
  - **Task:** Submits research sample to Microgen
  - **Arguments:** test.hash (str)
  - **Context:** Admin action for research cohort testing

- `submit_research_sample_lab_order_to_microgen.delay(test.hash)` (app/management/commands/create_study_cohort_tests.py)
  - **Task:** Submits research sample to Microgen
  - **Arguments:** test.hash (str)
  - **Context:** Management command for creating study cohort tests

### 7. Shipping & Fulfillment (shipping/)

- `update_individual_shipping_status.delay(status.id)` (shipping/tasks.py)
  - **Task:** Updates individual shipping status
  - **Arguments:** status.id (int)
  - **Context:** Called when processing batch shipping status updates

- `send_order_to_berlin_for_fulfillment.delay(...)` (shipping/tasks.py)
  - **Task:** Sends order to Berlin warehouse for fulfillment
  - **Arguments:** payload (dict), is_order_cancellation (bool), order.id (int)
  - **Context:** Called when order needs to be fulfilled

- `send_test_delivered_klaviyo_event.delay(test.hash)` (shipping/utils.py)
  - **Task:** Sends Klaviyo analytics event for test delivery
  - **Arguments:** test.hash (str)
  - **Context:** Called when test kit is marked as delivered

- `send_prescription_to_precision.delay(consult.uid)` (shipping/precision/tasks.py)
  - **Task:** Sends prescription to Precision pharmacy
  - **Arguments:** consult.uid (str)
  - **Context:** Called when prescription needs to be sent to Precision

- `send_treatment_delivered_event.delay(consult.uid)` (shipping/precision/utils.py)
  - **Task:** Sends analytics event for treatment delivery
  - **Arguments:** consult.uid (str)
  - **Context:** Called when treatment from Precision is delivered

### 8. Account Management (accounts/, api/v1/views/)

- `send_provider_verified_event.delay(provider_profile.provider.id)` (accounts/admin_actions.py)
  - **Task:** Sends analytics event for provider verification
  - **Arguments:** provider.id (int)
  - **Context:** Admin action when provider is verified

- `attach_unattached_orders_to_user.delay(user.id)` (api/v1/views/register.py)
  - **Task:** Attaches orders made before registration to user account
  - **Arguments:** user.id (int)
  - **Context:** Called after new user registration completes

- `send_provider_registered_event.delay(user.id)` (api/v1/views/register.py)
  - **Task:** Sends analytics event for provider registration
  - **Arguments:** user.id (int)
  - **Context:** Called after provider completes registration

- `send_intake_completed_notifications.delay(user.email)` (api/v1/views/account.py)
  - **Task:** Sends notifications when intake form is completed
  - **Arguments:** user.email (str)
  - **Context:** Called when user completes intake questionnaire

### 9. Consult API Endpoints (api/v1/views/consult.py)

- `update_treatment_end_date.delay(treatment_plan.id)` (2 occurrences)
  - **Task:** Updates treatment end date
  - **Arguments:** treatment_plan.id (int)
  - **Context:** Called when treatment plan details are updated via API

- `send_updated_treatment_start_date_event.delay(consult.uid)`
  - **Task:** Sends analytics event for updated treatment start date
  - **Arguments:** consult.uid (str)
  - **Context:** Called when patient updates their treatment start date

- `send_care_checkout_created_event.delay(consult.uid)` (2 occurrences)
  - **Task:** Sends analytics event for care checkout creation
  - **Arguments:** consult.uid (str)
  - **Context:** Called when care checkout is created via API

- `send_consult_intake_started_klaviyo_event.delay(intake.consult.uid)` (2 occurrences)
  - **Task:** Sends Klaviyo event for intake start
  - **Arguments:** consult.uid (str)
  - **Context:** Called when consult intake is started

- `resubmit_consult_photo_id_info_to_wheel.delay(consult.uid)`
  - **Task:** Resubmits photo ID information to Wheel
  - **Arguments:** consult.uid (str)
  - **Context:** Called when patient resubmits their photo ID

- `submit_async_consult.delay(consult.uid)`
  - **Task:** Submits consult to Wheel asynchronously
  - **Arguments:** consult.uid (str)
  - **Context:** Called when consult is ready for submission

### 10. Test & Lab Results (test_results/)

- `send_provider_test_results_ready.delay(provider.email)` (test_results/infection_state_service.py)
  - **Task:** Sends email to provider when test results are ready
  - **Arguments:** provider.email (str)
  - **Context:** Called when test results become available for provider-ordered tests

- `send_vip_test_status_update.delay(test_instance.hash, previous_status, test_instance.status)` (test_results/signals.py)
  - **Task:** Sends VIP notification for test status updates
  - **Arguments:** test.hash (str), previous_status (str), new_status (str)
  - **Context:** Signal triggered when test status changes

- `issue_lab_results_to_wheel_for_lab_test.delay(lab_test.id)` (test_results/signals.py)
  - **Task:** Issues lab results to Wheel platform
  - **Arguments:** lab_test.id (int)
  - **Context:** Signal triggered when lab results are available

- `send_coaching_call_completed_event.delay(instance.test.hash, instance.id, num_calls)` (test_results/signals.py)
  - **Task:** Sends analytics event for coaching call completion
  - **Arguments:** test.hash (str), coaching_call.id (int), num_calls (int)
  - **Context:** Signal triggered when coaching call is completed

- `issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))` (test_results/lab_services/providers/junction/results_processor.py)
  - **Task:** Issues Junction lab results to Wheel
  - **Arguments:** lab_test.id (str)
  - **Context:** Called when processing Junction results

- `send_urine_test_results_ready_analytics_events.delay(urine_test.hash)` (test_results/lab_services/providers/junction/results_processor.py)
  - **Task:** Sends analytics events for urine test results
  - **Arguments:** test.hash (str)
  - **Context:** Called when urine test results are ready

- `fetch_and_process_junction_results.delay(external_order_id)` (test_results/lab_services/lab_order_service.py)
  - **Task:** Fetches and processes results from Junction
  - **Arguments:** external_order_id (str)
  - **Context:** Called when Junction notifies that results are available

- `fulfill_uti_order_in_shopify.delay(...)` (test_results/lab_services/orchestrator.py)
  - **Task:** Fulfills UTI order in Shopify
  - **Arguments:** urine_test.hash (str), treatment_skus (list)
  - **Context:** Called when UTI test results warrant treatment fulfillment

- `send_vip_test_status_update.delay(urine_test.hash, old_status, new_status)` (test_results/lab_services/orchestrator.py)
  - **Task:** Sends VIP update for urine test status change
  - **Arguments:** test.hash (str), old_status (str), new_status (str)
  - **Context:** Called when urine test status changes during processing

- `send_eligible_for_care_1_for_test.delay(test.id)` (test_results/tasks.py)
  - **Task:** Sends notification that test is eligible for care
  - **Arguments:** test.id (int)
  - **Context:** Called when test results indicate eligibility for care

- `send_eligible_for_a_la_care_not_treatment_program.delay(test.id)` (test_results/tasks.py)
  - **Task:** Sends notification for a-la-carte care eligibility
  - **Arguments:** test.id (int)
  - **Context:** Called when test is eligible for a-la-carte care but not treatment program

- `send_provider_test_results_ready.delay(provider.email)` (test_results/utils.py)
  - **Task:** Sends provider notification for ready results
  - **Arguments:** provider.email (str)
  - **Context:** Called when provider-ordered test results are ready

- `send_results_ready_analytics_events.delay(...)` (test_results/utils.py)
  - **Task:** Sends analytics events for results ready
  - **Arguments:** test_hash (str), test_id (int), user_id (int)
  - **Context:** Called when test results are released to patient

- `issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))` (test_results/admin.py)
  - **Task:** Admin action to issue lab results to Wheel
  - **Arguments:** lab_test.id (str)
  - **Context:** Django admin action for manual result submission

### 11. Microgen Lab Integration (test_results/microgen/)

- `submit_lab_order_approval_to_microgen.delay(lab_order.uid)` (test_results/microgen/tasks.py)
  - **Task:** Submits lab order approval to Microgen
  - **Arguments:** lab_order.uid (str)
  - **Context:** Called when lab order is approved for Microgen

- `process_microgen_test_results_if_exists_in_s3.delay(test.hash)` (test_results/microgen/tasks.py)
  - **Task:** Checks S3 and processes Microgen results if available
  - **Arguments:** test.hash (str)
  - **Context:** Called to poll for results in S3

- `post_process_test_results.delay(test_hash, release_results)` (test_results/microgen/tasks.py)
  - **Task:** Post-processes test results after initial processing
  - **Arguments:** test_hash (str), release_results (bool)
  - **Context:** Called after test results are initially processed

- `send_pcr_test_results_ready.delay(test_hash)` (test_results/microgen/tasks.py)
  - **Task:** Sends PCR test results ready notification
  - **Arguments:** test_hash (str)
  - **Context:** Called when PCR test results are available

- `send_pcr_test_results_ready_provider_klaviyo_event.delay(test_hash, provider_test_order.id)` (test_results/microgen/tasks.py)
  - **Task:** Sends Klaviyo event for provider PCR results
  - **Arguments:** test_hash (str), provider_test_order.id (int)
  - **Context:** Called when provider-ordered PCR results are ready

- `send_test_sample_at_lab_but_not_activated.delay(test.hash)` (test_results/microgen/tasks.py)
  - **Task:** Sends notification that sample is at lab but test not activated
  - **Arguments:** test.hash (str)
  - **Context:** Called when Microgen receives sample but test isn't activated

- `send_ldt_test_sample_received_email.delay(test.hash)` (test_results/microgen/tasks.py)
  - **Task:** Sends email that LDT sample was received
  - **Arguments:** test.hash (str)
  - **Context:** Called when Microgen receives LDT sample

- `send_ldt_test_sample_sequencing_email.delay(test.hash)` (test_results/microgen/tasks.py)
  - **Task:** Sends email that sample is being sequenced
  - **Arguments:** test.hash (str)
  - **Context:** Called when sample enters sequencing phase

- `send_sample_sequencing_provider_klaviyo_event.delay(test_hash, provider_test_order.id)` (test_results/microgen/tasks.py)
  - **Task:** Sends Klaviyo event for provider sample sequencing
  - **Arguments:** test_hash (str), provider_test_order.id (int)
  - **Context:** Called when provider-ordered sample enters sequencing

- `process_microgen_vag_pcr_test_results.delay(test_hash)` (test_results/microgen/tasks.py)
  - **Task:** Processes vaginal PCR test results
  - **Arguments:** test_hash (str)
  - **Context:** Called when vaginal PCR results are available

- `process_microgen_test_results.delay(test_hash)` (test_results/microgen/tasks.py)
  - **Task:** Processes standard Microgen test results
  - **Arguments:** test_hash (str)
  - **Context:** Called when standard test results are available

- `summary_task.apply_async(countdown=cache_timeout)` (test_results/microgen/tasks.py)
  - **Task:** Generates test result summary
  - **Arguments:** None (context-dependent)
  - **Delay:** cache_timeout seconds
  - **Context:** Delayed to allow cache to populate before generating summary

- `process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)` (test_results/microgen/tasks.py)
  - **Task:** Processes Microgen results with delay
  - **Arguments:** test_hash (str)
  - **Delay:** delay_seconds (variable)
  - **Context:** Used for retry logic with exponential backoff

- `post_process_test_results.delay(test.hash)` (test_results/utils_processing.py)
  - **Task:** Post-processes test results
  - **Arguments:** test.hash (str)
  - **Context:** Called after initial test result processing

- `send_urine_test_results_ready_analytics_events.delay(urine_test.hash)` (test_results/post_processing_utils.py)
  - **Task:** Sends urine test analytics events
  - **Arguments:** test.hash (str)
  - **Context:** Called when urine test results are ready

### 12. E-commerce (ecomm/)

- `send_prescription_refills_paid_event.delay(prescription_fill_id, order.provider_id)` (ecomm/tasks.py)
  - **Task:** Sends analytics event for prescription refill payment
  - **Arguments:** prescription_fill_id (int), provider_id (int/None)
  - **Context:** Called when prescription refill order is paid

- `send_rx_order_attached_to_account_klaviyo_event.delay(consult.uid, order.order_number)` (ecomm/tasks.py)
  - **Task:** Sends Klaviyo event when Rx order is attached to account
  - **Arguments:** consult.uid (str), order.order_number (str)
  - **Context:** Called when unregistered Rx order is attached to user account

- `void_share_a_sale_transaction.delay(order_number, order_date, note)` (ecomm/utils.py)
  - **Task:** Voids ShareASale affiliate transaction
  - **Arguments:** order_number (str), order_date (date), note (str)
  - **Context:** Called when order is cancelled or refunded

- `send_ungated_rx_order_paid_event.delay(order.order_number)` (ecomm/utils.py)
  - **Task:** Sends analytics event for ungated Rx order payment
  - **Arguments:** order.order_number (str)
  - **Context:** Called when ungated prescription order is paid

- `process_gift_cards.delay(order.id, payload)` (ecomm/utils.py)
  - **Task:** Processes gift card redemptions/purchases
  - **Arguments:** order.id (int), payload (dict)
  - **Context:** Called when order contains gift cards

- `send_any_paid_event.delay(order.order_number)` (ecomm/utils.py)
  - **Task:** Sends generic paid event for any order type
  - **Arguments:** order.order_number (str)
  - **Context:** Called when any order is paid

- `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` (ecomm/utils.py)
  - **Task:** Sends order to Berlin warehouse
  - **Arguments:** payload (dict), is_order_cancellation (bool), order.id (int)
  - **Context:** Called when order needs fulfillment from Berlin warehouse

- `send_mpt_voucher_paid_event.delay(user.id)` (ecomm/utils.py)
  - **Task:** Sends event for Male Partner Treatment voucher payment
  - **Arguments:** user.id (int)
  - **Context:** Called when MPT voucher order is paid

- `create_unregistered_testkit_order_for_urine_test.delay(...)` (ecomm/utils.py)
  - **Task:** Creates test kit order for unregistered urine test
  - **Arguments:** email (str), order_number (str), kit_number (str)
  - **Context:** Called when urine test is ordered by unregistered user

- `send_patient_ordered_provider_test_notification.delay(...)` (ecomm/utils.py)
  - **Task:** Sends notification when patient orders provider test
  - **Arguments:** provider.email (str), patient_email (str), test_type (str)
  - **Context:** Called when patient orders a test via provider link

- `send_consult_paid_event.delay(consult.uid, order.provider_id)` (ecomm/utils.py)
  - **Task:** Sends analytics event for consult payment
  - **Arguments:** consult.uid (str), provider_id (int/None)
  - **Context:** Called when consult order is paid

- `send_additional_tests_paid_event.delay(None, order.provider_id)` (ecomm/utils.py)
  - **Task:** Sends event for additional tests payment (no test kit yet)
  - **Arguments:** test_hash (None), provider_id (int/None)
  - **Context:** Called when additional tests are paid but kit not assigned

- `send_additional_tests_paid_event.delay(test_kit.hash, order.provider_id)` (ecomm/utils.py)
  - **Task:** Sends event for additional tests payment
  - **Arguments:** test_hash (str), provider_id (int/None)
  - **Context:** Called when additional tests order is paid

- `send_prescription_refill_request.delay(order.id, prescription_fill.id)` (ecomm/utils.py)
  - **Task:** Sends prescription refill request to pharmacy
  - **Arguments:** order.id (int), prescription_fill.id (int)
  - **Context:** Called when refill order is paid and ready to fulfill

- `send_provider_bulk_order_paid_notification.delay(...)` (ecomm/utils.py)
  - **Task:** Sends notification for provider bulk order payment
  - **Arguments:** provider.email (str), order.order_number (str), test_count (int)
  - **Context:** Called when provider pays for bulk test order

- `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(...)` (ecomm/services/cart.py)
  - **Task:** Adds treatments to existing consult or creates new one
  - **Arguments:** order.id (int), user.id (int)
  - **Context:** Called when treatment order is placed

- `send_account_transfer_verification_email.delay(user.id, order.email, order_number)` (ecomm/services/cart.py, 2 occurrences)
  - **Task:** Sends verification email for account transfer
  - **Arguments:** user.id (int), order.email (str), order_number (str)
  - **Context:** Called when order email differs from user email

### 13. User Tests API (api/v1/views/user_tests.py)

- `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(...)`
  - **Task:** Adds treatments to consult
  - **Arguments:** order.id (int), user.id (int)
  - **Context:** Called when user adds treatments via API

- `send_additional_tests_checkout_created_event.delay(test_kit.hash)`
  - **Task:** Sends event for additional tests checkout
  - **Arguments:** test_kit.hash (str)
  - **Context:** Called when user creates checkout for additional tests

- `send_health_history_completed_klaviyo_event.delay(test.hash)`
  - **Task:** Sends Klaviyo event for health history completion
  - **Arguments:** test.hash (str)
  - **Context:** Called when user completes health history questionnaire

### 14. Provider Test Orders (api/v1/views/provider_test_orders.py)

- `send_provider_ordered_single_test_notifications.delay(...)`
  - **Task:** Sends notifications for single test order
  - **Arguments:** provider.email (str), patient_email (str), test_type (str)
  - **Context:** Called when provider orders single test for patient

- `send_provider_ordered_test_klaviyo_event.delay(...)` (2 occurrences)
  - **Task:** Sends Klaviyo event for provider test order
  - **Arguments:** test_hash (str), provider.id (int), patient_email (str)
  - **Context:** Called when provider orders test (single or bulk)

- `send_provider_bulk_ordered_tests_notification.delay(...)`
  - **Task:** Sends notification for bulk test order
  - **Arguments:** provider.email (str), test_count (int)
  - **Context:** Called when provider bulk orders tests

- `send_provider_reminded_patient_klaviyo_event.delay(...)`
  - **Task:** Sends event when provider reminds patient
  - **Arguments:** provider.id (int), patient_email (str)
  - **Context:** Called when provider sends reminder to patient

### 15. Webhooks (api/v1/views/webhooks.py)

- `process_tracking_statuses.delay(...)`
  - **Task:** Processes shipping tracking status updates
  - **Arguments:** tracking_data (dict), carrier (str)
  - **Context:** Called when shipping webhook receives tracking updates

- `process_lab_status_update_batch.delay(payload)`
  - **Task:** Processes batch lab status updates
  - **Arguments:** payload (dict)
  - **Context:** Called when lab webhook receives batch updates

- `process_precision_pharmacy_webhook.delay(payload)`
  - **Task:** Processes Precision pharmacy webhook
  - **Arguments:** payload (dict)
  - **Context:** Called when Precision sends webhook notification

### 16. Account Transfer Verification (api/v1/views/account_order_transfer_verification.py)

- `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(...)`
  - **Task:** Adds treatments after account transfer verification
  - **Arguments:** order.id (int), user.id (int)
  - **Context:** Called after user verifies account transfer

### 17. My Plan Views (api/v1/views/my_plan.py)

- `send_viewed_plan_klaviyo_event.delay(test.id)`
  - **Task:** Sends Klaviyo event when user views their plan
  - **Arguments:** test.id (int)
  - **Context:** Called when user opens their treatment plan

### 18. Analytics Tasks (analytics/tasks.py)

- `send_custom_analytics_event_to_fullstory_async.delay(...)`
  - **Task:** Sends custom analytics event to FullStory
  - **Arguments:** event_name (str), user_id (int), properties (dict)
  - **Context:** Called when sending analytics events that need FullStory tracking

- `send_custom_analytics_event_to_klaviyo_async.delay(payload)`
  - **Task:** Sends custom analytics event to Klaviyo
  - **Arguments:** payload (dict)
  - **Context:** Called when sending analytics events to Klaviyo

- `send_estimated_treatment_started_event.delay(treatment_plan.id)`
  - **Task:** Sends event for estimated treatment start
  - **Arguments:** treatment_plan.id (int)
  - **Context:** Called when treatment plan has estimated start date

- `send_treatment_ended_event.delay(treatment_plan.id)`
  - **Task:** Sends event for treatment end
  - **Arguments:** treatment_plan.id (int)
  - **Context:** Called when treatment plan ends

- `send_treatment_delivered_event.delay(treatment_plan.consult.uid)`
  - **Task:** Sends event for treatment delivery
  - **Arguments:** consult.uid (str)
  - **Context:** Called when treatment is delivered to patient

### 19. Scripts (scripts/)

- `send_prescription_refill_request.delay(order.id, prescription_fill.id)` (scripts/reprocess_subscription_refill_orders.py)
  - **Task:** Reprocesses refill requests
  - **Arguments:** order.id (int), prescription_fill.id (int)
  - **Context:** One-off script to reprocess failed refill requests

- `submit_lab_order_approval_to_junction.delay(lab_order.uid)` (scripts/backfill_unapproved_junction_submissions.py)
  - **Task:** Backfills unapproved Junction submissions
  - **Arguments:** lab_order.uid (str)
  - **Context:** One-off script to fix missing Junction submissions

- `create_test_result_tagset.delay(test.hash)` (scripts/test_result_tag_scripts.py)
  - **Task:** Creates test result tagset
  - **Arguments:** test.hash (str)
  - **Context:** Script to generate test result tags

- `issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))` (scripts/resend_lab_results_to_wheel.py)
  - **Task:** Resends lab results to Wheel
  - **Arguments:** lab_test.id (str)
  - **Context:** Script to fix missing Wheel result submissions

## Summary Statistics

- **Total `.delay()` calls:** 116
- **Total `.apply_async()` calls:** 6
- **Total `send_task()` calls:** 0
- **Total unique task enqueueing locations:** 122

## Key Patterns Observed

1. **Email & Notifications**: Largest category - sending transactional emails, Klaviyo events, FullStory events
2. **External Integrations**: Wheel (telehealth), Microgen/Junction (labs), Precision (pharmacy), Berlin (fulfillment)
3. **Signals**: Heavy use of Django signals to trigger async tasks on model changes
4. **Webhooks**: External services trigger async processing via webhook handlers
5. **Admin Actions**: Django admin actions trigger async tasks for batch operations
6. **Delayed Execution**: Several tasks use `apply_async(countdown=N)` for delayed execution:
   - 300 seconds (5 min) for lab order submissions
   - 30 seconds for treatment calendar regeneration
   - Variable delays for retry logic
7. **Transaction Safety**: Some tasks wrapped in `transaction.on_commit()` to ensure DB commits complete first

## Business Context Summary

The Celery task system orchestrates:
- **Patient care workflow**: Intake → Review → Consult → Prescription → Fulfillment → Follow-up
- **Lab integration**: Order submission → Sample tracking → Results processing → Provider notification
- **E-commerce**: Order payment → Fulfillment → Shipping → Delivery tracking
- **Analytics**: Event tracking across Klaviyo, FullStory, Braze, and internal systems
- **Communication**: Transactional emails, provider notifications, admin alerts
- **External services**: Wheel (telehealth), Microgen/Junction (labs), Precision/Organon (pharmacies), Berlin (warehouse), ShareASale (affiliates)
