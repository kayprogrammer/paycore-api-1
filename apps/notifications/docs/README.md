# Notifications Module

Complete notification system for PayCore API with in-app notifications, push notifications (FCM), and real-time WebSocket delivery.

## Features

- **In-App Notifications**: Store notifications in database for users to access later
- **Push Notifications**: Send notifications to mobile devices via Firebase Cloud Messaging (FCM)
- **Real-Time Notifications**: Instant delivery via WebSockets using Django Channels
- **Notification Preferences**: User-controlled settings for notification delivery
- **Notification Templates**: Reusable templates for consistent messaging
- **Quiet Hours**: Respect user's quiet hours (only urgent notifications during quiet hours)
- **Priority Levels**: low, medium, high, urgent
- **Notification Types**: payment, loan, card, kyc, bill, account, security, promotion, system, other

## Installation

### 1. Firebase Setup (for Push Notifications)

1. Create a Firebase project at https://console.firebase.google.com/
2. Download your service account key JSON file
3. Add to `.env`:
   ```
   FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json
   # OR use JSON string:
   FIREBASE_CREDENTIALS_JSON='{"type": "service_account", ...}'
   ```

### 2. Redis Setup (for WebSockets)

Add to `.env`:
```
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. Environment Variables

```env
# Notification Settings
NOTIFICATION_RETENTION_DAYS=90
SITE_URL=http://localhost:8000

# Firebase (for push notifications)
FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json

# Redis (for WebSockets)
REDIS_HOST=localhost
REDIS_PORT=6379
```

## API Endpoints

### Notifications

- `GET /api/v1/notifications/` - Get paginated list of notifications
- `GET /api/v1/notifications/unread-count` - Get count of unread notifications
- `GET /api/v1/notifications/stats` - Get notification statistics
- `POST /api/v1/notifications/mark-read` - Mark specific notifications as read
- `POST /api/v1/notifications/mark-all-read` - Mark all notifications as read
- `DELETE /api/v1/notifications/{notification_id}` - Delete a notification

### Device Tokens (FCM)

- `POST /api/v1/notifications/devices` - Register FCM device token
- `GET /api/v1/notifications/devices` - Get user's registered devices
- `PATCH /api/v1/notifications/devices/{token_id}` - Update device settings
- `DELETE /api/v1/notifications/devices/{token_id}` - Delete device token

### Preferences

- `GET /api/v1/notifications/preferences` - Get notification preferences
- `PATCH /api/v1/notifications/preferences` - Update notification preferences

### Test

- `POST /api/v1/notifications/test/send` - Send test notification

## WebSocket Connection

Connect to WebSocket for real-time notifications:

```javascript
// Connect with JWT token in query string
const ws = new WebSocket('ws://localhost:8000/ws/notifications/?token=<access_token>');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'notification') {
        console.log('New notification:', data.notification);
    } else if (data.type === 'unread_count') {
        console.log('Unread count:', data.count);
    }
};

// Send commands to server
ws.send(JSON.stringify({
    command: 'get_unread_count'
}));

ws.send(JSON.stringify({
    command: 'mark_read',
    notification_ids: ['uuid1', 'uuid2']
}));
```

## Usage in Code

### Using Notification Triggers (Recommended)

```python
from apps.notifications.triggers import NotificationTriggers

# Payment notification
NotificationTriggers.payment_received(
    user=user,
    amount=100.00,
    currency="USD",
    reference="PAY-12345"
)

# Loan notification
NotificationTriggers.loan_approved(
    user=user,
    loan_id=str(loan.loan_id),
    amount=5000.00,
    currency="USD"
)

# KYC notification
NotificationTriggers.kyc_approved(
    user=user,
    kyc_id=str(kyc.kyc_id),
    tier=2
)

# Security notification
NotificationTriggers.password_changed(user=user)
```

### Using NotificationService Directly

```python
from apps.notifications.services import NotificationService

notification = NotificationService.create_notification(
    user=user,
    title="Custom Notification",
    message="This is a custom message",
    notification_type="payment",
    priority="high",
    related_object_type="Payment",
    related_object_id="PAY-12345",
    action_url="/payments/PAY-12345",
    action_data={"payment_id": "PAY-12345"},
    send_push=True,
    send_realtime=True,
)
```

### Using Celery Tasks

```python
from apps.notifications.tasks import NotificationTasks

# Send single notification asynchronously
NotificationTasks.send_notification.delay(
    user_id=user.id,
    title="Async Notification",
    message="This notification is sent in the background",
    notification_type="system",
    priority="medium"
)

# Send bulk notification to multiple users
NotificationTasks.send_bulk_notification.delay(
    user_ids=[1, 2, 3, 4, 5],
    title="Announcement",
    message="System maintenance scheduled for tomorrow",
    notification_type="system",
    priority="high"
)
```

### Using Templates

```python
from apps.notifications.services import NotificationService

# First, create a template in Django admin:
# Name: payment_received
# Title Template: Payment of {{amount}} {{currency}} Received
# Message Template: You have received {{amount}} {{currency}} from {{sender}}

