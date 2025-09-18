from ninja.responses import Response


class CustomResponse:
    @staticmethod
    def success(message, data=None, status_code=200, og_resp=False):
        response_data = {
            "status": "success",
            "message": message,
            "data": data,
        }
        if data is None:
            response_data.pop("data", None)
        if og_resp:
            return Response(response_data, status=status_code)
        return status_code, response_data

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
