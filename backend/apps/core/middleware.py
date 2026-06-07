from django.conf import settings


class StaleSessionCleanupMiddleware:
    """
    Remove anonymous empty sessions so a stale or corrupted session cookie
    does not keep triggering Django's decode warning on every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        session_cookie_name = settings.SESSION_COOKIE_NAME
        has_session_cookie = session_cookie_name in request.COOKIES
        is_authenticated = getattr(request.user, "is_authenticated", False)

        if has_session_cookie and not is_authenticated and not request.session.keys():
            response.delete_cookie(
                session_cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

        return response
