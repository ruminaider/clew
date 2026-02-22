# Complete Celery Task Inventory — Evvy Backend

This document catalogs every Celery task defined across the evvy backend codebase. Tasks are organized by module.

---

## 1. `backend/app/tasks.py`

### `clean_log_entries`
- **Decorator:** `@shared_task`
- **Arguments:** `delete_all=False`
- **Enqueue pattern:** Scheduled via celery beat — daily at midnight
- **Retry config:** None
- **Business purpose:** Deletes `LogEntry` audit log records older than 30 days (RETENTION_PERIOD = 30 days). If `delete_all=True`, deletes all records regardless of age. Keeps the audit log table from growing indefinitely.

---

## 2. `backend/app/celery.py`

### `debug_task`
- **Decorator:** `@app.task(bind=True)`
- **Arguments:** `self` (bound task)
- **Enqueue pattern:** Scheduled via celery beat — every 15 minutes (`*/15`)
- **Retry config:** None
- **Business purpose:** Heartbeat/health check task. Confirms the Celery worker is alive and processing tasks.

---

## 3. `backend/subscriptions/tasks.py`

### `cancel_expired_prescription_subscriptions`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 3:00 AM
- **Retry config:** None (re-raises exceptions for visibility)
- **Business purpose:** Cancels Recharge subscriptions for prescriptions that have run out of refills. Delegates to `cancel_subscriptions_for_expired_prescriptions()` service.

---

## 4. `backend/accounts/tasks.py`

### `send_intake_completed_notifications`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_email` (str)
- **Enqueue pattern:** `.delay(provider_email)` — called when a provider completes intake
- **Retry config:** None
- **Business purpose:** Sends admin email notification when a B2B provider registers and completes their intake form. Sends to `B2B_PROVIDER_REGISTRATION_EMAIL` and `B2B_IN_CLINIC_EMAIL` with provider profile details. Handles special messaging for NY and "Other" state providers.

---

## 5. `backend/ecomm/shopify/tasks.py`

### `retry_failed_shopify_orders`
- **Decorator:** `@shared_task(soft_time_limit=600, time_limit=900)`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 1:00 AM
- **Retry config:** `soft_time_limit=600` (10 min soft limit), `time_limit=900` (15 min hard limit), paginated with `MAX_PAGES=50` guard
- **Business purpose:** Fetches Shopify orders from the last 3 days (excluding the last hour) that may not have been processed into the Evvy system. Pages through up to 50 pages of orders and calls `process_shopify_order_from_api()` to catch any orders missed during real-time webhook processing.

---

## 6. `backend/care/tasks.py`

### `update_treatment_end_date`
- **Decorator:** `@shared_task`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue pattern:** `.delay(treatment_plan_id)`
- **Retry config:** None
- **Business purpose:** Recalculates and saves the treatment end date for a given `TreatmentPlan` using `get_treatment_end_date()`. Called when a treatment plan's details change.

### `create_or_reset_calendar_treatments`
- **Decorator:** `@shared_task`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue pattern:** `.delay(treatment_plan_id)`
- **Retry config:** None
- **Business purpose:** Rebuilds the calendar treatment schedule for a treatment plan. Deletes all existing `CalendarTreatment` records and recreates them via `build_treatment_calendar()`. Used when prescriptions change or a plan needs reset.

### `heal_prescription_fill_orders`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 2 AM, 10 AM, 6 PM
- **Retry config:** None
- **Business purpose:** Healing task that finds `PrescriptionFill` records modified in the last 24 hours that have an `order` set but are missing a `PrescriptionFillOrder` linking record. Creates the missing `PrescriptionFillOrder` records for data consistency.

### `heal_otc_treatment_only_orders`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 2:15 AM, 10:15 AM, 6:15 PM
- **Retry config:** None
- **Business purpose:** Finds OTC (over-the-counter) treatment orders from the last 24 hours that were never sent to the pharmacy. For orders that contain only OTC products (no Rx), creates a `PrescriptionFill`, links OTC treatments, calls `send_otc_treatment_fill_request.delay()`, and marks the cart as purchased.

---

## 7. `backend/ecomm/tasks.py`

### `send_patient_ordered_provider_test_notification`
- **Decorator:** `@shared_task`
- **Arguments:** `patient_email` (str), `order_sku` (str), `order_provider_id` (int)
- **Enqueue pattern:** `.delay(patient_email, order_sku, order_provider_id)`
- **Retry config:** None
- **Business purpose:** Sends an admin FYI email to `B2B_IN_CLINIC_EMAIL` when a patient places an order for a provider-ordered test. Indicates who paid (provider vs patient) based on SKU.

### `void_share_a_sale_transaction`
- **Decorator:** `@shared_task` + `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)`
- **Arguments:** `order_number` (str), `order_date` (str), `reason` (str)
- **Enqueue pattern:** `.delay(order_number, order_date, reason)` — called on order cancellations
- **Retry config:** `retrying` library — up to 3 attempts, exponential backoff starting at 500ms
- **Business purpose:** Calls the ShareASale affiliate marketing API to void a transaction when an order is cancelled, preventing affiliate commissions from being paid on refunded orders.

### `send_prescription_refill_request`
- **Decorator:** `@shared_task`
- **Arguments:** `order_id` (int), `prescription_fill_id` (int)
- **Enqueue pattern:** `.delay(order_id, prescription_fill_id)` — called when a refill order is processed
- **Retry config:** None (raises on error)
- **Business purpose:** Orchestrates the full prescription refill fulfillment flow for a paid refill order. Validates state restrictions, checks remaining refills, updates fill status to CREATED, sends analytics event, creates patient/prescription/OTC records at Precision pharmacy, and submits the fill request.

### `send_otc_treatment_fill_request`
- **Decorator:** `@shared_task`
- **Arguments:** `order_id` (int), `prescription_fill_id` (int)
- **Enqueue pattern:** `.delay(order_id, prescription_fill_id)` — called from `care/tasks.py` heal task
- **Retry config:** None
- **Business purpose:** Separate fill request path for OTC-only orders (no prescriptions). No state restrictions or refill checks needed. Creates patient at Precision, sends each OTC treatment, then submits the fill request.

