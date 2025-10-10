# Cards Module

A comprehensive virtual and physical card management system for the PayCore API.

## Features

- **Multi-Provider Support**: Flutterwave, Sudo Africa, with easy extension for Stripe, Paystack
- **Multi-Currency Cards**: USD, NGN, GBP (provider-dependent)
- **Card Types**: Virtual and physical cards
- **Card Brands**: Visa, Mastercard, Verve
- **PalmPay-style Funding**: Money stays in wallet, card is spending instrument
- **Advanced Controls**: Spending limits, daily/monthly limits, transaction controls
- **Real-time Webhooks**: Transaction notifications from providers
- **Security**: Webhook signature verification, encrypted card details
- **Card Lifecycle**: Inactive → Active → Frozen/Blocked states

## Architecture

### Provider Abstraction Pattern

The module uses the **Factory Design Pattern** for provider abstraction:

```
BaseCardProvider (Abstract)
├── FlutterwaveCardProvider
├── SudoCardProvider
└── Future: StripeCardProvider, PaystackCardProvider
```

**Benefits**:
- Single Responsibility: Each provider handles only its integration
- Open/Closed: Open for extension, closed for modification
- Liskov Substitution: All providers are interchangeable
- Dependency Inversion: Code depends on abstraction, not concrete implementations

### File Structure

```
apps/cards/
├── models.py                      # Card model with provider fields
├── schemas.py                     # Pydantic request/response schemas
├── views.py                       # 13 API endpoints
├── webhooks.py                    # Webhook handlers for providers
├── services/
│   ├── card_manager.py           # Card lifecycle management
│   ├── card_operations.py        # Card operations (funding, transactions)
│   └── providers/
│       ├── base.py               # Abstract base provider
│       ├── factory.py            # Provider selection factory
│       ├── flutterwave.py        # Flutterwave integration
│       └── sudo.py               # Sudo Africa integration
└── README.md                      # This file
```

## Models

### Card Model

```python
class Card(BaseModel):
    # Relationships
    wallet = ForeignKey(Wallet)  # Card linked to wallet
    user = ForeignKey(User)

    # Card Identity
    card_id = UUIDField(unique=True)
    card_type = CharField(choices=CardType)  # virtual, physical
    card_brand = CharField(choices=CardBrand)  # visa, mastercard, verve
    card_number = CharField(unique=True)
    card_holder_name = CharField()
    expiry_month = PositiveIntegerField()
    expiry_year = PositiveIntegerField()
    cvv = CharField()  # Encrypted

    # Provider Integration
    card_provider = CharField(choices=CardProvider)  # flutterwave, sudo, etc.
    provider_card_id = CharField()  # Provider's internal ID
    provider_metadata = JSONField()
    is_test_mode = BooleanField()

    # Spending Limits
    spending_limit = DecimalField()  # Per-transaction limit
    daily_limit = DecimalField()
    monthly_limit = DecimalField()

    # Status and Security
    status = CharField(choices=CardStatus)  # inactive, active, frozen, blocked
    is_frozen = BooleanField()

    # Transaction Controls
    allow_online_transactions = BooleanField()
    allow_atm_withdrawals = BooleanField()
    allow_international_transactions = BooleanField()

    # Metadata
    nickname = CharField()
    created_for_merchant = CharField()
    billing_address = JSONField()
```

### Transaction Integration

Card transactions are recorded in the unified `Transaction` model with these additional fields:

```python
# Card-specific fields
card = ForeignKey(Card, null=True)
merchant_name = CharField()
merchant_category = CharField()
transaction_location = JSONField()

# Card transaction types
CARD_PURCHASE = "card_purchase"
CARD_WITHDRAWAL = "card_withdrawal"
CARD_REFUND = "card_refund"
CARD_REVERSAL = "card_reversal"
CARD_FUND = "card_fund"
```

## API Endpoints

