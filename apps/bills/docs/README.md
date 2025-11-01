# Bills Payment Module

A comprehensive bill payment system for the PayCore API supporting multiple payment categories and providers.

## Features

- **Multiple Bill Categories**: Airtime, Data, Electricity, Cable TV, Internet, Water, Education, and more
- **Multiple Providers**: Flutterwave, Paystack, VTPass, Baxi (extensible)
- **Customer Validation**: Verify customer details before payment
- **Predefined Packages**: Data bundles, cable TV plans with preset amounts
- **Flexible Amounts**: Support for custom amounts (electricity, airtime, etc.)
- **Beneficiary Management**: Save frequently used billers for quick payments
- **Recurring Payments**: Schedule automatic bill payments
- **Transaction Tracking**: Full integration with transaction system
- **Fee Management**: Transparent fee calculation and disclosure

## Architecture

### Provider Abstraction Pattern

The module uses the **Factory Design Pattern** for payment gateway abstraction:

```
BaseBillPaymentProvider (Abstract)
├── FlutterwaveBillProvider
├── PaystackBillProvider (Future)
├── VTPassProvider (Future)
└── BaxiProvider (Future)
```

**Benefits**:
- Single Responsibility: Each provider handles only its integration
- Open/Closed: Open for extension, closed for modification
- Liskov Substitution: All providers are interchangeable
- Dependency Inversion: Code depends on abstraction, not concrete implementations

### File Structure

```
apps/bills/
├── models.py                      # Bill models (Provider, Package, Payment, etc.)
├── schemas.py                     # Pydantic request/response schemas
├── views.py                       # API endpoints
├── services/
│   ├── bill_manager.py           # Bill payment business logic
│   └── providers/
│       ├── base.py               # Abstract base provider
│       ├── flutterwave.py        # Flutterwave integration
│       └── paystack.py           # Paystack integration (Future)
└── docs/
    └── README.md                 # This file
```

## Models

### 1. BillProvider

Represents bill payment service providers (MTN, EKEDC, DSTV, etc.).

```python
class BillProvider(BaseModel):
    name: str  # "MTN Airtime", "EKEDC Prepaid"
    slug: str  # "mtn-airtime", "ekedc-prepaid"
    category: str  # airtime, data, electricity, etc.
    provider_code: str  # Code used by payment gateway

    # Pricing
    supports_amount_range: bool  # Can user enter custom amount?
    min_amount: Decimal
    max_amount: Decimal

    # Fees
    fee_type: str  # flat, percentage, none
    fee_amount: Decimal
    fee_cap: Decimal  # Maximum fee

    # Validation
    requires_customer_validation: bool
    validation_fields: JSONField
```

### 2. BillPackage

Predefined packages (data bundles, cable TV plans).

```python
class BillPackage(BaseModel):
    provider: ForeignKey(BillProvider)
    name: str  # "10GB Monthly Plan", "DSTV Premium"
    code: str  # Package code from provider
    amount: Decimal
    validity_period: str  # "30 days", "1 month"
    benefits: List[str]  # Package features
    is_popular: bool  # Highlight popular packages
```

### 3. BillPayment

Bill payment transactions.

```python
class BillPayment(BaseModel):
    user: ForeignKey(User)
    wallet: ForeignKey(Wallet)
    transaction: ForeignKey(Transaction)
    provider: ForeignKey(BillProvider)
    package: ForeignKey(BillPackage, optional)

    # Payment Details
    amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal

    # Customer Details
    customer_id: str  # Meter number, phone, smartcard
    customer_name: str
    customer_email: str
    customer_phone: str

    # Status
    status: str  # pending, processing, completed, failed

    # Provider Response
    provider_reference: str
    token: str  # For electricity, etc.
    token_units: str  # kWh, GB, etc.
```

### 4. BillBeneficiary

Saved beneficiaries for quick payments.

```python
class BillBeneficiary(BaseModel):
    user: ForeignKey(User)
    provider: ForeignKey(BillProvider)
    nickname: str  # "Home Electricity", "Mom's Phone"
    customer_id: str
    customer_name: str
    usage_count: int
    last_used_at: datetime
```

### 5. BillPaymentSchedule

Recurring/scheduled bill payments.

```python
class BillPaymentSchedule(BaseModel):
    user: ForeignKey(User)
    provider: ForeignKey(BillProvider)
    wallet: ForeignKey(Wallet)
    customer_id: str
    amount: Decimal
    frequency: str  # daily, weekly, monthly, quarterly
    next_payment_date: date
    is_active: bool
    is_paused: bool
```

## API Endpoints

### Bill Providers & Packages

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/bills/providers` | List bill providers | Required |
| GET | `/api/v1/bills/providers/{id}` | Get provider details | Required |
| GET | `/api/v1/bills/providers/{id}/packages` | List provider packages | Required |

### Customer Validation

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/bills/validate-customer` | Validate customer details | Required |

