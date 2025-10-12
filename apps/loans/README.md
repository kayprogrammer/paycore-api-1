# Loans Module Documentation

## Overview

The Loans module provides a comprehensive lending platform with credit scoring, loan applications, disbursements, and repayment management. This module enables users to apply for various loan products, manage repayments, and build their credit history.

## Features

### 1. Loan Products
- **Multiple loan types**: Personal, Business, Payday, Emergency, Education, Auto, Home
- **Flexible configuration**: Min/max amounts, interest rates, tenure options
- **Fee structures**: Processing fees, late payment fees, early repayment fees
- **Requirements**: Credit score thresholds, collateral, guarantor requirements
- **Repayment frequencies**: Daily, Weekly, Bi-weekly, Monthly, Quarterly

### 2. Credit Scoring System
- **FICO-style scoring** (300-850 range)
- **Component scores**:
  - Payment History (35% weight) - Most important factor
  - Credit Utilization (30% weight) - Active loans and defaults
  - Account Age (15% weight) - User account longevity
  - Loan History (20% weight) - Completed vs defaulted loans
- **Risk assessment**: Low, Medium, High, Very High
- **Score bands**: Excellent (750-850), Good (700-749), Fair (650-699), Poor (600-649), Very Poor (300-599)
- **Personalized recommendations** for score improvement

### 3. Loan Applications
- **Application workflow**: Pending → Under Review → Approved/Rejected → Disbursed → Active → Paid
- **Comprehensive data collection**:
  - Employment and income information
  - Collateral details (if required)
  - Guarantor information (if required)
- **Automatic credit scoring** on application
- **Eligibility validation**:
  - Minimum credit score check
  - Account age verification
  - Existing active loan check

### 4. Loan Disbursement
- **Automatic wallet credit** upon approval
- **Transaction tracking** with complete audit trail
- **Instant availability** of funds

### 5. Repayment Management
- **Automated repayment schedule** generation
- **Multiple repayment frequencies** support
- **Flexible repayments**:
  - Full installment payment
  - Partial payments
  - Early full repayment
- **Late payment tracking** with penalty fees
- **Automatic status updates** (Paid, Overdue, Partial)

### 6. Analytics & Reporting
- **Loan summary dashboard**
- **Repayment history tracking**
- **Overdue alerts**
- **Credit score evolution**

## Architecture

### Models

#### LoanProduct
Core loan product configuration defining lending terms and requirements.

```python
- product_id (UUID) - Unique identifier
- name, description, product_type - Product details
- min_amount, max_amount - Loan limits
- min_interest_rate, max_interest_rate - Interest rates (per annum)
- min_tenure_months, max_tenure_months - Loan duration options
- processing_fee_percentage, processing_fee_fixed - Fees
- late_payment_fee, early_repayment_fee_percentage - Penalty fees
- min_credit_score - Minimum credit score requirement
- requires_collateral, requires_guarantor - Requirements
- min_account_age_days - Account age requirement
- allowed_repayment_frequencies - List of allowed frequencies
- currency - Loan currency
- is_active - Availability status
```

#### LoanApplication
User loan application with all details and status tracking.

```python
- application_id (UUID) - Unique identifier
- user, loan_product, wallet - References
- requested_amount, approved_amount - Loan amounts
- interest_rate, tenure_months, repayment_frequency - Terms
- processing_fee, total_interest, total_repayable - Calculated amounts
- monthly_repayment - Monthly payment amount
- purpose, purpose_details - Application purpose
- employment_status, employer_name, monthly_income - Employment
- collateral_type, collateral_value, collateral_description - Collateral
- guarantor_name, guarantor_phone, guarantor_email - Guarantor
- credit_score, credit_score_band, risk_assessment - Credit info
- status - Application status
- reviewed_by, reviewed_at, rejection_reason - Review details
- disbursed_at, disbursement_transaction - Disbursement info
```

#### LoanRepaymentSchedule
Individual installment schedule for a loan.

```python
- schedule_id (UUID) - Unique identifier
- loan - Parent loan
- installment_number - Sequence number
- due_date - Payment due date
- principal_amount, interest_amount, total_amount - Breakdown
- amount_paid, outstanding_amount - Payment tracking
- status - Payment status (pending, paid, overdue, partial, missed)
- paid_at - Payment completion timestamp
- days_overdue, late_fee - Late payment tracking
```

