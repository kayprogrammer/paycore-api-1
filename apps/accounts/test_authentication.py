"""
Unit tests for Authentication service (apps/accounts/auth.py)

Tests JWT token generation, validation, expiration, and Google OAuth logic.
These are UNIT tests - testing business logic directly, not API endpoints.
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch
from django.conf import settings
import jwt

from apps.accounts.auth import Authentication
from apps.accounts.models import User


@pytest.mark.unit
@pytest.mark.auth
class TestTokenGeneration:
    """Test JWT token generation logic."""

    @pytest.mark.django_db
    def test_create_access_token_structure(self, verified_user):
        """Test that access token contains correct claims."""
        token = Authentication.create_access_token(verified_user.id)

        # Decode without verification to inspect structure
        decoded = jwt.decode(token, options={"verify_signature": False})

        assert decoded["type"] == "access"
        assert decoded["user_id"] == str(verified_user.id)
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded  # JWT ID for token tracking

    @pytest.mark.django_db
    def test_create_access_token_expiration_time(self, verified_user):
        """Test that access token has correct expiration time."""
        token = Authentication.create_access_token(verified_user.id)
        decoded = jwt.decode(token, options={"verify_signature": False})

        # Calculate expected expiration
        expected_exp = datetime.now(UTC) + timedelta(
            minutes=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # Allow 5 second tolerance for test execution time
        token_exp = datetime.fromtimestamp(decoded["exp"], UTC)
        time_diff = abs((token_exp - expected_exp).total_seconds())

        assert time_diff < 5, "Token expiration time should match configured value"

    @pytest.mark.django_db
    def test_create_refresh_token_structure(self):
        """Test that refresh token contains correct claims."""
        token = Authentication.create_refresh_token()
        decoded = jwt.decode(token, options={"verify_signature": False})

        assert decoded["type"] == "refresh"
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded
        assert "data" in decoded  # Random data for additional entropy

    @pytest.mark.django_db
    def test_refresh_token_expiration_time(self):
        """Test that refresh token has correct expiration time."""
        token = Authentication.create_refresh_token()
        decoded = jwt.decode(token, options={"verify_signature": False})

        expected_exp = datetime.now(UTC) + timedelta(
            minutes=int(settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        )

        token_exp = datetime.fromtimestamp(decoded["exp"], UTC)
        time_diff = abs((token_exp - expected_exp).total_seconds())

        assert time_diff < 5

    @pytest.mark.django_db
    def test_custom_jti_in_access_token(self, verified_user):
        """Test that custom JTI is used when provided."""
        custom_jti = "custom-jti-12345"
        token = Authentication.create_access_token(verified_user.id, jti=custom_jti)
        decoded = jwt.decode(token, options={"verify_signature": False})

        assert decoded["jti"] == custom_jti

    @pytest.mark.django_db
    def test_random_string_generation_uniqueness(self):
        """Test that random string generator produces unique values."""
        random1 = Authentication.get_random(16)
        random2 = Authentication.get_random(16)

        assert random1 != random2
        assert len(random1) > 0
        assert len(random2) > 0


@pytest.mark.unit
@pytest.mark.auth
class TestTokenValidation:
    """Test JWT token validation and decoding logic."""

    @pytest.mark.django_db
    def test_decode_valid_access_token(self, verified_user):
        """Test decoding a valid access token."""
        token = Authentication.create_access_token(verified_user.id)
        decoded = Authentication.decode_jwt(token, "access")

        assert decoded is not None
        assert decoded["user_id"] == str(verified_user.id)
        assert decoded["type"] == "access"

    @pytest.mark.django_db
    def test_decode_valid_refresh_token(self):
        """Test decoding a valid refresh token."""
        token = Authentication.create_refresh_token()
        decoded = Authentication.decode_jwt(token, "refresh")

        assert decoded is not None
        assert decoded["type"] == "refresh"

    @pytest.mark.django_db
    def test_decode_expired_token(self, verified_user):
        """Test that expired tokens are rejected."""
        # Create token with past expiration
        past_time = datetime.now(UTC) - timedelta(hours=1)
        expired_token = jwt.encode(
            {
                "exp": past_time,
                "iat": past_time - timedelta(minutes=30),
                "user_id": str(verified_user.id),
                "jti": "test-jti",
                "type": "access",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        decoded = Authentication.decode_jwt(expired_token, "access")
        assert decoded is None, "Expired token should be rejected"

    @pytest.mark.django_db
    def test_decode_wrong_token_type(self, verified_user):
        """Test that token type mismatch is rejected."""
        access_token = Authentication.create_access_token(verified_user.id)

        # Try to decode access token as refresh token
        decoded = Authentication.decode_jwt(access_token, "refresh")
        assert decoded is None, "Token type mismatch should be rejected"

    @pytest.mark.django_db
    def test_decode_invalid_signature(self, verified_user):
        """Test that tokens with invalid signatures are rejected."""
        # Create token with wrong secret
        fake_token = jwt.encode(
            {
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC),
                "user_id": str(verified_user.id),
                "jti": "test-jti",
                "type": "access",
            },
            "wrong-secret-key",
            algorithm="HS256",
        )

        decoded = Authentication.decode_jwt(fake_token, "access")
        assert decoded is None, "Token with invalid signature should be rejected"

    @pytest.mark.django_db
    def test_decode_malformed_token(self):
        """Test that malformed tokens are rejected."""
        malformed_tokens = [
            "not.a.jwt",
            "invalid-token",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
        ]

        for token in malformed_tokens:
            decoded = Authentication.decode_jwt(token, "access")
            assert decoded is None, f"Malformed token should be rejected: {token}"


@pytest.mark.unit
@pytest.mark.auth
class TestTokenRetrieval:
    """Test user retrieval from tokens."""

    @pytest.mark.django_db(transaction=True)
    async def test_retrieve_user_from_valid_token(self, verified_user):
        """Test retrieving user from a valid token."""
        token = Authentication.create_access_token(verified_user.id)

        # Save token to user (simulating login)
        verified_user.access = token
        await verified_user.asave()

        retrieved_user = await Authentication.retrieve_user_from_token(token)

        assert retrieved_user is not None
        assert retrieved_user.id == verified_user.id
        assert retrieved_user.email == verified_user.email

    @pytest.mark.django_db
    async def test_retrieve_user_from_expired_token(self, verified_user):
        """Test that expired token returns None."""
        # Create expired token
        past_time = datetime.now(UTC) - timedelta(hours=1)
        expired_token = jwt.encode(
            {
                "exp": past_time,
                "iat": past_time - timedelta(minutes=30),
                "user_id": str(verified_user.id),
                "jti": "test-jti",
                "type": "access",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        retrieved_user = await Authentication.retrieve_user_from_token(expired_token)
        assert retrieved_user is None

    @pytest.mark.django_db(transaction=True)
    async def test_retrieve_nonexistent_user(self):
        """Test retrieving a user that doesn't exist."""
        # Create token for non-existent user
        fake_user_id = "00000000-0000-0000-0000-000000000000"
        token = Authentication.create_access_token(fake_user_id)

        retrieved_user = await Authentication.retrieve_user_from_token(token)
        assert retrieved_user is None


