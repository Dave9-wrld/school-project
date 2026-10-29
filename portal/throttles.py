from rest_framework.throttling import SimpleRateThrottle
import hashlib


class LoginRateThrottle(SimpleRateThrottle):
    scope = 'login'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class RegistrationRateThrottle(LoginRateThrottle):
    scope = 'register'


class ResetRequestThrottle(LoginRateThrottle):
    scope = 'password_reset'


class ResetConfirmThrottle(LoginRateThrottle):
    scope = 'password_reset_confirm'


class ResetEmailThrottle(SimpleRateThrottle):
    scope = 'password_reset_email'

    def get_cache_key(self, request, view):
        email = str(request.data.get('email', '') if hasattr(request.data, 'get') else '').strip().casefold()
        digest = hashlib.sha256(email.encode()).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': digest}