#### LoanRepayment
Individual repayment transaction record.

```python
- repayment_id (UUID) - Unique identifier
- loan, schedule - References
- amount - Total payment amount
- principal_paid, interest_paid, late_fee_paid - Breakdown
- wallet, transaction - Payment source
- is_early_repayment, early_repayment_fee - Early repayment
- reference, external_reference - Payment tracking
- status, payment_method - Payment details
```

#### CreditScore
User credit score record with detailed breakdown.

```python
- score_id (UUID) - Unique identifier
- user - User reference
- score (300-850) - Overall credit score
- score_band - Score category
- payment_history_score, credit_utilization_score - Component scores
- account_age_score, loan_history_score - Component scores
- total_loans, active_loans, completed_loans, defaulted_loans - Metrics
- on_time_payments, late_payments, missed_payments - Payment history
- total_borrowed, total_repaid, current_debt - Financial metrics
- risk_level - Risk assessment
- account_age_days - Account age
- factors - Detailed scoring breakdown (JSON)
- recommendations - Score improvement tips (JSON)
```

### Services

#### CreditScoreService
Manages credit score calculation and tracking.

**Key Methods:**
- `calculate_credit_score(user)` - Calculate comprehensive credit score
- `get_latest_credit_score(user)` - Get user's most recent score
- `check_eligibility(user, min_score)` - Check if user meets requirement

**Credit Score Formula:**
```
Final Score =
  (Payment History Score × 35%) +
  (Credit Utilization Score × 30%) +
  (Account Age Score × 15%) +
  (Loan History Score × 20%)
```

**Scoring Factors:**
- **Payment History**: On-time payment ratio, late payment penalties (-50 each), missed payment penalties (-100 each)
- **Credit Utilization**: Number of active loans, defaulted loans (-150 each), debt-to-borrowing ratio
- **Account Age**: Days since account creation (newer accounts start at 300, increases over time)
- **Loan History**: Completion ratio, total loan count bonuses, default penalties (-200 each)

#### LoanManager
Manages loan product discovery, applications, and approval workflow.

**Key Methods:**
- `get_active_loan_products(currency, type)` - List available products
- `get_loan_product(product_id)` - Get product details
- `calculate_loan(product, amount, tenure, frequency)` - Calculate loan details
- `create_loan_application(user, data)` - Create application
- `get_loan_application(user, application_id)` - Get application details
- `list_loan_applications(user, status, limit, offset)` - List applications
- `approve_loan(reviewer, application_id, data)` - Approve application (admin)
- `reject_loan(reviewer, application_id, data)` - Reject application (admin)
- `cancel_loan_application(user, application_id)` - Cancel pending application
- `get_repayment_schedule(user, application_id)` - Get repayment schedule

**Loan Calculation:**
```
Interest Calculation: Simple Interest
Total Interest = (Principal × Annual Rate × Tenure in Years)
Total Repayable = Principal + Total Interest
Installment Amount = Total Repayable ÷ Number of Installments

Processing Fee = max(Amount × Fee %, Fixed Fee)
```

#### LoanProcessor
Processes loan disbursements and repayments.

**Key Methods:**
- `disburse_loan(application_id, admin_user)` - Disburse approved loan
- `make_repayment(user, application_id, data)` - Process repayment
- `get_loan_repayments(user, application_id, limit, offset)` - Get repayment history
- `get_loan_summary(user)` - Get user's loan summary
- `get_loan_details(user, application_id)` - Get comprehensive loan details

**Repayment Allocation:**
1. Late fees paid first
2. Remaining amount split proportionally between principal and interest
3. Schedule updated with payment tracking
4. Loan status updated when all schedules paid
5. Credit score recalculated on completion

### API Endpoints

#### Loan Products

##### List Loan Products
```
GET /api/v1/loans/products/list
Auth: Required
Query Params: currency_code, product_type
Response: List of active loan products
```

##### Get Loan Product
```
GET /api/v1/loans/products/{product_id}
Auth: Required
Response: Detailed product information
```

##### Calculate Loan
```
POST /api/v1/loans/calculate
Auth: Required
Body: product_id, amount, tenure_months, repayment_frequency
Response: Calculated loan details (interest, fees, installments)
```

