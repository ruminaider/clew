# E2 Exploration Log

## Search 1: Find all files with @shared_task or @app.task decorator
Searched for `@app\.task|@celery\.task|@shared_task` across the codebase.

Found 16 backend task files (excluding venv and docs):
- `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/subscriptions/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/care/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/accounts/tasks.py`
- `/Users/albertgwo/Work/evvy/backend/app/tasks.py`

Also confirmed one more via `find`:
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/tasks.py` (present on disk but no @shared_task match — confirms no tasks there)

## Search 2: Read all task files
Read all 15 task files in full. Key findings organized below.

## Search 3: Find apply_async and send_task usages
Searched for `.apply_async\(|send_task\(` to find non-.delay() enqueue patterns.

Found:
- `care/signals.py:121,129` — `create_or_reset_calendar_treatments.apply_async()` with `countdown=`
- `consults/utils.py:404,406` — `submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)`
- `test_results/microgen/tasks.py:317` — `summary_task.apply_async(countdown=cache_timeout)` (used internally within microgen tasks)
- `test_results/microgen/tasks.py:450` — `process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)`

---

## Final Answer

### Complete Inventory of Celery Tasks

All tasks use `@shared_task` decorator (imported from `celery`). No tasks use `@app.task` directly. The only retry mechanism found is the `retrying` library's `@retry` decorator on one task and Celery's native `bind=True, max_retries=N` on two tasks.

---

## 1. `accounts/tasks.py`

### `send_intake_completed_notifications`
- **File**: `/Users/albertgwo/Work/evvy/backend/accounts/tasks.py`
- **Arguments**: `provider_email` (str)
- **Enqueue**: `.delay()` (called from provider registration flow — not shown in task file)
- **Retry**: None
- **Purpose**: Sends admin email notifications when a B2B provider completes their intake registration. Constructs an email with provider profile details (type, specialty, clinic state, etc.) and sends to B2B registration and in-clinic email addresses.

---

## 2. `analytics/tasks.py` — 24 tasks

### `send_custom_analytics_event_to_fullstory_async`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `user_id` (int), `event_name` (str), `event_properties` (dict), `use_recent_session` (bool)
- **Enqueue**: `.delay()` — called from `send_custom_analytics_event_to_destinations()`
- **Retry**: None
- **Purpose**: Generic async wrapper for sending a custom event to Fullstory. Looks up the User by ID and calls the Fullstory utility.

### `send_custom_analytics_event_to_klaviyo_async`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `payload` (dict — Klaviyo-formatted event payload)
- **Enqueue**: `.delay()` — called from `send_custom_analytics_event_to_destinations()`
- **Retry**: None
- **Purpose**: Generic async wrapper for sending a custom event to Klaviyo. Takes a pre-formatted Klaviyo payload dict.

### `send_sample_sequencing_provider_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str), `provider_test_order_id` (int)
- **Enqueue**: `.delay()` — called from `test_results/microgen/tasks.py` when test enters sequencing status
- **Retry**: None
- **Purpose**: Sends a "[Provider] Sample Sequencing" Klaviyo event to a B2B provider when their ordered test begins sequencing at the lab.

### `send_pcr_test_results_ready_provider_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str), `provider_test_order_id` (int)
- **Enqueue**: `.delay()` — called from `test_results/microgen/tasks.py` when PCR results are processed
- **Retry**: None
- **Purpose**: Sends a "[Provider] Preliminary Results Ready" Klaviyo event to a B2B provider when expanded PCR results are ready.

### `send_results_ready_analytics_events`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str), `eligible_for_care` (bool), `ineligible_reason` (str | None)
- **Enqueue**: `.delay()` — called when test results are released
- **Retry**: None
- **Purpose**: Comprehensive analytics task fired when a vaginal test's results are released. Creates/updates `CareEligible` records, tracks bundle and a-la-carte treatment eligibility, then sends "Results Ready" events to Fullstory, Klaviyo, and Braze, including care eligibility flags and recommended treatments.

### `send_urine_test_results_ready_analytics_events`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `urine_test_hash` (str)
- **Enqueue**: `.delay()` — called when urine test results are released
- **Retry**: None
- **Purpose**: Similar to above but for urine (UTI) tests. Saves UTI care eligibility data to the `CareEligible` model including eligibility expiration date.

### `send_care_checkout_created_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when a care checkout is created
- **Retry**: None
- **Purpose**: Sends "Care Checkout Created" event to Fullstory when a user initiates a care checkout. Includes test hash, care price, consult type, purchase type, and treatment selections.

### `send_ungated_rx_order_paid_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `order_number` (str)
- **Enqueue**: `.delay()` — called on ungated RX order payment
- **Retry**: None
- **Purpose**: Sends "Ungated Paid" event to Fullstory and `URX_PURCHASE` event to Braze when a symptom-relief (ungated RX) order is paid.

### `send_mpt_voucher_paid_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `user_id` (int)
- **Enqueue**: `.delay()` — called on MPT voucher payment
- **Retry**: None
- **Purpose**: Sends "MPT Voucher Paid" event to Fullstory, Klaviyo, and Braze (`MPT_VOUCHER_PAID`).

### `send_consult_paid_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str), `order_number` (str)
- **Enqueue**: `.delay()` — called when care is paid
- **Retry**: None
- **Purpose**: Sends "Care Paid" event across Fullstory, Klaviyo, and Braze (`CONSULT_PAID`, or `UTI_CONSULT_PAID` for UTI consults). Includes purchase type, pharmacy type, SKUs, care eligibility, and infection state.

### `send_any_paid_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `order_number` (str)
- **Enqueue**: `.delay()` — called on any order payment
- **Retry**: None
- **Purpose**: Sends an "Any Paid" event to Fullstory for any order, classifying by type (test, care, refill, ungated rx, etc.) based on business verticals and order type.

### `send_prescription_refills_paid_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `prescription_refill_id` (int), `order_number` (str)
- **Enqueue**: `.delay()` — called from `ecomm/tasks.py:send_prescription_refill_request`
- **Retry**: None
- **Purpose**: Sends "Prescription Refills Paid" event to Fullstory when a prescription refill order is paid.

