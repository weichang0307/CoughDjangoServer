from __future__ import annotations

from time import perf_counter


class RequestPathLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = perf_counter()
        response = self.get_response(request)
        duration_ms = (perf_counter() - started_at) * 1000
        print(
            "[request] "
            f"{request.method} {request.path} "
            f"status={response.status_code} "
            f"duration_ms={duration_ms:.1f}"
        )
        return response