@pytest.mark.unit
@pytest.mark.auth
class TestTokenPairCreation:
    """Test creation of token pairs for users."""

    @pytest.mark.django_db(transaction=True)
    async def test_create_tokens_for_user(self, verified_user):
        """Test creating both access and refresh tokens for a user."""
        access_token, refresh_token = await Authentication.create_tokens_for_user(
            verified_user
        )

        # Verify tokens are not empty
        assert access_token
        assert refresh_token

        # Verify tokens are different
        assert access_token != refresh_token

        # Verify access token contains user_id
        decoded_access = jwt.decode(access_token, options={"verify_signature": False})
        assert decoded_access["user_id"] == str(verified_user.id)

        # Verify refresh token structure
        decoded_refresh = jwt.decode(refresh_token, options={"verify_signature": False})
        assert decoded_refresh["type"] == "refresh"

    @pytest.mark.django_db(transaction=True)
    async def test_tokens_saved_to_user(self, verified_user):
        """Test that tokens are saved to user model."""
        access_token, refresh_token = await Authentication.create_tokens_for_user(
            verified_user
        )

        # Refresh user from database
        await verified_user.arefresh_from_db()

        assert verified_user.access == access_token
        assert verified_user.refresh == refresh_token

    @pytest.mark.django_db(transaction=True)
    async def test_old_tokens_invalidated(self, verified_user):
        """Test that old tokens are replaced when creating new ones."""
        # Create first set of tokens
        old_access, old_refresh = await Authentication.create_tokens_for_user(
            verified_user
        )

        # Create new set of tokens
        new_access, new_refresh = await Authentication.create_tokens_for_user(
            verified_user
        )

        # Verify tokens changed
        assert old_access != new_access
        assert old_refresh != new_refresh

        # Verify user has new tokens
        await verified_user.arefresh_from_db()
        assert verified_user.access == new_access
        assert verified_user.refresh == new_refresh


