class CustomResponse:
    @staticmethod
    def success(message, data=None, status_code=200):
        response = {
            "status": "success",
            "message": message,
            "data": data,
        }
        if data is None:
            response.pop("data", None)
        return status_code, response

    @staticmethod
    def error(message, err_code, data=None, status_code=400):
        response = {
            "status": "failure",
            "message": message,
            "code": err_code,
            "data": data,
        }
        if data is None:
            response.pop("data", None)
        return status_code, response