### `send_additional_tests_checkout_created_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called from checkout flows
- **Retry**: None
- **Purpose**: Sends "Additional Tests Checkout Created" event to Fullstory when a user starts checkout for additional tests.

### `send_additional_tests_paid_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str | None), `order_number` (str)
- **Enqueue**: `.delay()` — called on additional test purchase
- **Retry**: None
- **Purpose**: Sends "Additional Tests Paid" event to Fullstory.

### `send_consult_intake_ineligible_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str), `refer_out_reason` (str)
- **Enqueue**: `.delay()` — called when consult intake deems user ineligible
- **Retry**: None
- **Purpose**: Sends "Consult Intake Ineligible" event to Fullstory when a user is referred out during care intake.

### `send_rx_order_attached_to_account_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str), `order_number` (str)
- **Enqueue**: `.delay()` — called from `ecomm/tasks.py:add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Retry**: None
- **Purpose**: Sends "RX Attached to Account" Klaviyo event when an ungated RX order is linked to a user's existing consult.

### `send_consult_intake_submitted_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from `consults/wheel/tasks.py:submit_consult_intake_to_wheel`
- **Retry**: None
- **Purpose**: Sends "Consult Intake Submitted" events to Fullstory, Klaviyo, and Braze (`CONSULT_INTAKE_SUBMITTED` or `UTI_CONSULT_INTAKE_SUBMITTED` for UTI consults).

### `send_coaching_call_completed_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str), `coaching_call_notes_id` (int, optional), `num_calls` (int, optional)
- **Enqueue**: `.delay()` — called when a coaching call is recorded
- **Retry**: None
- **Purpose**: Sends "Coaching Call Completed" event to Fullstory when an expert coaching call is recorded.

### `send_treatment_delivered_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from `send_treatment_probably_delivered_events_for_treatment_plans`
- **Retry**: None
- **Purpose**: Sends "Treatment Delivered" event to Klaviyo when prescriptions arrive at the patient.

### `send_estimated_treatment_started_events` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat (periodic), then triggers `send_estimated_treatment_started_event.delay(treatment_plan.id)` for each plan
- **Retry**: None
- **Purpose**: Scans treatment plans with start dates falling today or yesterday and dispatches individual treatment-started events.

### `send_estimated_treatment_started_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `treatment_plan_id` (int)
- **Enqueue**: `.delay()` — from `send_estimated_treatment_started_events`
- **Retry**: None
- **Purpose**: Sends "Treatment Started" Klaviyo event for one treatment plan if the estimated start date falls within today or yesterday.

### `send_test_delivered_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called when test kit is delivered (shipping webhook)
- **Retry**: None
- **Purpose**: Sends "Test Kit Delivered" Klaviyo event using the ecomm order email (works for users who have not created an account yet).

### `send_health_history_completed_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called when health history is submitted
- **Retry**: None
- **Purpose**: Sends "Health History Completed" Klaviyo event.

### `send_updated_treatment_start_date_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when user updates their treatment start date
- **Retry**: None
- **Purpose**: Sends "Updated Treatment Start Date" Klaviyo event with new and computed end dates.

### `send_treatment_ended_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `treatment_plan_id` (int)
- **Enqueue**: `.delay()` — from `send_treatment_ended_events_for_treatment_plans`
- **Retry**: None
- **Purpose**: Sends "Treatment Ended" event to Klaviyo and Braze (`TREATMENT_ENDED`).

### `send_treatment_ended_events_for_treatment_plans` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `send_treatment_ended_event.delay()` per plan
- **Retry**: None
- **Purpose**: Finds treatment plans whose end date is today or yesterday and triggers per-plan ended events.

### `send_treatment_probably_delivered_events_for_treatment_plans` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `send_treatment_delivered_event.delay()` per plan
- **Retry**: None
- **Purpose**: For treatment plans without a delivery timestamp, fires "Treatment Delivered" events once average fulfillment days have passed since plan creation.

### `send_provider_registered_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `provider_id` (int)
- **Enqueue**: `.delay()` — called when a provider completes registration
- **Retry**: None
- **Purpose**: Sends "Provider Registered" Klaviyo event to a newly registered B2B provider.

### `send_provider_verified_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `provider_id` (int)
- **Enqueue**: `.delay()` — called when provider is verified
- **Retry**: None
- **Purpose**: Sends "[Provider] Provider Verified" Klaviyo event, but only if provider is actually in verified state.

### `send_provider_ordered_test_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `provider_id` (int), `provider_test_order_ids` (list[int]), `payer` (str), `add_expanded_pcr` (bool=False), `patient_email` (str=None)
- **Enqueue**: `.delay()` — called when a provider orders a test for a patient
- **Retry**: None
- **Purpose**: Sends two Klaviyo events: "Provider Ordered A Test for User" (to patient) and "[Provider] Provider Ordered a Test" (to provider). Includes checkout link for patient-paid orders.

### `send_provider_reminded_patient_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `provider_id` (int), `patient_email` (str)
- **Enqueue**: `.delay()` — called when provider sends a reminder to a patient
- **Retry**: None
- **Purpose**: Sends "Provider Reminded User to Purchase Test" Klaviyo event to the patient with a checkout link.

### `send_viewed_plan_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `test_id` (int)
- **Enqueue**: `.delay()` — called when user views their test plan
- **Retry**: None
- **Purpose**: Sends "Viewed Plan" Klaviyo event (deduplicated per test hash).

### `send_consult_intake_started_klaviyo_event`
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when a consult intake is started
- **Retry**: None
- **Purpose**: Sends "Consult Intake Started" Klaviyo event (deduplicated per consult UID).

### `send_three_weeks_after_treatment_delivered_klaviyo` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Finds consults eligible for prescription refill (3+ weeks post-delivery) and sends "Consult Eligible for Refill" Klaviyo event to each.

---

## 3. `app/tasks.py`