### `attach_unattached_orders_to_user`
- **Decorator:** `@shared_task`
- **Arguments:** `user_id` (int)
- **Enqueue pattern:** `.delay(user_id)` — called when a new user account is created
- **Retry config:** None
- **Business purpose:** Finds all unattached orders (no user set) whose email matches the new user, assigns the user to those orders, and for ungated Rx orders, attaches treatments to the latest consult or creates a new one.

### `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Decorator:** `@shared_task`
- **Arguments:** `user_id` (int), `order_number` (str)
- **Enqueue pattern:** `.delay(user_id, order_number)` — called after attaching orders to a user
- **Retry config:** None
- **Business purpose:** For ungated Rx orders, either adds selected treatments to an existing in-progress consult, or auto-creates a new `TYPE_UNGATED_RX` consult. Handles health history pre-population from associated tests when purchased via health history cross-sell flow.

### `create_consults_for_ungated_rx_orders_with_users_but_no_consult`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 7:15 AM
- **Retry config:** None
- **Business purpose:** Healing task that finds ungated Rx orders with a user but no associated `ConsultOrder`. Creates consults for these missed orders by calling `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`.

### `process_gift_card_redemptions`
- **Decorator:** `@shared_task`
- **Arguments:** `order_id` (int)
- **Enqueue pattern:** `.delay(order_id)`
- **Retry config:** None (raises on error)
- **Business purpose:** Processes gift card redemptions for a specific order by calling `GiftCardRedemptionService.process_order_gift_card_redemptions()`.

### `process_gift_cards`
- **Decorator:** `@shared_task`
- **Arguments:** `order_id` (int), `payload` (dict, optional)
- **Enqueue pattern:** `.delay(order_id, payload)` or `.delay(order_id)`
- **Retry config:** None (raises on error)
- **Business purpose:** Processes both gift card purchases and redemptions for an order. If payload is provided, handles purchases; otherwise only processes redemptions.

### `reprocess_subscription_refill_orders_daily`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 4:00 AM
- **Retry config:** None (raises on exception)
- **Business purpose:** Reprocesses subscription refill orders from the last 24 hours that were missed or incorrectly routed. Delegates to `scripts.reprocess_subscription_refill_orders` with `batch_size=200`.

---

## 8. `backend/analytics/tasks.py`

### `send_custom_analytics_event_to_fullstory_async`
- **Decorator:** `@shared_task`
- **Arguments:** `user_id` (int), `event_name` (str), `event_properties` (dict), `use_recent_session` (bool)
- **Enqueue pattern:** `.delay(user_id, event_name, event_properties, use_recent_session)` — called from `send_custom_analytics_event_to_destinations()`
- **Retry config:** None
- **Business purpose:** Async wrapper for sending events to Fullstory analytics.

### `send_custom_analytics_event_to_klaviyo_async`
- **Decorator:** `@shared_task`
- **Arguments:** `payload` (dict)
- **Enqueue pattern:** `.delay(payload)` — called from `send_custom_analytics_event_to_destinations()`
- **Retry config:** None
- **Business purpose:** Async wrapper for sending events to Klaviyo email/SMS platform.

### `send_sample_sequencing_provider_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `provider_test_order_id` (int)
- **Enqueue pattern:** `.delay(test_hash, provider_test_order.id)` — from microgen task
- **Retry config:** None
- **Business purpose:** Sends a `[Provider] Sample Sequencing` Klaviyo event to a provider when their ordered patient's test enters sequencing.

### `send_pcr_test_results_ready_provider_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `provider_test_order_id` (int)
- **Enqueue pattern:** `.delay(test_hash, provider_test_order.id)` — from microgen task
- **Retry config:** None
- **Business purpose:** Sends a `[Provider] Preliminary Results Ready` Klaviyo event to a provider when PCR results are ready for their patient's test.

### `send_results_ready_analytics_events`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `eligible_for_care` (bool), `ineligible_reason` (str or None)
- **Enqueue pattern:** `.delay(test_hash, eligible_for_care, ineligible_reason)` — called from test results release
- **Retry config:** None
- **Business purpose:** Large event task triggered when test results are ready. Creates `CareEligible` records, calculates bundle/a-la-carte eligibility, creates `BundleTreatment` and `ALaCareTreatment` records, sends "Results Ready" event to Fullstory, Klaviyo, and Braze, and updates user profiles.

### `send_urine_test_results_ready_analytics_events`
- **Decorator:** `@shared_task`
- **Arguments:** `urine_test_hash` (str)
- **Enqueue pattern:** `.delay(urine_test_hash)` — from urine test results release
- **Retry config:** None
- **Business purpose:** UTI-specific version of the results ready analytics task. Creates/updates `CareEligible` records with UTI care eligibility, expiration date, and reason for ineligibility.

### `send_care_checkout_created_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)`
- **Retry config:** None
- **Business purpose:** Sends "Care Checkout Created" event to Fullstory when a user begins the care checkout flow. Includes test details, care price, eligibility, and selected treatments.

### `send_ungated_rx_order_paid_event`
- **Decorator:** `@shared_task`
- **Arguments:** `order_number` (str)
- **Enqueue pattern:** `.delay(order_number)` — on order payment
- **Retry config:** None
- **Business purpose:** Sends "Ungated Paid" event to Fullstory and `URX_PURCHASE` event to Braze when a symptom relief (ungated Rx) order is paid.

### `send_mpt_voucher_paid_event`
- **Decorator:** `@shared_task`
- **Arguments:** `user_id` (int)
- **Enqueue pattern:** `.delay(user_id)`
- **Retry config:** None
- **Business purpose:** Sends "MPT Voucher Paid" event to Fullstory, Klaviyo, and Braze when a user purchases an MPT (multi-panel test) voucher.

### `send_consult_paid_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str), `order_number` (str)
- **Enqueue pattern:** `.delay(consult_uid, order_number)` — on care order payment
- **Retry config:** None
- **Business purpose:** Sends "Care Paid" event across Fullstory, Klaviyo, and Braze when a consult is paid. Includes SKUs, purchase type, pharmacy type, care eligibility, subscription info, and treatment details.

