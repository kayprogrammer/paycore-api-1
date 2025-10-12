# Payments Module Documentation

## Overview

The Payments module provides merchant payment features for the Paycore API, enabling users to create payment links, invoices, and accept payments from customers. This is separate from the P2P wallet-to-wallet transfers handled by the Wallets module.

## Features

### 1. Payment Links
- **Shareable URLs** for collecting payments without integration
- **Fixed or flexible amounts** with min/max ranges
- **Single-use or multi-use** links
- **Expiration dates** for time-limited payments
- **Custom branding** (logo, brand colors)
- **Redirect URLs** after successful payment
- **Analytics** (views, payments count, total collected)

### 2. Invoices
- **Professional invoicing** with line items
- **Customer information** tracking
- **Tax and discount** calculations
- **Due dates and overdue** tracking
- **Partial payments** support
- **Status management** (draft, sent, paid, overdue, cancelled)

### 3. Payments
- **Transaction processing** with fee calculation (1.5% capped at 1000)
- **Wallet debits/credits** with atomic transactions
- **Payment references** for tracking
- **Payment history** for merchants
- **Integration** with Transaction model

### 4. API Keys (Future)
- **Programmatic access** for merchant integrations
- **Test/Live modes** for different environments
- **Permission control** (create links, invoices, view payments)

## Architecture

### Models

#### PaymentLink
- `link_id` (UUID) - Unique identifier
- `user` (FK) - Owner/merchant
- `wallet` (FK) - Wallet to receive payments
- `title`, `description` - Link details
- `slug` (unique) - URL slug for public access
- `amount`, `is_amount_fixed`, `min_amount`, `max_amount` - Payment configuration
- `status` - active, inactive, expired, completed
- `is_single_use`, `expires_at` - Usage settings
- `logo_url`, `brand_color` - Branding
- `views_count`, `payments_count`, `total_collected` - Analytics

#### Invoice
- `invoice_id` (UUID), `invoice_number` (unique) - Identifiers
- `user` (FK), `wallet` (FK) - Owner details
- `customer_name`, `customer_email`, `customer_phone`, `customer_address` - Customer info
- `title`, `description`, `notes` - Invoice details
- `subtotal`, `tax_amount`, `discount_amount`, `total_amount` - Financial details
- `amount_paid`, `amount_due` - Payment tracking
- `status` - draft, sent, paid, partially_paid, overdue, cancelled
- `issue_date`, `due_date`, `paid_at` - Dates

#### InvoiceItem
- `item_id` (UUID) - Identifier
- `invoice` (FK) - Parent invoice
- `description`, `quantity`, `unit_price`, `amount` - Line item details

#### Payment
- `payment_id` (UUID) - Identifier
- `payment_link` (FK), `invoice` (FK) - Source
- `transaction` (OneToOne FK) - Related transaction
- `payer_name`, `payer_email`, `payer_phone`, `payer_wallet` - Payer details
- `merchant_user`, `merchant_wallet` - Merchant details
- `amount`, `fee_amount`, `net_amount` - Payment amounts
- `status` - pending, processing, completed, failed, refunded
- `reference`, `external_reference` - Tracking

#### MerchantAPIKey
- `key_id` (UUID), `key`, `prefix` - API key details
- `user` (FK) - Owner
- `name` - Descriptive name
- `is_active`, `is_test_mode` - Settings
- `can_create_links`, `can_create_invoices`, `can_view_payments` - Permissions
- `requests_count`, `last_used_at` - Usage stats

### Services

#### PaymentLinkManager
- `create_payment_link(user, data)` - Create new payment link
- `get_payment_link(user, link_id)` - Get link by ID (owner only)
- `get_payment_link_by_slug(slug)` - Get link by slug (public, increments views)
- `list_payment_links(user, status, limit, offset)` - List user's links
- `update_payment_link(user, link_id, data)` - Update link
- `delete_payment_link(user, link_id)` - Soft delete (set inactive)
- `validate_payment_link(link)` - Validate if link can accept payments

