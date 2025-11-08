# Unified Notification Dispatcher Guide

## Overview

The Unified Notification Dispatcher provides a centralized system for sending notifications across multiple channels (in-app, push, email) with a single function call. It automatically routes to the appropriate email tasks and handles user preferences.

## Features

- **Multi-channel Support**: Send to in-app, push, and email simultaneously
- **Automatic Routing**: Automatically routes emails to correct Celery tasks
- **User Preferences**: Respects user notification preferences (in_app_enabled, push_enabled, email_enabled)
- **Type Safety**: Uses enums for event types and channels
- **Error Handling**: Comprehensive error handling and logging
- **Flexible API**: Both detailed and quick-notify methods available

## Quick Start

### Basic Usage

```python
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType
)

# Send notification across all channels
result = UnifiedNotificationDispatcher.quick_notify(
    user=user,
    event_type=NotificationEventType.LOAN_APPROVED,
    title="Loan Approved!",
    message="Your loan application has been approved.",
    object_id=str(loan.application_id),
    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
)
```

## Available Event Types

### KYC Events
- `KYC_APPROVED` - KYC verification approved
- `KYC_PENDING` - KYC verification pending review
- `KYC_REJECTED` - KYC verification rejected/action required

### Loan Events
- `LOAN_APPROVED` - Loan application approved
- `LOAN_DISBURSED` - Loan disbursed to wallet
- `LOAN_REPAYMENT` - Loan repayment successful

### Investment Events
- `INVESTMENT_CREATED` - Investment created successfully
- `INVESTMENT_MATURED` - Investment has matured

### Card Events
- `CARD_ISSUED` - Card issued to user

### Wallet Events
- `WALLET_CREATED` - Wallet created successfully

### Bill Payment Events
- `BILL_PAYMENT_SUCCESS` - Bill payment successful

### Transfer Events
- `TRANSFER_SUCCESS` - Transfer successful

### Payment Events
- `PAYMENT_SUCCESS` - Payment successful (for payer)
- `PAYMENT_RECEIVED` - Payment received (for merchant)

## Available Channels

- `NotificationChannel.IN_APP` - In-app notification
- `NotificationChannel.PUSH` - Push notification via FCM
- `NotificationChannel.EMAIL` - Email notification

## Methods

### 1. `quick_notify()` - Simplified Method

Best for most use cases. Automatically maps object_id to the correct field.

```python
UnifiedNotificationDispatcher.quick_notify(
    user=user,
    event_type=NotificationEventType.WALLET_CREATED,
    title="Wallet Created",
    message="Your USD wallet has been created successfully.",
    object_id=str(wallet.wallet_id),
    channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.MEDIUM,
    action_url="/wallets"
)
```

### 2. `dispatch()` - Advanced Method

For complex scenarios requiring custom context data.

```python
UnifiedNotificationDispatcher.dispatch(
    user=user,
    event_type=NotificationEventType.PAYMENT_RECEIVED,
    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
    title="Payment Received",
    message=f"You received ${amount} from {payer_name}",
    context_data={
        "payment_id": str(payment.payment_id),
        "amount": str(amount),
        "payer_name": payer_name
    },
    priority=NotificationPriority.HIGH,
    related_object_type="Payment",
    related_object_id=str(payment.payment_id),
    action_url="/transactions",
    action_data={
        "payment_id": str(payment.payment_id),
        "reference": payment.reference
    }
)
```

## Usage Examples

### Example 1: KYC Approval Notification

```python
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType
)
from apps.notifications.models import NotificationPriority

# In your KYC approval service
def approve_kyc(kyc_verification):
    # ... approval logic ...

    # Send notification across all channels
    UnifiedNotificationDispatcher.quick_notify(
        user=kyc_verification.user,
        event_type=NotificationEventType.KYC_APPROVED,
        title="KYC Verified!",
        message="Your identity verification has been approved.",
        object_id=str(kyc_verification.kyc_id),
        channels=[
            NotificationChannel.IN_APP,
            NotificationChannel.PUSH,
            NotificationChannel.EMAIL
        ],
        priority=NotificationPriority.HIGH,
        action_url="/dashboard"
    )
```

