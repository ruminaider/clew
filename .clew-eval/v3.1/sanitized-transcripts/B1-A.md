# Exploration Transcript: Tool A — B1

**Task:** "We're considering changing the signature of the function that processes shopify orders for treatment refills. What would break? Find all callers, understand what arguments they pass, and identify any test coverage."

---

## Step 1: Initial Discovery

I'll systematically explore the codebase to find the function that processes Shopify orders for treatment refills and analyze the impact of changing its signature.

**Tool call:** `find_files("*.py")` — listing Python files and top-level directory structure

**Result (excerpt):**
```
backend/ecomm/shopify/tasks.py
backend/ecomm/utils.py
backend/ecomm/tests/test_utils.py
backend/ecomm/tests/test_shopify_tasks.py
backend/subscriptions/service.py
backend/scripts/reprocess_subscription_refill_orders.py
...
```

---

## Step 2: Broad Search for the Target Function

**Tool call:** `search("shopify.*order|order.*shopify|treatment.*refill|refill.*treatment", files_with_matches=True, case_insensitive=True)`

**Result:** 135 files matched. Key files identified:
- `backend/ecomm/utils.py`
- `backend/ecomm/shopify/tasks.py`
- `backend/ecomm/tests/test_utils.py`
- `backend/ecomm/tests/test_shopify_tasks.py`
- `backend/subscriptions/service.py`
- `backend/scripts/reprocess_subscription_refill_orders.py`

---

## Step 3: Find Function Definitions

**Tool call:** `search("def.*process.*shopify.*order|def.*shopify.*order.*process|def.*process.*order.*refill|def.*refill.*order", output_mode="content", case_insensitive=True)`

**Result:**
```
backend/ecomm/utils.py:204:def process_shopify_order(payload: dict[str, Any], is_order_cancellation: bool):
backend/ecomm/utils.py:238:def _process_shopify_order_impl(
backend/ecomm/utils.py:1600:def process_shopify_order_for_test(
backend/ecomm/utils.py:1788:def process_shopify_order_for_unknown_order_sku(
backend/ecomm/utils.py:1807:def process_shopify_order_for_care(
backend/ecomm/utils.py:1964:def process_shopify_order_for_pcr_add_on(
backend/ecomm/utils.py:2089:def process_shopify_order_for_treatment_refill(
backend/ecomm/utils.py:2732:def can_refill_entire_order(user: User, order: Order) -> bool:
backend/ecomm/shopify/tasks.py:20:def process_shopify_order_from_api(shopify_order_list):
backend/ecomm/shopify/tasks.py:48:def process_unprocessed_shopify_orders_by_email(order_email: str):
backend/ecomm/shopify/tasks.py:54:def process_unprocessed_shopify_orders_by_checkout_token(checkout_token: str):
backend/analytics/tasks.py:863:def send_prescription_refills_paid_event(prescription_refill_id, order_number):
backend/ecomm/tasks.py:157:def send_prescription_refill_request(order_id, prescription_fill_id):
backend/ecomm/tasks.py:587:def reprocess_subscription_refill_orders_daily():
backend/scripts/reprocess_subscription_refill_orders.py:238:def reprocess_subscription_refill_orders(
```

---

## Step 4: Read the Tasks File (Entry Points)

**Tool call:** `read("backend/ecomm/shopify/tasks.py")`