### `clean_log_entries`
- **File**: `/Users/albertgwo/Work/evvy/backend/app/tasks.py`
- **Arguments**: `delete_all` (bool=False)
- **Enqueue**: Celery Beat (periodic)
- **Retry**: None
- **Purpose**: Deletes audit log entries older than 30 days (or all entries if `delete_all=True`) from the `auditlog.LogEntry` table.

---

## 4. `care/tasks.py`

### `update_treatment_end_date`
- **File**: `/Users/albertgwo/Work/evvy/backend/care/tasks.py`
- **Arguments**: `treatment_plan_id` (int)
- **Enqueue**: `.delay()` — called when treatment plan changes
- **Retry**: None
- **Purpose**: Recalculates and saves the treatment end date for a treatment plan based on consult and treatment data.

### `create_or_reset_calendar_treatments`
- **File**: `/Users/albertgwo/Work/evvy/backend/care/tasks.py`
- **Arguments**: `treatment_plan_id` (int)
- **Enqueue**: `.apply_async(args=[treatment_plan_id], countdown=N)` — called from `care/signals.py` with a countdown delay
- **Retry**: None
- **Purpose**: Deletes all existing calendar treatments for a plan and regenerates them from the consult's prescriptions.

### `heal_prescription_fill_orders` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/care/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Data healing task. Finds prescription fills modified in the last 24 hours that have an order but no `PrescriptionFillOrder` linking record, and creates the missing links.

### `heal_otc_treatment_only_orders` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/care/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; internally calls `send_otc_treatment_fill_request.delay()`
- **Retry**: None
- **Purpose**: Data healing task. Finds OTC-only orders from the last 24 hours where the OTC treatment was never sent to the pharmacy, creates prescription fills for them, and dispatches them to Precision pharmacy.

---

## 5. `ecomm/tasks.py`

### `send_patient_ordered_provider_test_notification`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `patient_email` (str), `order_sku` (str), `order_provider_id` (int)
- **Enqueue**: `.delay()` — called when a patient completes a provider-ordered test purchase
- **Retry**: None
- **Purpose**: Sends an internal FYI admin email when a patient pays for a provider-ordered test, noting who paid (provider or patient).

### `void_share_a_sale_transaction`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `order_number` (str), `order_date` (str), `reason` (str)
- **Enqueue**: `.delay()` — called on order cancellation/refund
- **Retry**: `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` — up to 3 attempts with exponential backoff (500ms base)
- **Purpose**: Calls the ShareASale affiliate API to void a commission transaction when an order is cancelled or refunded.

### `send_prescription_refill_request`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `order_id` (int), `prescription_fill_id` (int)
- **Enqueue**: `.delay()` — called on refill order payment
- **Retry**: None
- **Purpose**: Orchestrates sending a prescription refill to Precision pharmacy. Validates state restrictions, checks refill counts, updates fill status to CREATED, fires analytics, creates/sends patient and prescription records to Precision, then sends the fill request. Also handles cancellation by calling cancel fill.

### `send_otc_treatment_fill_request`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `order_id` (int), `prescription_fill_id` (int)
- **Enqueue**: `.delay()` — called from `care/tasks.py:heal_otc_treatment_only_orders`
- **Retry**: None
- **Purpose**: Sends OTC-only (no prescription) treatment fill requests to Precision pharmacy. No jurisdictional restrictions since OTC products can ship anywhere.

### `attach_unattached_orders_to_user`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `user_id` (int)
- **Enqueue**: `.delay()` — called on user account creation/login
- **Retry**: None
- **Purpose**: Finds orders matching the user's email that have no `user` FK set and attaches them. Also triggers consult creation for ungated RX orders and OTC treatment attachment.

### `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `user_id` (int), `order_number` (str)
- **Enqueue**: `.delay()` — called from `attach_unattached_orders_to_user`
- **Retry**: None
- **Purpose**: For ungated RX orders, finds the user's latest in-progress consult and adds the order's products to it. If no consult exists, creates a new ungated RX consult. Fires Klaviyo "RX Attached to Account" event.

### `create_consults_for_ungated_rx_orders_with_users_but_no_consult` (periodic/admin)
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: None
- **Enqueue**: Celery Beat or manual trigger
- **Retry**: None
- **Purpose**: Data healing task. Finds all ungated RX orders that have a user but no ConsultOrder and creates consults for them.

### `process_gift_card_redemptions`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `order_id` (int)
- **Enqueue**: `.delay()` — called on order payment
- **Retry**: None
- **Purpose**: Processes gift card redemptions applied to a specific order via the `GiftCardRedemptionService`.

### `process_gift_cards`
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: `order_id` (int), `payload` (dict=None)
- **Enqueue**: `.delay()` — called on order payment
- **Retry**: None
- **Purpose**: Processes both gift card purchases and redemptions for an order. If a Shopify payload is provided, handles gift card purchases; otherwise only handles redemptions.

### `reprocess_subscription_refill_orders_daily` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Daily healing job to reprocess subscription refill orders from the last 24 hours that were incorrectly routed. Calls `reprocess_subscription_refill_orders` script with batch size of 200.

---

## 6. `ecomm/shopify/tasks.py`

### `retry_failed_shopify_orders` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None (but has `soft_time_limit=600, time_limit=900` task-level limits)
- **Purpose**: Fetches recent Shopify orders (last 3 days, excluding last hour) via the Admin API and processes any orders missing from the Evvy system. Handles up to 50 pages (1,000 orders) before stopping.

---

## 7. `shipping/tasks.py`

### `update_individual_shipping_status`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: `status_id` (int)
- **Enqueue**: `.delay()` — called from `update_eligible_shipping_statuses_async`
- **Retry**: None
- **Purpose**: Updates the shipping status for a single kit or return sample by calling the shipping provider API (USPS/FedEx tracking).

### `update_eligible_shipping_statuses_async` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `update_individual_shipping_status.delay()` per status record
- **Retry**: None
- **Purpose**: Identifies all open shipping statuses needing update (with different frequency rules for kits vs. recently/stale-activated samples vs. unactivated samples) and fans out individual update tasks.

