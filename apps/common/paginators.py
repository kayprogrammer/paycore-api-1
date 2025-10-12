from typing import Any, List
from ninja.pagination import PaginationBase
from ninja import Schema
from asgiref.sync import sync_to_async
from apps.common.exceptions import RequestError, ErrorCode
import math


class CustomPagination(PaginationBase):
    class Output(Schema):
        items: List[Any]
        total: int
        limit: int
        page: int
        total_pages: int

    async def paginate_queryset(self, queryset, current_page, limit=50):
        if current_page < 1:
            raise RequestError(
                err_code=ErrorCode.INVALID_PAGE,
                err_msg="Invalid Page",
                status_code=404,
            )
        async_queryset = await sync_to_async(list)(queryset)
        queryset_count = await queryset.acount()
        items = async_queryset[(current_page - 1) * limit : current_page * limit]
        if queryset_count > 0 and not items:
            raise RequestError(
                err_code=ErrorCode.INVALID_PAGE,
                err_msg="Page number is out of range",
                status_code=400,
            )
        last_page = max(1, math.ceil(queryset_count / limit))
        return {
            "items": items,
            "total": queryset_count,
            "limit": limit,
            "page": current_page,
            "total_pages": last_page,
        }


Paginator = CustomPagination()