**Result:**
```python
from ecomm.utils import process_shopify_order

def process_shopify_order_from_api(shopify_order_list):
    processed_orders = []
    for shopify_order in shopify_order_list:
        order_number = shopify_order["node"]["name"].replace("#", "").strip()
        order = Order.objects.filter(order_number=order_number).first()

        if not order:
            logger.warning(f"Order {order_number} created in Shopify but missing in Evvy system")
            is_cancellation_order = shopify_order["node"]["cancelReason"]
            shopify_payload = format_shopify_webhook_payload_from_api(shopify_order)
            if is_cancellation_order:
                order = process_shopify_order(shopify_payload, is_order_cancellation=True)
            else:
                order = process_shopify_order(shopify_payload, is_order_cancellation=False)
            processed_orders.append(order)
        else:
            processed_orders.append(order)
    return processed_orders

def process_unprocessed_shopify_orders_by_email(order_email: str):
    client = ShopifyAdminAPIClient()
    shopify_orders = client.get_unprocessed_orders_by_email(order_email)
    return process_shopify_order_from_api(shopify_orders)

def process_unprocessed_shopify_orders_by_checkout_token(checkout_token: str):
    client = ShopifyAdminAPIClient()
    shopify_orders = client.get_unprocessed_orders_by_checkout_token(checkout_token)
    return process_shopify_order_from_api(shopify_orders)

@shared_task(soft_time_limit=600, time_limit=900)
def retry_failed_shopify_orders():
    # ... paginated fetch from Shopify Admin API, calls process_shopify_order_from_api()
```

---

## Step 5: Read the Target Function

**Tool call:** `read("backend/ecomm/utils.py", offset=2089, limit=150)`

**Result:**
```python
def process_shopify_order_for_treatment_refill(
    order: Order, payload: dict[str, Any], order_logger: OrderEventLogger | None = None
):
    """
    Custom order processing logic for prescription refill, replacement, and otc treatment orders.
    Supports both legacy consult-based orders and new evergreen prescription orders.
    """
    # 1. parse order attributes to get ids
    order_attrs = _parse_order_note_attributes(payload)
    replacement_fill_id = _parse_replacement_fill_id(payload)
    prescription_fill_id = order_attrs.prescription_fill_id or replacement_fill_id

    # 2. get prescription fill using the id or create a new one if it doesn't exist
    if prescription_fill_id and _is_valid_uuid(prescription_fill_id):
        prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)
    else:
        lookup_params = {"order": order}
        if order.user:
            lookup_params["user"] = order.user
        prescription_fill, _ = PrescriptionFill.objects.get_or_create(**lookup_params)

    # 3. determine user for the order and set consult uid if it exists
    user = None
    consult = None

    if order_attrs.consult_uid:
        consult = Consult.objects.filter(uid=order_attrs.consult_uid).first()
        if consult:
            prescription_fill.consult = consult
            prescription_fill.save()

    # Try to get user from email
    if order_attrs.user_account_email:
        user = User.objects.filter(email__iexact=order_attrs.user_account_email.lower()).first()

    # ungated rx orders don't have a user account email, so use the cart user if it exists
    if not user and order.cart and order.cart.user:
        user = order.cart.user

    if not user and consult:
        user = consult.user

    # Fallback to order email if still no user found
    if not user and order.email:
        user = User.objects.filter(email__iexact=order.email.lower()).first()

    # Set the user on the order
    if user:
        order.user = user
        order.save()

    # 4. set the order on the prescription fill and through table
    prescription_fill.order = order
    prescription_fill.save()
    PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)

    # 5. get the ordered products, prescriptions, and otc treatments
    ordered_products = get_care_products_from_orders([order])
    prescriptions = Prescription.objects.none()

    # If specific prescription IDs were provided, filter to those
    if order_attrs.prescription_ids:
        try:
            prescription_id_list = [
                int(pid.strip()) for pid in order_attrs.prescription_ids.split(",") if pid.strip()
            ]
            prescriptions = Prescription.objects.filter(id__in=prescription_id_list)
            for prescription in prescriptions:
                if prescription.user != order.user:
                    error_message = f"User on prescription {prescription.id} is not the same as the order user {order.user.id}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(
                f"Invalid prescription_ids format in order {order.order_number}: {order_attrs.prescription_ids}. Unable to process prescriptions"
            )
            raise e
    elif order.user:
        # For evergreen prescriptions, get user prescriptions directly
        prescriptions = (
            Prescription.objects.filter(
                user=order.user, product__in=ordered_products, deleted=False
            )
            .order_by("product_id", "create_date")
            .distinct("product_id")
        )
    else:
        logger.warning(
            f"No prescription IDs provided for order {order.order_number} and no user found, cannot process prescriptions"
        )

    otc_treatments = order.otc_treatments.all()

    if not prescriptions.exists() and not otc_treatments.exists():
        logger.error(
            f"No prescriptions and no otc treatments found for order {order.order_number}. "
            "Unable to send prescription fill request to precision."
        )
        return

    # 6. create the prescription fill (prescriptions and otc treatments)
    if prescriptions.exists():
        create_prescription_fill_prescriptions(prescription_fill, list(prescriptions), [order])
    if otc_treatments.exists() and order.status != Order.STATUS_CANCELLED:
        create_prescription_fill_otc_treatments(prescription_fill, list(otc_treatments))

    # 7. send the prescription fill request to precision
    send_prescription_refill_request.delay(order.id, prescription_fill.id)

    # 8. mark the cart as purchased if it exists
    order = mark_order_cart_as_purchased(cart_id=order_attrs.cart_id, order=order)
```

