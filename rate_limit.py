"""Single shared slowapi Limiter instance, keyed by client IP (X-Forwarded-For aware)."""
from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request):
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func)
