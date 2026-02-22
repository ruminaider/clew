# E2 Exploration Log

## Search 1: Celery task decorator (semantic search)
Searched for Celery task definitions broadly. Found:
- `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py` — contains the Beat schedule (all scheduled tasks)
- `/Users/albertgwo/Work/evvy/backend/app/celery.py` — app setup with `debug_task`
- `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py` — email tasks

The semantic search was low confidence (0.05) and returned mostly file-level summaries, not per-task detail. The Beat schedule file was the most valuable artifact from this search.

## Search 2: apply_async delay celery (semantic search)
Searched for Celery invocation patterns. Found confirmation of tasks in:
- `shipping/precision/tasks.py`: `retry_failed_prescription_fills`
- `consults/wheel/tasks.py`: `retry_creating_async_consults`
- `app/settings_celery.py` snippet showing the Beat schedule

Score was 0.88 on the settings file but only surface-level.

## Search 3: Glob for all tasks.py files
Used Glob to enumerate all `tasks.py` files in `backend/`. Found 14 application task files (excluding venv):
- `app/tasks.py`
- `accounts/tasks.py`
- `analytics/tasks.py`
- `care/tasks.py`
- `consults/wheel/tasks.py`
- `ecomm/tasks.py`
- `ecomm/shopify/tasks.py`
- `providers/tasks.py`
- `shipping/tasks.py`
- `shipping/precision/tasks.py`
- `subscriptions/tasks.py`
- `test_results/tasks.py`
- `test_results/microgen/tasks.py`
- `test_results/lab_services/providers/junction/tasks.py`

