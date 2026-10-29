import math

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .throttles import LoginRateThrottle


class BrowserLoginThrottleMiddleware(MiddlewareMixin):
    """Apply the same login limit to the portal, DRF browser login and admin."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method == 'POST' and request.resolver_match.url_name == 'login':
            throttle = LoginRateThrottle()
            if not throttle.allow_request(request, view_func):
                wait = math.ceil(throttle.wait())
                response = JsonResponse({'detail': f'Too many login attempts. Try again in {wait} seconds.'}, status=429)
                response['Retry-After'] = str(wait)
                return response
