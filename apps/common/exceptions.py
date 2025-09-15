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


class ValidationError(RequestError):
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