---

## Step 6: Find All Callers of the Target Function

**Tool call:** `search("process_shopify_order_for_treatment_refill", output_mode="content")`

**Result:**
```
backend/ecomm/utils.py:672:        process_shopify_order_for_treatment_refill(order, payload, order_logger)
backend/ecomm/utils.py:682:            process_shopify_order_for_treatment_refill(order, payload, order_logger)
backend/ecomm/utils.py:2089:def process_shopify_order_for_treatment_refill(
backend/ecomm/utils.py:2757:    # process_shopify_order_for_treatment_refill() so the same prescriptions
backend/ecomm/tests/test_utils.py:2006:    def test_process_shopify_order_for_treatment_refill(self, mock_task):
backend/ecomm/tests/test_utils.py:3487:@patch("ecomm.utils.process_shopify_order_for_treatment_refill")
backend/ecomm/tests/test_utils.py:3511:        should route to process_shopify_order_for_treatment_refill.
backend/scripts/reprocess_subscription_refill_orders.py:5:were being routed to `process_shopify_order_for_care` instead of `process_shopify_order_for_treatment_refill`,
```

There are exactly **two call sites** in production code, both within `_process_shopify_order_impl()` in `backend/ecomm/utils.py`.

---

## Step 7: Read Both Call Sites in Context

**Tool call:** `read("backend/ecomm/utils.py", offset=640, limit=80)`

**Result (call site 1 — line 672):**
```python
    # now perform order type specific updates
    if order.order_type in [
        Order.ORDER_TYPE_VAGINITIS_CARE,
        Order.ORDER_TYPE_STI_CARE,
        Order.ORDER_TYPE_UTI_CARE,
        Order.ORDER_TYPE_A_LA_CARTE,
        Order.ORDER_TYPE_DYNAMIC_BUNDLE,
        Order.ORDER_TYPE_MIXED_CARE,
        Order.ORDER_TYPE_MALE_PARTNER,
    ]:
        order = process_shopify_order_for_care(order, payload, order_logger)
    elif order.order_type in [
        Order.ORDER_TYPE_TEST,
        Order.ORDER_TYPE_EXPANDED_TEST,
        Order.ORDER_TYPE_URINE_TEST,
    ]:
        process_shopify_order_for_test(order, payload, bulk_order_id, order_logger)
    elif order.order_type == Order.ORDER_TYPE_PCR_ADD_ON:
        process_shopify_order_for_pcr_add_on(order, payload, order_logger)
    else:
        process_shopify_order_for_unknown_order_sku(order, payload, order_logger)

    # Orders with prescription refills could be labeled with the "Test" order type, so check the line items.
    if (
        order.order_type
        not in [
            Order.ORDER_TYPE_A_LA_CARTE,
            Order.ORDER_TYPE_MIXED_CARE,
            Order.ORDER_TYPE_DYNAMIC_BUNDLE,
            Order.ORDER_TYPE_UNGATED_RX,
            Order.ORDER_TYPE_MALE_PARTNER,
        ]
        and Order.ORDER_TYPE_PRESCRIPTION_TREATMENT in line_item_order_types
    ):
        process_shopify_order_for_treatment_refill(order, payload, order_logger)  # LINE 672
```