### `send_daily_express_orders_email` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends a daily email (and updates a Google Sheet) with all express-shipping orders from the last 24 hours to the Berlin fulfillment team.

### `process_tracking_statuses`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: `test_hash` (str), `order_number` (str), `kit_tracking_number` (str), `sample_tracking_number` (str), `mode` (str=`MODE_ALL`), `from_csv` (bool=False)
- **Enqueue**: `.delay()` — called from Berlin webhook handler
- **Retry**: None
- **Purpose**: Core tracking task. Links a test kit to its Shopify order, creates `ShippingStatus` records for kit and return sample tracking numbers, associates tests with ProviderTestOrders, adds expanded PCR panels if needed, and marks the Shopify order as fulfilled.

### `send_order_to_berlin_for_fulfillment`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: `shopify_payload` (dict), `is_order_cancellation` (bool), `order_id` (int)
- **Enqueue**: `.delay()` — called on Shopify order webhook
- **Retry**: None (but has NewRelic monitoring and error logging)
- **Purpose**: Sends a new or cancelled order to Berlin (3PL fulfillment partner) for test kit fulfillment. Marks `sent_to_berlin_at` on success.

### `retry_failed_berlin_order_fulfillments` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `send_order_to_berlin_for_fulfillment.delay()` per failed order
- **Retry**: None
- **Purpose**: Finds orders created since the Berlin integration went live that were never successfully sent to Berlin and retries sending them.

### `alert_if_no_orders_sent_to_berlin` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Health check alert — raises an exception (triggers alerting) if no orders have been sent to Berlin in the last 6 hours.

### `alert_if_no_orders_created` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Health check alert — raises an exception if no new orders have been created in the last 6 hours, indicating a possible Shopify webhook failure.

---

## 8. `shipping/precision/tasks.py`

### `process_precision_pharmacy_webhook`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `payload` (dict — Precision webhook payload)
- **Enqueue**: `.delay()` — called from Precision webhook endpoint
- **Retry**: None
- **Purpose**: Dispatches incoming Precision pharmacy webhooks by type: "received" (no action), "shipped" (marks fill as shipped), "delivered" (marks fill as delivered, triggers emails).

### `send_prescription_to_precision`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `consult_uid` (str), `skip_set_sent_to_pharmacy` (bool=False)
- **Enqueue**: `.delay()` — called from `consults/wheel/tasks.py:check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **Retry**: None
- **Purpose**: Creates the patient in Precision pharmacy, then creates and fills prescriptions. Marks `sent_to_pharmacy_at` on the consult. Also fires a Braze `CONSULT_ELIGIBLE_FOR_REFILLS` event if applicable.

### `send_create_patient_request_to_precision`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `prescription_fill_id` (int), `consult_uid` (str=None), `user_id` (int=None), `order_id` (int=None)
- **Enqueue**: Called directly (not `.delay()`) from `ecomm/tasks.py:send_prescription_refill_request`
- **Retry**: None
- **Purpose**: Creates or updates a patient record in Precision pharmacy. Saves the `pharmacy_patient_id` to the prescription fill.

### `send_create_prescription_request_to_precision`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `prescription_uid` (str), `fill_quantity` (int=None), `prescription_fill_prescription` (PrescriptionFillPrescriptions=None)
- **Enqueue**: Called directly from `ecomm/tasks.py:send_prescription_refill_request`
- **Retry**: None
- **Purpose**: Creates a single prescription record in Precision. On failure, sets the prescription fill to WARNING status.

### `send_create_otc_treatment_request_to_precision`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `otc_treatment_uid` (str), `prescription_fill_otc_treatment_id` (int)
- **Enqueue**: Called directly from `ecomm/tasks.py:send_prescription_refill_request` and `send_otc_treatment_fill_request`
- **Retry**: None
- **Purpose**: Creates an OTC treatment record in Precision. On failure, sets the prescription fill to WARNING status.

### `send_fill_request_to_precision`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `fill_uid` (int), `order_shipping_address` (OrderShippingAddress=None)
- **Enqueue**: Called directly from orchestrating tasks (not `.delay()`)
- **Retry**: None
- **Purpose**: Sends the final fill request to Precision pharmacy. On success, marks `sent_to_pharmacy_at` on consult. On failure, sets fill status to WARNING.

### `send_cancel_fill_request_to_precision`
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: `fill_uid` (int)
- **Enqueue**: Called directly from `ecomm/tasks.py:send_prescription_refill_request` (not `.delay()`)
- **Retry**: None
- **Purpose**: Cancels a prescription fill at Precision pharmacy. Raises exception if fill is already shipped or delivered.

### `send_missing_prescriptions_to_precision` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `send_prescription_to_precision.delay()` per consult
- **Retry**: None
- **Purpose**: Healing task. Finds completed Precision consults from the last 2 days where prescriptions were never sent to Precision, verifies prescription match, and resubmits.

### `retry_failed_prescription_fills` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None (self-implements retry logic — up to 3 days before marking as FAILED)
- **Purpose**: Retries prescription fills in WARNING status. Processes up to 10 fills per run, only fills older than 1 hour but less than 7 days. Marks fills as permanently FAILED after 3 days and creates ConsultTask for manual intervention.

### `send_notification_for_stuck_prescriptions` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends an admin email alert for refill prescription fills that have been in CREATED status for more than 3 business days without shipping.

---

## 9. `subscriptions/tasks.py`

### `cancel_expired_prescription_subscriptions` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/subscriptions/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Daily task that cancels Recharge subscription billing for prescriptions that have run out of refills, by calling `cancel_subscriptions_for_expired_prescriptions`.

---

## 10. `test_results/tasks.py`

### `create_test_result_tagset`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: Called directly (no `.delay()`) from `post_process_test_results`
- **Retry**: None
- **Purpose**: Creates or updates a `TestResultTagSet` for a test result, computing pregnancy, menopause, symptom, pathogen, and health context tags used for plan profile selection.

### `post_process_test_results`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: `test_hash` (str), `release_results` (bool=True)
- **Enqueue**: `.delay()` — called from `test_results/microgen/tasks.py:process_microgen_test_results`
- **Retry**: None
- **Purpose**: Core post-processing pipeline for test results: updates Valencia type, creates test scores, creates fertility module, captures infection state, computes tags, assigns plan profile, assigns suspected yeast flag, creates recommended treatment program, checks auto-release eligibility, and if auto-releasable, releases results to the user.

### `assign_suspected_yeast_flag_to_test_result`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: Called directly from `post_process_test_results`
- **Retry**: None
- **Purpose**: Sets `suspected_yeast=True` on a test result if yeast is present in results or patient has a recent yeast infection diagnosis in health history.

### `send_results_ready_emails`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called when test results are released
- **Retry**: None
- **Purpose**: Sends the "Results Ready" transactional email to the user and, if eligible for care, also triggers care eligibility emails.

### `send_test_status_duration_alert` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Checks for MDX tests stuck in RECEIVED (>7 days), SEQUENCING (>7 days), or PROCESSING (>4 days) status and sends admin email alerts, separating tests waiting on lab orders from truly stuck tests.

### `send_lab_test_status_duration_alert` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Checks for PCR lab tests stuck in AT_LAB status for more than 3 days and sends admin email alerts.

### `send_vip_test_status_update`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`
- **Arguments**: `test_hash` (str), `previous_status` (str), `new_status` (str)
- **Enqueue**: `.delay()` — called on test status change for VIP/provider tests
- **Retry**: None
- **Purpose**: Sends a VIP notification email to an internal address when a provider-ordered test changes status, including provider details and order info.