#### Loan Applications

##### Create Loan Application
```
POST /api/v1/loans/applications/create
Auth: Required
Body: CreateLoanApplicationSchema
Response: Created application with status PENDING
```

##### List Loan Applications
```
GET /api/v1/loans/applications/list
Auth: Required
Query Params: status, limit, offset
Response: List of user's applications
```

##### Get Loan Application
```
GET /api/v1/loans/applications/{application_id}
Auth: Required
Response: Detailed application information
```

##### Cancel Loan Application
```
DELETE /api/v1/loans/applications/{application_id}
Auth: Required
Response: Success message
```

#### Repayment Schedule

##### Get Repayment Schedule
```
GET /api/v1/loans/applications/{application_id}/schedule
Auth: Required
Response: List of scheduled installments
```

#### Loan Repayment

##### Make Loan Repayment
```
POST /api/v1/loans/applications/{application_id}/repay
Auth: Required
Body: wallet_id, amount, schedule_id (optional), pin (optional), notes (optional)
Response: Repayment record with transaction details
```

##### Get Loan Repayments
```
GET /api/v1/loans/applications/{application_id}/repayments
Auth: Required
Query Params: limit, offset
Response: Repayment history
```

#### Credit Score

##### Get Credit Score
```
GET /api/v1/loans/credit-score
Auth: Required
Response: User's latest credit score with breakdown
```

##### Refresh Credit Score
```
POST /api/v1/loans/credit-score/refresh
Auth: Required
Response: Newly calculated credit score
```

#### Summary & Details

##### Get Loan Summary
```
GET /api/v1/loans/summary
Auth: Required
Response: User's loan summary dashboard
```

##### Get Loan Details
```
GET /api/v1/loans/applications/{application_id}/details
Auth: Required
Response: Comprehensive loan details (application + schedule + repayments)
```

## Loan Workflow

### Application Flow

1. **User browses loan products**
   ```
   GET /api/v1/loans/products/list?currency_code=USD
   ```

2. **User calculates loan before applying**
   ```
   POST /api/v1/loans/calculate
   {
     "product_id": "...",
     "amount": 5000,
     "tenure_months": 12,
     "repayment_frequency": "monthly"
   }
   ```

3. **User submits loan application**
   ```
   POST /api/v1/loans/applications/create
   {
     "loan_product_id": "...",
     "wallet_id": "...",
     "requested_amount": 5000,
     "tenure_months": 12,
     "repayment_frequency": "monthly",
     "purpose": "Business expansion",
     "employment_status": "Self-employed",
     "monthly_income": 10000
   }
   ```

4. **System validates application**
   - Checks credit score against minimum requirement
   - Validates account age
   - Checks for existing active loans
   - Validates collateral/guarantor if required
   - Creates application with PENDING status

5. **Admin reviews and approves** (via Django Admin or future admin API)
   - Application status → APPROVED
   - Repayment schedule generated automatically

6. **Loan disbursed**
   - Funds credited to user's wallet
   - Transaction record created
   - Application status → ACTIVE

### Repayment Flow

1. **User views repayment schedule**
   ```
   GET /api/v1/loans/applications/{application_id}/schedule
   ```

2. **User makes repayment**
   ```
   POST /api/v1/loans/applications/{application_id}/repay
   {
     "wallet_id": "...",
     "amount": 450.50,
     "notes": "Monthly payment"
   }
   ```

3. **System processes payment**
   - Validates wallet balance
   - Debits wallet
   - Creates transaction record
   - Updates repayment schedule
   - Updates loan status if fully paid
   - Recalculates credit score on completion

4. **User tracks progress**
   ```
   GET /api/v1/loans/summary
   GET /api/v1/loans/applications/{application_id}/details
   ```

## Credit Score Improvement

### How to Improve Your Score

1. **Make Payments On Time** (35% of score)
   - Never miss a payment due date
   - Set up payment reminders
   - Pay before due date when possible

2. **Manage Credit Utilization** (30% of score)
   - Avoid having too many active loans simultaneously
   - Never default on a loan
   - Pay off loans completely

3. **Build Account History** (15% of score)
   - Keep your account active over time
   - Score improves as account ages

