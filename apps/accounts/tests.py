import json, pytest
from unittest.mock import AsyncMock, patch
from django.test import TestCase
from apps.accounts.auth import Authentication
from apps.common.exceptions import ErrorCode
from apps.accounts.models import User
from apps.common.tests import aclient


class TestAccountsUtil:
    def unverified_user():
        return User.objects.create_user(
            first_name="Test",
            last_name="Name",
            email="testname@example.com",
            password="testpassword",
        )

    def first_verified_user():
        return User.objects.create_user(
            first_name="Test",
            last_name="Verified",
            email="testverified@example.com",
            is_email_verified=True,
            password="testpassword",
        )

    def second_verified_user():
        return User.objects.create_user(
            first_name="TestSecond",
            last_name="Verified",
            email="testsecondverified@example.com",
            is_email_verified=True,
            password="testpassword",
        )

    def auth_token(user: User):
        access = Authentication.create_access_token(user.id)
        return access


@pytest.mark.django_db
class TestAuthAndAccountsManagementEndpoints(TestCase):
    BASE_URI_PATH = "/api/v1/auth"
    register_url = f"{BASE_URI_PATH}/register"
    verify_email_url = f"{BASE_URI_PATH}/verify-email"
    resend_verification_email_url = f"{BASE_URI_PATH}/resend-verification-otp"
    send_password_reset_otp_url = f"{BASE_URI_PATH}/send-password-reset-otp"
    set_new_password_url = f"{BASE_URI_PATH}/set-new-password"
    login_url = f"{BASE_URI_PATH}/login"
    refresh_url = f"{BASE_URI_PATH}/refresh"
    google_login_url = f"{BASE_URI_PATH}/google-login"
    logout_url = f"{BASE_URI_PATH}/logout"
    logout_all_url = f"{BASE_URI_PATH}/logout-all"

    def setUp(self):
        self.unverified_user = TestAccountsUtil.unverified_user()
        verified_user = TestAccountsUtil.first_verified_user()
        self.verified_user = verified_user
        self.auth_token = TestAccountsUtil.auth_token(verified_user)

    # TEST POSSIBLE RESPONSES FOR REGISTRATION ENDPOINT
    async def test_account_duplication_error_reponse(self):
        data = {
            "first_name": "Testregister",
            "last_name": "User",
            "email": self.unverified_user.email,
            "password": "testregisteruserpassword",
        }

        response = await aclient.post(
            self.register_url,
            json.dumps(data),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INVALID_ENTRY,
                "message": "Invalid Entry",
                "data": {"email": "Email already registered!"},
            },
        )

    @patch("apps.accounts.emails.EmailUtil.send_otp", new_callable=AsyncMock)
    async def test_account_created_successfully(self, mock_send_otp):
        mock_send_otp.return_value = 1  # fake async result

        data = {
            "first_name": "Testregister",
            "last_name": "User",
            "email": "test@example.com",
            "password": "testregisteruserpassword",
        }

        response = await aclient.post(
            self.register_url,
            json.dumps(data),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Registration successful",
                "data": {"email": data["email"]},
            },
        )
        mock_send_otp.assert_awaited_once()

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR EMAIL VERIFICATION ENDPOINT
    async def test_verify_email_user_not_found(self):
        data = {"email": "nonexistent@example.com", "otp": "123456"}

        response = await aclient.post(self.verify_email_url, json.dumps(data))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INCORRECT_EMAIL,
                "message": "Incorrect Email",
            },
        )

    async def test_verify_email_already_verified(self):
        data = {"email": self.verified_user.email, "otp": "123456"}

        response = await aclient.post(self.verify_email_url, json.dumps(data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Email already verified",
            },
        )

    async def test_verify_email_incorrect_otp(self):
        self.unverified_user.otp_code = "123456"
        await self.unverified_user.asave()

        data = {"email": self.unverified_user.email, "otp": "654321"}

        response = await aclient.post(self.verify_email_url, json.dumps(data))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INCORRECT_OTP,
                "message": "Incorrect Otp",
            },
        )

    @patch("apps.accounts.models.User.is_otp_expired")
    async def test_verify_email_expired_otp(self, mock_is_otp_expired):
        mock_is_otp_expired.return_value = True
        self.unverified_user.otp_code = "123456"
        await self.unverified_user.asave()

        data = {"email": self.unverified_user.email, "otp": "123456"}

        response = await aclient.post(self.verify_email_url, json.dumps(data))
        self.assertEqual(response.status_code, 410)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.EXPIRED_OTP,
                "message": "Expired Otp",
            },
        )

    @patch("apps.accounts.emails.EmailUtil.welcome_email")
    @patch("apps.accounts.models.User.is_otp_expired")
    async def test_verify_email_successful(
        self, mock_is_otp_expired, mock_welcome_email
    ):
        mock_is_otp_expired.return_value = False
        self.unverified_user.otp_code = "123456"
        await self.unverified_user.asave()

        data = {"email": self.unverified_user.email, "otp": "123456"}

        response = await aclient.post(self.verify_email_url, json.dumps(data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Account verification successful",
            },
        )
        mock_welcome_email.assert_called_once()

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR RESEND VERIFICATION OTP ENDPOINT
    async def test_resend_verification_email_user_not_found(self):
        data = {"email": "nonexistent@example.com"}

        response = await aclient.post(
            self.resend_verification_email_url, json.dumps(data)
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INCORRECT_EMAIL,
                "message": "Incorrect Email",
            },
        )

    async def test_resend_verification_email_already_verified(self):
        data = {"email": self.verified_user.email}

        response = await aclient.post(
            self.resend_verification_email_url, json.dumps(data)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Email already verified",
            },
        )

    @patch("apps.accounts.emails.EmailUtil.send_otp", new_callable=AsyncMock)
    async def test_resend_verification_email_successful(self, mock_send_otp):
        mock_send_otp.return_value = 1
        data = {"email": self.unverified_user.email}

        response = await aclient.post(
            self.resend_verification_email_url, json.dumps(data)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Verification email sent",
            },
        )
        mock_send_otp.assert_awaited_once()

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR SEND PASSWORD RESET OTP ENDPOINT
    async def test_send_password_reset_otp_user_not_found(self):
        data = {"email": "nonexistent@example.com"}

        response = await aclient.post(
            self.send_password_reset_otp_url, json.dumps(data)
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INCORRECT_EMAIL,
                "message": "Incorrect Email",
            },
        )

    @patch("apps.accounts.emails.EmailUtil.send_otp", new_callable=AsyncMock)
    async def test_send_password_reset_otp_successful(self, mock_send_otp):
        mock_send_otp.return_value = 1
        data = {"email": self.verified_user.email}

        response = await aclient.post(
            self.send_password_reset_otp_url, json.dumps(data)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Password otp sent",
            },
        )
        mock_send_otp.assert_awaited_once()

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR SET NEW PASSWORD ENDPOINT
    async def test_set_new_password_user_not_found(self):
        data = {
            "email": "nonexistent@example.com",
            "otp": "123456",
            "password": "newpassword123",
        }

        response = await aclient.post(self.set_new_password_url, json.dumps(data))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INCORRECT_EMAIL,
                "message": "Incorrect Email",
            },
        )

    async def test_set_new_password_incorrect_otp(self):
        self.verified_user.otp_code = "123456"
        await self.verified_user.asave()

        data = {
            "email": self.verified_user.email,
            "otp": "654321",
            "password": "newpassword123",
        }

        response = await aclient.post(self.set_new_password_url, json.dumps(data))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INCORRECT_OTP,
                "message": "Incorrect Otp",
            },
        )

    @patch("apps.accounts.models.User.is_otp_expired")
    async def test_set_new_password_expired_otp(self, mock_is_otp_expired):
        mock_is_otp_expired.return_value = True
        self.verified_user.otp_code = "123456"
        await self.verified_user.asave()

        data = {
            "email": self.verified_user.email,
            "otp": "123456",
            "password": "newpassword123",
        }

        response = await aclient.post(self.set_new_password_url, json.dumps(data))
        self.assertEqual(response.status_code, 410)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.EXPIRED_OTP,
                "message": "Expired Otp",
            },
        )

    @patch("apps.accounts.emails.EmailUtil.password_reset_confirmation")
    @patch("apps.accounts.models.User.is_otp_expired")
    async def test_set_new_password_successful(
        self, mock_is_otp_expired, mock_password_reset_confirmation
    ):
        mock_is_otp_expired.return_value = False
        self.verified_user.otp_code = "123456"
        await self.verified_user.asave()

        data = {
            "email": self.verified_user.email,
            "otp": "123456",
            "password": "newpassword123",
        }

        response = await aclient.post(self.set_new_password_url, json.dumps(data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Password reset successful",
            },
        )
        mock_password_reset_confirmation.assert_called_once()

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR LOGIN ENDPOINT
    async def test_login_invalid_credentials_user_not_found(self):
        data = {"email": "nonexistent@example.com", "password": "wrongpassword"}

        response = await aclient.post(self.login_url, json.dumps(data))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INVALID_CREDENTIALS,
                "message": "Invalid credentials",
            },
        )

    async def test_login_invalid_credentials_wrong_password(self):
        data = {"email": self.verified_user.email, "password": "wrongpassword"}

        response = await aclient.post(self.login_url, json.dumps(data))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INVALID_CREDENTIALS,
                "message": "Invalid credentials",
            },
        )

    async def test_login_unverified_user(self):
        data = {"email": self.unverified_user.email, "password": "testpassword"}

        response = await aclient.post(self.login_url, json.dumps(data))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.UNVERIFIED_USER,
                "message": "Verify your email first",
            },
        )

    async def test_login_successful(self):
        data = {"email": self.verified_user.email, "password": "testpassword"}

        response = await aclient.post(self.login_url, json.dumps(data))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "Login successful")
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR REFRESH TOKEN ENDPOINT
    async def test_refresh_token_invalid_token(self):
        data = {"token": "invalid_token"}

        response = await aclient.post(self.refresh_url, json.dumps(data))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INVALID_TOKEN,
                "message": "Refresh token is invalid or expired",
            },
        )

    async def test_refresh_token_not_found(self):
        refresh_token = Authentication.create_refresh_token()
        data = {"token": refresh_token}

        response = await aclient.post(self.refresh_url, json.dumps(data))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INVALID_TOKEN,
                "message": "Refresh token is invalid or expired",
            },
        )

    async def test_refresh_token_successful(self):
        user = self.verified_user
        refresh_token = Authentication.create_refresh_token()
        access_token = Authentication.create_access_token(user.id)
        user.access, user.refresh = access_token, refresh_token
        await user.asave()
        data = {"token": refresh_token}

        response = await aclient.post(self.refresh_url, json.dumps(data))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "Tokens refresh successful")
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR GOOGLE LOGIN ENDPOINT
    @patch("apps.accounts.auth.Authentication.validate_google_token")
    @patch("apps.accounts.auth.Authentication.store_google_user")
    async def test_google_login_invalid_token(
        self, mock_store_google_user, mock_validate_google_token
    ):
        mock_validate_google_token.return_value = (
            None,
            ErrorCode.INVALID_TOKEN,
            "Invalid token",
        )

        data = {"token": "invalid_google_token"}

        response = await aclient.post(self.google_login_url, json.dumps(data))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": "failure",
                "code": ErrorCode.INVALID_TOKEN,
                "message": "Invalid token",
            },
        )

    @patch("apps.accounts.auth.Authentication.validate_google_token")
    @patch("apps.accounts.auth.Authentication.store_google_user")
    async def test_google_login_successful(
        self, mock_store_google_user, mock_validate_google_token
    ):
        mock_validate_google_token.return_value = (
            {
                "email": "googleuser@example.com",
                "name": "Google User",
                "picture": "http://example.com/pic.jpg",
            },
            None,
            None,
        )
        mock_store_google_user.return_value = self.verified_user

        data = {"token": "valid_google_token"}

        response = await aclient.post(self.google_login_url, json.dumps(data))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "Tokens created successfully")
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR LOGOUT ENDPOINT
    async def test_logout_successful(self):
        response = await aclient.get(
            self.logout_url, headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Logout successful",
            },
        )

    # ------------------------------------------------------------------------

    # TEST POSSIBLE RESPONSES FOR LOGOUT ALL ENDPOINT
    async def test_logout_all_successful(self):
        response = await aclient.get(
            self.logout_all_url, headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "success",
                "message": "Logout successful",
            },
        )