---

## 11. `test_results/microgen/tasks.py`

### `submit_lab_order_approval_to_microgen`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: `lab_order_uid` (str)
- **Enqueue**: `.delay()` — called from `consults/wheel/tasks.py:fetch_and_process_completed_lab_order_details`
- **Retry**: None
- **Purpose**: Submits an approved Wheel lab order to Microgen API for DNA sequencing of vaginal microbiome samples.

### `submit_research_sample_lab_order_to_microgen`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called for research-tagged samples
- **Retry**: None
- **Purpose**: Submits electronic lab order for research (non-LDT) samples to Microgen API.

### `submit_missing_lab_order_approvals_to_microgen` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `submit_lab_order_approval_to_microgen.delay()` per lab order
- **Retry**: None
- **Purpose**: Healing task. Finds approved lab orders from the last 60 days that were never submitted to Microgen and resubmits them.

### `process_test_results_stuck_in_sequencing_status` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `process_microgen_test_results_if_exists_in_s3.delay()` per stuck test
- **Retry**: None
- **Purpose**: Finds tests stuck in SEQUENCING status for 7-60 days (excluding low-reads errors) and attempts to process results from S3.

### `process_microgen_test_results`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: `test_hash` (str), `report_errors` (bool=True), `read_from_staging` (bool=False), `release_results` (bool=True), `bypass_ready_check` (bool=False), `force_update_result_value` (bool=False)
- **Enqueue**: `.delay()` or `.apply_async(args=[test_hash], countdown=delay_seconds)` — called from Microgen webhook handler with optional random load-balancing delay
- **Retry**: None
- **Purpose**: Processes NGS results from S3 for a test, then dispatches `post_process_test_results` as a follow-up async task.

### `process_microgen_test_results_if_exists_in_s3`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — from `process_test_results_stuck_in_sequencing_status`
- **Retry**: None
- **Purpose**: Wrapper around `process_microgen_test_results` that silently ignores S3 `NoSuchKey` errors (used for healing tasks where results may not exist yet).

### `process_microgen_vag_pcr_test_results`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called from `process_lab_status_update` when "partial-results" webhook arrives
- **Retry**: None
- **Purpose**: Processes expanded PCR (vaginal STI) panel results from Microgen S3. Re-scores test if full results are already ready. Triggers PCR results email and Braze events.

### `send_summary_tests_entered_sequencing`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: None (deferred via cache lock)
- **Enqueue**: `.apply_async(countdown=cache_timeout)` — triggered via `_queue_summary_notification` with a 60-minute delay
- **Retry**: None
- **Purpose**: Sends a summary admin email of how many tests entered sequencing in the last 2 hours. Deduped via Redis cache.

### `send_summary_vpcr_results_processed`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: None (deferred via cache lock)
- **Enqueue**: `.apply_async(countdown=cache_timeout)` — triggered with 20-minute delay
- **Retry**: None
- **Purpose**: Sends summary admin email of PCR results processed in the last 2 hours.

### `send_summary_vngs_results_processed`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: None (deferred via cache lock)
- **Enqueue**: `.apply_async(countdown=cache_timeout)` — triggered with 20-minute delay
- **Retry**: None
- **Purpose**: Sends summary admin email of NGS results processed in the last 2 hours.

### `process_lab_status_update_batch`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`
- **Arguments**: `payload` (dict with `status_updates` list)
- **Enqueue**: `.delay()` — called from Microgen batch webhook endpoint
- **Retry**: None
- **Purpose**: Processes a batch of lab status updates from Microgen by calling `process_lab_status_update` synchronously for each update in the batch.

---

## 12. `test_results/lab_services/providers/junction/tasks.py`

### `create_unregistered_testkit_order_for_urine_test`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`
- **Arguments**: `urine_test_ids` (list[int]), `ecomm_order_id` (int)
- **Enqueue**: `.delay()` — called during order processing after urine tests are created
- **Retry**: None (errors are logged and alerted but not retried)
- **Purpose**: Creates "unregistered testkit orders" with Junction (UTI lab) for each urine test in a new order. Stores the Junction external_order_id and pre-populates address from the Shopify shipping address.

### `submit_lab_order_approval_to_junction`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`
- **Arguments**: `lab_order_uid` (str)
- **Enqueue**: `.delay()` — called from `consults/wheel/tasks.py:fetch_and_process_completed_lab_order_details`
- **Retry**: `bind=True, max_retries=3, default_retry_delay=60`. HTTP 5xx errors and timeouts use exponential backoff: 60s, 120s, 240s. HTTP 4xx errors are not retried.
- **Purpose**: Registers the existing unregistered testkit order with Junction after Wheel approves the lab order, providing clinician NPI, health context, and patient info. Sets `electronic_order_submitted_at` on success.

