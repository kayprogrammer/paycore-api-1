# Firebase Cloud Messaging (FCM) Setup Guide

This guide explains how to configure Firebase Cloud Messaging for push notifications in PayCore.

## Prerequisites

1. A Firebase project (create one at https://console.firebase.google.com)
2. Firebase Admin SDK service account credentials

## Getting Your Firebase Credentials

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project
3. Click the gear icon ⚙️ > **Project settings**
4. Navigate to the **Service accounts** tab
5. Click **Generate new private key**
6. Download the JSON file

## Configuration Options

You have **two options** for configuring Firebase credentials:

### Option 1: Environment Variable (Recommended for Production)

This is the **recommended approach** for production environments as it doesn't require storing sensitive files in your repository.

#### Steps:

1. **Open your downloaded Firebase JSON file** and copy its entire content

2. **Convert to single-line string** (optional but recommended):
   - Remove all newlines except those in the `private_key` field
   - The `private_key` should keep its `\n` characters

3. **Add to your `.env` file**:

```bash
FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project-id","private_key_id":"abc123...","private_key":"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----\n","client_email":"firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com","client_id":"123456789","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40your-project.iam.gserviceaccount.com"}'
```

**Important Notes:**
- Use **single quotes** `'...'` to wrap the JSON string
- Keep the `\n` characters in the `private_key` field - they are required!
- Make sure there are no line breaks in your `.env` file entry

### Option 2: JSON File (Development Only)

This approach is simpler for local development but **should NOT be used in production**.

#### Steps:

1. **Save your Firebase credentials file** as `fcm.json` in your project root:

```
paycore-api-1/
├── fcm.json          # Your Firebase credentials file
├── apps/
├── paycore/
└── ...
```

2. **Add to your `.env` file**:

```bash
FIREBASE_CREDENTIALS_PATH=fcm.json
```

3. **Verify `.gitignore`** includes `fcm.json` (already configured):

```gitignore
# Firebase credentials
fcm.json
firebase-credentials.json
*-firebase-adminsdk-*.json
```

**⚠️ Warning:** Never commit your Firebase credentials file to version control!

## How It Works

The Firebase Admin SDK is initialized in `paycore/settings/base.py`:

```python
# Firebase Admin SDK Configuration
FIREBASE_APP = None
FIREBASE_CREDENTIALS_JSON = config("FIREBASE_CREDENTIALS_JSON", default="")
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default="")

# Initialize Firebase Admin SDK
if FIREBASE_CREDENTIALS_JSON:
    # Option 1: Using JSON string (Production)
    cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
    cred = credentials.Certificate(cred_dict)
    FIREBASE_APP = firebase_admin.initialize_app(cred)
elif FIREBASE_CREDENTIALS_PATH:
    # Option 2: Using JSON file (Development)
    service_account_path = os.path.join(BASE_DIR, FIREBASE_CREDENTIALS_PATH)
    cred = credentials.Certificate(service_account_path)
    FIREBASE_APP = firebase_admin.initialize_app(cred)

# FCM Django Settings
FCM_DJANGO_SETTINGS = {
    "DEFAULT_FIREBASE_APP": FIREBASE_APP,
    "APP_VERBOSE_NAME": "PayCore",
    "ONE_DEVICE_PER_USER": True,  # Payment platform - one device per user for security
    "DELETE_INACTIVE_DEVICES": True,
    "TIMEOUT": 30,
}
```

**Priority:** If both `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` are set, the JSON string takes priority.

## ONE_DEVICE_PER_USER Behavior

PayCore uses `ONE_DEVICE_PER_USER: True` for security reasons since it's a payment platform. This means:

### How It Works

- **New Device Registration:** When a user logs in from a new device and registers their FCM token:
  - The old device token is automatically deactivated
  - The new device token becomes the only active token
  - The user will only receive notifications on their newest device

### Why This Matters for Payment Apps

1. **Security:** Users should only have one active session for financial transactions
2. **Compliance:** Prevents unauthorized devices from receiving sensitive payment notifications
3. **Simplicity:** Clear device management - the latest login is the active device

### User Experience

When a user logs in from a new phone:
```
User logs in on iPhone → iPhone gets notifications
User logs in on Android → iPhone stops getting notifications, Android gets notifications
User logs back in on iPhone → Android stops getting notifications, iPhone gets notifications
```

### Implementation

This is handled automatically by `fcm_django` when `ONE_DEVICE_PER_USER` is enabled. When registering a device token:

```python
from fcm_django.models import FCMDevice

# When user registers new device token
device = FCMDevice.objects.create(
    user=request.user,
    registration_id=fcm_token,  # New device token
    type="android"  # or "ios", "web"
)
# fcm_django automatically deactivates other devices for this user
```

## Verification

To verify your Firebase configuration is working:

```bash
python manage.py shell
```

```python
from apps.notifications.services import FCMService

# Check if Firebase is initialized
if FCMService.is_firebase_initialized():
    print("✅ Firebase is properly configured!")
else:
    print("❌ Firebase initialization failed. Check your credentials.")
```

## Production Deployment Checklist

When deploying to production:

- [ ] Use `FIREBASE_CREDENTIALS_JSON` environment variable
- [ ] Never commit `fcm.json` or any credentials files
- [ ] Store credentials securely (e.g., AWS Secrets Manager, Azure Key Vault, Heroku Config Vars)
- [ ] Verify `.gitignore` includes Firebase credential files
- [ ] Test push notifications in staging environment first

## Environment-Specific Configuration

### Local Development

```bash
# .env (local)
FIREBASE_CREDENTIALS_PATH=fcm.json
```

### Staging/Production

```bash
# Environment variables (Heroku, AWS, etc.)
FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
```

## Troubleshooting

### "Firebase not initialized" warning

**Cause:** Firebase credentials are not configured or invalid.

**Solutions:**
1. Check that either `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_PATH` is set in your `.env`
2. Verify the JSON format is valid (use a JSON validator)
3. Ensure the `private_key` contains `\n` characters
4. Check the file path is correct (for file-based configuration)

### "Permission denied" errors

**Cause:** The service account doesn't have proper permissions.

**Solution:**
1. Go to Firebase Console > Project Settings > Service Accounts
2. Verify your service account has "Firebase Admin SDK Administrator Service Agent" role

### Push notifications not being delivered

**Causes:**
- Invalid FCM device tokens
- Firebase app not properly initialized
- Device tokens not registered

**Solutions:**
1. Verify Firebase initialization: `FCMService.is_firebase_initialized()`
2. Check that device tokens are being registered via the API
3. Review FCM service logs for detailed error messages

## Additional Resources

- [Firebase Admin SDK Documentation](https://firebase.google.com/docs/admin/setup)
- [FCM Django Library](https://github.com/xtrinch/fcm-django)
- [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging)

## Support

For issues related to Firebase setup, check the logs or contact the development team.