### `send_any_paid_event`
- **Decorator:** `@shared_task`
- **Arguments:** `order_number` (str)
- **Enqueue pattern:** `.delay(order_number)` — on any order payment
- **Retry config:** None
- **Business purpose:** Sends generic "Any Paid" event to Fullstory for any order type. Classifies the order as test, vaginitis care, refill, ungated Rx, refill+test, vaginitis+test, or other.

### `send_prescription_refills_paid_event`
- **Decorator:** `@shared_task`
- **Arguments:** `prescription_refill_id` (int), `order_number` (str)
- **Enqueue pattern:** `.delay(prescription_fill_id, order.provider_id)` — from `send_prescription_refill_request` task
- **Retry config:** None
- **Business purpose:** Sends "Prescription Refills Paid" event to Fullstory when a prescription refill is submitted. Includes line item slugs and consult UID.

### `send_additional_tests_checkout_created_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)`
- **Retry config:** None
- **Business purpose:** Sends "Additional Tests Checkout Created" event to Fullstory.

### `send_additional_tests_paid_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `order_number` (str)
- **Enqueue pattern:** `.delay(test_hash, order_number)`
- **Retry config:** None
- **Business purpose:** Sends "Additional Tests Paid" event to Fullstory when an additional test order is paid.

### `send_consult_intake_ineligible_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str), `refer_out_reason` (str)
- **Enqueue pattern:** `.delay(consult_uid, refer_out_reason)`
- **Retry config:** None
- **Business purpose:** Sends "Consult Intake Ineligible" event to Fullstory when a consult intake is rejected/referred out.

### `send_rx_order_attached_to_account_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str), `order_number` (str)
- **Enqueue pattern:** `.delay(consult.uid, order.order_number)` — from `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Retry config:** None
- **Business purpose:** Sends "RX Attached to Account" Klaviyo event when an Rx order is linked to a user account, including consult type, purchase type, and selected treatment slugs.

### `send_consult_intake_submitted_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — from `submit_consult_intake_to_wheel` task
- **Retry config:** None
- **Business purpose:** Sends "Consult Intake Submitted" event to Fullstory, Klaviyo, and Braze (with UTI-specific handling). Includes recommended prescriptions and pricing.

### `send_coaching_call_completed_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `coaching_call_notes_id` (int, optional), `num_calls` (int, optional)
- **Enqueue pattern:** `.delay(test_hash, ...)`
- **Retry config:** None
- **Business purpose:** Sends "Coaching Call Completed" event to Fullstory.

### `send_treatment_delivered_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(treatment_plan.consult.uid)` — from `send_treatment_probably_delivered_events_for_treatment_plans`
- **Retry config:** None
- **Business purpose:** Sends "Treatment Delivered" Klaviyo event with SKUs, treatment start/end dates, deduplicated by `consult_uid`.

### `send_estimated_treatment_started_events`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 7:15 AM
- **Retry config:** None
- **Business purpose:** Finds treatment plans where the estimated start date is today, and enqueues individual `send_estimated_treatment_started_event` tasks for each.

### `send_estimated_treatment_started_event`
- **Decorator:** `@shared_task`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue pattern:** `.delay(treatment_plan.id)` — from `send_estimated_treatment_started_events`
- **Retry config:** None
- **Business purpose:** Sends "Treatment Started" Klaviyo event if the estimated treatment start date is today or yesterday, including treatment slugs and dates.

### `send_test_delivered_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)`
- **Retry config:** None
- **Business purpose:** Sends "Test Kit Delivered" Klaviyo event to the ecomm order email when a test kit is delivered.

### `send_health_history_completed_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)`
- **Retry config:** None
- **Business purpose:** Sends "Health History Completed" Klaviyo event when a user submits their health history form.

### `send_updated_treatment_start_date_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)`
- **Retry config:** None
- **Business purpose:** Sends "Updated Treatment Start Date" Klaviyo event when a user changes their treatment start date.

### `send_treatment_ended_event`
- **Decorator:** `@shared_task`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue pattern:** `.delay(treatment_plan.id)` — from `send_treatment_ended_events_for_treatment_plans`
- **Retry config:** None
- **Business purpose:** Sends "Treatment Ended" to Klaviyo and `TREATMENT_ENDED` event to Braze when a treatment plan's end date is reached.

### `send_treatment_ended_events_for_treatment_plans`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 2:15 AM
- **Retry config:** None
- **Business purpose:** Fan-out task: finds treatment plans ending today or yesterday and enqueues individual `send_treatment_ended_event` tasks.

### `send_treatment_probably_delivered_events_for_treatment_plans`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 6:15 AM
- **Retry config:** None
- **Business purpose:** Fan-out task: finds treatment plans where delivery is inferred (no actual delivery timestamp, created `AVERAGE_PRESCRIPTION_FULFILLMENT_DAYS` ago) and enqueues individual `send_treatment_delivered_event` tasks.

### `send_provider_registered_event`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_id` (int)
- **Enqueue pattern:** `.delay(provider_id)` — on provider registration
- **Retry config:** None
- **Business purpose:** Sends "Provider Registered" Klaviyo event when a provider completes registration.

### `send_provider_verified_event`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_id` (int)
- **Enqueue pattern:** `.delay(provider_id)` — on provider verification
- **Retry config:** None
- **Business purpose:** Sends "[Provider] Provider Verified" Klaviyo event when a provider is verified by Evvy staff.

### `send_provider_ordered_test_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_id` (int), `provider_test_order_ids` (list), `payer` (str), `add_expanded_pcr` (bool), `patient_email` (str, optional)
- **Enqueue pattern:** `.delay(...)` — when a provider orders a test for a patient
- **Retry config:** None
- **Business purpose:** Sends two Klaviyo events: "Provider Ordered A Test for User" (to the patient) and "[Provider] Provider Ordered a Test" (to the provider), including a checkout link for the patient.

### `send_provider_reminded_patient_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_id` (int), `patient_email` (str)
- **Enqueue pattern:** `.delay(provider_id, patient_email)` — when a provider sends a reminder
- **Retry config:** None
- **Business purpose:** Sends "Provider Reminded User to Purchase Test" Klaviyo event with a checkout link.