### `fetch_and_process_junction_results`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`
- **Arguments**: `external_order_id` (str)
- **Enqueue**: `.delay()` — called from Junction results_ready webhook handler
- **Retry**: `bind=True, max_retries=3` with exponential backoff (60s, 120s, 240s, max 300s)
- **Purpose**: Fetches UTI lab results from Junction API and processes them through `LabServicesOrchestrator`. Decouples webhook response time from API call latency.

### `fulfill_uti_order_in_shopify`
- **File**: `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`
- **Arguments**: `urine_test_id` (int), `tracking_number` (str), `courier` (str)
- **Enqueue**: `.delay()` — called from Junction transit webhook handler
- **Retry**: None
- **Purpose**: Marks a UTI order as fulfilled in Shopify with Junction-provided tracking information when the test kit ships to the customer.

---

## 13. `providers/tasks.py`

### `send_provider_ordered_single_test_notifications`
- **File**: `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Arguments**: `provider_email` (str), `patient_email` (str), `provider_test_order_id` (int), `payer` (str), `add_expanded_pcr` (bool=False)
- **Enqueue**: `.delay()` — called when a provider orders a single test for a patient
- **Retry**: None
- **Purpose**: Sends an internal FYI admin email to B2B in-clinic address with provider order details.

### `send_provider_bulk_ordered_tests_notification`
- **File**: `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Arguments**: `provider_email` (str), `num_ordered` (int), `provider_test_order_ids` (list)
- **Enqueue**: `.delay()` — called when a provider initiates a bulk test order
- **Retry**: None
- **Purpose**: Sends an FYI admin email noting the bulk order is pending payment.

### `send_provider_bulk_order_paid_notification`
- **File**: `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Arguments**: `ecomm_order_id` (int), `provider_email` (str), `quantity` (int)
- **Enqueue**: `.delay()` — called when a bulk provider order is paid
- **Retry**: None
- **Purpose**: Sends an FYI admin email confirming bulk order payment with order details.

### `send_provider_test_results_ready`
- **File**: `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Arguments**: `provider_email` (str)
- **Enqueue**: `.delay()` — called when test results for a provider-ordered test are released
- **Retry**: None
- **Purpose**: Sends the "Provider Results Ready" transactional email to the provider notifying them their patient's results are available.

---

## 14. `consults/wheel/tasks.py` — 19 tasks

### `submit_async_consult`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when consult intake is submitted
- **Retry**: None
- **Purpose**: Entry point for consult submission. Sets recommended prescriptions, checks if manual review is required. If manual review needed, creates a `ConsultReview` record; otherwise submits directly to Wheel.

### `submit_consult_intake_to_wheel`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: Called directly from `submit_async_consult` (no `.delay()`)
- **Retry**: None (but NewRelic monitoring)
- **Purpose**: Submits the consult intake to Wheel's async consult API. On success, fires `send_consult_intake_submitted_event` and `send_consult_intake_reviewed_email`.

### `issue_lab_results_to_wheel_for_lab_test`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `lab_test_id` (str)
- **Enqueue**: `.delay()` — called when PCR/NGS/urine results are processed
- **Retry**: None
- **Purpose**: Issues lab test results (NGS, vPCR, or urine PCR) back to Wheel as a "result follow-up" on an approved lab order.

### `resubmit_consult_photo_id_info_to_wheel`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when user re-uploads photo ID after verification failure
- **Retry**: None
- **Purpose**: Re-submits updated patient photo ID information to Wheel after a previous ID verification failure.

### `fetch_and_process_completed_consult_details`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from Wheel webhook when consult is diagnosed
- **Retry**: None
- **Purpose**: Fetches finalized consult details (clinician info, diagnosis, prescriptions, clinical notes) from Wheel and stores them. Then checks prescriptions match before completing the consult and sending to Precision pharmacy.

### `fetch_and_process_completed_lab_order_details`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `lab_order_uid` (str)
- **Enqueue**: `.delay()` — called from Wheel webhook when lab order is approved
- **Retry**: None
- **Purpose**: Fetches and stores approved lab order details from Wheel (clinician NPI, display name, disposition). Routes approved orders to Microgen (vaginal) or Junction (urine) lab providers.

### `retry_consult_detail_processing` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `fetch_and_process_completed_consult_details.delay()` or `fetch_and_process_referred_consult_details.delay()`
- **Retry**: None
- **Purpose**: Healing task. Finds consults in IN_PROGRESS/SUBMITTED/ERROR status for more than 24 hours, checks their Wheel status, and retries fetching/processing if they're finished on the Wheel side.

### `retry_creating_async_consults` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `submit_async_consult.delay()`
- **Retry**: None
- **Purpose**: Finds SUBMITTED consults that were submitted 1-5 days ago but have no `submitted_at` timestamp, and retries submitting them to Wheel.

### `retry_errored_consult_creation` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `submit_async_consult.delay()`
- **Retry**: None
- **Purpose**: Finds consults in ERROR status with no `submitted_at` and retries creating them in Wheel.

### `fetch_and_process_follow_up_consult_details`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `lab_order_uid` (str), `follow_up_external_id` (str)
- **Enqueue**: `.delay()` — called from `send_notification_for_diagnosis_pending_consults` and from Wheel follow-up webhooks
- **Retry**: None
- **Purpose**: Fetches Wheel diagnosis follow-up (interpretability, patient instructions, contact requirements) and confirms or flags diagnosis. Creates `ConsultTask` if diagnosis is disagreed upon.

### `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from `fetch_and_process_completed_consult_details`
- **Retry**: None
- **Purpose**: Verifies that the prescriptions from Wheel match what was recommended. If they match, marks the consult COMPLETE, fires Braze `CONSULT_COMPLETED` event, and sends prescriptions to Precision pharmacy.