**Tool call:** `read("backend/ecomm/utils.py", offset=676, limit=15)`

**Result (call site 2 — line 682):**
```python
    # Ungated RX orders: route to refill path if all Rx products have valid prescriptions,
    # otherwise fall back to consult/intake path.
    if order.order_type == Order.ORDER_TYPE_UNGATED_RX and order.user:
        if can_refill_entire_order(order.user, order):
            logger.info(
                f"UX order {order.order_number}: routing to refill path "
                f"(all Rx products have valid prescriptions for user {order.user.id})"
            )
            process_shopify_order_for_treatment_refill(order, payload, order_logger)  # LINE 682
        else:
            logger.info(
                f"UX order {order.order_number}: routing to consult/intake path "
                f"(not all Rx products have refillable prescriptions for user {order.user.id})"
            )
            add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(
                order.user.id, order.order_number
            )
```

Both call sites pass exactly: `(order, payload, order_logger)` — same arguments, same pattern.

---

## Step 8: Read the Public Wrapper and Inner Implementation

**Tool call:** `read("backend/ecomm/utils.py", offset=204, limit=34)`

**Result:**
```python
def process_shopify_order(payload: dict[str, Any], is_order_cancellation: bool):
    """
    Wrapper for order processing with comprehensive error handling and monitoring.
    """
    order_number = str(payload.get("order_number", ""))
    shopify_order_id = str(payload.get("id", ""))
    start_time = time.time()
    order_logger = create_order_logger()

    try:
        return _process_shopify_order_impl(payload, is_order_cancellation, order_logger)
    except Exception as e:
        # logs to NewRelic and re-raises
        raise
```

**Tool call:** `read("backend/ecomm/utils.py", offset=238, limit=80)`

**Result:**
```python
def _process_shopify_order_impl(
    payload: dict[str, Any], is_order_cancellation: bool, order_logger: OrderEventLogger
):
    """
    Processes shopify webhook payload.
    Most orders have a single line item, but an order may have multiple line items.
    This function is idempotent.
    """
    # ... parses payload, creates Order records, determines order type ...
    # ... then calls process_shopify_order_for_treatment_refill() at lines 672 and 682
```

---

## Step 9: Read Test Coverage for the Target Function

**Tool call:** `read("backend/ecomm/tests/test_utils.py", offset=2006, limit=160)`

**Result — Direct tests (lines 2006–2140):**

```python
@patch("ecomm.utils.send_prescription_refill_request")
def test_process_shopify_order_for_treatment_refill(self, mock_task):
    # Sets up user, consult, EcommProduct with RFLBA001 SKU, Prescription, PrescriptionFill
    payload = {
        "order_number": 1234,
        "email": "test@example.com",
        "note_attributes": [
            {"name": "prescription_fill_id", "value": str(prescription_fill.id)}
        ],
        "test": False,
        "total_line_items_price": "50.00",
        "line_items": [{"sku": "RFLBA001", ...}],
    }
    process_shopify_order(payload, is_order_cancellation=False)
    order = Order.objects.get(order_number="1234")
    self.assertEqual(order.business_verticals, [Order.VERTICAL_CARE])
    self.assertEqual(order.user_id, user.id)
    mock_task.delay.assert_called_with(order.id, prescription_fill.id)

@patch("ecomm.utils.send_prescription_refill_request")
def test_process_shopify_order_for_manual_treatment_refill(self, mock_task):
    # Uses "source_name": "shopify_draft_order" and stores fill id in payload["note"]
    payload = {
        "order_number": 1234,
        "email": "test@example.com",
        "note": str(prescription_fill.id),
        "source_name": "shopify_draft_order",
        ...
    }
    process_shopify_order(payload, is_order_cancellation=False)
    mock_task.delay.assert_called_with(order.id, prescription_fill.id)

@patch("ecomm.utils.send_prescription_refill_request")
def test_process_shopify_order_for_replacement_treatment(self, mock_task):
    # Uses "note": f"replacement-{str(draft_fill.id)}" for replacement orders
    payload = {
        "order_number": 1234,
        "email": "test@example.com",
        "note": f"replacement-{str(draft_fill.id)}",
        ...
    }
    process_shopify_order(payload, is_order_cancellation=False)
    mock_task.delay.assert_called_with(order.id, draft_fill.id)
```