#### InvoiceManager
- `create_invoice(user, data)` - Create invoice with line items
- `get_invoice(user, invoice_id)` - Get invoice by ID
- `get_invoice_by_number(invoice_number)` - Get by number (public)
- `list_invoices(user, status, limit, offset)` - List user's invoices
- `update_invoice(user, invoice_id, data)` - Update invoice
- `delete_invoice(user, invoice_id)` - Cancel invoice
- `mark_invoice_paid(invoice, amount)` - Update invoice payment status

#### PaymentProcessor
- `calculate_fee(amount)` - Calculate 1.5% fee (capped at 1000)
- `process_payment_link_payment(link_slug, data)` - Process payment via link
- `process_invoice_payment(invoice_number, data)` - Process invoice payment

### API Endpoints

#### Payment Links (Authenticated)
- `POST /api/v1/payments/links/create` - Create payment link
- `GET /api/v1/payments/links/list` - List payment links
- `GET /api/v1/payments/links/{link_id}` - Get payment link details
- `PUT /api/v1/payments/links/{link_id}` - Update payment link
- `DELETE /api/v1/payments/links/{link_id}` - Delete payment link

#### Payment Links (Public)
- `GET /api/v1/payments/pay/{slug}` - Get payment link by slug
- `POST /api/v1/payments/pay/{slug}` - Make payment via link

#### Invoices (Authenticated)
- `POST /api/v1/payments/invoices/create` - Create invoice
- `GET /api/v1/payments/invoices/list` - List invoices
- `GET /api/v1/payments/invoices/{invoice_id}` - Get invoice details
- `PUT /api/v1/payments/invoices/{invoice_id}` - Update invoice
- `DELETE /api/v1/payments/invoices/{invoice_id}` - Delete invoice

#### Invoices (Public)
- `GET /api/v1/payments/invoice/{invoice_number}` - Get invoice by number
- `POST /api/v1/payments/invoice/{invoice_number}/pay` - Pay invoice

#### Payment History (Authenticated)
- `GET /api/v1/payments/payments/list` - List merchant payments
- `GET /api/v1/payments/payments/{payment_id}` - Get payment details

## Payment Flow

### Payment Link Flow
1. Merchant creates payment link with wallet_id, title, amount settings
2. System generates unique slug and link_id
3. Merchant shares link URL: `/pay/{slug}`
4. Customer visits link (views_count incremented)
5. Customer provides payment details (wallet_id, amount if flexible, payer info)
6. System validates:
   - Link is active and not expired
   - Amount matches requirements
   - Payer wallet has sufficient balance
   - Currency matches
7. System processes payment:
   - Calculates fee (1.5% capped at 1000)
   - Debits payer wallet (total amount)
   - Credits merchant wallet (net amount = amount - fee)
   - Creates Transaction record
   - Creates Payment record
   - Updates link statistics
8. Customer receives payment confirmation

### Invoice Flow
1. Merchant creates invoice with line items, customer details
2. System generates unique invoice_number
3. Merchant sends invoice to customer
4. Customer visits invoice page
5. Customer pays (full or partial)
6. System processes payment (same as payment link)
7. Invoice status updated (partially_paid or paid)
8. Customer receives payment confirmation

## Fee Structure

- **Payment Fee**: 1.5% of transaction amount
- **Fee Cap**: Maximum 1000 (in wallet currency)
- **Calculation**: `min(amount * 0.015, 1000)`
- **Net Amount**: `amount - fee_amount` (credited to merchant)
- **Total Amount**: `amount` (debited from payer)

## Error Codes

- `PAYMENT_LINK_EXPIRED` - Payment link has expired
- `PAYMENT_LINK_INACTIVE` - Payment link is not active
- `PAYMENT_ALREADY_PAID` - Payment has already been processed
- `INVOICE_ALREADY_PAID` - Invoice has been fully paid
- `INVOICE_EXPIRED` - Invoice is past due date
- `INSUFFICIENT_BALANCE` - Payer wallet has insufficient funds
- `INVALID_API_KEY` - API key is invalid
- `API_KEY_INACTIVE` - API key is not active

## Best Practices

### Payment Links
- Use descriptive titles that clearly indicate what the payment is for
- Set appropriate min/max amounts for flexible links
- Set expiration dates for time-sensitive payments
- Use single-use links for one-time payments (invoices, orders)
- Monitor views_count to track link engagement

