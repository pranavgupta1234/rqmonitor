import traceback


class RQMonitorException(Exception):
    '''
    used to catch any possible exception that might occur in used libraries
    or while performing some action and display gracefully inside rqmonitor
    '''
    def __init__(self, message='RQ Monitor Global Exception',
                 status_code=500, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['traceback'] = ''.join(traceback.format_tb(self.__traceback__))
        return rv
