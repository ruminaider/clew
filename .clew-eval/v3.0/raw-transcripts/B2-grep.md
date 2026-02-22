# B2 Grep Search Transcript: Order, PrescriptionFill, and Prescription Relationships

## Tool Call Summary
1. Searched for class definitions of Order, PrescriptionFill, and Prescription across Python files
2. Found models in:
   - Order: `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`
   - PrescriptionFill and Prescription: `/Users/albertgwo/Work/evvy/backend/care/models.py`
3. Read complete model files to analyze relationships
4. Cross-referenced model relationships

## Complete Relationship Mapping

### 1. Order Model (ecomm.models.Order)
**Location:** `backend/ecomm/models/order.py`

**Key Fields:**
- `id` (Primary Key)
- `user` - ForeignKey to User (nullable)
- `email` - EmailField
- `provider` - CharField (default: "SH" for Shopify)
- `provider_id` - CharField (DEPRECATED, use order_number)
- `order_number` - CharField
- `order_type` - CharField with choices (VAGINITIS_CARE, STI_CARE, PRESCRIPTION_TREATMENT, etc.)
- `status` - CharField (ACTIVE, CANCELLED)

**Relationships TO Order:**
- `OrderLineItem.order` - ForeignKey (related_name="line_items")
- `OrderShippingAddress.order` - OneToOneField
- `RelatedOrder.parent_order` - ForeignKey (for cross-sell tracking)
- `RelatedOrder.cross_sell_order` - ForeignKey (related_name="cross_sell_orders")
- `PrescriptionFill.order` - ForeignKey (nullable, SET_NULL)
- `PrescriptionFillOrder.order` - ForeignKey (through table)
- `OTCTreatment.order` - ForeignKey (related_name="otc_treatments")

### 2. Prescription Model (care.models.Prescription)
**Location:** `backend/care/models.py` (lines 481-683)

**Key Fields:**
- `id` (Primary Key)
- `uid` - UUIDField (unique identifier)
- `user` - ForeignKey to User
- `product` - ForeignKey to care.Product (nullable - for non-Evvy products)
- `consult` - ForeignKey to consults.Consult
- `prescription_date` - DateField
- `expiration_date` - DateField (computed)
- `num_allowed_refills` - IntegerField (default=0)
- `rx_price` - DecimalField (set from product price)
- `deleted` - BooleanField (soft delete)
- `sent_to_pharmacy_at` - DateTimeField

**Many-to-Many Relationships:**
- `tests` - ManyToManyField to test_results.Test (through="PrescriptionTest")
- `consults` - ManyToManyField to consults.Consult (through="PrescriptionConsults")

**Computed Properties:**
- `@property fill_count` - Returns total number of fills used (from PrescriptionFillPrescriptions)
- `@property is_refillable_product` - Returns True if product is not antibiotic/antifungal
- `@property is_otc_product` - Returns True if product is over-the-counter
- `@property refills_remaining` - Calculated from num_allowed_refills - fill_count + 1
- `@property can_refill` - Boolean based on refills_remaining, expiration, and product status

### 3. PrescriptionFill Model (care.models.PrescriptionFill)
**Location:** `backend/care/models.py` (lines 721-829)

**Key Fields:**
- `id` - UUID Primary Key (via UUIDPrimaryKeyMixin)
- `user` - ForeignKey to User (nullable)
- `consult` - ForeignKey to consults.Consult (nullable since 5/2/2025)
- `order` - ForeignKey to ecomm.Order (nullable, SET_NULL)
- `status` - CharField (DRAFT, CREATED, SHIPPED, DELIVERED, WARNING, CANCELLED, FAILED)
- `shipped_at` - DateTimeField
- `delivered_at` - DateTimeField
- `cancelled_at` - DateTimeField
- `sent_to_pharmacy_at` - DateTimeField
- `shipping_tracking_number` - CharField
- `fill_count` - IntegerField (default=1)
- Shipping address fields: `address_first_line`, `address_second_line`, `city`, `state_code`, `zip_code`
- `pharmacy_patient_id` - CharField

**Many-to-Many Relationships:**
- `prescriptions` - ManyToManyField to Prescription (through="PrescriptionFillPrescriptions")
- `otctreatments` - ManyToManyField to OTCTreatment (through="PrescriptionFillOTCTreatments")

**Computed Properties:**
- `@property shipping_tracking_url` - Generated from tracking number
- `@property is_refill` - Returns True if fill_count > 1
- `@property full_address_string` - Concatenated address
- `@property can_cancel` - Returns True if status is CREATED and sent_to_pharmacy_at is set

### 4. Through Tables

#### PrescriptionFillPrescriptions
**Location:** `backend/care/models.py` (lines 864-893)

**Purpose:** Connects PrescriptionFill to Prescription (many-to-many)

**Fields:**
- `prescriptionfill` - ForeignKey to PrescriptionFill
- `prescription` - ForeignKey to Prescription
- `fill_quantity` - IntegerField (nullable, falls back to prescription.quantity_value)
- `precision_reference_id` - CharField (pharmacy reference)

**Methods:**
- `get_effective_fill_quantity()` - Returns fill_quantity or product's quantity_value