# Then use it:
NotificationService.create_from_template(
    user=user,
    template_name="payment_received",
    context={
        "amount": "100.00",
        "currency": "USD",
        "sender": "John Doe"
    }
)
```

## Notification Types

Available notification types:

- `payment` - Payment-related notifications
- `loan` - Loan-related notifications
- `card` - Card/transaction notifications
- `kyc` - KYC/compliance notifications
- `bill` - Bill payment notifications
- `account` - Account-related notifications
- `security` - Security alerts
- `promotion` - Promotional messages
- `system` - System announcements
- `other` - Other notifications

## Priority Levels

- `low` - Can be batched, non-urgent
- `medium` - Standard priority (default)
- `high` - Important, send immediately
- `urgent` - Critical, bypass quiet hours

## User Preferences

Users can control their notification preferences:

```json
{
  "push_enabled": true,
  "in_app_enabled": true,
  "email_enabled": true,
  "notification_types": {
    "payment": {
      "push": true,
      "in_app": true,
      "email": false
    },
    "loan": {
      "push": true,
      "in_app": true,
      "email": true
    }
  },
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00",
  "minimum_priority": "medium"
}
```

## Celery Tasks

### Background Tasks

- `notifications.send_notification` - Send notification asynchronously
- `notifications.send_bulk_notification` - Send to multiple users

### Periodic Tasks (Celery Beat)

- `cleanup_old_notifications` - Daily at 2 AM - Delete old read notifications
- `cleanup_expired_notifications` - Hourly - Delete expired notifications
- `cleanup_inactive_devices` - Daily at 3 AM - Deactivate unused device tokens
- `generate_daily_stats` - Daily at 00:05 - Generate notification statistics

## Admin Interface

All notification models are available in Django admin:

- **Notifications**: View all notifications, filter by type/priority/status
- **Device Tokens**: Manage FCM device registrations
- **Notification Preferences**: View/edit user preferences
- **Notification Templates**: Create reusable templates

## Testing

### Test Push Notification

```bash
curl -X POST http://localhost:8000/api/v1/notifications/test/send \
  -H "Authorization: Bearer <your_token>"
```

### Test WebSocket Connection

```bash
# Using websocat
websocat "ws://localhost:8000/ws/notifications/?token=<your_token>"
```

## Mobile App Integration

### iOS (Swift)

```swift
import Firebase
import FirebaseMessaging

// Register for push notifications
Messaging.messaging().token { token, error in
    if let error = error {
        print("Error fetching FCM token: \(error)")
    } else if let token = token {
        // Send token to backend
        registerDevice(fcmToken: token, deviceType: "ios")
    }
}

func registerDevice(fcmToken: String, deviceType: String) {
    let params = [
        "fcm_token": fcmToken,
        "device_type": deviceType,
        "device_name": UIDevice.current.name,
        "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "",
        "os_version": UIDevice.current.systemVersion
    ]

    // POST to /api/v1/notifications/devices
    API.post("/api/v1/notifications/devices", parameters: params)
}
```

### Android (Kotlin)

```kotlin
import com.google.firebase.messaging.FirebaseMessaging

// Get FCM token
FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
    if (task.isSuccessful) {
        val token = task.result
        registerDevice(token, "android")
    }
}

fun registerDevice(fcmToken: String, deviceType: String) {
    val params = mapOf(
        "fcm_token" to fcmToken,
        "device_type" to deviceType,
        "device_name" to Build.MODEL,
        "app_version" to BuildConfig.VERSION_NAME,
        "os_version" to Build.VERSION.RELEASE
    )

    // POST to /api/v1/notifications/devices
    api.post("/api/v1/notifications/devices", params)
}
```

## Production Deployment

### 1. Run with Daphne (ASGI Server)

```bash
# For WebSocket support, use Daphne instead of Gunicorn
daphne -b 0.0.0.0 -p 8000 paycore.asgi:application
```

### 2. Start Celery Workers

```bash
# Main worker
celery -A paycore worker -l info -Q notifications,default

# Beat scheduler (for periodic tasks)
celery -A paycore beat -l info
```

### 3. Configure Reverse Proxy (Nginx)

```nginx
# HTTP/HTTPS
location / {
    proxy_pass http://127.0.0.1:8000;
}

# WebSocket
location /ws/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

## Troubleshooting

### Push Notifications Not Working

1. Check Firebase credentials are configured correctly
2. Verify device token is active: `GET /api/v1/notifications/devices`
3. Check Celery logs for FCM errors
4. Verify FCM token is valid in Firebase Console

### WebSocket Connection Fails

1. Ensure Redis is running: `redis-cli ping`
2. Check CHANNEL_LAYERS configuration in settings
3. Verify JWT token is valid
4. Check Daphne is running (not Gunicorn)

### Notifications Not Received

1. Check user preferences: `GET /api/v1/notifications/preferences`
2. Verify notification type is enabled
3. Check if quiet hours is blocking (only urgent bypass)
4. Check minimum priority setting

## Architecture

```
User Action � NotificationTrigger
              �
              NotificationService.create_notification()
              �
               � Database (Notification model)
               � FCMService.send_to_user() � Firebase � Mobile Device
               � WebSocketService.send_notification() � Redis � WebSocket Client
```
