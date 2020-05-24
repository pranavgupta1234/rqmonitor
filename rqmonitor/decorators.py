from functools import wraps
from flask import make_response

def cache_control_no_store(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        _rendered_template = func(*args, **kwargs)
        _make_response = make_response(_rendered_template)
        _make_response.headers.set("Cache-Control", "no-store")
        return _make_response
    return _wrapper