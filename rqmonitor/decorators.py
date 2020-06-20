import sys
import traceback
from functools import wraps
from flask import make_response
from rqmonitor.exceptions import RQMonitorException


def cache_control_no_store(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        _rendered_template = func(*args, **kwargs)
        _make_response = make_response(_rendered_template)
        _make_response.headers.set("Cache-Control", "no-store")
        return _make_response
    return _wrapper


def catch_global_exception(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            inner_response = func(*args, **kwargs)
        except Exception as e:
            tb = sys.exc_info()[2]
            error_message = getattr(e, 'message', None)
            status_code = getattr(e, 'status_code', None)
            kwargs = {}
            if error_message is not None:
                kwargs.update({'message': error_message})
            if status_code is not None:
                kwargs.update({'status_code': status_code})
            raise RQMonitorException(**kwargs).with_traceback(tb)
        return inner_response
    return _wrapper