4. **Complete Loans Successfully** (20% of score)
   - Finish loan repayments fully
   - Build a positive loan history
   - Avoid partial repayments

### Score Band Ranges

- **Excellent (750-850)**: Best rates, highest loan amounts, all products available
- **Good (700-749)**: Great rates, high loan amounts, most products available
- **Fair (650-699)**: Moderate rates, standard loan amounts, may require collateral/guarantor
- **Poor (600-649)**: Higher rates, lower loan amounts, likely requires collateral/guarantor
- **Very Poor (300-599)**: Limited products, highest rates, strict requirements

## Interest Calculation

### Simple Interest Formula
```
Annual Interest = Principal × Annual Rate
Total Interest = Annual Interest × (Tenure in Months ÷ 12)
Total Repayable = Principal + Total Interest
Monthly Payment = Total Repayable ÷ Tenure in Months
```

### Example Calculation
```
Loan Amount: $10,000
Interest Rate: 15% per annum
Tenure: 12 months

Annual Interest = 10,000 × 0.15 = $1,500
Total Interest = 1,500 × (12 ÷ 12) = $1,500
Total Repayable = 10,000 + 1,500 = $11,500
Monthly Payment = 11,500 ÷ 12 = $958.33

Processing Fee (2%): 10,000 × 0.02 = $200 (deducted at disbursement)
Net Disbursement: 10,000 - 200 = $9,800
```

## Fee Structure

### Processing Fees
- **Calculation**: `max(Amount × Fee %, Fixed Fee)`
- **Deduction**: At loan disbursement
- **Range**: Typically 1-5% or fixed amount

### Late Payment Fees
- **Applied**: When payment overdue
- **Amount**: Fixed per product (e.g., $25)
- **Accumulation**: Per installment

### Early Repayment Fees
- **Applied**: On full early repayment
- **Calculation**: Outstanding Balance × Fee %
- **Range**: Typically 0-3%

## Error Codes

- `LOAN_PRODUCT_INACTIVE` - Product no longer available
- `LOAN_AMOUNT_BELOW_MIN` - Amount below minimum
- `LOAN_AMOUNT_ABOVE_MAX` - Amount exceeds maximum
- `LOAN_TENURE_INVALID` - Tenure outside allowed range
- `LOAN_ALREADY_ACTIVE` - User has existing active loan
- `LOAN_NOT_APPROVED` - Loan not yet approved
- `LOAN_ALREADY_DISBURSED` - Loan already disbursed
- `LOAN_NOT_ACTIVE` - Loan not in active status
- `LOAN_ALREADY_PAID` - All installments paid
- `CREDIT_SCORE_TOO_LOW` - Score below requirement
- `ACCOUNT_AGE_INSUFFICIENT` - Account too new
- `COLLATERAL_REQUIRED` - Product requires collateral
- `GUARANTOR_REQUIRED` - Product requires guarantor
- `REPAYMENT_SCHEDULE_NOT_FOUND` - Schedule not found
- `REPAYMENT_AMOUNT_INVALID` - Invalid payment amount
- `INSUFFICIENT_BALANCE` - Wallet balance too low

## Best Practices

### For Users
1. **Check eligibility** before applying (credit score, account age)
2. **Calculate loan terms** before submitting application
3. **Provide accurate information** for faster approval
4. **Set up payment reminders** to avoid late fees
5. **Make extra payments** when possible to reduce interest
6. **Monitor credit score** regularly

### For Developers
1. **Use atomic transactions** for disbursements and repayments
2. **Validate all inputs** thoroughly
3. **Check wallet balance** before debiting
4. **Generate unique references** for all transactions
5. **Update credit scores** after loan completion
6. **Handle partial payments** correctly
7. **Calculate late fees** accurately

### For Administrators
1. **Review applications** promptly
2. **Verify employment** and income claims
3. **Assess collateral value** properly
4. **Contact guarantors** when provided
5. **Monitor overdue loans** actively
6. **Adjust loan products** based on performance
7. **Set appropriate** interest rates by risk level

## Database Schema