**Tool call:** `read("backend/ecomm/tests/test_utils.py", offset=3487, limit=80)`

**Result — UX/Ungated RX routing tests (line 3487):**

```python
@patch("ecomm.utils.process_shopify_order_for_treatment_refill")
@patch("ecomm.utils.add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult")
class TestUngatedRxOrderRouting(TestCase):
    """Integration tests for UX order routing to refill vs consult path."""

    def setUp(self):
        # Sets up user, products with URXBA001 SKU, payload

    def test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path(
        self, mock_consult, mock_refill, mock_fulfill
    ):
        """UX order where user has valid prescriptions for all Rx products
        should route to process_shopify_order_for_treatment_refill."""
        PrescriptionFactory.create(user=self.user, product=self.rx_product, num_allowed_refills=5, ...)
        process_shopify_order(self.payload, is_order_cancellation=False)
        mock_refill.assert_called_once()
        mock_consult.assert_not_called()

    def test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path(
        self, mock_consult, mock_refill, mock_fulfill
    ):
        """UX order where user has NO prescriptions should route to
        add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult."""
        process_shopify_order(self.payload, is_order_cancellation=False)
        mock_consult.assert_called_once()
        mock_refill.assert_not_called()
```

---

## Step 10: Read the OrderNoteAttributes Dataclass

**Tool call:** `search("class OrderNoteAttributes", output_mode="content")`

**Tool call:** `read("backend/ecomm/utils.py", offset=142, limit=25)`

**Result:**
```python
class OrderNoteAttributes(BaseModel):
    """Represents parsed order note attributes from Shopify payload."""

    prescription_fill_id: str | None = None
    cart_id: str | None = None
    consult_uid: str | None = None
    user_account_email: str | None = None
    prescription_ids: str | None = None
```

---

## Step 11: Read the Reprocessing Script

**Tool call:** `read("backend/scripts/reprocess_subscription_refill_orders.py")`

**Result:** A backfill/reprocessing script that does NOT directly call `process_shopify_order_for_treatment_refill()`. Instead it reimplements equivalent logic inline (`create_prescription_fill_prescriptions`, `create_prescription_fill_otc_treatments`, `send_prescription_refill_request`). It references the function name only in its docstring/comment.

---

## Step 12: Read the send_prescription_refill_request Task

**Tool call:** `read("backend/ecomm/tasks.py", offset=155, limit=60)`

**Result:**
```python
@shared_task
def send_prescription_refill_request(order_id, prescription_fill_id):
    """
    Assumptions:
    - Order has an associated prescription fill ID
    - Prescriptions have been sent to the pharmacy
    - If there are no prescriptions, then it is an otc-only order
    """
    order = Order.objects.get(id=order_id)
    prescription_fill = PrescriptionFill.objects.get(id=prescription_fill_id)
    # ... handles cancellations, verifies shipping address, checks prescription refills ...
    # ... then calls precision pharmacy API to fulfill ...
```

---

## Step 13: Read the can_refill_entire_order Function

**Tool call:** `read("backend/ecomm/utils.py", offset=2720, limit=80)`