Also found `api/v1/views/tasks.py` (not a Celery task file — it's a DRF view).

## Search 4: Read settings_celery.py
Read the full Celery Beat schedule. This gave me all 30+ scheduled tasks with their crontab schedules.

## Search 5–14: Read each tasks.py file
Read all 14 task files in full. This gave me complete task signatures, business logic, and invocation patterns.

---

## Final Answer

### Overview

The Evvy backend uses Celery with Redis as the broker/result backend. Tasks use `@shared_task` (with one exception: `debug_task` uses `@celery_app.task(bind=True)` and `submit_lab_order_approval_to_junction` uses `bind=True, max_retries=3`). The primary invocation mechanism is `.delay()` throughout the codebase. `apply_async(countdown=...)` is used in a few places for delayed execution. `retry()` is used inside `submit_lab_order_approval_to_junction` and `fetch_and_process_junction_results` for explicit retry logic. `@retry` from the `retrying` library is used on `void_share_a_sale_transaction`.

The Beat schedule is defined in `/Users/albertgwo/Work/evvy/backend/app/settings_celery.py`.

---

### app/celery.py — Core Celery App

**File:** `/Users/albertgwo/Work/evvy/backend/app/celery.py`

#### 1. `debug_task`
- **Signature:** `debug_task(self)` — no arguments (bound task)
- **Decorator:** `@celery_app.task(bind=True)`
- **Enqueue:** Beat schedule every 15 minutes (`app.celery.debug_task`)
- **Retry:** None
- **Purpose:** Heartbeat task — prints the request object, used to verify workers are alive.

---

### app/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/app/tasks.py`

#### 2. `clean_log_entries`
- **Signature:** `clean_log_entries(delete_all=False)`
- **Decorator:** `@shared_task`
- **Enqueue:** Beat schedule daily at midnight (`app.tasks.clean_log_entries`)
- **Retry:** None
- **Purpose:** Deletes Django audit log (`LogEntry`) entries older than 30 days to manage database size.

---

### accounts/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/accounts/tasks.py`

#### 3. `send_intake_completed_notifications`
- **Signature:** `send_intake_completed_notifications(provider_email)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(provider_email)` — called when a provider completes registration intake
- **Retry:** None
- **Purpose:** Sends an admin notification email to B2B team when a provider registers and completes their intake form. Includes provider profile details (type, specialty, state, etc.).

---

### transactional_email/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`

All tasks use `@shared_task`. This file has many tasks — some are scheduled via Beat, others invoked directly via `.delay()`.

#### 4. `send_test_activated_reminder`
- **Signature:** `send_test_activated_reminder()` — no args
- **Enqueue:** Beat schedule daily at 9AM
- **Retry:** None
- **Purpose:** Sends reminder emails to users who activated their test but haven't progressed to "taken" status in 4+ days.

#### 5. `send_tests_in_transit_through_usps_and_fedex_emails`
- **Signature:** No args
- **Enqueue:** Beat schedule (currently DISABLED in settings)
- **Retry:** None
- **Purpose:** Sends in-transit notification emails for tests that moved to in-transit status in the last 3 days.

#### 6. `send_tests_in_transit_hh_incomplete`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 11AM and 5PM
- **Retry:** None
- **Purpose:** Sends email to users whose test is in transit but they haven't completed their health history.

#### 7. `send_tests_received_at_lab_hh_incomplete`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 11AM and 5PM
- **Retry:** None
- **Purpose:** Sends email to users whose test was received at the lab but health history is still incomplete.

#### 8. `send_ldt_test_sample_received_email`
- **Signature:** `send_ldt_test_sample_received_email(test_hash)`
- **Enqueue:** `.delay(test.hash)` — triggered from `test_results/microgen/tasks.py` on "received" status webhook
- **Retry:** None
- **Purpose:** Sends a "sample arrived at lab" email to users. Uses different templates for standard vs comprehensive (vPCR) LDT tests.

#### 9. `send_ldt_test_sample_sequencing_email`
- **Signature:** `send_ldt_test_sample_sequencing_email(test_hash)`
- **Enqueue:** `.delay(test.hash)` — triggered from `test_results/microgen/tasks.py` on "sequencing" status
- **Retry:** None
- **Purpose:** Notifies user that their sample is being sequenced. Also sends notification to lab updates email.

#### 10. `send_ldt_tests_results_almost_ready`
- **Signature:** No args
- **Enqueue:** Beat schedule (currently DISABLED)
- **Retry:** None
- **Purpose:** Sends "almost ready" email to users whose LDT tests have been in sequencing for 10+ days (7 business days).

#### 11. `send_pcr_test_results_ready`
- **Signature:** `send_pcr_test_results_ready(test_hash)`
- **Enqueue:** `.delay(test_hash)` — triggered from `test_results/microgen/tasks.py` after PCR processing
- **Retry:** None
- **Purpose:** Sends email notification that PCR test results are ready.

#### 12. `send_expert_call_emails`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 8AM
- **Retry:** None
- **Purpose:** Sends coaching call offer email to users whose results were ready 1-6 days ago who don't have active consults.

#### 13. `send_view_unread_plan_emails`
- **Signature:** No args
- **Enqueue:** Beat schedule (DISABLED)
- **Retry:** None
- **Purpose:** Sends email to users who viewed results 3-6 days ago but haven't viewed their plan yet.

#### 14. `send_eligible_for_care_1_for_test`
- **Signature:** `send_eligible_for_care_1_for_test(test_id)`
- **Enqueue:** `.delay(test.id)` — from `test_results/tasks.py` after results release
- **Retry:** None
- **Purpose:** Sends the first "eligible for care" marketing email to users with LDT results.

#### 15. `send_eligible_for_a_la_care_not_treatment_program`
- **Signature:** `send_eligible_for_a_la_care_not_treatment_program(test_id)`
- **Enqueue:** `.delay(test.id)` — from `test_results/tasks.py`
- **Retry:** None
- **Purpose:** Sends a la carte care eligibility email to users who are eligible for individual treatments but not the full program.

#### 16. `send_a_la_care_treatments_ready`
- **Signature:** `send_a_la_care_treatments_ready(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven from care flow
- **Retry:** None
- **Purpose:** Notifies user that their a la carte individual treatment plan is ready.

#### 17. `send_eligible_for_care_2`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 9:45AM
- **Retry:** None
- **Purpose:** Sends follow-up care eligibility email 6-8 days after results ready, for users who haven't purchased care yet.

#### 18. `send_eligible_for_care_3`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10:15AM
- **Retry:** None
- **Purpose:** Sends third care eligibility email 12-14 days after results ready.

#### 19. `send_treatments_shipped`
- **Signature:** `send_treatments_shipped(prescription_fill_id)`
- **Enqueue:** `.delay(fill.id)` — triggered by Precision pharmacy webhook
- **Retry:** None
- **Purpose:** Sends shipping notification email to user when prescription treatments have been shipped.

#### 20. `send_treatments_delivered`
- **Signature:** `send_treatments_delivered(prescription_fill_id)`
- **Enqueue:** `.delay(fill.id)` — triggered by Precision pharmacy webhook
- **Retry:** None
- **Purpose:** Sends delivery confirmation email for prescription treatments. Selects different templates based on whether it's a refill vs initial consult vs a la carte.

#### 21. `send_consult_intake_abandonment_reminder`
- **Signature:** No args
- **Enqueue:** Beat schedule (DISABLED)
- **Retry:** None
- **Purpose:** Reminds users who started but didn't complete consult intake 2-6 hours after care was paid.

#### 22. `send_consult_intake_abandonment_reminder_2`
- **Signature:** No args
- **Enqueue:** Beat schedule (DISABLED)
- **Retry:** None
- **Purpose:** Second abandonment reminder 24-48 hours after consult ordered.

#### 23. `send_sti_consult_intake_abandonment_reminder`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10:30AM, 4:30PM, 10:30PM
- **Retry:** None
- **Purpose:** Sends abandonment reminder specifically for STI consult intake (24-36 hours window).

#### 24. `send_sti_prescription_sent_to_pharmacy_email`
- **Signature:** `send_sti_prescription_sent_to_pharmacy_email(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven
- **Retry:** None
- **Purpose:** Notifies STI patients that their prescription has been sent to their selected pharmacy with pickup details.

#### 25. `send_email_organon_prescriptions_ready`
- **Signature:** `send_email_organon_prescriptions_ready(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven
- **Retry:** None
- **Purpose:** Sends notification that Organon prescription is ready for pharmacy pickup.

#### 26. `send_consult_intake_reviewed_email`
- **Signature:** `send_consult_intake_reviewed_email(consult_uid)`
- **Enqueue:** `.delay(consult_uid)` — from `consults/wheel/tasks.py` after Wheel consult submission
- **Retry:** None
- **Purpose:** Sends email to patient confirming their consult intake has been reviewed.

#### 27. `send_treatment_plan_ready_email`
- **Signature:** `send_treatment_plan_ready_email(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven
- **Retry:** None
- **Purpose:** Notifies user that their treatment plan is ready to view.

#### 28. `send_lab_order_rejected_email`
- **Signature:** `send_lab_order_rejected_email(lab_order_uid)`
- **Enqueue:** `.delay(lab_order_uid)` — event-driven
- **Retry:** None
- **Purpose:** Notifies user when their lab order was rejected.

#### 29. `send_id_verification_failed_email`
- **Signature:** `send_id_verification_failed_email(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven after Wheel ID verification failure
- **Retry:** None
- **Purpose:** Sends email explaining ID verification failure and instructions to re-upload.

#### 30. `send_care_referred_out_email`
- **Signature:** `send_care_referred_out_email(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — from `consults/wheel/tasks.py`
- **Retry:** None
- **Purpose:** Notifies user that their consult was referred out (ineligible for Evvy care).

#### 31. `send_new_consult_message_email`
- **Signature:** `send_new_consult_message_email(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven when clinician sends a message
- **Retry:** None
- **Purpose:** Notifies patient of a new message in their consult thread.

#### 32. `send_care_first_check_in_email`
- **Signature:** No args
- **Enqueue:** Beat schedule (not visible in current settings — appears commented out or removed from schedule at the time of reading)
- **Retry:** None
- **Purpose:** Sends care check-in email 4-24 hours after treatment plan is complete (v0 bundle only).

#### 33. `send_prescription_refills_available`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 7:15AM
- **Retry:** None
- **Purpose:** Sends email to consults that are eligible for prescription refills.

#### 34. `send_sample_taken_but_not_in_transit_reminder`
- **Signature:** No args
- **Enqueue:** Beat schedule (DISABLED)
- **Retry:** None
- **Purpose:** Reminds users who took their sample 5-10 days ago but haven't shipped it back yet.

#### 35. `send_test_sample_at_lab_but_not_activated`
- **Signature:** `send_test_sample_at_lab_but_not_activated(test_hash)`
- **Enqueue:** `.delay(test.hash)` — from microgen tasks on "received" status for unactivated tests
- **Retry:** None
- **Purpose:** Reminds customers that their sample arrived at the lab but they haven't activated their test yet.

#### 36. `send_test_sample_received_at_lab_but_not_activated`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 4PM (`sample-at-lab-not-activated`)
- **Retry:** None
- **Purpose:** Batch version of above — finds all unactivated tests received at lab in the last 7 days.

#### 37. `send_account_transfer_verification_email`
- **Signature:** `send_account_transfer_verification_email(user_id: int, order_email: str, order_number: str)`
- **Enqueue:** `.delay(user_id, order_email, order_number)` — event-driven when order email doesn't match account email
- **Retry:** None
- **Purpose:** Sends a verification email to allow users to transfer an order from a different email address to their account.

---

### care/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/care/tasks.py`

#### 38. `update_treatment_end_date`
- **Signature:** `update_treatment_end_date(treatment_plan_id: int)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(treatment_plan.id)` — event-driven when treatment plan is updated
- **Retry:** None
- **Purpose:** Computes and saves the treatment end date based on the treatment plan's calendar products.

#### 39. `create_or_reset_calendar_treatments`
- **Signature:** `create_or_reset_calendar_treatments(treatment_plan_id: int)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(treatment_plan.id)` — event-driven
- **Retry:** None
- **Purpose:** Rebuilds the treatment calendar for a treatment plan — deletes existing calendar treatments and recreates them from prescriptions.

#### 40. `heal_prescription_fill_orders`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 2AM, 10AM, 6PM
- **Retry:** None
- **Purpose:** Backfill task — finds PrescriptionFills modified in the last 24 hours that have an order set but no `PrescriptionFillOrder` relationship, and creates the missing link.

#### 41. `heal_otc_treatment_only_orders`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 2:15AM, 10:15AM, 6:15PM
- **Retry:** None
- **Purpose:** Heals OTC-only orders (orders with only over-the-counter treatments, no prescriptions) that were created in the last day but never sent to Precision pharmacy. Creates PrescriptionFill and sends the fill request.

---

### shipping/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`

#### 42. `update_individual_shipping_status`
- **Signature:** `update_individual_shipping_status(status_id)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(status.id)` — called in a loop from `update_eligible_shipping_statuses_async`
- **Retry:** None
- **Purpose:** Updates the shipping status for a single test kit or sample by polling the shipping carrier API.

#### 43. `update_eligible_shipping_statuses_async`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 8:30AM, 4:30PM, 1:30AM
- **Retry:** None
- **Purpose:** Finds all open shipping statuses (kits and samples) eligible for update and enqueues individual `update_individual_shipping_status` tasks for each. Has different update frequencies: daily for recent tests, every 3 days for old tests, weekly for unactivated tests.

#### 44. `send_daily_express_orders_email`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 9:30AM
- **Retry:** None
- **Purpose:** Sends a daily email to Berlin (fulfillment center) listing all express shipping orders from the last 24 hours. Also adds them to a shared Google Sheet.

#### 45. `process_tracking_statuses`
- **Signature:** `process_tracking_statuses(test_hash: str, order_number: str, kit_tracking_number: str, sample_tracking_number: str, mode=MODE_ALL, from_csv=False)`
- **Enqueue:** `.delay(...)` or `.apply_async(...)` — called from Berlin webhook handler and CSV processing
- **Retry:** None
- **Purpose:** Core fulfillment task. When Berlin ships a test kit, this task: (1) links the test to the ecomm order, (2) creates shipping status records for kit and sample tracking numbers, (3) marks the Shopify order as fulfilled with tracking info. Supports multiple modes: `all`, `all_no_confirmation`, `fulfill_only`, `fulfill_no_confirmation`.

#### 46. `send_order_to_berlin_for_fulfillment`
- **Signature:** `send_order_to_berlin_for_fulfillment(shopify_payload: Dict[str, Any], is_order_cancellation: bool, order_id: int) -> bool`
- **Enqueue:** `.delay(order.payload, is_order_cancellation, order.id)` — from Shopify webhook handler and `retry_failed_berlin_order_fulfillments`
- **Retry:** None (the caller `retry_failed_berlin_order_fulfillments` re-enqueues on failure)
- **Purpose:** Sends an order to Berlin (kit fulfillment center) via API. Handles both new orders and cancellations. Tracks `sent_to_berlin_at` timestamp for monitoring.

#### 47. `retry_failed_berlin_order_fulfillments`
- **Signature:** No args
- **Enqueue:** Beat schedule every 6 hours
- **Retry:** None
- **Purpose:** Finds active or cancelled orders created after 3/27/2024 that were never sent to Berlin (`sent_to_berlin_at` is null) and re-enqueues them for fulfillment.

#### 48. `alert_if_no_orders_sent_to_berlin`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10AM, 4PM, 10PM
- **Retry:** None
- **Purpose:** Monitoring alert — raises an exception and sends an admin email if no orders have been sent to Berlin in the last 6 hours.

#### 49. `alert_if_no_orders_created`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10AM, 4PM, 10PM
- **Retry:** None
- **Purpose:** Monitoring alert — sends admin email if no new orders have been created in the last 6 hours (checks Shopify order pipeline health).

---

### shipping/precision/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`

#### 50. `process_precision_pharmacy_webhook`
- **Signature:** `process_precision_pharmacy_webhook(payload)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(payload)` — from webhook endpoint handling Precision pharmacy callbacks
- **Retry:** None
- **Purpose:** Processes incoming webhooks from Precision pharmacy. Routes by webhook type: "received" (no action), "shipped" (processes shipping), "delivered" (marks delivered), "warning" (no action).

#### 51. `send_prescription_to_precision`
- **Signature:** `send_prescription_to_precision(consult_uid, skip_set_sent_to_pharmacy=False)`
- **Enqueue:** `.delay(consult.uid)` — from `check_recommended_prescriptions_against_prescribed_and_send_prescriptions` and `send_missing_prescriptions_to_precision`
- **Retry:** None
- **Purpose:** End-to-end prescription submission: creates patient in Precision pharmacy, then creates and fills the prescription from the consult data. Tracks `sent_to_pharmacy_at` timestamp.

#### 52. `send_create_patient_request_to_precision`
- **Signature:** `send_create_patient_request_to_precision(prescription_fill_id: int, consult_uid: str = None, user_id: int = None, order_id: int = None)`
- **Enqueue:** Called directly (not via `.delay()`) inside `send_prescription_refill_request` and `send_otc_treatment_fill_request`
- **Retry:** None
- **Purpose:** Creates a patient record in Precision pharmacy. Accepts three different identifier contexts (consult, user, or order). Saves the `pharmacy_patient_id` to the prescription fill.

#### 53. `send_create_prescription_request_to_precision`
- **Signature:** `send_create_prescription_request_to_precision(prescription_uid, fill_quantity=None, prescription_fill_prescription=None)`
- **Enqueue:** Called directly inside `send_prescription_refill_request`
- **Retry:** None (raises exception on failure, which sets fill to WARNING status)
- **Purpose:** Creates a prescription record in Precision pharmacy for a specific prescription. On failure, marks the fill as WARNING status.

#### 54. `send_create_otc_treatment_request_to_precision`
- **Signature:** `send_create_otc_treatment_request_to_precision(otc_treatment_uid: str, prescription_fill_otc_treatment_id: int)`
- **Enqueue:** Called directly inside `send_prescription_refill_request` and `send_otc_treatment_fill_request`
- **Retry:** None (raises on failure, sets fill to WARNING)
- **Purpose:** Creates an OTC (over-the-counter) treatment record in Precision pharmacy.

#### 55. `send_fill_request_to_precision`
- **Signature:** `send_fill_request_to_precision(fill_uid, order_shipping_address=None)`
- **Enqueue:** Called directly inside `send_prescription_refill_request` and `send_otc_treatment_fill_request`
- **Retry:** None (raises on failure, sets fill to WARNING)
- **Purpose:** Sends the final fill request to Precision pharmacy to actually dispense the medication. Tracks fulfillment with NewRelic and order logger.

#### 56. `send_cancel_fill_request_to_precision`
- **Signature:** `send_cancel_fill_request_to_precision(fill_uid)`
- **Enqueue:** Called directly in `send_prescription_refill_request` on cancellation path
- **Retry:** None
- **Purpose:** Cancels an existing fill request at Precision pharmacy. Guards against cancelling already-shipped or delivered fills.

#### 57. `send_missing_prescriptions_to_precision`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 1:15AM and 7:15PM
- **Retry:** None
- **Purpose:** Healing task — finds consults completed in the last 2 days that use Precision pharmacy but were never sent. Checks prescriptions match before submitting.

#### 58. `retry_failed_prescription_fills`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 2:30AM, 10:30AM, 6:30PM
- **Retry:** None (task has no Celery retry, but includes logic to re-attempt WARNING fills)
- **Purpose:** Retries prescription fills in WARNING status (failed to reach Precision). Has safeguards: only retries fills older than 1 hour, less than 7 days old, limits to 10 per run. Fills failing for >3 days are marked FAILED and a ConsultTask is created.

#### 59. `send_notification_for_stuck_prescriptions`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10AM
- **Retry:** None
- **Purpose:** Monitoring alert — finds refill prescription fills that have been in CREATED status for more than 3 business days and sends an admin email.

---

### consults/wheel/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`

#### 60. `submit_async_consult`
- **Signature:** `submit_async_consult(consult_uid)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(consult.uid)` — from consult intake submission flow; also from `retry_creating_async_consults` and `retry_errored_consult_creation`
- **Retry:** None
- **Purpose:** Prepares and routes a consult to Wheel. First sets recommended prescriptions, then checks if manual review is required. If yes, creates a `ConsultReview`. If no, calls `submit_consult_intake_to_wheel` directly.

#### 61. `submit_consult_intake_to_wheel`
- **Signature:** `submit_consult_intake_to_wheel(consult_uid)`
- **Enqueue:** Called directly from `submit_async_consult`, also `.delay(consult.uid)` — event-driven
- **Retry:** None (raises on failure)
- **Purpose:** Submits the completed consult intake to the Wheel telehealth API. On success triggers `send_consult_intake_submitted_event` and `send_consult_intake_reviewed_email`.

#### 62. `issue_lab_results_to_wheel_for_lab_test`
- **Signature:** `issue_lab_results_to_wheel_for_lab_test(lab_test_id: str)`
- **Enqueue:** `.delay(lab_test.id)` — event-driven after lab results are received
- **Retry:** None
- **Purpose:** Sends lab results back to Wheel so the clinician can review them. Supports VNGS, VPCR, and urine PCR result types.

#### 63. `resubmit_consult_photo_id_info_to_wheel`
- **Signature:** `resubmit_consult_photo_id_info_to_wheel(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — triggered by ops when user re-uploads ID after verification failure
- **Retry:** None
- **Purpose:** Re-submits updated photo ID to Wheel after previous verification failure. Resets consult status to IN_PROGRESS.

#### 64. `fetch_and_process_completed_consult_details`
- **Signature:** `fetch_and_process_completed_consult_details(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — from Wheel webhook and `retry_consult_detail_processing`
- **Retry:** None
- **Purpose:** Fetches finalized consult details from Wheel (clinician info, diagnosis, prescriptions, clinical notes), stores them, and triggers prescription sending to Precision.

#### 65. `fetch_and_process_completed_lab_order_details`
- **Signature:** `fetch_and_process_completed_lab_order_details(lab_order_uid)`
- **Enqueue:** `.delay(lab_order.uid)` — from Wheel webhook for approved lab orders
- **Retry:** None
- **Purpose:** Fetches approved lab order details from Wheel and routes to the appropriate lab provider: urine tests go to Junction, vaginal tests go to Microgen.

#### 66. `retry_consult_detail_processing`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 6:15AM
- **Retry:** None
- **Purpose:** Healing task — finds consults that have been in review for more than 24 hours, checks their status on Wheel side, and re-triggers processing for completed ones.

#### 67. `retry_creating_async_consults`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10AM
- **Retry:** None
- **Purpose:** Finds consults in SUBMITTED status with no `submitted_at` timestamp (i.e., creation failed) from the last 1-5 days and re-enqueues `submit_async_consult`.

#### 68. `retry_errored_consult_creation`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10AM
- **Retry:** None
- **Purpose:** Finds consults in ERROR status with no `submitted_at` timestamp and re-enqueues `submit_async_consult` for each.

#### 69. `fetch_and_process_follow_up_consult_details`
- **Signature:** `fetch_and_process_follow_up_consult_details(lab_order_uid: str, follow_up_external_id: str)`
- **Enqueue:** `.delay(lab_order.uid, follow_up.external_id)` — from Wheel follow-up webhook and `send_notification_for_diagnosis_pending_consults`
- **Retry:** None
- **Purpose:** Fetches diagnosis interpretation from Wheel follow-up consult and processes it. Confirms diagnosis if interpretability is ALL or SOME. Creates ConsultTask for manual review if NONE (disagreement).

#### 70. `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **Signature:** `check_recommended_prescriptions_against_prescribed_and_send_prescriptions(consult_uid)`
- **Enqueue:** `.delay(consult_uid)` — from `fetch_and_process_completed_consult_details`
- **Retry:** None
- **Purpose:** Verifies that Wheel prescribed exactly the recommended medications. If they match, marks consult COMPLETE and sends to Precision pharmacy. If not, creates a ConsultReview for manual review.

#### 71. `check_recommended_prescriptions_against_prescribed`
- **Signature:** `check_recommended_prescriptions_against_prescribed(consult_uid, notify_admins=False)`
- **Enqueue:** Called directly (non-async) from `send_missing_prescriptions_to_precision`
- **Retry:** None
- **Purpose:** Compares recommended prescription slugs against actual prescribed slugs from Wheel. Returns boolean indicating match.

#### 72. `fetch_and_process_referred_consult_details`
- **Signature:** `fetch_and_process_referred_consult_details(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — from Wheel webhook and `retry_consult_detail_processing`
- **Retry:** None
- **Purpose:** Handles auto-referred-out consults (where Wheel's clinician determines the patient is ineligible). Stores referral info, creates ConsultTask, marks consult as REFERRED, and sends referred-out email.

#### 73. `submit_lab_order_to_wheel`
- **Signature:** `submit_lab_order_to_wheel(lab_order_uid)`
- **Enqueue:** `.delay(lab_order.uid)` — from lab order submission flow and healing tasks
- **Retry:** None
- **Purpose:** Submits a lab order to Wheel for clinician approval. Guards against re-submission if already approved or submitted.

#### 74. `resubmit_stuck_lab_orders_to_wheel`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 11:30PM
- **Retry:** None
- **Purpose:** Healing task — finds lab orders stuck in CREATED or SUBMITTED status for more than 1 hour and re-submits them to Wheel. Skips Canadian lab orders (Wheel doesn't support Canada).

#### 75. `resubmit_errored_lab_orders_to_wheel`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 11:15PM
- **Retry:** None
- **Purpose:** Re-submits all ERROR status lab orders to Wheel. Skips Canadian orders and orders where results have already been sent (to prevent status regression).

#### 76. `mark_wheel_consult_message_as_read`
- **Signature:** `mark_wheel_consult_message_as_read(consult_uid, message_id)`
- **Enqueue:** `.delay(consult.uid, message_id)` — event-driven when user reads a message
- **Retry:** None
- **Purpose:** Marks a consult message as read in the Wheel system.

#### 77. `send_notification_for_stuck_consults`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10AM
- **Retry:** None
- **Purpose:** Monitoring alert — sends admin emails for: (1) non-UTI consults in review for 24+ hours, (2) lab orders stuck in processing for 24+ hours, (3) open consult manual reviews.

#### 78. `send_notification_for_stuck_uti_consults`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10:05AM
- **Retry:** None
- **Purpose:** UTI-specific monitoring — alerts for UTI consults stuck in review 24+ hours and open UTI manual reviews.

#### 79. `send_notification_for_diagnosis_pending_consults`
- **Signature:** `send_notification_for_diagnosis_pending_consults(hours_threshold=24)`
- **Enqueue:** Beat schedule daily at 10:10AM
- **Retry:** None
- **Purpose:** Monitoring alert — finds tests where lab results were sent to Wheel but diagnosis hasn't been confirmed after `hours_threshold` hours. Sends separate alerts for vaginitis and UTI tests. Also re-triggers `fetch_and_process_follow_up_consult_details` for pending tests.

#### 80. `send_notification_for_care_orders_in_bad_states`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 10:15AM
- **Retry:** None
- **Purpose:** Comprehensive data integrity monitoring — alerts for: (1) care orders without attached consult, (2) completed consults without prescription fill, (3) ungated RX orders without consult.

#### 81. `attach_latest_otc_treatment_to_consult`
- **Signature:** `attach_latest_otc_treatment_to_consult(consult: Consult) -> None`
- **Enqueue:** Called directly (non-async) from `_post_prescription_fetch_and_process_consult_details`
- **Retry:** None
- **Purpose:** Checks if the user has an active probiotic subscription and attaches the latest OTC treatment to the consult if not already attached.

---

### test_results/microgen/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`

#### 82. `submit_lab_order_approval_to_microgen`
- **Signature:** `submit_lab_order_approval_to_microgen(lab_order_uid)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(lab_order.uid)` — from `fetch_and_process_completed_lab_order_details` and `submit_missing_lab_order_approvals_to_microgen`
- **Retry:** None
- **Purpose:** Sends approved lab order data to Microgen (the sequencing lab). Guards against duplicate submission by checking `electronic_order_submitted_at`.

#### 83. `submit_research_sample_lab_order_to_microgen`
- **Signature:** `submit_research_sample_lab_order_to_microgen(test_hash)`
- **Enqueue:** `.delay(test_hash)` — event-driven for research samples
- **Retry:** None
- **Purpose:** Submits electronic lab order for research samples to Microgen.

#### 84. `submit_missing_lab_order_approvals_to_microgen`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 1:15AM
- **Retry:** None
- **Purpose:** Healing task — finds approved lab orders from the last 60 days that were never submitted to Microgen and re-submits them.

#### 85. `process_test_results_stuck_in_sequencing_status`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 1AM
- **Retry:** None
- **Purpose:** Healing task — finds tests stuck in sequencing status for more than 7 days (but less than 60) and tries to process their results from S3.

#### 86. `process_microgen_test_results`
- **Signature:** `process_microgen_test_results(test_hash, report_errors=True, read_from_staging=False, release_results=True, bypass_ready_check=False, force_update_result_value=False)`
- **Enqueue:** `.delay(test_hash)` or `.apply_async(args=[test_hash], countdown=delay_seconds)` — from Microgen "ready" status webhook, with optional random delay for load balancing
- **Retry:** None
- **Purpose:** Processes NGS results file from S3 for a test, then triggers `post_process_test_results`. The `countdown` parameter enables load-balancing by spreading result processing over `RESULTS_PROCESSING_MAX_DELAY_MINUTES`.

#### 87. `process_microgen_test_results_if_exists_in_s3`
- **Signature:** `process_microgen_test_results_if_exists_in_s3(test_hash)`
- **Enqueue:** `.delay(test.hash)` — from `process_test_results_stuck_in_sequencing_status`
- **Retry:** None
- **Purpose:** Wrapper that silently ignores `NoSuchKey` errors (results not yet in S3).

#### 88. `process_microgen_vag_pcr_test_results`
- **Signature:** `process_microgen_vag_pcr_test_results(test_hash)`
- **Enqueue:** `.delay(test_hash)` — from `process_lab_status_update` on "partial-results" webhook
- **Retry:** None
- **Purpose:** Processes vaginitis PCR panel results from S3. After processing, re-computes test scores and sends the PCR results ready email and analytics events.

#### 89. `send_summary_tests_entered_sequencing`
- **Signature:** No args
- **Enqueue:** `.apply_async(countdown=cache_timeout)` — delayed 60 minutes via Redis cache lock inside `_queue_summary_notification`
- **Retry:** None
- **Purpose:** Sends a summary notification of how many tests entered sequencing in the last 2 hours to the lab team.

#### 90. `send_summary_vpcr_results_processed`
- **Signature:** No args
- **Enqueue:** `.apply_async(countdown=cache_timeout)` — delayed 20 minutes via Redis cache lock
- **Retry:** None
- **Purpose:** Sends a summary of PCR results processed in the last 2 hours to the lab team.

#### 91. `send_summary_vngs_results_processed`
- **Signature:** No args
- **Enqueue:** `.apply_async(countdown=cache_timeout)` — delayed 20 minutes via Redis cache lock
- **Retry:** None
- **Purpose:** Sends a summary of NGS results processed in the last 2 hours to the lab team.

#### 92. `process_lab_status_update_batch`
- **Signature:** `process_lab_status_update_batch(payload)`
- **Enqueue:** `.delay(payload)` or `.apply_async(...)` — from Microgen batch webhook endpoint
- **Retry:** None
- **Purpose:** Wrapper that iterates over a batch of lab status updates and processes each one via the `process_lab_status_update` helper.

---

### test_results/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`

#### 93. `create_test_result_tagset`
- **Signature:** `create_test_result_tagset(test_hash: str)`
- **Decorator:** `@shared_task`
- **Enqueue:** Called directly (non-async) from `post_process_test_results`; also `.delay()` — event-driven
- **Retry:** None
- **Purpose:** Creates or updates the test result tag set (pregnancy, menopause, symptoms, pathogen tags) based on health history and test results. Used for personalized plan generation.

#### 94. `post_process_test_results`
- **Signature:** `post_process_test_results(test_hash, release_results=True)`
- **Enqueue:** `.delay(test_hash, release_results)` — from `process_microgen_test_results` after NGS processing
- **Retry:** None
- **Purpose:** Core post-processing pipeline after results come in: updates Valencia type, computes test scores, creates fertility module, captures infection state, creates tag set, assigns plan profile, assigns suspected yeast flag, creates recommended treatment program. Releases results automatically if eligible.

#### 95. `assign_suspected_yeast_flag_to_test_result`
- **Signature:** `assign_suspected_yeast_flag_to_test_result(test_hash: str)`
- **Enqueue:** Called directly from `post_process_test_results`
- **Retry:** None
- **Purpose:** Checks if yeast is present in results or if the user has been diagnosed with yeast infection in the past year, and flags the test result accordingly.

#### 96. `send_results_ready_emails`
- **Signature:** `send_results_ready_emails(test_hash: str)`
- **Enqueue:** `.delay(test_hash)` — event-driven after results are released to user
- **Retry:** None
- **Purpose:** Sends the "results ready" email to the user. Also triggers care eligibility email 1 if the test is eligible for care.

#### 97. `send_test_status_duration_alert`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 6:15AM
- **Retry:** None
- **Purpose:** Monitoring alert — checks tests stuck in RECEIVED, SEQUENCING, or PROCESSING status beyond their alert duration thresholds (7 days for received/sequencing, 4 days for processing). Sends summary email to lab delay email address.

#### 98. `send_lab_test_status_duration_alert`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 6:15AM
- **Retry:** None
- **Purpose:** Monitoring alert — checks PCR lab tests stuck in AT_LAB status for more than 3 days and sends alert email.

#### 99. `send_vip_test_status_update`
- **Signature:** `send_vip_test_status_update(test_hash, previous_status, new_status)`
- **Enqueue:** `.delay(test_hash, previous_status, new_status)` — from test status change signal
- **Retry:** None
- **Purpose:** Sends a VIP notification email when a provider-ordered test changes status, including provider details and order information.

---

### analytics/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`

#### 100. `send_custom_analytics_event_to_fullstory_async`
- **Signature:** `send_custom_analytics_event_to_fullstory_async(user_id, event_name, event_properties, use_recent_session)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(user.id, event_name, event_properties, use_recent_session_fullstory)` — from `send_custom_analytics_event_to_destinations`
- **Retry:** None
- **Purpose:** Generic async wrapper for sending events to FullStory analytics.

#### 101. `send_custom_analytics_event_to_klaviyo_async`
- **Signature:** `send_custom_analytics_event_to_klaviyo_async(payload)`
- **Enqueue:** `.delay(payload)` — from `send_custom_analytics_event_to_destinations`
- **Retry:** None
- **Purpose:** Generic async wrapper for sending events to Klaviyo (email marketing platform).

#### 102. `send_sample_sequencing_provider_klaviyo_event`
- **Signature:** `send_sample_sequencing_provider_klaviyo_event(test_hash: str, provider_test_order_id: int)`
- **Enqueue:** `.delay(test_hash, provider_test_order.id)` — from microgen tasks on sequencing status
- **Retry:** None
- **Purpose:** Sends "[Provider] Sample Sequencing" Klaviyo event to the provider when their patient's test enters sequencing.

#### 103. `send_pcr_test_results_ready_provider_klaviyo_event`
- **Signature:** `send_pcr_test_results_ready_provider_klaviyo_event(test_hash: str, provider_test_order_id: int)`
- **Enqueue:** `.delay(test_hash, provider_test_order.id)` — from microgen tasks after PCR results
- **Retry:** None
- **Purpose:** Sends "[Provider] Preliminary Results Ready" Klaviyo event to notify the provider that PCR results are ready for their patient.

#### 104. `send_results_ready_analytics_events`
- **Signature:** `send_results_ready_analytics_events(test_hash: str, eligible_for_care: bool, ineligible_reason: str | None)`
- **Enqueue:** `.delay(...)` — event-driven when results are released
- **Retry:** None
- **Purpose:** Comprehensive analytics event sent when test results are ready. Creates/updates `CareEligible` record, tracks eligibility for bundle and a la carte care, sends to FullStory, Klaviyo, and Braze simultaneously.

#### 105. `send_urine_test_results_ready_analytics_events`
- **Signature:** `send_urine_test_results_ready_analytics_events(urine_test_hash: str)`
- **Enqueue:** `.delay(...)` — event-driven after UTI results released
- **Retry:** None
- **Purpose:** UTI-specific analytics — records UTI care eligibility in CareEligible record with expiration date.

#### 106. `send_care_checkout_created_event`
- **Signature:** `send_care_checkout_created_event(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — event-driven at checkout
- **Retry:** None
- **Purpose:** Sends "Care Checkout Created" FullStory event with consult details, care eligibility, infection state, and transparent pricing info.

#### 107. `send_ungated_rx_order_paid_event`
- **Signature:** `send_ungated_rx_order_paid_event(order_number)`
- **Enqueue:** `.delay(order.order_number)` — on ungated RX order payment
- **Retry:** None
- **Purpose:** Sends "Ungated Paid" FullStory event and `URX_PURCHASE` Braze event for symptom-relief orders.

#### 108. `send_mpt_voucher_paid_event`
- **Signature:** `send_mpt_voucher_paid_event(user_id)`
- **Enqueue:** `.delay(user.id)` — event-driven on MPT voucher purchase
- **Retry:** None
- **Purpose:** Sends "MPT Voucher Paid" analytics event to FullStory, Klaviyo, and Braze.

#### 109. `send_consult_paid_event`
- **Signature:** `send_consult_paid_event(consult_uid, order_number)`
- **Enqueue:** `.delay(consult.uid, order.order_number)` — on care purchase completion
- **Retry:** None
- **Purpose:** Sends "Care Paid" analytics event with full purchase details to FullStory, Klaviyo, and Braze. Handles UTI-specific events automatically.

#### 110. `send_any_paid_event`
- **Signature:** `send_any_paid_event(order_number: str)`
- **Enqueue:** `.delay(order.order_number)` — on any order payment
- **Retry:** None
- **Purpose:** Sends generic "Any Paid" FullStory event categorizing the order type (test, vaginitis+test, care, refill, ungated RX, etc.).

#### 111. `send_prescription_refills_paid_event`
- **Signature:** `send_prescription_refills_paid_event(prescription_refill_id, order_number)`
- **Enqueue:** `.delay(prescription_fill_id, order.provider_id)` — from `send_prescription_refill_request`
- **Retry:** None
- **Purpose:** Sends "Prescription Refills Paid" FullStory event with the prescription slugs purchased.

#### 112. `send_additional_tests_checkout_created_event`
- **Signature:** `send_additional_tests_checkout_created_event(test_hash)`
- **Enqueue:** `.delay(test_hash)` — on additional test kit checkout
- **Retry:** None
- **Purpose:** Sends "Additional Tests Checkout Created" FullStory event.

#### 113. `send_additional_tests_paid_event`
- **Signature:** `send_additional_tests_paid_event(test_hash, order_number)`
- **Enqueue:** `.delay(test_hash, order.order_number)` — on additional test purchase
- **Retry:** None
- **Purpose:** Sends "Additional Tests Paid" FullStory event.

#### 114. `send_consult_intake_ineligible_event`
- **Signature:** `send_consult_intake_ineligible_event(consult_uid, refer_out_reason)`
- **Enqueue:** `.delay(consult.uid, reason)` — when consult intake is deemed ineligible
- **Retry:** None
- **Purpose:** Sends "Consult Intake Ineligible" FullStory event with referral reason.

#### 115. `send_rx_order_attached_to_account_klaviyo_event`
- **Signature:** `send_rx_order_attached_to_account_klaviyo_event(consult_uid, order_number)`
- **Enqueue:** `.delay(consult.uid, order.order_number)` — from `add_order_treatments_to_latest_existing_consult`
- **Retry:** None
- **Purpose:** Sends "RX Attached to Account" Klaviyo event when an ungated RX order gets linked to a user account.

#### 116. `send_consult_intake_submitted_event`
- **Signature:** `send_consult_intake_submitted_event(consult_uid)`
- **Enqueue:** `.delay(consult_uid)` — from `submit_consult_intake_to_wheel` after Wheel submission
- **Retry:** None
- **Purpose:** Sends "Consult Intake Submitted" analytics event to FullStory, Klaviyo, and Braze. Handles UTI-specific events.

#### 117. `send_coaching_call_completed_event`
- **Signature:** `send_coaching_call_completed_event(test_hash, coaching_call_notes_id=None, num_calls=None)`
- **Enqueue:** `.delay(...)` — event-driven when coaching call notes are saved
- **Retry:** None
- **Purpose:** Sends "Coaching Call Completed" FullStory event.

#### 118. `send_treatment_delivered_event`
- **Signature:** `send_treatment_delivered_event(consult_uid)`
- **Enqueue:** `.delay(treatment_plan.consult.uid)` — from `send_treatment_probably_delivered_events_for_treatment_plans`
- **Retry:** None
- **Purpose:** Sends "Treatment Delivered" Klaviyo event with treatment dates and SKUs.

#### 119. `send_estimated_treatment_started_events`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 7:15AM
- **Retry:** None
- **Purpose:** Finds treatment plans where treatment should have started (based on start date, delivered date, or estimated date) and enqueues `send_estimated_treatment_started_event` for each.

#### 120. `send_estimated_treatment_started_event`
- **Signature:** `send_estimated_treatment_started_event(treatment_plan_id: int)`
- **Enqueue:** `.delay(treatment_plan.id)` — from `send_estimated_treatment_started_events`
- **Retry:** None
- **Purpose:** Sends "Treatment Started" Klaviyo event if the estimated treatment start date is today or yesterday.

#### 121. `send_test_delivered_klaviyo_event`
- **Signature:** `send_test_delivered_klaviyo_event(test_hash)`
- **Enqueue:** `.delay(test_hash)` — event-driven when test kit is delivered to customer
- **Retry:** None
- **Purpose:** Sends "Test Kit Delivered" Klaviyo event using the ecomm order email.

#### 122. `send_health_history_completed_klaviyo_event`
- **Signature:** `send_health_history_completed_klaviyo_event(test_hash)`
- **Enqueue:** `.delay(test_hash)` — on health history submission
- **Retry:** None
- **Purpose:** Sends "Health History Completed" Klaviyo event.

#### 123. `send_updated_treatment_start_date_event`
- **Signature:** `send_updated_treatment_start_date_event(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — when user updates their treatment start date
- **Retry:** None
- **Purpose:** Sends "Updated Treatment Start Date" Klaviyo event.

#### 124. `send_treatment_ended_event`
- **Signature:** `send_treatment_ended_event(treatment_plan_id: int)`
- **Enqueue:** `.delay(treatment_plan.id)` — from `send_treatment_ended_events_for_treatment_plans`
- **Retry:** None
- **Purpose:** Sends "Treatment Ended" Klaviyo event and Braze `TREATMENT_ENDED` event when a treatment plan ends.

#### 125. `send_treatment_ended_events_for_treatment_plans`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 2:15AM
- **Retry:** None
- **Purpose:** Finds treatment plans whose end date is today or yesterday and enqueues `send_treatment_ended_event` for each.

#### 126. `send_treatment_probably_delivered_events_for_treatment_plans`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 6:15AM
- **Retry:** None
- **Purpose:** Finds treatment plans where no delivery timestamp has been recorded but the expected delivery window has passed (based on average fulfillment days), and sends treatment delivered events.

#### 127. `send_provider_registered_event`
- **Signature:** `send_provider_registered_event(provider_id)`
- **Enqueue:** `.delay(provider.id)` — on provider registration
- **Retry:** None
- **Purpose:** Sends "Provider Registered" Klaviyo event.

#### 128. `send_provider_verified_event`
- **Signature:** `send_provider_verified_event(provider_id)`
- **Enqueue:** `.delay(provider.id)` — when a provider's account is verified
- **Retry:** None
- **Purpose:** Sends "[Provider] Provider Verified" Klaviyo event.

#### 129. `send_provider_ordered_test_klaviyo_event`
- **Signature:** `send_provider_ordered_test_klaviyo_event(provider_id, provider_test_order_ids, payer, add_expanded_pcr=False, patient_email=None)`
- **Enqueue:** `.delay(...)` — when provider creates a test order
- **Retry:** None
- **Purpose:** Sends two Klaviyo events: "Provider Ordered A Test for User" (to patient) and "[Provider] Provider Ordered a Test" (to provider) with checkout link, payer info, and test count.

#### 130. `send_provider_reminded_patient_klaviyo_event`
- **Signature:** `send_provider_reminded_patient_klaviyo_event(provider_id, patient_email)`
- **Enqueue:** `.delay(...)` — when provider sends a reminder to patient
- **Retry:** None
- **Purpose:** Sends "Provider Reminded User to Purchase Test" Klaviyo event with checkout link.

#### 131. `send_viewed_plan_klaviyo_event`
- **Signature:** `send_viewed_plan_klaviyo_event(test_id)`
- **Enqueue:** `.delay(test.id)` — when user views their plan
- **Retry:** None
- **Purpose:** Sends "Viewed Plan" Klaviyo event.

#### 132. `send_consult_intake_started_klaviyo_event`
- **Signature:** `send_consult_intake_started_klaviyo_event(consult_uid)`
- **Enqueue:** `.delay(consult.uid)` — when user starts consult intake
- **Retry:** None
- **Purpose:** Sends "Consult Intake Started" Klaviyo event.

#### 133. `send_three_weeks_after_treatment_delivered_klaviyo`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 7:15AM
- **Retry:** None
- **Purpose:** Sends "Consult Eligible for Refill" Klaviyo event for all consults that are now eligible for prescription refills (~3 weeks after treatment delivered).

---

### ecomm/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`

#### 134. `send_patient_ordered_provider_test_notification`
- **Signature:** `send_patient_ordered_provider_test_notification(patient_email, order_sku, order_provider_id)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(...)` — event-driven when a patient pays for a provider-ordered test
- **Retry:** None
- **Purpose:** Sends admin notification to B2B in-clinic team when a patient (or provider) pays for a provider-ordered test.

#### 135. `void_share_a_sale_transaction`
- **Signature:** `void_share_a_sale_transaction(order_number, order_date, reason)`
- **Decorator:** `@shared_task` + `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` (using `retrying` library)
- **Enqueue:** `.delay(...)` — event-driven on order cancellation
- **Retry:** Up to 3 attempts with exponential backoff (500ms multiplier) via `retrying` library
- **Purpose:** Voids a ShareASale affiliate commission for a cancelled order via the ShareASale API.

#### 136. `send_prescription_refill_request`
- **Signature:** `send_prescription_refill_request(order_id, prescription_fill_id)`
- **Enqueue:** `.delay(order.id, prescription_fill.id)` — from Shopify webhook handler on subscription refill orders
- **Retry:** None
- **Purpose:** Processes a prescription refill order end-to-end: validates state eligibility, checks remaining refills, creates patient in Precision, creates prescriptions, creates OTC treatments, and sends fill request to Precision pharmacy.

#### 137. `send_otc_treatment_fill_request`
- **Signature:** `send_otc_treatment_fill_request(order_id: int, prescription_fill_id: int)`
- **Enqueue:** `.delay(order.id, prescription_fill.id)` — from `care/tasks.py:heal_otc_treatment_only_orders`
- **Retry:** None
- **Purpose:** Processes OTC-only orders (no prescription medications). No state restrictions apply. Creates patient, OTC treatments, and sends fill request to Precision.

#### 138. `attach_unattached_orders_to_user`
- **Signature:** `attach_unattached_orders_to_user(user_id: int) -> None`
- **Enqueue:** `.delay(user.id)` — event-driven when a user account is created or email changes
- **Retry:** None
- **Purpose:** Links all existing orders with the same email address to a newly-created user account. For ungated RX orders, also creates or attaches to a consult.

#### 139. `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Signature:** `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(user_id: int, order_number: str)`
- **Enqueue:** `.delay(...)` — called from `attach_unattached_orders_to_user` and event-driven
- **Retry:** None
- **Purpose:** Handles ungated RX orders: consolidates treatment selections into the latest in-progress consult, or creates a new ungated RX consult. Pre-populates intake with health history symptoms if available.

#### 140. `create_consults_for_ungated_rx_orders_with_users_but_no_consult`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 7:15AM
- **Retry:** None
- **Purpose:** Healing task — finds ungated RX orders with users but no associated consult and creates the consult.

#### 141. `process_gift_card_redemptions`
- **Signature:** `process_gift_card_redemptions(order_id: int) -> None`
- **Enqueue:** `.delay(order.id)` — event-driven on order payment
- **Retry:** None
- **Purpose:** Processes gift card redemptions for a specific order using `GiftCardRedemptionService`.

#### 142. `process_gift_cards`
- **Signature:** `process_gift_cards(order_id: int, payload: dict = None) -> None`
- **Enqueue:** `.delay(order.id, payload)` — event-driven on order payment (includes Shopify payload)
- **Retry:** None
- **Purpose:** Processes both gift card purchases and redemptions for an order. Without payload, only processes redemptions.

#### 143. `reprocess_subscription_refill_orders_daily`
- **Signature:** No args
- **Enqueue:** Beat schedule daily at 4AM
- **Retry:** None
- **Purpose:** Healing task — reprocesses subscription refill orders from the last 24 hours that were incorrectly routed or missed.

---

### ecomm/shopify/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`

#### 144. `retry_failed_shopify_orders`
- **Signature:** No args
- **Decorator:** `@shared_task(soft_time_limit=600, time_limit=900)`
- **Enqueue:** Beat schedule daily at 1AM
- **Retry:** None (but uses soft_time_limit=600s, hard time_limit=900s)
- **Purpose:** Fetches orders from Shopify API from the last 3 days (excluding last 1 hour) and processes any orders that exist in Shopify but are missing from Evvy's database. Paginates up to 50 pages (1000 orders max).

---

### providers/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`

#### 145. `send_provider_ordered_single_test_notifications`
- **Signature:** `send_provider_ordered_single_test_notifications(provider_email, patient_email, provider_test_order_id, payer, add_expanded_pcr=False)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(...)` — event-driven when provider orders a single test
- **Retry:** None
- **Purpose:** Sends FYI admin email to B2B in-clinic team when a provider creates a single test order for a patient.

#### 146. `send_provider_bulk_ordered_tests_notification`
- **Signature:** `send_provider_bulk_ordered_tests_notification(provider_email, num_ordered, provider_test_order_ids)`
- **Enqueue:** `.delay(...)` — event-driven on bulk test order
- **Retry:** None
- **Purpose:** Sends FYI admin email when a provider creates a bulk test order (pending payment).

#### 147. `send_provider_bulk_order_paid_notification`
- **Signature:** `send_provider_bulk_order_paid_notification(ecomm_order_id, provider_email, quantity)`
- **Enqueue:** `.delay(...)` — event-driven on bulk order payment
- **Retry:** None
- **Purpose:** Sends FYI admin email when a provider bulk order is paid.

#### 148. `send_provider_test_results_ready`
- **Signature:** `send_provider_test_results_ready(provider_email)`
- **Enqueue:** `.delay(provider_email)` — event-driven when patient results are ready
- **Retry:** None
- **Purpose:** Sends "Results Ready" email to the provider whose patient's test results are now available.

---

### subscriptions/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/tasks.py`

#### 149. `cancel_expired_prescription_subscriptions`
- **Signature:** No args (returns `Dict[str, Any]`)
- **Decorator:** `@shared_task`
- **Enqueue:** Beat schedule daily at 3AM
- **Retry:** None
- **Purpose:** Cancels Recharge subscription charges for prescriptions that have run out of refills. Delegates to `cancel_subscriptions_for_expired_prescriptions` service function.

---

### test_results/lab_services/providers/junction/tasks.py

**File:** `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`

#### 150. `create_unregistered_testkit_order_for_urine_test`
- **Signature:** `create_unregistered_testkit_order_for_urine_test(urine_test_ids: list[int], ecomm_order_id: int)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(urine_test_ids, ecomm_order_id)` — from Shopify order processing when UTI tests are created
- **Retry:** None
- **Purpose:** Creates unregistered testkit orders with Junction lab service for UTI tests immediately at order time. The testkit will be registered later when Wheel approves the lab order. Sends Slack alert on success or failure.

#### 151. `submit_lab_order_approval_to_junction`
- **Signature:** `submit_lab_order_approval_to_junction(self, lab_order_uid: str)`
- **Decorator:** `@shared_task(bind=True, max_retries=3, default_retry_delay=60)`
- **Enqueue:** `.delay(lab_order.uid)` — from `fetch_and_process_completed_lab_order_details` for urine tests
- **Retry:** Up to 3 retries with exponential backoff (60s, 120s, 240s) on 5xx errors and timeouts. On final failure, `task_failure` signal sends a Slack alert.
- **Purpose:** Registers an approved urine test lab order with Junction lab service. This is called after Wheel approves the lab order (clinician NPI confirmed). Registers the pre-created unregistered testkit order.

#### 152. `fetch_and_process_junction_results`
- **Signature:** `fetch_and_process_junction_results(self, external_order_id: str)`
- **Decorator:** `@shared_task(bind=True, max_retries=3)`
- **Enqueue:** `.delay(external_order_id)` — from Junction results webhook handler
- **Retry:** Up to 3 retries with exponential backoff (60s, 120s, 240s, capped at 300s)
- **Purpose:** Fetches lab results from Junction API after receiving a "results_ready" webhook. Processes results via `LabServicesOrchestrator`. The webhook endpoint returns 200 immediately after dispatching this task.

#### 153. `fulfill_uti_order_in_shopify`
- **Signature:** `fulfill_uti_order_in_shopify(urine_test_id: int, tracking_number: str, courier: str)`
- **Decorator:** `@shared_task`
- **Enqueue:** `.delay(urine_test.id, tracking_number, courier)` — from Junction webhook on "transit_customer" status
- **Retry:** None
- **Purpose:** Marks a UTI test kit order as fulfilled in Shopify with the tracking number from Junction when the test kit is shipped to the customer.

---

## Summary: Retry Configurations

The vast majority of tasks have **no Celery-level retry configuration**. The few with explicit retry logic are:

| Task | File | Retry Mechanism |
|------|------|----------------|
| `submit_lab_order_approval_to_junction` | `junction/tasks.py` | Celery `bind=True, max_retries=3`, exponential backoff (60s→120s→240s), only for 5xx/timeouts |
| `fetch_and_process_junction_results` | `junction/tasks.py` | Celery `bind=True, max_retries=3`, exponential backoff (60s→120s→240s, max 300s) |
| `void_share_a_sale_transaction` | `ecomm/tasks.py` | `@retry` decorator (retrying library), 3 attempts, 500ms exponential backoff |
| `retry_failed_shopify_orders` | `ecomm/shopify/tasks.py` | No retry, but has `soft_time_limit=600, time_limit=900` |

Application-level "retry" patterns (not Celery retries) exist in:
- `retry_failed_prescription_fills` — re-queries WARNING fills and calls Precision API again
- `retry_failed_berlin_order_fulfillments` — re-enqueues `send_order_to_berlin_for_fulfillment`
- All `retry_*` / `resubmit_*` Beat-scheduled tasks — are healing cron jobs, not Celery retries

## Summary: Enqueue Methods

| Method | Usage Pattern |
|--------|--------------|
| `.delay(args)` | Standard async invocation — used throughout (majority of all task calls) |
| `.apply_async(args=[...], countdown=N)` | Delayed execution — used for load balancing in `process_microgen_test_results` and for batching summaries in `_queue_summary_notification` |
| `self.retry(exc=e, countdown=N)` | Inside `submit_lab_order_approval_to_junction` and `fetch_and_process_junction_results` |
| Beat schedule | ~30 tasks scheduled via `CELERY_BEAT_SCHEDULE` in `settings_celery.py` |
| Called directly (synchronously) | Several tasks are called directly rather than via `.delay()`: `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_create_otc_treatment_request_to_precision`, `send_fill_request_to_precision`, `send_cancel_fill_request_to_precision`, `send_prescription_to_precision` (direct call in `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`), `create_test_result_tagset`, `assign_suspected_yeast_flag_to_test_result`, `attach_latest_otc_treatment_to_consult`, `check_recommended_prescriptions_against_prescribed` |