### Example 2: Loan Disbursement

```python
# In your loan processor
async def disburse_loan(loan):
    # ... disbursement logic ...

    # Notify user about disbursement
    result = UnifiedNotificationDispatcher.quick_notify(
        user=loan.user,
        event_type=NotificationEventType.LOAN_DISBURSED,
        title="Loan Disbursed",
        message=f"Your loan of ${loan.approved_amount:,.2f} has been credited to your wallet.",
        object_id=str(loan.application_id),
        channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    )

    logger.info(f"Loan disbursement notification sent: {result}")
```

### Example 3: Investment Maturity

```python
# In your investment processor
def process_maturity(investment):
    # ... maturity processing ...

    UnifiedNotificationDispatcher.quick_notify(
        user=investment.user,
        event_type=NotificationEventType.INVESTMENT_MATURED,
        title="Investment Matured!",
        message=f"Your investment has matured. Total payout: ${investment.total_payout:,.2f}",
        object_id=str(investment.investment_id),
        channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
        priority=NotificationPriority.HIGH,
        action_url="/investments/portfolio"
    )
```

### Example 4: Payment with Custom Data

```python
# In your payment processor
async def process_payment(payment):
    # ... payment processing ...

    # Notify payer
    UnifiedNotificationDispatcher.dispatch(
        user=payment.payer_wallet.user,
        event_type=NotificationEventType.PAYMENT_SUCCESS,
        channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
        title="Payment Successful",
        message=f"Your payment of ${payment.amount:,.2f} was successful.",
        context_data={
            "payment_id": str(payment.payment_id),
            "amount": str(payment.amount),
            "merchant_name": payment.merchant_user.full_name
        },
        priority=NotificationPriority.MEDIUM,
        related_object_type="Payment",
        related_object_id=str(payment.payment_id),
        action_url="/transactions",
        action_data={
            "payment_id": str(payment.payment_id),
            "reference": payment.reference
        }
    )

    # Notify merchant
    UnifiedNotificationDispatcher.quick_notify(
        user=payment.merchant_user,
        event_type=NotificationEventType.PAYMENT_RECEIVED,
        title="Payment Received",
        message=f"You received ${payment.net_amount:,.2f} from {payment.payer_name}.",
        object_id=str(payment.payment_id),
        channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
        priority=NotificationPriority.HIGH,
    )
```

### Example 5: Only Email Notification

```python
# Send only email (no in-app or push)
UnifiedNotificationDispatcher.quick_notify(
    user=user,
    event_type=NotificationEventType.CARD_ISSUED,
    title="Card Issued",
    message="Your new card has been issued.",
    object_id=str(card.card_id),
    channels=[NotificationChannel.EMAIL],  # Only email
)
```

## Channel Selection Strategies

### All Channels (High Priority Events)
```python
channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL]
```
Use for: Loan approvals, investment maturity, KYC approval, large payments

### In-App + Email (Medium Priority)
```python
channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL]
```
Use for: Wallet creation, card issuance, bill payments, transfers

### In-App Only (Low Priority)
```python
channels=[NotificationChannel.IN_APP]
```
Use for: Minor updates, informational messages

### In-App + Push (Real-time Alerts)
```python
channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH]
```
Use for: Time-sensitive notifications where email delay is unacceptable

## Response Structure

```python
{
    "success": True,
    "channels_attempted": ["in_app", "push", "email"],
    "channels_sent": ["in_app", "push", "email"],
    "errors": []
}
```

## User Preferences

The dispatcher automatically respects user preferences:

- `user.in_app_enabled` - Controls in-app notifications
- `user.push_enabled` - Controls push notifications
- `user.email_enabled` - Controls email notifications

If a channel is disabled for a user, it will be skipped without errors.

## Error Handling

The dispatcher handles errors gracefully:

