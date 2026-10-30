"""Optional pagination: DRF returns `results` only when ?page= is supplied."""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

# Hard cap on any client-provided page size, so a single request can never
# serialise the whole table (data-blast / amplification protection).
MAX_PAGE_SIZE = 100


class OptionalPagination(PageNumberPagination):
    """All paginate request pages=1 but list endpoints without ?page= return raw lists."""

    page_size_query_param = "page_size"

    def _requested_page_size(self, request) -> int:
        """Tolerant parse of ?page_size=: invalid values fall back to the
        default (never a 500), and the result is always capped."""
        raw = request.query_params.get("page_size")
        if raw is None or not str(raw).strip():
            return self.page_size
        try:
            size = int(str(raw).strip())
        except (TypeError, ValueError):
            return self.page_size
        return max(1, min(size, MAX_PAGE_SIZE))

    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get("page") is None:
            return None  # skip pagination entirely
        self.page_size = self._requested_page_size(request)
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
        # ?page= not supplied: return a plain list, but never dump the whole
        # table - cap the response at MAX_PAGE_SIZE rows.
        serializer = serializer_class(queryset[:MAX_PAGE_SIZE], many=True, context=ctx)
        return Response(serializer.data)
    serializer = serializer_class(qs, many=True, context=ctx)
    return paginator.get_paginated_response(serializer.data)
