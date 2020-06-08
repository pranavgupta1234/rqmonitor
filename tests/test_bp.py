import unittest
import sys
import os
import redis
from rq import  pop_connection, push_connection

sys.path.insert(0, os.path.join(os.getcwd(), "../"))

from rqmonitor.cli import create_app_with_blueprint

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500

class TestDecorators(unittest.TestCase):
    redis_client = None

    def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = redis.Redis()
        return self.redis_client

    def setUp(self):
        self.app = create_app_with_blueprint()
        self.app.testing = True
        self.app.config['RQ_MONITOR_REDIS_URL'] = 'redis://127.0.0.1'
        self.app.redis_conn = self.get_redis_client()
        push_connection(self.get_redis_client())
        self.client = self.app.test_client()

    def tearDown(self):
        pop_connection()

    def test_dashboard_ok(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, HTTP_OK)

    def test_redis_index_before_request(self):
        response = self.client.get('/', query_string={ 'redis_instance_index' : 100})
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_job_cancel_with_no_id(self):
        response = self.client.post('/jobs/cancel')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_job_delete_with_no_id(self):
        response = self.client.post('/jobs/delete')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_job_requeue_with_no_id(self):
        response = self.client.post('/jobs/requeue')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)