### Card Management

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/cards/create` | Create new card | Required |
| GET | `/api/v1/cards/list` | List user cards | Required |
| GET | `/api/v1/cards/{card_id}` | Get card details | Required |
| PATCH | `/api/v1/cards/{card_id}` | Update card | Required |
| DELETE | `/api/v1/cards/{card_id}` | Delete card | Required |

### Card Operations

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/cards/{card_id}/fund` | Fund card (PalmPay-style) | Required |
| POST | `/api/v1/cards/{card_id}/freeze` | Freeze card | Required |
| POST | `/api/v1/cards/{card_id}/unfreeze` | Unfreeze card | Required |
| POST | `/api/v1/cards/{card_id}/block` | Block card permanently | Required |
| POST | `/api/v1/cards/{card_id}/activate` | Activate card | Required |
| PATCH | `/api/v1/cards/{card_id}/controls` | Update card controls | Required |
| GET | `/api/v1/cards/{card_id}/transactions` | Get transaction history | Required |

### Webhooks

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/cards/webhooks/flutterwave` | Flutterwave webhook | None |
| POST | `/api/v1/cards/webhooks/sudo` | Sudo webhook | None |

## Card Providers

### Flutterwave

**Supported Features**:
- Virtual cards: USD, NGN, GBP
- Card freeze/unfreeze
- Card termination
- Webhook notifications

**API Documentation**: https://developer.flutterwave.com/docs/issuing-cards

**Settings**:
```python
FLUTTERWAVE_TEST_SECRET_KEY = "FLWSECK_TEST-xxx"
FLUTTERWAVE_LIVE_SECRET_KEY = "FLWSECK-xxx"
FLUTTERWAVE_WEBHOOK_SECRET = "xxx"
```

### Sudo Africa

**Supported Features**:
- Virtual cards: USD, NGN
- Card freeze/unfreeze
- Card termination
- Webhook notifications

**API Documentation**: https://docs.sudo.africa/reference/cards

**Settings**:
```python
SUDO_TEST_SECRET_KEY = "eyJxxx"
SUDO_LIVE_SECRET_KEY = "eyJxxx"
SUDO_WEBHOOK_SECRET = "xxx"
```

### Provider Selection

The factory automatically selects the appropriate provider based on currency:

```python
CURRENCY_PROVIDER_MAP = {
    "USD": CardProvider.FLUTTERWAVE,  # Flutterwave for USD
    "NGN": CardProvider.FLUTTERWAVE,  # Flutterwave for NGN
    "GBP": CardProvider.FLUTTERWAVE,  # Flutterwave for GBP
}
```

If Flutterwave is not configured, the factory automatically falls back to Sudo for USD/NGN.

## Usage Examples

### 1. Create a Card

```python
POST /api/v1/cards/create
{
    "wallet_id": "uuid",
    "card_type": "virtual",
    "card_brand": "visa",
    "currency_code": "USD",
    "nickname": "Netflix Card",
    "spending_limit": 500.00,
    "daily_limit": 1000.00,
    "monthly_limit": 5000.00,
    "billing_address": {
        "street": "123 Main St",
        "city": "New York",
        "state": "NY",
        "country": "US",
        "postal_code": "10001"
    }
}
```

**Response**:
```json
{
    "status": "success",
    "message": "Card created successfully",
    "data": {
        "card_id": "uuid",
        "card_type": "virtual",
        "card_brand": "visa",
        "card_number": "4111111111111234",
        "card_holder_name": "JOHN DOE",
        "masked_number": "**** **** **** 1234",
        "expiry_month": 12,
        "expiry_year": 2029,
        "cvv": "123",
        "status": "inactive",
        "currency": {
            "code": "USD",
            "symbol": "$"
        },
        "provider": "flutterwave",
        "is_test_mode": true
    }
}
```

### 2. Activate Card

```python
POST /api/v1/cards/{card_id}/activate
```

### 3. Fund Card (PalmPay-style)

```python
POST /api/v1/cards/{card_id}/fund
{
    "amount": 1000.00,
    "pin": "1234"
}
```

**Note**: This doesn't transfer money. It's for authorization tracking only. Money stays in wallet.

### 4. Freeze Card

```python
POST /api/v1/cards/{card_id}/freeze
```

### 5. Update Card Controls

```python
PATCH /api/v1/cards/{card_id}/controls
{
    "allow_online_transactions": true,
    "allow_atm_withdrawals": false,
    "allow_international_transactions": true
}
```

## Card Funding Model

**PalmPay-style Funding** (Default):

- Money stays in wallet
- Card is just a spending instrument
- Card purchases debit wallet directly
- No actual balance transfer occurs
- Funding transaction is for record-keeping and authorization only

**Flow**:
1. User creates card linked to USD wallet
2. User "funds" card with $1000 (authorization only)
3. User makes $50 purchase at merchant
4. Webhook received: `card.transaction` event
5. $50 deducted from wallet, not from card
6. Transaction recorded with merchant details

**Benefits**:
- Simpler balance management
- Single source of truth (wallet balance)
- No reconciliation needed
- Matches PalmPay's model

## Webhook Processing

### Flutterwave Webhook

**Signature Verification**:
- Header: `verif-hash`
- Method: Compare with configured secret hash

**Events**:
- `card.transaction`: Card purchase/withdrawal
- `card.created`: Card was created
- `card.frozen`: Card was frozen
- `card.blocked`: Card was blocked

### Sudo Webhook

**Signature Verification**:
- Header: `X-Sudo-Signature`
- Method: HMAC SHA256

**Events**:
- `card.transaction`: Card purchase/withdrawal
- `card.created`: Card was created
- `card.frozen`: Card was frozen
- `card.unfrozen`: Card was unfrozen

### Webhook Flow

1. Provider sends webhook to `/api/v1/cards/webhooks/{provider}`
2. Signature verified using provider's webhook secret
3. Event parsed into standardized format
4. Card transaction recorded in database
5. Wallet balance updated
6. Card spending limits updated
7. HTTP 200 returned to provider

## Security Features

1. **Webhook Signature Verification**: All webhooks verified before processing
2. **Encrypted Card Details**: CVV and card number encrypted at rest
3. **PIN Verification**: Required for sensitive operations
4. **Spending Limits**: Per-transaction, daily, and monthly limits
5. **Transaction Controls**: Online, ATM, international toggles
6. **Card Freeze**: Temporary block without termination
7. **Audit Trail**: All card operations logged in Transaction model

## Testing

### Test Mode

Set `CARD_PROVIDERS_TEST_MODE=True` in settings to use sandbox credentials.

### Test Cards

**Flutterwave Test Cards**:
- Follow: https://developer.flutterwave.com/docs/test-cards

**Sudo Test Cards**:
- Cards created in sandbox automatically work
- Follow: https://docs.sudo.africa/reference/testing

## Environment Variables

Add to your `.env` file:

```bash
# Card Provider Settings
CARD_PROVIDERS_TEST_MODE=True

# Flutterwave
FLUTTERWAVE_TEST_SECRET_KEY=FLWSECK_TEST-xxx
FLUTTERWAVE_LIVE_SECRET_KEY=FLWSECK-xxx
FLUTTERWAVE_WEBHOOK_SECRET=xxx

# Sudo Africa
SUDO_TEST_SECRET_KEY=eyJxxx
SUDO_LIVE_SECRET_KEY=eyJxxx
SUDO_WEBHOOK_SECRET=xxx
```

## Future Enhancements

1. **Additional Providers**:
   - Stripe Issuing
   - Paystack Virtual Cards
   - Adyen Card Issuing

2. **Physical Cards**:
   - Shipping address management
   - Card delivery tracking
   - PIN management

3. **Enhanced Security**:
   - 3DS authentication
   - Biometric verification
   - Device fingerprinting

4. **Advanced Features**:
   - Recurring card payments
   - Card-to-card transfers
   - Cashback rewards
   - Card statement generation

## Support

For issues or questions about the cards module, contact the development team or open an issue in the project repository.
