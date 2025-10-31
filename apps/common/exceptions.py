from ninja.responses import Response
from http import HTTPStatus


class ErrorCode:
    UNAUTHORIZED_USER = "unauthorized_user"
    NETWORK_FAILURE = "network_failure"
    SERVER_ERROR = "server_error"
    INVALID_ENTRY = "invalid_entry"
    INCORRECT_EMAIL = "incorrect_email"
    INCORRECT_OTP = "incorrect_otp"
    EXPIRED_OTP = "expired_otp"
    INVALID_AUTH = "invalid_auth"
    INVALID_TOKEN = "invalid_token"
    INVALID_CLIENT_ID = "invalid_client_id"
    INVALID_CREDENTIALS = "invalid_credentials"
    UNVERIFIED_USER = "unverified_user"
    NON_EXISTENT = "non_existent"
    INVALID_OWNER = "invalid_owner"
    INVALID_PAGE = "invalid_page"
    INVALID_VALUE = "invalid_value"
    NOT_ALLOWED = "not_allowed"
    INVALID_DATA_TYPE = "invalid_data_type"
    INVALID_QUERY_PARAM = "invalid_query_param"
    RATE_LIMITED = "rate_limited"

    # kyc specific
    KYC_ALREADY_SUBMITTED = "kyc_already_submitted"
    KYC_NOT_FOUND = "kyc_not_found"
    KYC_INVALID_STATUS = "kyc_invalid_status"

    MISMATCH = "mismatch"
    VALIDATION_ERROR = "validation_error"

    EXTERNAL_SERVICE_ERROR = "external_service_error"
    BILL_PROVIDER_UNAVAILABLE = "bill_provider_unavailable"
    BILL_CUSTOMER_VALIDATION_FAILED = "bill_customer_validation_failed"

    # Payment specific
    PAYMENT_LINK_EXPIRED = "payment_link_expired"
    PAYMENT_LINK_INACTIVE = "payment_link_inactive"
    PAYMENT_ALREADY_PAID = "payment_already_paid"
    INVOICE_ALREADY_PAID = "invoice_already_paid"
    INVOICE_EXPIRED = "invoice_expired"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INVALID_API_KEY = "invalid_api_key"
    API_KEY_INACTIVE = "api_key_inactive"

    # Loan specific
    LOAN_PRODUCT_INACTIVE = "loan_product_inactive"
    LOAN_AMOUNT_BELOW_MIN = "loan_amount_below_min"
    LOAN_AMOUNT_ABOVE_MAX = "loan_amount_above_max"
    LOAN_TENURE_INVALID = "loan_tenure_invalid"
    LOAN_ALREADY_ACTIVE = "loan_already_active"
    LOAN_NOT_APPROVED = "loan_not_approved"
    LOAN_ALREADY_DISBURSED = "loan_already_disbursed"
    LOAN_NOT_ACTIVE = "loan_not_active"
    LOAN_ALREADY_PAID = "loan_already_paid"
    CREDIT_SCORE_TOO_LOW = "credit_score_too_low"
    ACCOUNT_AGE_INSUFFICIENT = "account_age_insufficient"
    COLLATERAL_REQUIRED = "collateral_required"
    GUARANTOR_REQUIRED = "guarantor_required"
    REPAYMENT_SCHEDULE_NOT_FOUND = "repayment_schedule_not_found"
    REPAYMENT_AMOUNT_INVALID = "repayment_amount_invalid"
    EARLY_REPAYMENT_NOT_ALLOWED = "early_repayment_not_allowed"

    # Investment specific
    INVESTMENT_PRODUCT_INACTIVE = "investment_product_inactive"
    INVESTMENT_PRODUCT_SOLD_OUT = "investment_product_sold_out"
    INVESTMENT_AMOUNT_BELOW_MIN = "investment_amount_below_min"
    INVESTMENT_AMOUNT_ABOVE_MAX = "investment_amount_above_max"
    INVESTMENT_DURATION_BELOW_MIN = "investment_duration_below_min"
    INVESTMENT_DURATION_ABOVE_MAX = "investment_duration_above_max"
    INVESTMENT_NOT_ACTIVE = "investment_not_active"
    INVESTMENT_NOT_MATURED = "investment_not_matured"
    INVESTMENT_EARLY_LIQUIDATION_NOT_ALLOWED = (
        "investment_early_liquidation_not_allowed"
    )
    INVESTMENT_RENEWAL_NOT_ALLOWED = "investment_renewal_not_allowed"
    INVESTMENT_RETURN_ALREADY_PAID = "investment_return_already_paid"

    # Compliance specific
    KYC_ALREADY_VERIFIED = "kyc_already_verified"
    KYC_PENDING = "kyc_pending"
    KYC_REQUIRED = "kyc_required"
    KYC_LEVEL_INSUFFICIENT = "kyc_level_insufficient"
    KYC_DOCUMENT_UPLOAD_FAILED = "kyc_document_upload_failed"
    AML_CHECK_FAILED = "aml_check_failed"
    SANCTIONS_MATCH_FOUND = "sanctions_match_found"
    TRANSACTION_FLAGGED = "transaction_flagged"
    COMPLIANCE_REVIEW_REQUIRED = "compliance_review_required"


class RequestError(Exception):
    default_detail = "An error occured"

    def __init__(
        self, err_code: str, err_msg: str, status_code: int = 400, data: dict = None
    ) -> None:
        self.status_code = HTTPStatus(status_code)
        self.err_code = err_code
        self.err_msg = err_msg
        self.data = data
        super().__init__()


class BodyValidationError(RequestError):
    """
    For field errors that aren't controlled directly in the schemas but needs to be called or validated manually in the endpoints
    """

    def __init__(self, field, field_err_msg):
        super().__init__(
            ErrorCode.INVALID_ENTRY, "Invalid Entry", 422, {field: field_err_msg}
        )


class NotFoundError(RequestError):
    """
    For not found errors
    """

    def __init__(self, err_msg):
        super().__init__(ErrorCode.NON_EXISTENT, err_msg, 404)


def validation_errors(exc):
    details = exc.errors
    modified_details = {}
    for error in details:
        field_name = error["loc"][-1]
        err_msg = error["msg"]
        err_type = error["type"]
        if err_type == "string_too_short":
            err_msg = f"{error['ctx']['min_length']} characters min"
        elif err_type == "string_too_long":
            err_msg = f"{error['ctx']['max_length']} characters max"
        elif err_type == "type_error.enum":
            allowed_enum_values = ", ".join(
                [value.name for value in error["ctx"]["enum_values"]]
            )
            err_msg = f"Invalid choice! Allowed: {allowed_enum_values}"
        modified_details[f"{field_name}"] = err_msg
    return Response(
        {
            "status": "failure",
            "code": ErrorCode.INVALID_ENTRY,
            "message": "Invalid Entry",
            "data": modified_details,
        },
        status=422,
    )


def request_errors(exc):
    err_dict = {
        "status": "failure",
        "code": exc.err_code,
        "message": exc.err_msg,
    }
    if exc.data:
        err_dict["data"] = exc.data
    return Response(err_dict, status=exc.status_code)