### `check_recommended_prescriptions_against_prescribed`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str), `notify_admins` (bool=False)
- **Enqueue**: Called directly (no `.delay()`)
- **Retry**: None
- **Purpose**: Compares recommended prescription slugs to actual prescribed slugs. If mismatched and `notify_admins=True`, creates a `ConsultReview` for manual review.

### `fetch_and_process_referred_consult_details`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from `retry_consult_detail_processing` and Wheel webhook for referred consults
- **Retry**: None
- **Purpose**: Handles consults that Wheel referred out (disqualified). Stores referral info, creates a `ConsultTask`, marks consult as REFERRED, and sends "care referred out" email.

### `submit_lab_order_to_wheel`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `lab_order_uid` (str)
- **Enqueue**: `.delay()` or `.apply_async((lab_order.uid,), countdown=300)` — called from `consults/utils.py` when lab order intake is submitted
- **Retry**: None
- **Purpose**: Submits a new lab order (health history/requisition) to Wheel for clinical review. Skips if already approved or submitted.

### `resubmit_stuck_lab_orders_to_wheel` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `submit_lab_order_to_wheel.delay()`
- **Retry**: None
- **Purpose**: Finds lab orders in CREATED/SUBMITTED status with a provider_id and submitted intake that are more than 1 hour old (and not in manual-review states), clears the provider_id, and resubmits to Wheel.

### `resubmit_errored_lab_orders_to_wheel` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat; dispatches `submit_lab_order_to_wheel.delay()`
- **Retry**: None
- **Purpose**: Finds lab orders in ERROR status and resubmits them to Wheel. Skips Canadian addresses and orders that already have results sent.

### `mark_wheel_consult_message_as_read`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult_uid` (str), `message_id` (str)
- **Enqueue**: `.delay()` — called when provider reads a consult message
- **Retry**: None
- **Purpose**: Marks a Wheel consult thread message as read via the Wheel API.

### `send_notification_for_stuck_consults` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends admin email alerts for: (1) non-UTI consults stuck in clinical review for >24 hours, (2) stuck lab orders, and (3) open manual consult reviews.

### `send_notification_for_stuck_uti_consults` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: UTI-specific monitoring alert for consults in review for >24 hours and open UTI consult manual reviews.

### `send_notification_for_diagnosis_pending_consults` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `hours_threshold` (int=24)
- **Enqueue**: Celery Beat; dispatches `fetch_and_process_follow_up_consult_details.delay()`
- **Retry**: None
- **Purpose**: Finds tests with diagnosis pending from Wheel for more than 24 hours (both vaginal and UTI), retries fetching the follow-up, and sends admin email alerts broken down by test type.

### `send_notification_for_care_orders_in_bad_states` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Comprehensive data integrity check. Alerts for: care orders without consults, ungated RX orders with users but no consult, and completed consults missing prescription fills.

### `attach_latest_otc_treatment_to_consult`
- **File**: `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`
- **Arguments**: `consult` (Consult object — not serializable, so called directly)
- **Enqueue**: Called directly from `_post_prescription_fetch_and_process_consult_details` (no `.delay()`)
- **Retry**: None
- **Purpose**: If the user has an active probiotic subscription, finds the latest OTCTreatment for that product and attaches it to the consult.

---

## 15. `transactional_email/tasks.py` — 27 tasks

### `send_test_activated_reminder` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends reminder emails to users who activated their test but haven't progressed to "taken" within 4 days.

### `send_tests_in_transit_through_usps_and_fedex_emails` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends "test in transit" emails to users whose samples moved to IN_TRANSIT status in the last 3 days.

### `send_tests_in_transit_hh_incomplete` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends "sample in transit but health history incomplete" emails, prompting users to fill out their health history while their sample is in transit.

### `send_tests_received_at_lab_hh_incomplete` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Similar to above — sends reminder when sample is received at the lab but health history is still incomplete.

### `send_ldt_test_sample_received_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called from Microgen webhook handler when status = "received"
- **Retry**: None
- **Purpose**: Sends an email to users notifying them their LDT sample has arrived at the lab (separate templates for standard vs. comprehensive tests).

### `send_ldt_test_sample_sequencing_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called from Microgen webhook handler when status = "sequencing"
- **Retry**: None
- **Purpose**: Sends an update to users that their LDT sample is being sequenced at the lab.

### `send_ldt_tests_results_almost_ready` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends "results almost ready" emails to users whose tests entered sequencing approximately 10 days ago and are still in sequencing status.

### `send_pcr_test_results_ready`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called from `process_microgen_vag_pcr_test_results`
- **Retry**: None
- **Purpose**: Sends email to users that their expanded PCR (partial results) are ready to view.

### `send_expert_call_emails` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends expert coaching call offer emails 1 day after results are ready, excluding users who have already purchased care.

### `send_view_unread_plan_emails` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends "view your plan" reminder emails to users whose results were viewed 3 days ago but whose plan has not yet been viewed.

### `send_eligible_for_care_1_for_test`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `test_id` (int)
- **Enqueue**: `.delay()` — called from `test_results/tasks.py:send_results_ready_emails`
- **Retry**: None
- **Purpose**: Sends first care eligibility email (Care Eligibility 1) to users immediately when they become eligible.

### `send_eligible_for_a_la_care_not_treatment_program`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `test_id` (int)
- **Enqueue**: `.delay()` — called from `test_results/tasks.py:send_results_ready_emails`
- **Retry**: None
- **Purpose**: Sends a-la-carte care eligibility email to users who are eligible for individual treatments but not a full bundle program.

### `send_a_la_care_treatments_ready`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when a-la-carte treatment plan is ready
- **Retry**: None
- **Purpose**: Sends "Individual Treatments Ready" email linking to the treatment plan.

### `send_eligible_for_care_2` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Second care eligibility reminder email — sent 6 days after results ready.

### `send_eligible_for_care_3` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Third care eligibility reminder email — sent 12 days after results ready.

