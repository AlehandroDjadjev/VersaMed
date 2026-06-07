from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie


@method_decorator(ensure_csrf_cookie, name="dispatch")
class EmptyHomeView(View):
    def get(self, request):
        return HttpResponse("", content_type="text/plain")