### Bill Payments

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/bills/pay` | Process bill payment | Required |
| GET | `/api/v1/bills/payments` | List user's bill payments | Required |
| GET | `/api/v1/bills/payments/{id}` | Get payment details | Required |

## Usage Examples

### 1. List Bill Providers

```http
GET /api/v1/bills/providers?category=airtime
Authorization: Bearer {token}
```

**Response**:
```json
[
  {
    "provider_id": "uuid",
    "name": "MTN Airtime",
    "slug": "mtn-airtime",
    "category": "airtime",
    "supports_amount_range": true,
    "min_amount": 50.00,
    "max_amount": 50000.00,
    "fee_type": "flat",
    "fee_amount": 20.00,
    "logo_url": "https://...",
    "is_available": true
  }
]
```

### 2. Validate Customer

```http
POST /api/v1/bills/validate-customer
Authorization: Bearer {token}
Content-Type: application/json

{
  "provider_id": "uuid",
  "customer_id": "08012345678"
}
```

**Response**:
```json
{
  "is_valid": true,
  "customer_name": "John Doe",
  "customer_id": "08012345678",
  "customer_type": "prepaid",
  "address": "123 Main St, Lagos",
  "balance": "0.00",
  "extra_info": {
    "minimum_amount": 50.00,
    "maximum_amount": 50000.00
  }
}
```

### 3. Buy Airtime

```http
POST /api/v1/bills/pay
Authorization: Bearer {token}
Content-Type: application/json

{
  "wallet_id": "uuid",
  "provider_id": "uuid",
  "customer_id": "08012345678",
  "amount": 1000.00,
  "customer_phone": "08012345678",
  "save_beneficiary": true,
  "beneficiary_nickname": "My Number"
}
```

**Response**:
```json
{
  "payment_id": "uuid",
  "provider": {
    "name": "MTN Airtime",
    "category": "airtime"
  },
  "amount": 1000.00,
  "fee_amount": 20.00,
  "total_amount": 1020.00,
  "customer_id": "08012345678",
  "customer_name": "John Doe",
  "status": "completed",
  "provider_reference": "FLW-12345",
  "created_at": "2025-10-10T10:30:00Z",
  "completed_at": "2025-10-10T10:30:05Z"
}
```

### 4. Buy Data Bundle (Package)

```http
POST /api/v1/bills/pay
Authorization: Bearer {token}
Content-Type: application/json

{
  "wallet_id": "uuid",
  "provider_id": "uuid",
  "customer_id": "08012345678",
  "package_id": "uuid"
}
```

### 5. Pay Electricity Bill

```http
POST /api/v1/bills/pay
Authorization: Bearer {token}
Content-Type: application/json

{
  "wallet_id": "uuid",
  "provider_id": "uuid",
  "customer_id": "1234567890",
  "amount": 5000.00,
  "customer_email": "john@example.com"
}
```

**Response** (includes token):
```json
{
  "payment_id": "uuid",
  "provider": {
    "name": "EKEDC Prepaid",
    "category": "electricity"
  },
  "amount": 5000.00,
  "fee_amount": 50.00,
  "total_amount": 5050.00,
  "customer_id": "1234567890",
  "customer_name": "John Doe",
  "status": "completed",
  "token": "1234-5678-9012-3456-7890",
  "token_units": "45.5 kWh",
  "provider_reference": "FLW-67890"
}
```

## Bill Categories

### 1. Airtime Recharge
- **Providers**: MTN, Airtel, Glo, 9mobile
- **Amount**: Flexible (₦50 - ₦50,000)
- **Instant**: Yes
- **Validation**: Optional

### 2. Data Bundles
- **Providers**: MTN, Airtel, Glo, 9mobile
- **Amount**: Predefined packages
- **Instant**: Yes
- **Validation**: Optional

### 3. Electricity Bills
- **Providers**: EKEDC, IKEDC, AEDC, PHED, etc.
- **Types**: Prepaid, Postpaid
- **Amount**: Flexible
- **Returns**: Token for prepaid meters
- **Validation**: Required

### 4. Cable TV
- **Providers**: DSTV, GOtv, StarTimes
- **Amount**: Predefined packages
- **Subscription periods**: Monthly, quarterly, annual
- **Validation**: Required (smartcard number)

### 5. Internet Service
- **Providers**: Spectranet, Smile, Swift
- **Amount**: Predefined packages
- **Validation**: Required

### 6. Water Bills
- **Providers**: State water corporations
- **Amount**: Flexible
- **Validation**: Required

## Payment Flow

### Standard Payment Flow

```
1. User selects bill category (airtime, electricity, etc.)
   ↓
2. User selects provider (MTN, EKEDC, etc.)
   ↓
3. User enters customer ID (phone, meter number, etc.)
   ↓
4. System validates customer (if supported)
   ↓
5. User selects package or enters amount
   ↓
6. System calculates fees and shows total
   ↓
7. User confirms payment
   ↓
8. System debits wallet
   ↓
9. System processes payment with provider
   ↓
10. System returns result (with token if applicable)
    ↓
11. User receives confirmation
```

### With Beneficiary

```
1. User views saved beneficiaries
   ↓
2. User selects beneficiary
   ↓
3. System auto-fills customer details
   ↓