**Result:**
```python
def can_refill_entire_order(user: User, order: Order) -> bool:
    """
    Check whether every Rx care product in the order has a valid, refillable
    prescription for the given user.  OTC products pass unconditionally.
    """
    care_products = get_care_products_from_orders([order])
    ...
    # Mirror the "evergreen prescription" lookup used by
    # process_shopify_order_for_treatment_refill() so the same prescriptions
    # will be found downstream.
    # NOTE: This mirrors the `elif order.user:` branch of the downstream
    # function.  If an order carries explicit `prescription_ids` in its note
    # attributes, the downstream function uses those IDs instead.
    prescriptions = (
        Prescription.objects.filter(user=user, product__in=rx_products, deleted=False)
        .order_by("product_id", "create_date")
        .distinct("product_id")
    )
    ...
```

This function has an explicit comment noting it mirrors the lookup logic inside `process_shopify_order_for_treatment_refill()`.

---

## Step 14: Check All Sibling Functions (Same Signature Pattern)

**Tool call:** `read("backend/ecomm/utils.py", offset=1788, limit=25)`

Other sibling functions all share the same signature pattern `(order, payload, order_logger=None)`:
- `process_shopify_order_for_unknown_order_sku(order, payload, order_logger=None)`
- `process_shopify_order_for_care(order, payload, order_logger=None) -> Order`
- `process_shopify_order_for_test(order, payload, bulk_order_id=None, order_logger=None)`

---

## Step 15: Confirm Comprehensive Search — All References

**Tool call:** `search("process_shopify_order_for_treatment_refill|_process_shopify_order_impl", output_mode="content", case_insensitive=True)`

**Result:**
```
docs/adr/00052-subscription-refill-order-custom-attributes.md:55:  - `_process_shopify_order_impl()` - Lines 580-595 (checkout source logic)
backend/ecomm/utils.py:217:        return _process_shopify_order_impl(payload, is_order_cancellation, order_logger)
backend/ecomm/utils.py:238:def _process_shopify_order_impl(
backend/ecomm/utils.py:672:        process_shopify_order_for_treatment_refill(order, payload, order_logger)
backend/ecomm/utils.py:682:            process_shopify_order_for_treatment_refill(order, payload, order_logger)
backend/ecomm/utils.py:2089:def process_shopify_order_for_treatment_refill(
backend/ecomm/utils.py:2757:    # process_shopify_order_for_treatment_refill() so the same prescriptions
backend/ecomm/tests/test_order_monitoring.py:72:        with patch("ecomm.utils._process_shopify_order_impl", side_effect=ValueError("Test error")):
backend/ecomm/tests/test_utils.py:2006:    def test_process_shopify_order_for_treatment_refill(self, mock_task):
backend/ecomm/tests/test_utils.py:3487:@patch("ecomm.utils.process_shopify_order_for_treatment_refill")
backend/ecomm/tests/test_utils.py:3511:        should route to process_shopify_order_for_treatment_refill.
backend/scripts/reprocess_subscription_refill_orders.py:5:...routed to `process_shopify_order_for_care` instead of `process_shopify_order_for_treatment_refill`...
```

---

## Final Answer: Impact Analysis

### Function Being Changed

`process_shopify_order_for_treatment_refill(order, payload, order_logger=None)` in `backend/ecomm/utils.py` (line 2089).

**Current signature:**
```python
def process_shopify_order_for_treatment_refill(
    order: Order,
    payload: dict[str, Any],
    order_logger: OrderEventLogger | None = None
):
```

### All Callers (Production Code)

There are exactly **2 call sites**, both inside `_process_shopify_order_impl()` in `backend/ecomm/utils.py`:

| Location | Trigger condition | Arguments passed |
|---|---|---|
| Line 672 | Order has `ORDER_TYPE_PRESCRIPTION_TREATMENT` line items (and order type not in excluded set) | `(order, payload, order_logger)` |
| Line 682 | Order type is `ORDER_TYPE_UNGATED_RX` AND user has valid prescriptions for all Rx products | `(order, payload, order_logger)` |

Both call sites pass the same three arguments. The `order_logger` argument is passed positionally (not as a keyword argument).

### Internal Dependencies (Functions Called Inside)

Changing the function signature may also require updating these internal helper calls if they become parameters:
- `_parse_order_note_attributes(payload)` — parses `note_attributes`, `consult_uid`, `user_account_email`, `prescription_ids`, `_evvyCartId`
- `_parse_replacement_fill_id(payload)` — parses `note` field for replacement fill IDs
- `get_care_products_from_orders([order])` — fetches care products from order line items
- `create_prescription_fill_prescriptions(prescription_fill, list(prescriptions), [order])`
- `create_prescription_fill_otc_treatments(prescription_fill, list(otc_treatments))`
- `send_prescription_refill_request.delay(order.id, prescription_fill.id)` — async Celery task
- `mark_order_cart_as_purchased(cart_id=order_attrs.cart_id, order=order)`

### Related Functions That May Need Updating

**`can_refill_entire_order(user, order)`** — This function has an explicit code comment noting it mirrors the prescription lookup logic inside `process_shopify_order_for_treatment_refill()`. If the signature change involves how prescriptions are selected, this function must be kept in sync.

**Sibling functions** all use the same `(order, payload, order_logger=None)` pattern:
- `process_shopify_order_for_care`
- `process_shopify_order_for_test`
- `process_shopify_order_for_unknown_order_sku`
- `process_shopify_order_for_pcr_add_on`

If the signature change is motivated by a need to add parameters beyond `(order, payload, order_logger)`, consistency with sibling functions should be considered.

### Test Coverage

**Direct test coverage** (`backend/ecomm/tests/test_utils.py`):
- `test_process_shopify_order_for_treatment_refill` (line 2006) — tests standard prescription refill via `prescription_fill_id` in `note_attributes`
- `test_process_shopify_order_for_manual_treatment_refill` (line 2052) — tests draft order (invoice) path where fill ID is in `payload["note"]`
- `test_process_shopify_order_for_replacement_treatment` (line 2098) — tests replacement path where `payload["note"]` has `replacement-{fill_id}` prefix
- `test_process_shopify_order_for_otc_treatments` (line 2141) — tests OTC-only orders

**Routing tests** (`TestUngatedRxOrderRouting` class, line 3487):
- `test__process_shopify_order__ux_order_with_valid_prescriptions__routes_to_refill_path` — mocks the function and asserts it was called
- `test__process_shopify_order__ux_order_without_prescriptions__routes_to_consult_path` — asserts it was NOT called

All test cases call the function **indirectly** through `process_shopify_order(payload, is_order_cancellation=False)` — none call `process_shopify_order_for_treatment_refill()` directly. The routing tests that use `@patch("ecomm.utils.process_shopify_order_for_treatment_refill")` would need to be updated if the signature changes, since they mock at the module level.

### Summary of What Would Break

| Item | What breaks | Effort |
|---|---|---|
| `_process_shopify_order_impl()` line 672 | Direct caller, must update call | Low |
| `_process_shopify_order_impl()` line 682 | Direct caller, must update call | Low |
| `test_process_shopify_order_for_treatment_refill` | Calls via public wrapper; may still pass depending on change | Medium |
| `test_process_shopify_order_for_manual_treatment_refill` | Same | Medium |
| `test_process_shopify_order_for_replacement_treatment` | Same | Medium |
| `TestUngatedRxOrderRouting` (2 tests) | Uses `@patch` — mock args may need updating | Low |
| `can_refill_entire_order()` | Not a caller but mirrors internal logic; may need sync | Medium |
| `reprocess_subscription_refill_orders.py` script | Does NOT call this function; uses inline reimplementation | None |
