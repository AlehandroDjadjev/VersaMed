import logging
import time

from django.conf import settings
from django.http import HttpResponse

from .xml_responses import build_error_response

logger = logging.getLogger("his_mock")


class HisMockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() != "authorization"
        }
        logger.info(
            "HIS mock request method=%s path=%s headers=%s body_bytes=%s",
            request.method,
            request.path,
            headers,
            len(request.body),
        )

        if not request.path.startswith("/v1/"):
            return self.get_response(request)

        latency_ms = max(0, int(settings.MOCK_LATENCY_MS))
        if latency_ms:
            time.sleep(latency_ms / 1000)

        if settings.MOCK_FORCE_ERROR:
            status = int(settings.MOCK_ERROR_STATUS)
            return self._error("MOCK_FORCED_ERROR", "Forced mock error", status)

        if not settings.MOCK_AUTH_DISABLED and not request.headers.get("Authorization"):
            return self._error(
                "AUTH_REQUIRED",
                "Authorization header is missing in mock mode",
                401,
            )

        return self.get_response(request)

    @staticmethod
    def _error(code, message, status):
        return HttpResponse(
            build_error_response(code, message, status),
            status=status,
            content_type="application/xml",
        )