4. User enters amount/package
   ↓
5. Rest of flow continues...
```

## Provider Integration

### Flutterwave Bills

**Supported Services**:
- Airtime (all networks)
- Data bundles
- Electricity (30+ DISCOs)
- Cable TV (DSTV, GOtv, StarTimes)
- Internet services

**Documentation**: https://developer.flutterwave.com/docs/bills-payment

**Key Features**:
- Customer validation
- Instant processing
- Token generation for prepaid meters
- Transaction status query

### Adding New Providers

To add a new bill payment provider:

1. **Create Provider Class**:
```python
# apps/bills/services/providers/vtpass.py
from apps.bills.services.providers.base import BaseBillPaymentProvider

class VTPassProvider(BaseBillPaymentProvider):
    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)
        # Initialize with API credentials

    async def validate_customer(self, provider_code, customer_id, **kwargs):
        # Implement validation
        pass

    async def process_payment(self, provider_code, customer_id, amount, reference, **kwargs):
        # Implement payment processing
        pass

    # Implement other abstract methods...
```

2. **Update Factory** (if using factory pattern)
3. **Add Provider Settings** to Django settings
4. **Add Provider** to database

## Fee Structure

### Provider Fees

Different providers charge different fees:

**Flutterwave**:
- Airtime/Data: ₦20 flat fee
- Electricity: 1% (capped at ₦100)
- Cable TV: 1% (capped at ₦100)

### Platform Fees

Additional platform fees can be configured per provider or globally.

### Fee Disclosure

All fees are:
- Calculated before payment
- Displayed to user for approval
- Itemized in transaction record
- Included in total amount

## Recurring Payments

Schedule automatic bill payments:

```python
schedule = await BillPaymentSchedule.objects.acreate(
    user=user,
    provider=provider,
    wallet=wallet,
    customer_id="08012345678",
    amount=Decimal("1000.00"),
    frequency="monthly",
    next_payment_date=date.today() + timedelta(days=30),
)
```

**Features**:
- Multiple frequencies: Daily, weekly, monthly, quarterly
- Pause/resume schedules
- Automatic retry on failure
- Email notifications
- Usage statistics

## Error Handling

### Common Errors

1. **Invalid Customer**:
```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "Invalid meter number"
}
```

2. **Insufficient Balance**:
```json
{
  "status": "error",
  "code": "INSUFFICIENT_BALANCE",
  "message": "Insufficient balance. Required: ₦1,020, Available: ₦500"
}
```

3. **Provider Unavailable**:
```json
{
  "status": "error",
  "code": "EXTERNAL_SERVICE_ERROR",
  "message": "Service temporarily unavailable"
}
```

4. **Payment Failed**:
```json
{
  "status": "error",
  "code": "PAYMENT_FAILED",
  "message": "Payment processing failed"
}
```

## Security Features

1. **Transaction PIN**: Required for payments (configurable)
2. **Amount Limits**: Min/max amounts per provider
3. **Rate Limiting**: Prevent abuse
4. **Customer Validation**: Verify details before payment
5. **Idempotency**: Prevent duplicate payments
6. **Audit Trail**: Full transaction logging

## Testing

### Test Mode

Enable test mode in settings:
```python
BILL_PAYMENT_TEST_MODE = True
```

### Test Providers

In test mode:
- Use test API credentials
- Payments don't actually process
- Test customer IDs work
- Test data is returned

### Test Customer IDs

**Flutterwave Test**:
- Electricity: Use `1234567890` for any DISCO
- Airtime: Any valid phone format
- Cable TV: Use `1234567890` for any provider

## Environment Variables

Add to your `.env` file:

```bash
# Bill Payment Settings
BILL_PAYMENT_TEST_MODE=True

# Flutterwave (already configured for cards)
FLUTTERWAVE_TEST_SECRET_KEY=your_test_key
FLUTTERWAVE_LIVE_SECRET_KEY=your_live_key
```

## Database Setup

Run migrations to create bill payment tables:

```bash
python manage.py makemigrations bills
python manage.py migrate bills
```

## Seeding Providers

You'll need to seed bill providers into the database:

```python
# Create providers
BillProvider.objects.create(
    name="MTN Airtime",
    slug="mtn-airtime",
    category="airtime",
    provider_code="BIL099",  # Flutterwave code
    supports_amount_range=True,
    min_amount=50,
    max_amount=50000,
    fee_type="flat",
    fee_amount=20,
    is_active=True,
)
```

## Future Enhancements

1. **Additional Providers**:
   - Paystack Bills
   - VTPass
   - Baxi
   - Quickteller

2. **New Categories**:
   - Government services (FRSC, NIN)
   - Insurance premiums
   - Loan repayments

3. **Advanced Features**:
   - Bulk bill payments
   - Bill splitting
   - Payment reminders
   - Bill analytics dashboard
   - Auto-top up (when balance low)

4. **Integrations**:
   - USSD bill payment
   - WhatsApp bill payment
   - SMS notifications
   - Email receipts

## Support

For issues or questions about the bills module, contact the development team or open an issue in the project repository.