@pytest.mark.django_db
class TestProfilesManagementEndpoints(TestCase):
    BASE_URI_PATH = "/api/v1/profiles"
    get_profile_url = update_profile_url = BASE_URI_PATH

    def setUp(self):
        verified_user = TestAccountsUtil.first_verified_user()
        self.verified_user = verified_user
        self.auth_token = TestAccountsUtil.auth_token(verified_user)
        self.header_args = {"headers": {"Authorization": f"Bearer {self.auth_token}"}}

    # TEST POSSIBLE RESPONSES FOR GET PROFILE ENDPOINT
    async def test_get_profile_successful(self):
        user = self.verified_user

        response = await aclient.get(self.get_profile_url, **self.header_args)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "Profile retrieved successfully")
        self.assertEqual(
            response.data["data"],
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "bio": user.bio,
                "dob": user.dob,
                "avatar_url": user.avatar_url,
            },
        )

    # TEST POSSIBLE RESPONSES FOR UPDATE PROFILE ENDPOINT
    async def test_update_profile_successful(self):
        data = {
            "first_name": "Updated",
            "last_name": "Name",
            "dob": "2000-12-12",
            "bio": "Updated bio",
        }

        response = await aclient.put(
            self.update_profile_url, data=data, **self.header_args
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "Profile updated successfully")
        self.assertIn("data", response.data)