```sql
-- Loan Products
CREATE TABLE loan_products (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    product_type VARCHAR(20) NOT NULL,
    min_amount DECIMAL(20,2) NOT NULL,
    max_amount DECIMAL(20,2) NOT NULL,
    min_interest_rate DECIMAL(5,2) NOT NULL,
    max_interest_rate DECIMAL(5,2) NOT NULL,
    min_tenure_months INT NOT NULL,
    max_tenure_months INT NOT NULL,
    currency_id BIGINT REFERENCES currencies(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Loan Applications
CREATE TABLE loan_applications (
    id BIGSERIAL PRIMARY KEY,
    application_id UUID UNIQUE NOT NULL,
    user_id BIGINT REFERENCES users(id),
    loan_product_id BIGINT REFERENCES loan_products(id),
    wallet_id BIGINT REFERENCES wallets(id),
    requested_amount DECIMAL(20,2) NOT NULL,
    approved_amount DECIMAL(20,2),
    status VARCHAR(20) DEFAULT 'pending',
    credit_score INT,
    disbursed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Repayment Schedules
CREATE TABLE loan_repayment_schedules (
    id BIGSERIAL PRIMARY KEY,
    schedule_id UUID UNIQUE NOT NULL,
    loan_id BIGINT REFERENCES loan_applications(id),
    installment_number INT NOT NULL,
    due_date DATE NOT NULL,
    total_amount DECIMAL(20,2) NOT NULL,
    outstanding_amount DECIMAL(20,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    UNIQUE (loan_id, installment_number)
);

-- Repayments
CREATE TABLE loan_repayments (
    id BIGSERIAL PRIMARY KEY,
    repayment_id UUID UNIQUE NOT NULL,
    loan_id BIGINT REFERENCES loan_applications(id),
    schedule_id BIGINT REFERENCES loan_repayment_schedules(id),
    amount DECIMAL(20,2) NOT NULL,
    reference VARCHAR(100) UNIQUE NOT NULL,
    wallet_id BIGINT REFERENCES wallets(id),
    transaction_id BIGINT REFERENCES transactions(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Credit Scores
CREATE TABLE credit_scores (
    id BIGSERIAL PRIMARY KEY,
    score_id UUID UNIQUE NOT NULL,
    user_id BIGINT REFERENCES users(id),
    score INT NOT NULL,
    score_band VARCHAR(20) NOT NULL,
    risk_level VARCHAR(20) DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Testing

Run tests with:
```bash
python manage.py test apps.loans
```

## Admin Interface

All models are registered in Django Admin with comprehensive views:
- **Loan Products**: Manage loan offerings
- **Loan Applications**: Review and approve applications
- **Repayment Schedules**: Track payment schedules
- **Loan Repayments**: Monitor repayment transactions
- **Credit Scores**: View user credit histories

## Future Enhancements

1. **Admin API Endpoints** - API for loan approval/rejection
2. **Automatic Repayment** - Scheduled auto-debit from wallet
3. **Loan Restructuring** - Modify terms for struggling borrowers
4. **Collateral Management** - Upload and verify collateral documents
5. **Guarantor Verification** - Contact and verify guarantors
6. **Risk-Based Pricing** - Dynamic interest rates by credit score
7. **Loan Calculator Widget** - Embeddable calculator for websites
8. **Notifications** - Email/SMS for due dates and overdue payments
9. **Loan Insurance** - Optional payment protection insurance
10. **Refinancing** - Refinance existing loans at better rates

## Security Considerations

1. **Personal Data Protection**: Employment and income data is sensitive
2. **Credit Score Privacy**: Scores should only be visible to user and admins
3. **Atomic Transactions**: All financial operations use database transactions
4. **Balance Validation**: Always check wallet balance before debits
5. **Reference Uniqueness**: All references must be cryptographically secure
6. **Admin Authorization**: Only authorized admins can approve/reject loans
7. **Audit Trail**: All loan actions logged for compliance

## Compliance & Regulations

- **Fair Lending**: Ensure non-discriminatory lending practices
- **Truth in Lending**: Provide clear interest rate and fee disclosures
- **Data Privacy**: Comply with GDPR/CCPA for personal data
- **Credit Reporting**: Consider integration with credit bureaus
- **Interest Rate Caps**: Respect jurisdictional usury laws
- **Debt Collection**: Follow fair debt collection practices

## Support

For questions or issues with the loans module, please contact the development team or file an issue in the project repository.