```python
result = UnifiedNotificationDispatcher.quick_notify(...)

if result["success"]:
    logger.info(f"Notification sent via: {result['channels_sent']}")
else:
    logger.error(f"Notification errors: {result['errors']}")
```

## Email Task Routing

The dispatcher automatically routes emails to the correct Celery task based on event type:

| Event Type | Email Task | Required ID Field |
|------------|------------|-------------------|
| KYC_APPROVED | `KYCEmailTasks.send_kyc_approved_email` | `kyc_id` |
| KYC_PENDING | `KYCEmailTasks.send_kyc_pending_email` | `kyc_id` |
| KYC_REJECTED | `KYCEmailTasks.send_kyc_rejected_email` | `kyc_id` |
| LOAN_APPROVED | `LoanEmailTasks.send_loan_approved_email` | `loan_id` |
| LOAN_DISBURSED | `LoanEmailTasks.send_loan_disbursed_email` | `loan_id` |
| LOAN_REPAYMENT | `LoanEmailTasks.send_loan_repayment_email` | `repayment_id` |
| INVESTMENT_CREATED | `InvestmentEmailTasks.send_investment_created_email` | `investment_id` |
| INVESTMENT_MATURED | `InvestmentEmailTasks.send_investment_matured_email` | `investment_id` |
| CARD_ISSUED | `CardEmailTasks.send_card_issued_email` | `card_id` |
| WALLET_CREATED | `WalletEmailTasks.send_wallet_created_email` | `wallet_id` |
| BILL_PAYMENT_SUCCESS | `BillPaymentEmailTasks.send_bill_payment_success_email` | `bill_payment_id` |
| TRANSFER_SUCCESS | `TransferEmailTasks.send_transfer_success_email` | `transaction_id` |
| PAYMENT_SUCCESS | `PaymentEmailTasks.send_payment_confirmation_email` | `payment_id` |
| PAYMENT_RECEIVED | `PaymentEmailTasks.send_payment_received_email` | `payment_id` |

## Best Practices

1. **Always use event types**: Use the predefined `NotificationEventType` enum for type safety
2. **Provide meaningful titles and messages**: Keep them concise and actionable
3. **Include action URLs**: Provide deep links for better user experience
4. **Choose appropriate priority**: Use HIGH for urgent matters, MEDIUM for standard, LOW for informational
5. **Log results**: Always log the dispatch results for debugging
6. **Handle errors gracefully**: Check the success flag and errors array

## Adding New Event Types

To add a new event type:

1. Add to `NotificationEventType` enum in `dispatcher.py`
2. Add email task routing in `EMAIL_TASK_ROUTER`
3. Add notification type mapping in `EVENT_TO_NOTIFICATION_TYPE`
4. Update this documentation

## Migration from Old System

### Before (Old System)
```python
# Had to manually handle each channel
NotificationService.create_notification(user, title, message, ...)
PaymentEmailTasks.send_payment_email.delay(payment_id)
FCMService.send_to_user(user, title, message, ...)
```

### After (Unified System)
```python
# Single call handles all channels
UnifiedNotificationDispatcher.quick_notify(
    user=user,
    event_type=NotificationEventType.PAYMENT_SUCCESS,
    title=title,
    message=message,
    object_id=str(payment_id),
    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL]
)
```

## Performance Considerations

- **In-app + Push**: Handled synchronously (fast)
- **Email**: Dispatched to Celery queue (asynchronous, no blocking)
- **User Preferences**: Checked before sending (no wasted resources)
- **Error Isolation**: Failure in one channel doesn't affect others

## Troubleshooting

### Emails not sending
- Check `user.email_enabled` is True
- Verify Celery worker is running
- Check Celery logs for task execution
- Verify email task exists in routing map

### Push notifications not sending
- Check `user.push_enabled` is True
- Verify FCM configuration is correct
- Check if user has FCM tokens registered

### In-app notifications not showing
- Check `user.in_app_enabled` is True
- Verify WebSocket connection is active
- Check browser console for errors