@pytest.mark.unit
@pytest.mark.auth
class TestGoogleOAuth:
    """Test Google OAuth validation logic."""

    @pytest.mark.django_db
    def test_validate_google_token_success(self):
        """Test successful Google token validation."""
        from django.conf import settings

        mock_id_info = {
            "sub": "1234567890",
            "email": "google_user@example.com",
            "name": "Google User",
            "picture": "https://example.com/pic.jpg",
            "email_verified": True,
            "aud": settings.GOOGLE_CLIENT_ID,
        }

        with patch(
            "google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info
        ):
            user_data, error_code, error_message = Authentication.validate_google_token(
                "fake-google-token"
            )

            assert user_data is not None
            assert user_data["email"] == "google_user@example.com"
            assert user_data["name"] == "Google User"
            assert error_code is None
            assert error_message is None

    @pytest.mark.django_db
    def test_validate_google_token_invalid(self):
        """Test handling of invalid Google token."""
        from google.auth.exceptions import GoogleAuthError

        with patch(
            "google.oauth2.id_token.verify_oauth2_token",
            side_effect=GoogleAuthError("Invalid token"),
        ):
            user_data, error_code, error_message = Authentication.validate_google_token(
                "invalid-token"
            )

            assert user_data is None
            assert error_code is not None
            assert error_message is not None

    @pytest.mark.django_db(transaction=True)
    async def test_store_google_user_new_user(self):
        """Test creating a new user from Google data."""
        user = await Authentication.store_google_user(
            email="newgoogle@example.com",
            name="New GoogleUser",
            avatar="https://example.com/pic.jpg",
        )

        assert user is not None
        assert user.email == "newgoogle@example.com"
        assert user.first_name == "New"
        assert user.last_name == "GoogleUser"
        assert user.is_email_verified is True  # Google users are pre-verified
        assert user.social_avatar == "https://example.com/pic.jpg"

    @pytest.mark.django_db(transaction=True)
    async def test_store_google_user_existing_user(self, verified_user):
        """Test retrieving existing user from Google data."""
        user = await Authentication.store_google_user(
            email=verified_user.email,
            name="Updated Name",
            avatar="https://example.com/new-pic.jpg",
        )

        assert user is not None
        assert user.id == verified_user.id
        assert user.email == verified_user.email
        # User data should be retrieved
        assert user.avatar is not None


@pytest.mark.unit
@pytest.mark.auth
class TestSecurityFeatures:
    """Test security-related token features."""

    @pytest.mark.django_db
    def test_token_signature_verification(self, verified_user):
        """Test that token signature is properly verified."""
        token = Authentication.create_access_token(verified_user.id)

        # Verify with correct secret
        decoded = Authentication.decode_jwt(token, "access")
        assert decoded is not None

        # Tamper with token
        parts = token.split(".")
        tampered_token = parts[0] + "." + parts[1] + ".tampered_signature"

        decoded_tampered = Authentication.decode_jwt(tampered_token, "access")
        assert decoded_tampered is None

    @pytest.mark.django_db
    def test_token_iat_validation(self, verified_user):
        """Test that issued-at time is validated."""
        token = Authentication.create_access_token(verified_user.id)
        decoded = jwt.decode(token, options={"verify_signature": False})

        # Verify iat is recent (within last minute)
        iat_time = datetime.fromtimestamp(decoded["iat"], UTC)
        now = datetime.now(UTC)
        time_diff = abs((now - iat_time).total_seconds())

        assert time_diff < 60, "Token IAT should be recent"

    @pytest.mark.django_db
    def test_jti_uniqueness(self, verified_user):
        """Test that JTI (JWT ID) is unique for each token."""
        token1 = Authentication.create_access_token(verified_user.id)
        token2 = Authentication.create_access_token(verified_user.id)

        decoded1 = jwt.decode(token1, options={"verify_signature": False})
        decoded2 = jwt.decode(token2, options={"verify_signature": False})

        assert decoded1["jti"] != decoded2["jti"], "JTI should be unique for each token"

    @pytest.mark.django_db
    def test_refresh_token_randomness(self):
        """Test that refresh tokens have random data for additional entropy."""
        token1 = Authentication.create_refresh_token()
        token2 = Authentication.create_refresh_token()

        decoded1 = jwt.decode(token1, options={"verify_signature": False})
        decoded2 = jwt.decode(token2, options={"verify_signature": False})

        # Verify random data exists and is different
        assert "data" in decoded1
        assert "data" in decoded2
        assert decoded1["data"] != decoded2["data"]