### Invoices
- Always include detailed line items for clarity
- Set realistic due dates
- Use status field to track invoice lifecycle
- Send reminders for overdue invoices
- Support partial payments for large invoices

### Security
- Always validate payment amounts before processing
- Use atomic transactions to prevent race conditions
- Check wallet balances before debiting
- Verify currency matches between wallets
- Generate cryptographically secure references

### Performance
- Use `select_related()` for foreign keys to reduce queries
- Paginate lists with limit/offset
- Use database indexes on frequently queried fields (slug, invoice_number, reference)
- Cache payment link data for public pages

## Database Schema

```sql
-- Payment Links
CREATE TABLE payment_links (
    id BIGSERIAL PRIMARY KEY,
    link_id UUID UNIQUE NOT NULL,
    user_id BIGINT REFERENCES users(id),
    wallet_id BIGINT REFERENCES wallets(id),
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    amount DECIMAL(20,2),
    is_amount_fixed BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'active',
    -- ... more fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Invoices
CREATE TABLE invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID UNIQUE NOT NULL,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    user_id BIGINT REFERENCES users(id),
    wallet_id BIGINT REFERENCES wallets(id),
    customer_name VARCHAR(200) NOT NULL,
    total_amount DECIMAL(20,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    -- ... more fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Payments
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    payment_id UUID UNIQUE NOT NULL,
    payment_link_id BIGINT REFERENCES payment_links(id),
    invoice_id BIGINT REFERENCES invoices(id),
    transaction_id BIGINT UNIQUE REFERENCES transactions(id),
    merchant_user_id BIGINT REFERENCES users(id),
    merchant_wallet_id BIGINT REFERENCES wallets(id),
    amount DECIMAL(20,2) NOT NULL,
    fee_amount DECIMAL(20,2) DEFAULT 0,
    net_amount DECIMAL(20,2) NOT NULL,
    reference VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Example Usage

### Create Payment Link

```python
# Request
POST /api/v1/payments/links/create
{
    "wallet_id": "123e4567-e89b-12d3-a456-426614174000",
    "title": "Product Purchase",
    "slug": "buy-product-123",
    "amount": "100.00",
    "is_amount_fixed": true,
    "brand_color": "#3B82F6"
}

# Response
{
    "status": "success",
    "message": "Payment link created successfully",
    "data": {
        "link_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
        "title": "Product Purchase",
        "slug": "buy-product-123",
        "amount": "100.00",
        "currency": {"code": "USD", "symbol": "$"},
        "is_active": true,
        "created_at": "2025-01-15T10:30:00Z"
    }
}
```

### Pay via Link

```python
# Request
POST /api/v1/payments/pay/buy-product-123
{
    "wallet_id": "456e7890-e12b-34d5-a678-901234567890",
    "payer_name": "John Doe",
    "payer_email": "john@example.com"
}

# Response
{
    "status": "success",
    "message": "Payment completed successfully",
    "data": {
        "payment_id": "abc12345-6789-0def-1234-567890abcdef",
        "reference": "PAY-1705315800-987fcdeb",
        "amount": "100.00",
        "fee_amount": "1.50",
        "net_amount": "98.50",
        "status": "completed",
        "created_at": "2025-01-15T10:30:00Z"
    }
}
```

## Future Enhancements

1. **Webhooks** - Notify merchants of payment events
2. **Refunds** - Process payment refunds
3. **Recurring Payments** - Subscription-based payments
4. **Payment Methods** - Support cards, bank transfers
5. **Multi-Currency** - Cross-currency payments
6. **Analytics Dashboard** - Detailed payment analytics
7. **Export** - Export invoices/payments to PDF/CSV
8. **Templates** - Invoice templates for branding

## Testing

Run tests with:
```bash
python manage.py test apps.payments
```

## Admin Interface

All models are registered in Django Admin with custom list displays, filters, and search fields:
- Payment Links - View, search, filter by status
- Invoices - Track customer invoices, overdue alerts
- Payments - Monitor all payment transactions
- API Keys - Manage merchant API access
