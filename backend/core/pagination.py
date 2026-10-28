"""Optional pagination: DRF returns `results` only when ?page= is supplied."""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class OptionalPagination(PageNumberPagination):
    """All paginate request pages=1 but list endpoints without ?page= return raw lists."""

    page_size_query_param = "page_size"

    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get("page") is None:
            return None  # skip pagination entirely
        self.page_size = int(request.query_params.get("page_size", 10))
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "pages": self.page.paginator.num_pages,
                "page": self.page.number,
                "results": data,
            }
        )


def paginate_response(serializer_class, request, queryset, context=None):
    """Serialization helper: paginate only when ?page= is present."""
    paginator = OptionalPagination()
    ctx = context or {"request": request}
    qs = paginator.paginate_queryset(queryset, request)
    if qs is None:
        # ?page= not supplied: return the complete list without pagination.
        serializer = serializer_class(queryset, many=True, context=ctx)
        return Response(serializer.data)
    serializer = serializer_class(qs, many=True, context=ctx)
    return paginator.get_paginated_response(serializer.data)