#### PrescriptionFillOrder
**Location:** `backend/care/models.py` (lines 831-846)

**Purpose:** Links PrescriptionFill to Order (many-to-many audit table)

**Fields:**
- `id` - UUID Primary Key
- `prescription_fill` - ForeignKey to PrescriptionFill
- `order` - ForeignKey to ecomm.Order
- Timestamps from TimestampMixin

**Unique Constraint:** (prescription_fill, order)

#### PrescriptionTest
**Location:** `backend/care/models.py` (lines 685-694)

**Purpose:** Through table for Prescription ↔ Test relationship

**Fields:**
- `prescription` - ForeignKey to Prescription
- `test` - ForeignKey to test_results.Test

#### PrescriptionConsults
**Location:** `backend/care/models.py` (lines 696-718)

**Purpose:** Audit table tracking prescription updates across consults

**Fields:**
- `prescription` - ForeignKey to Prescription
- `consult` - ForeignKey to consults.Consult
- `updated_refill_count` - IntegerField (nullable)
- `updated_expiration_date` - DateField (nullable)
- `updated_date` - DateTimeField (nullable)

**Unique Constraint:** (prescription, consult)

### 5. Complete Relationship Chain

**Order → PrescriptionFill:**
- Direct ForeignKey: `PrescriptionFill.order`
- Through table: `PrescriptionFillOrder` (many-to-many audit)
- Cardinality: One Order can have multiple PrescriptionFills

**PrescriptionFill → Prescription:**
- Many-to-Many through `PrescriptionFillPrescriptions`
- Each through record tracks `fill_quantity` and `precision_reference_id`
- Cardinality: One PrescriptionFill can contain multiple Prescriptions (bundle fills)

**Prescription → Order (Indirect):**
- No direct foreign key relationship
- Connected via: Prescription → PrescriptionFill → Order
- Path: `prescription.prescriptionfillprescriptions_set.all()` → `prescriptionfill.order`

**Order → Prescription (Indirect):**
- Connected via: Order → PrescriptionFill → Prescription
- Path: `order.prescriptionfill_set.all()` → `prescriptions.all()`

### 6. Additional Related Models

#### OrderLineItem
**Fields:**
- `order` - ForeignKey to Order (related_name="line_items")
- `care_product` - ForeignKey to care.Product (nullable)
- `ecomm_product` - ForeignKey to ecomm.Product (nullable)
- `sku`, `quantity`, `price`

#### OTCTreatment
**Fields:**
- `order` - ForeignKey to ecomm.Order (related_name="otc_treatments")
- `product` - ForeignKey to care.Product
- Can also be part of PrescriptionFill via PrescriptionFillOTCTreatments

### 7. Key Business Logic

**Fill Counting (Prescription.fill_count property):**
```python
# Counts all non-draft, non-cancelled fills
valid_fills = PrescriptionFillPrescriptions.objects.filter(
    prescription=self
).exclude(
    prescriptionfill__status__in=[DRAFT, CANCELLED]
)
total_quantity = sum(fill.get_effective_fill_quantity() for fill in valid_fills)
return math.ceil(total_quantity / self.product.quantity_value)
```

**Refills Remaining:**
- Calculation: `num_allowed_refills - fill_count + 1`
- Capped by `product.max_allowed_refills` if set
- Returns 0 if prescription is expired

**Can Refill Logic:**
- Must have refills_remaining > 0
- Must be refillable product type (not antibiotic/antifungal)
- Must not be expired
- Product must not be disabled or deprecated

### 8. Data Flow Summary

**Purchase Flow:**
1. User creates Order (via Shopify checkout)
2. Order contains OrderLineItems (with care_product references)
3. After consult, Prescription is created (linked to product and consult)
4. When prescription is filled:
   - PrescriptionFill is created
   - PrescriptionFill.order points to the Order
   - PrescriptionFillPrescriptions links the Prescription(s) to the Fill
   - PrescriptionFillOrder audit record is created
5. Tracking information stored on PrescriptionFill
6. Fill count increments, affecting refills_remaining

**Refill Flow:**
1. User initiates refill (creates draft PrescriptionFill)
2. New Order created via checkout
3. PrescriptionFill.order updated to new Order
4. PrescriptionFillOrder record created
5. Fill transitions from DRAFT → CREATED → SHIPPED → DELIVERED
6. Prescription.fill_count increases based on quantity

## Model File Locations
- `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` - Order, OrderLineItem, OrderShippingAddress, RelatedOrder
- `/Users/albertgwo/Work/evvy/backend/care/models.py` - Prescription, PrescriptionFill, PrescriptionFillPrescriptions, PrescriptionFillOrder, Product, OTCTreatment

## Summary
The relationship between these three models forms a prescription fulfillment system:
- **Order** represents the e-commerce purchase transaction
- **Prescription** represents the clinical prescription from a provider
- **PrescriptionFill** bridges them, representing the actual fulfillment/shipment event

The many-to-many relationship between PrescriptionFill and Prescription allows for:
- Bundle orders (multiple prescriptions in one fill)
- Partial fills (fill_quantity tracking)
- Refill tracking (fill_count property)
- Complete audit trail via through tables
