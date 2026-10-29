from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    # Allow @role_required("admin") as well as @role_required(["admin", "staff"])
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            if user.is_superuser or getattr(user, "role", None) in allowed_roles:
                return view_func(request, *args, **kwargs)

            raise PermissionDenied

        return _wrapped_view
         
    return decorator