### `send_viewed_plan_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `test_id` (int)
- **Enqueue pattern:** `.delay(test_id)` — when a user views their care plan
- **Retry config:** None
- **Business purpose:** Sends "Viewed Plan" Klaviyo event, deduplicated by test hash.

### `send_consult_intake_started_klaviyo_event`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — when a user starts the consult intake
- **Retry config:** None
- **Business purpose:** Sends "Consult Intake Started" Klaviyo event, deduplicated by consult UID.

### `send_three_weeks_after_treatment_delivered_klaviyo`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 7:15 AM
- **Retry config:** None
- **Business purpose:** Sends "Consult Eligible for Refill" Klaviyo event to users whose treatment has been delivered ~3 weeks ago (eligible for refill). Uses `find_consults_eligible_for_refill()` to find candidates.

---

## 9. `backend/providers/tasks.py`

### `send_provider_ordered_single_test_notifications`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_email` (str), `patient_email` (str), `provider_test_order_id` (int), `payer` (str), `add_expanded_pcr` (bool, default False)
- **Enqueue pattern:** `.delay(...)` — when a provider orders a test for a single patient
- **Retry config:** None
- **Business purpose:** Sends FYI admin email to `B2B_IN_CLINIC_EMAIL` when a provider orders a test for a patient.

### `send_provider_bulk_ordered_tests_notification`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_email` (str), `num_ordered` (int), `provider_test_order_ids` (list)
- **Enqueue pattern:** `.delay(...)` — when a provider creates a bulk test order (pending payment)
- **Retry config:** None
- **Business purpose:** Sends FYI admin email to `B2B_IN_CLINIC_EMAIL` for a bulk test order pending payment.

### `send_provider_bulk_order_paid_notification`
- **Decorator:** `@shared_task`
- **Arguments:** `ecomm_order_id` (int), `provider_email` (str), `quantity` (int)
- **Enqueue pattern:** `.delay(...)` — when a provider bulk order is paid
- **Retry config:** None
- **Business purpose:** Sends FYI admin email to `B2B_IN_CLINIC_EMAIL` confirming a provider bulk order is paid.

### `send_provider_test_results_ready`
- **Decorator:** `@shared_task`
- **Arguments:** `provider_email` (str)
- **Enqueue pattern:** `.delay(provider_email)` — when provider-ordered test results are ready
- **Retry config:** None
- **Business purpose:** Sends a transactional email to the provider using `TEMPLATE_PROVIDER_RESULTS_READY` template when their patient's test results are ready.

---

## 10. `backend/shipping/precision/tasks.py`

### `process_precision_pharmacy_webhook`
- **Decorator:** `@shared_task`
- **Arguments:** `payload` (dict)
- **Enqueue pattern:** `.delay(payload)` — from webhook handler view
- **Retry config:** None
- **Business purpose:** Routes Precision pharmacy webhooks by type: `shipped` (calls `process_precision_shipped_webhook`), `delivered` (calls `process_precision_delivered_webhook`), `received` and `warning` are logged only.