### `send_treatments_shipped`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `prescription_fill_id` (int)
- **Enqueue**: `.delay()` — called from Precision "shipped" webhook handler
- **Retry**: None
- **Purpose**: Sends a "treatments shipped" email with tracking information when prescriptions are shipped from Precision pharmacy.

### `send_treatments_delivered`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `prescription_fill_id` (int)
- **Enqueue**: `.delay()` — called from Precision "delivered" webhook handler
- **Retry**: None
- **Purpose**: Sends a "treatments delivered" email when prescriptions are delivered. Uses different templates for refills vs. initial treatment and for a-la-carte vs. bundle purchases.

### `send_consult_intake_abandonment_reminder` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends first abandonment reminder email to users who paid for care but haven't submitted intake after 2-6 hours (excludes STI consults).

### `send_consult_intake_abandonment_reminder_2` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Second abandonment reminder at 24-48 hours after care paid.

### `send_sti_consult_intake_abandonment_reminder` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: STI-specific abandonment reminder at 24-36 hours after care paid.

### `send_sti_prescription_sent_to_pharmacy_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when STI prescription is sent to local pharmacy
- **Retry**: None
- **Purpose**: Sends pickup instructions email for STI prescriptions routed to patient's local pharmacy.

### `send_email_organon_prescriptions_ready`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called for Organon pharmacy prescriptions
- **Retry**: None
- **Purpose**: Sends prescription pickup instructions for Organon-partnered pharmacy.

### `send_consult_intake_reviewed_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from `consults/wheel/tasks.py:submit_consult_intake_to_wheel`
- **Retry**: None
- **Purpose**: Sends "intake reviewed" notification email when Wheel processes the consult.

### `send_treatment_plan_ready_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when treatment plan is finalized
- **Retry**: None
- **Purpose**: Sends "treatment plan ready" email linking to the treatment plan page.

### `send_lab_order_rejected_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `lab_order_uid` (str)
- **Enqueue**: `.delay()` — called when Wheel rejects a lab order
- **Retry**: None
- **Purpose**: Sends an email to the user informing them their lab order was rejected and directing them to contact support.

### `send_id_verification_failed_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when ID verification fails
- **Retry**: None
- **Purpose**: Sends an ID verification failure email with a link to re-upload their photo ID (allows duplicates — can be sent multiple times).

### `send_care_referred_out_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called from `fetch_and_process_referred_consult_details`
- **Retry**: None
- **Purpose**: Sends care referred-out email when Wheel auto-refers a patient out due to disqualifying health responses.

### `send_new_consult_message_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `consult_uid` (str)
- **Enqueue**: `.delay()` — called when provider sends a message in consult thread
- **Retry**: None
- **Purpose**: Sends email notification to user when there is a new message in their consult thread.

### `send_care_first_check_in_email` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends a first check-in email 4 hours after treatment plan status changes to COMPLETE for bundle purchase consults.

### `send_prescription_refills_available` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Finds consults eligible for prescription refills (3+ weeks after delivery) and sends "prescription refills available" emails with a link to the refill page.

### `send_sample_taken_but_not_in_transit_reminder` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Sends reminder to users whose sample has been taken for 5+ days but hasn't been scanned in transit (i.e., they may have forgotten to mail it back).

### `send_test_sample_at_lab_but_not_activated`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `test_hash` (str)
- **Enqueue**: `.delay()` — called from Microgen webhook when test received at lab but not yet activated
- **Retry**: None
- **Purpose**: Sends activation reminder email when a sample arrives at the lab but the test hasn't been activated by the user (no account created).

### `send_test_sample_received_at_lab_but_not_activated` (periodic)
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: None (periodic/beat task)
- **Enqueue**: Celery Beat
- **Retry**: None
- **Purpose**: Batch version — finds all tests received at lab in the last week without user activation and sends activation reminder emails.

### `send_account_transfer_verification_email`
- **File**: `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`
- **Arguments**: `user_id` (int), `order_email` (str), `order_number` (str)
- **Enqueue**: `.delay()` — called when user tries to claim an order placed with a different email
- **Retry**: None
- **Purpose**: Creates an `OrderTransferVerification` record and sends a verification email to the order email address so the user can confirm they want to transfer the order to their Evvy account.

---

## Summary Statistics

| Module | Task Count |
|--------|-----------|
| `analytics/tasks.py` | 31 tasks |
| `transactional_email/tasks.py` | 27 tasks |
| `consults/wheel/tasks.py` | 19 tasks |
| `shipping/precision/tasks.py` | 9 tasks |
| `ecomm/tasks.py` | 9 tasks |
| `test_results/microgen/tasks.py` | 12 tasks |
| `test_results/lab_services/providers/junction/tasks.py` | 4 tasks |
| `shipping/tasks.py` | 8 tasks |
| `test_results/tasks.py` | 7 tasks |
| `care/tasks.py` | 4 tasks |
| `providers/tasks.py` | 4 tasks |
| `accounts/tasks.py` | 1 task |
| `subscriptions/tasks.py` | 1 task |
| `app/tasks.py` | 1 task |
| `ecomm/shopify/tasks.py` | 1 task |
| **Total** | **~138 tasks** |

## Retry Configuration Summary

Only 3 tasks have explicit retry logic:

1. **`void_share_a_sale_transaction`** (`ecomm/tasks.py`): Uses `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` from the `retrying` library — up to 3 attempts with exponential backoff starting at 500ms.

2. **`submit_lab_order_approval_to_junction`** (`test_results/lab_services/providers/junction/tasks.py`): `bind=True, max_retries=3, default_retry_delay=60` with exponential backoff (60s → 120s → 240s) for HTTP 5xx and timeouts only.

3. **`fetch_and_process_junction_results`** (`test_results/lab_services/providers/junction/tasks.py`): `bind=True, max_retries=3` with exponential backoff (60s → 120s → 240s, capped at 300s) for any exception.

One task has task-level time limits (not retries):
- **`retry_failed_shopify_orders`** (`ecomm/shopify/tasks.py`): `soft_time_limit=600, time_limit=900` seconds.