### `send_prescription_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str), `skip_set_sent_to_pharmacy` (bool, default False)
- **Enqueue pattern:** `.delay(consult.uid)` — from `send_missing_prescriptions_to_precision` and `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **Retry config:** None
- **Business purpose:** Sends an initial prescription to Precision pharmacy for a completed consult. Creates patient in Precision, creates and fills prescription, marks consult as sent to pharmacy. Also sends Braze refill eligibility event.

### `send_create_patient_request_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** `prescription_fill_id` (int), `consult_uid` (str, optional), `user_id` (int, optional), `order_id` (int, optional)
- **Enqueue pattern:** Called directly (not `.delay()`) from `send_prescription_refill_request`
- **Retry config:** None (logs exception, doesn't raise)
- **Business purpose:** Creates or updates a patient record in Precision pharmacy and saves the resulting `pharmacy_patient_id` to the `PrescriptionFill`. Accepts consult, user, or order as patient identifier.

### `send_create_prescription_request_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** `prescription_uid` (str), `fill_quantity` (int, optional), `prescription_fill_prescription` (PrescriptionFillPrescriptions, optional)
- **Enqueue pattern:** Called directly (not `.delay()`) from `send_prescription_refill_request`
- **Retry config:** None (re-raises after setting fill to WARNING status)
- **Business purpose:** Creates a prescription record in Precision pharmacy for a specific `Prescription` object. Sets `PrescriptionFill` status to WARNING on failure.

### `send_create_otc_treatment_request_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** `otc_treatment_uid` (str), `prescription_fill_otc_treatment_id` (int)
- **Enqueue pattern:** Called directly (not `.delay()`) from both refill request tasks
- **Retry config:** None (re-raises after setting fill to WARNING status)
- **Business purpose:** Creates an OTC treatment record in Precision pharmacy. Sets `PrescriptionFill` status to WARNING on failure.

### `send_fill_request_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** `fill_uid` (int), `order_shipping_address` (optional)
- **Enqueue pattern:** Called directly (not `.delay()`) from refill request tasks
- **Retry config:** None (re-raises after setting fill to WARNING status, logs to NewRelic)
- **Business purpose:** Submits the actual fill request to Precision pharmacy. Updates fill status to WARNING and clears `sent_to_pharmacy_at` on failure. Logs to NewRelic and order monitoring system.

### `send_cancel_fill_request_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** `fill_uid` (int)
- **Enqueue pattern:** Called directly (not `.delay()`) from `send_prescription_refill_request`
- **Retry config:** None
- **Business purpose:** Cancels a fill request at Precision pharmacy. Raises if fill is already shipped or delivered (cannot cancel).

### `send_missing_prescriptions_to_precision`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 1:15 AM and 7:15 PM
- **Retry config:** None
- **Business purpose:** Healing task that finds consults completed in the last 2 days that were never sent to Precision pharmacy. For each, checks prescribed vs recommended slugs match, then enqueues `send_prescription_to_precision`.

### `retry_failed_prescription_fills`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 2:30 AM, 10:30 AM, 6:30 PM
- **Retry config:** None (task-level retry, not `@retry` decorator). Internal safeguards: only retries fills in WARNING status that are older than 1 hour and younger than 7 days; limit of 10 per run; fills failing >3 days are marked FAILED.
- **Business purpose:** Retries prescription fills stuck in WARNING status (failed to send to Precision). Creates `ConsultTask` for fills marked as permanently failed.

### `send_notification_for_stuck_prescriptions`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 10:00 AM
- **Retry config:** None
- **Business purpose:** Monitors prescription fills that have been in CREATED status for more than 3 business days. Sends an admin alert email with the list of stuck refill fills.

---

## 11. `backend/shipping/tasks.py`

### `update_individual_shipping_status`
- **Decorator:** `@shared_task`
- **Arguments:** `status_id` (int)
- **Enqueue pattern:** `.delay(status.id)` — from `update_eligible_shipping_statuses_async`
- **Retry config:** None
- **Business purpose:** Updates the USPS/FedEx shipping tracking status for a single `ShippingStatus` record.

### `update_eligible_shipping_statuses_async`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 8:30 AM, 4:30 PM, 1:30 AM
- **Retry config:** None
- **Business purpose:** Fan-out task that finds all relevant shipping status records (test kits and samples) needing an update (with different time windows: daily for kits and recent samples, every 3 days for stale samples, weekly for unactivated samples) and enqueues individual `update_individual_shipping_status` tasks.

### `send_daily_express_orders_email`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 9:30 AM
- **Retry config:** None
- **Business purpose:** Sends a daily email and updates a Google Sheet with all express-shipping orders from the last 24 hours, for operations to prioritize fulfillment.

### `process_tracking_statuses`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `order_number` (str), `kit_tracking_number` (str), `sample_tracking_number` (str), `mode` (str, default `"all"`), `from_csv` (bool, default False)
- **Enqueue pattern:** `.delay(...)` — from Berlin webhook handler
- **Retry config:** None
- **Business purpose:** Core Berlin fulfillment webhook handler. Links a test to an order, creates `ShippingStatus` records for kit and sample tracking numbers, handles duplicate detection (including bulk orders with shared tracking), and marks orders as fulfilled in Shopify.

### `send_order_to_berlin_for_fulfillment`
- **Decorator:** `@shared_task`
- **Arguments:** `shopify_payload` (dict), `is_order_cancellation` (bool), `order_id` (int)
- **Enqueue pattern:** `.delay(order.payload, is_order_cancellation, order.id)` — from order processing
- **Retry config:** None (raises on failure, logged to NewRelic)
- **Business purpose:** Sends a test kit order or cancellation to Berlin (fulfillment/lab partner) API. Updates `sent_to_berlin_at` on success. Logs to NewRelic and order monitoring.

### `retry_failed_berlin_order_fulfillments`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — every 6 hours
- **Retry config:** None
- **Business purpose:** Finds active and cancelled orders created after 2024-03-27 that were never sent to Berlin (no `sent_to_berlin_at`), and enqueues individual `send_order_to_berlin_for_fulfillment` tasks for each.

### `alert_if_no_orders_sent_to_berlin`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 10 AM, 4 PM, 10 PM
- **Retry config:** None
- **Business purpose:** Monitors fulfillment health. If no orders have been sent to Berlin in the past 6 hours, sends an admin alert email and raises an exception (which alerts in monitoring).

### `alert_if_no_orders_created`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 10 AM, 4 PM, 10 PM
- **Retry config:** None
- **Business purpose:** Monitors order intake health. If no new orders have been created in 6 hours, sends admin email warning to check Shopify.

---

## 12. `backend/transactional_email/tasks.py`

All tasks in this file are `@shared_task` with no retry configuration unless noted. They all send transactional emails via SendGrid templates.

### `send_test_activated_reminder`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 9 AM
- **Business purpose:** Reminds users who activated a test 4+ days ago but haven't progressed to "taken" status to send their sample.

### `send_tests_in_transit_through_usps_and_fedex_emails`
- **Arguments:** None
- **Enqueue pattern:** DISABLED in beat schedule (commented out)
- **Business purpose:** Notifies users when their sample is in transit to the lab.

### `send_tests_in_transit_hh_incomplete`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 11 AM and 5 PM
- **Business purpose:** Notifies users whose sample is in transit but health history form is incomplete.

### `send_tests_received_at_lab_hh_incomplete`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 11 AM and 5 PM
- **Business purpose:** Notifies users whose sample was received at the lab but health history is incomplete.

### `send_ldt_test_sample_received_email`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test.hash)` — from microgen lab status update
- **Business purpose:** Sends email to LDT test users confirming sample arrived at the lab. Different templates for standard vs comprehensive tests.

### `send_ldt_test_sample_sequencing_email`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test.hash)` — from microgen lab status update
- **Business purpose:** Notifies users that their LDT test sample is being sequenced. Also sends notification to lab updates email.

### `send_ldt_tests_results_almost_ready`
- **Arguments:** None
- **Enqueue pattern:** DISABLED in beat schedule
- **Business purpose:** Notifies users in sequencing status for 10+ days that results are almost ready.

### `send_pcr_test_results_ready`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)` — from microgen PCR processing
- **Business purpose:** Sends email to users when their PCR (preliminary) test results are ready.

### `send_expert_call_emails`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 8 AM
- **Business purpose:** Offers an expert coaching call to users 1+ day after their results are ready, excluding those who have active care consults.

### `send_view_unread_plan_emails`
- **Arguments:** None
- **Enqueue pattern:** DISABLED in beat schedule
- **Business purpose:** Nudges users who viewed their results 3 days ago but haven't yet viewed their care plan.

### `send_eligible_for_care_1_for_test`
- **Arguments:** `test_id` (int)
- **Enqueue pattern:** `.delay(test.id)` — from `send_results_ready_emails`
- **Business purpose:** First care eligibility email when test results are released and user is eligible for care.

### `send_eligible_for_a_la_care_not_treatment_program`
- **Arguments:** `test_id` (int)
- **Enqueue pattern:** `.delay(test.id)` — from `send_results_ready_emails`
- **Business purpose:** Care eligibility email for users eligible for a-la-carte care but not the bundled treatment program.

### `send_a_la_care_treatments_ready`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)`
- **Business purpose:** Notifies user when their individually selected treatments are ready.

### `send_eligible_for_care_2`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 9:45 AM
- **Business purpose:** Second care eligibility follow-up email sent 6 days after results for eligible LDT users not yet in care.

### `send_eligible_for_care_3`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 10:15 AM
- **Business purpose:** Third care eligibility follow-up email sent 12 days after results for eligible LDT users not yet in care.

### `send_consult_intake_abandonment_reminder`
- **Arguments:** None
- **Enqueue pattern:** DISABLED in beat schedule
- **Business purpose:** Reminds users 2-6 hours after care purchase if they haven't submitted their intake form.

### `send_consult_intake_abandonment_reminder_2`
- **Arguments:** None
- **Enqueue pattern:** DISABLED in beat schedule
- **Business purpose:** Second abandonment reminder 24-48 hours after care purchase.

### `send_sti_consult_intake_abandonment_reminder`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 10:30 AM, 4:30 PM, 10:30 PM
- **Business purpose:** Reminds STI consult users 24-36 hours after care purchase if intake is not submitted.

### `send_treatments_shipped`
- **Arguments:** `prescription_fill_id` (int)
- **Enqueue pattern:** `.delay(prescription_fill_id)` — from precision shipped webhook
- **Business purpose:** Notifies user that their prescription treatments have shipped, with tracking link.

### `send_treatments_delivered`
- **Arguments:** `prescription_fill_id` (int)
- **Enqueue pattern:** `.delay(prescription_fill_id)` — from precision delivered webhook
- **Business purpose:** Notifies user that their prescription treatments have been delivered. Uses different templates for refills vs initial fills, and for individual vs bundled treatments.

### `send_consult_intake_reviewed_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — from `submit_consult_intake_to_wheel`
- **Business purpose:** Notifies user that their consult intake has been received and is under clinical review.

### `send_treatment_plan_ready_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — from consult completion
- **Business purpose:** Notifies user that their treatment plan is ready to view.

### `send_lab_order_rejected_email`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue pattern:** `.delay(lab_order_uid)` — from lab order rejection
- **Business purpose:** Sends email when a lab order is rejected.

### `send_id_verification_failed_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — when ID verification fails
- **Business purpose:** Notifies user that their ID verification failed with a re-upload link.

### `send_care_referred_out_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult.uid)` — from `fetch_and_process_referred_consult_details`
- **Business purpose:** Notifies user that their consult was referred out (clinician couldn't treat).

### `send_new_consult_message_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — on new clinician message
- **Business purpose:** Notifies user of a new message from their clinician in the consult thread.

### `send_care_first_check_in_email`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — implied periodic; checks 4h after consult complete
- **Business purpose:** Sends a first care check-in email 4 hours after a v0 bundle consult is complete.

### `send_prescription_refills_available`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 7:15 AM
- **Business purpose:** Sends prescription refills available email to consults eligible for refill.

### `send_sample_taken_but_not_in_transit_reminder`
- **Arguments:** None
- **Enqueue pattern:** DISABLED in beat schedule
- **Business purpose:** Reminds users 5+ days after taking sample but not yet showing as in transit.

### `send_test_sample_at_lab_but_not_activated`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test.hash)` — from microgen status update when sample received but test not activated
- **Business purpose:** Reminds the purchaser to activate their test kit since the sample has already arrived at the lab.

### `send_test_sample_received_at_lab_but_not_activated`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 4 PM
- **Business purpose:** Batch version of the above for all tests received at lab in the last 7 days that haven't been activated.

### `send_sti_prescription_sent_to_pharmacy_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — when STI prescription is sent to local pharmacy
- **Business purpose:** Notifies user that their STI prescription has been sent to their selected local pharmacy with pharmacy contact info.

### `send_email_organon_prescriptions_ready`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — for Organon pharmacy consults
- **Business purpose:** Notifies user that their Organon prescriptions are ready for pickup at selected pharmacy.

### `send_account_transfer_verification_email`
- **Arguments:** `user_id` (int), `order_email` (str), `order_number` (str)
- **Enqueue pattern:** `.delay(user_id, order_email, order_number)` — when order transfer is needed
- **Business purpose:** Sends an email to the Evvy account email with a verification link to transfer an order from a different email address to the user's account.

---

## 13. `backend/consults/wheel/tasks.py`

### `submit_async_consult`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult.uid)` — from intake submission; `.delay(consult.uid)` — from retry tasks
- **Retry config:** None
- **Business purpose:** Entry point for submitting a consult to Wheel. Sets recommended prescriptions, checks if manual review is required. If not required, submits directly; if required, creates a `ConsultReview` record.

### `submit_consult_intake_to_wheel`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** Called directly (not `.delay()`) from `submit_async_consult`; `.delay(consult_uid)` from manual review completion
- **Retry config:** None (re-raises; logged to NewRelic)
- **Business purpose:** Submits the consult intake to Wheel's async consult API. On success, enqueues `send_consult_intake_submitted_event` and `send_consult_intake_reviewed_email`. Logs to order monitoring.

### `issue_lab_results_to_wheel_for_lab_test`
- **Decorator:** `@shared_task`
- **Arguments:** `lab_test_id` (str)
- **Enqueue pattern:** `.delay(lab_test_id)` — from lab results processing
- **Retry config:** None
- **Business purpose:** Issues lab results (NGS, PCR, or Urine PCR) to Wheel's follow-up consult API. Skips if results already sent.

### `resubmit_consult_photo_id_info_to_wheel`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — when user re-uploads ID after failed verification
- **Retry config:** None
- **Business purpose:** Amends patient photo ID info in Wheel after an ID verification failure and resets consult to `IN_PROGRESS`.

### `fetch_and_process_completed_consult_details`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult.uid)` — from `retry_consult_detail_processing` and Wheel webhook
- **Retry config:** None
- **Business purpose:** Fetches finalized consult details from Wheel (clinician, diagnosis, prescriptions, clinical notes), stores them, checks prescription match, and either completes consult or creates manual review.

### `fetch_and_process_completed_lab_order_details`
- **Decorator:** `@shared_task`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue pattern:** `.delay(lab_order.uid)` — from Wheel webhook
- **Retry config:** None
- **Business purpose:** Fetches approved lab order details from Wheel, stores clinician info, then routes to appropriate lab provider: urine tests → Junction, vaginal tests → Microgen.

### `retry_consult_detail_processing`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 6:15 AM
- **Retry config:** None
- **Business purpose:** Healing task. Finds consults in progress/submitted/error for more than 24 hours with a Wheel `provider_id`. Checks Wheel for each and enqueues `fetch_and_process_completed_consult_details` or `fetch_and_process_referred_consult_details` as appropriate.

### `retry_creating_async_consults`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 10 AM
- **Retry config:** None
- **Business purpose:** Finds consults in SUBMITTED status (no `submitted_at`, intake submitted 1-5 days ago) with no open tasks or reviews. Re-enqueues `submit_async_consult` for each.

### `retry_errored_consult_creation`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled via celery beat — daily at 10 AM
- **Retry config:** None
- **Business purpose:** Finds consults in ERROR status with no `submitted_at` and no open tasks or reviews. Re-enqueues `submit_async_consult`.

### `fetch_and_process_follow_up_consult_details`
- **Decorator:** `@shared_task`
- **Arguments:** `lab_order_uid` (str), `follow_up_external_id` (str)
- **Enqueue pattern:** `.delay(lab_order_uid, follow_up_external_id)` — from Wheel follow-up webhook
- **Retry config:** None
- **Business purpose:** Fetches follow-up consult details from Wheel. Handles diagnosis confirmation for VNGS and urine PCR results. Creates amendment `ConsultTask` on disagreement.

### `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult_uid)` — from `_post_prescription_fetch_and_process_consult_details`
- **Retry config:** None
- **Business purpose:** Verifies that the prescriptions written by the clinician match what Evvy recommended. If they match, marks consult complete, sends Braze `CONSULT_COMPLETED` event, and sends prescription to Precision.

### `check_recommended_prescriptions_against_prescribed`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str), `notify_admins` (bool, default False)
- **Enqueue pattern:** Called directly (not `.delay()`) from above task and from `send_missing_prescriptions_to_precision`
- **Retry config:** None
- **Business purpose:** Returns bool indicating whether recommended prescription slugs match actual prescribed slugs. Creates manual `ConsultReview` if mismatch and `notify_admins=True`.

### `fetch_and_process_referred_consult_details`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str)
- **Enqueue pattern:** `.delay(consult.uid)` — from `retry_consult_detail_processing` and Wheel webhook
- **Retry config:** None
- **Business purpose:** Handles consults that Wheel referred out (clinician couldn't treat). Stores referral info, creates a `TASK_TYPE_REFERRED_OUT` ConsultTask, sets consult status to REFERRED, sends `send_care_referred_out_email`.

### `submit_lab_order_to_wheel`
- **Decorator:** `@shared_task`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue pattern:** `.delay(lab_order.uid)` — from `resubmit_stuck_lab_orders_to_wheel`, `resubmit_errored_lab_orders_to_wheel`
- **Retry config:** None
- **Business purpose:** Submits an LDT lab order to Wheel's API. Skips if already approved or submitted.

### `resubmit_stuck_lab_orders_to_wheel`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 11:30 PM
- **Retry config:** None
- **Business purpose:** Finds lab orders stuck in CREATED/SUBMITTED status for 1+ hour with a provider_id set. Clears the provider_id and re-enqueues `submit_lab_order_to_wheel`. Skips Canadian orders.

### `resubmit_errored_lab_orders_to_wheel`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 11:15 PM
- **Retry config:** None
- **Business purpose:** Re-submits all lab orders in ERROR status. Skips Canadian orders and lab orders that already had results sent (to prevent status regression).

### `mark_wheel_consult_message_as_read`
- **Decorator:** `@shared_task`
- **Arguments:** `consult_uid` (str), `message_id` (str)
- **Enqueue pattern:** `.delay(consult_uid, message_id)` — when admin reads a message in the portal
- **Retry config:** None
- **Business purpose:** Marks a consult message as read in Wheel's messaging API.

### `send_notification_for_stuck_consults`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 10:00 AM
- **Retry config:** None
- **Business purpose:** Sends admin email summaries for: consults stuck in clinical review for 24+ hours (excluding UTI), stuck lab orders, and open manual reviews. Excludes UTI consults which have their own task.

### `send_notification_for_stuck_uti_consults`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 10:05 AM
- **Retry config:** None
- **Business purpose:** UTI-specific version of stuck consult notifications. Monitors UTI consults in review for 24+ hours and open UTI manual reviews.

---

## 14. `backend/test_results/tasks.py`

### `create_test_result_tagset`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** Called directly (not `.delay()`) from `post_process_test_results`
- **Retry config:** None
- **Business purpose:** Creates or updates the `TestResultTagSet` for a test result, computing pregnancy, menopause, symptoms, pathogen, and health context tags from health history.

### `post_process_test_results`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `release_results` (bool, default True)
- **Enqueue pattern:** `.delay(test_hash, release_results)` — from `process_microgen_test_results`
- **Retry config:** None
- **Business purpose:** Major post-processing pipeline after NGS results arrive. Updates Valencia type, creates test scores, fertility module, captures infection state, computes postmenopausal atrophy tag, creates tagset, auto-assigns plan profile, assigns suspected yeast flag, creates recommended treatment program, and auto-releases results if eligible.

### `assign_suspected_yeast_flag_to_test_result`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** Called directly (not `.delay()`) from `post_process_test_results`
- **Retry config:** None
- **Business purpose:** Sets `suspected_yeast=True` on a test result if yeast is present or user has reported yeast infection diagnosis in last year.

### `send_results_ready_emails`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)` — from `release_test_results()`
- **Retry config:** None (raises on email failure)
- **Business purpose:** Sends "Results Ready" email to the user. Also triggers care eligibility emails (email 1 for bundle care or a-la-carte care) via `.delay()`.

### `send_test_status_duration_alert`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 6:15 AM
- **Retry config:** None
- **Business purpose:** Monitors MDX tests stuck in RECEIVED (7+ days), SEQUENCING (7+ days), or PROCESSING (4+ days) status. Sends categorized admin alerts (delayed, waiting on lab order, errors).

### `send_lab_test_status_duration_alert`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 6:15 AM
- **Retry config:** None
- **Business purpose:** Monitors PCR `LabTest` records stuck in AT_LAB status for 3+ days. Sends admin alert email.

### `send_vip_test_status_update`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `previous_status` (str), `new_status` (str)
- **Enqueue pattern:** `.delay(test_hash, previous_status, new_status)` — from test status change signal/handler
- **Retry config:** None
- **Business purpose:** Sends VIP test status update notifications to `settings.VIP_TEST_EMAIL` when a provider-ordered VIP test changes status.

---

## 15. `backend/test_results/microgen/tasks.py`

### `submit_lab_order_approval_to_microgen`
- **Decorator:** `@shared_task`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue pattern:** `.delay(lab_order.uid)` — from Wheel approved webhook; directly called from `submit_missing_lab_order_approvals_to_microgen`
- **Retry config:** None (raises if not approved)
- **Business purpose:** Submits an approved lab order to Microgen's electronic lab order API. Skips if already submitted. Saves `electronic_order_submitted_at` timestamp.

### `submit_research_sample_lab_order_to_microgen`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)`
- **Retry config:** None
- **Business purpose:** Submits a research sample lab order to Microgen (different API path from clinical LDT orders).

### `submit_missing_lab_order_approvals_to_microgen`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 1:15 AM
- **Retry config:** None
- **Business purpose:** Healing task. Finds approved lab orders from the last 60 days that were never submitted to Microgen (no `electronic_order_submitted_at`). Enqueues `submit_lab_order_approval_to_microgen` for each.

### `process_test_results_stuck_in_sequencing_status`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** Scheduled — daily at 1:00 AM
- **Retry config:** None
- **Business purpose:** Finds tests stuck in SEQUENCING status for 7-60 days (no processing errors, not low-reads negative). Enqueues `process_microgen_test_results_if_exists_in_s3` to attempt results processing.

### `process_microgen_test_results`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str), `report_errors` (bool, default True), `read_from_staging` (bool), `release_results` (bool), `bypass_ready_check` (bool), `force_update_result_value` (bool)
- **Enqueue pattern:** `.delay(test_hash)` or `.apply_async(args=[test_hash], countdown=delay_seconds)` — from microgen status webhook; random delay for load balancing
- **Retry config:** Optional random delay via `RESULTS_PROCESSING_MAX_DELAY_MINUTES` setting (load balancing ADR-00015)
- **Business purpose:** Main test results processing task. Reads NGS results from S3 via `process_microgen_ngs_results_file_upload_from_s3()`, then enqueues `post_process_test_results`.

### `process_microgen_test_results_if_exists_in_s3`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test.hash)` — from `process_test_results_stuck_in_sequencing_status`
- **Retry config:** None (silently swallows S3 NoSuchKey; re-raises other ClientErrors)
- **Business purpose:** Safe wrapper around `process_microgen_test_results` that ignores S3 "file not found" errors, used for healing/retry scenarios.

### `process_microgen_vag_pcr_test_results`
- **Decorator:** `@shared_task`
- **Arguments:** `test_hash` (str)
- **Enqueue pattern:** `.delay(test_hash)` — from `process_lab_status_update` on "partial-results" with `vag-sti` panel
- **Retry config:** None
- **Business purpose:** Processes vaginal STI PCR results from S3. Re-scores the test if NGS results are already ready. Sends PCR results ready email, Braze event, and provider Klaviyo event.

### `send_summary_tests_entered_sequencing`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** `.apply_async(countdown=cache_timeout)` — batched via Redis cache lock from `_queue_summary_notification`
- **Retry config:** None
- **Business purpose:** Sends admin summary notification of how many tests entered sequencing in the last 2 hours (batched to avoid spam during high-volume processing).

### `send_summary_vpcr_results_processed`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** `.apply_async(countdown=cache_timeout)` — batched
- **Retry config:** None
- **Business purpose:** Sends admin summary notification of how many PCR results were processed in the last 2 hours.

### `send_summary_vngs_results_processed`
- **Decorator:** `@shared_task`
- **Arguments:** None
- **Enqueue pattern:** `.apply_async(countdown=cache_timeout)` — batched
- **Retry config:** None
- **Business purpose:** Sends admin summary notification of how many NGS results were processed in the last 2 hours.

### `process_lab_status_update_batch`
- **Decorator:** `@shared_task`
- **Arguments:** `payload` (dict with `status_updates` list)
- **Enqueue pattern:** Called from webhook handler
- **Retry config:** None
- **Business purpose:** Batch webhook handler for Microgen status updates. Iterates through each update and calls `process_lab_status_update()`.

---

## Summary Statistics

**Total task files:** 13 application task files (excluding venv packages)
**Total `@shared_task` tasks:** ~95 tasks across all modules

**Tasks with explicit retry logic:**
- `void_share_a_sale_transaction`: `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` via `retrying` library

**Tasks with time limits:**
- `retry_failed_shopify_orders`: `soft_time_limit=600, time_limit=900`

**Tasks with load-balancing delays:**
- `process_microgen_test_results`: `apply_async(countdown=random_delay)` controlled by `RESULTS_PROCESSING_MAX_DELAY_MINUTES` setting

**Scheduled (celery beat) tasks:** ~35 tasks scheduled via `CELERY_BEAT_SCHEDULE` in `backend/app/settings_celery.py`

**Primary enqueue patterns:**
- `.delay(args)` — most common, fire-and-forget
- `.apply_async(args=[], countdown=N)` — used for delayed execution (load balancing, batch summaries)
- Direct function call (synchronous) — used for sub-tasks within the same request that don't need separate worker context
