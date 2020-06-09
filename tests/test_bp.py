import unittest
import sys
import os
import redis
from rq import  pop_connection, push_connection

sys.path.insert(0, os.path.join(os.getcwd(), "../"))

from tests import RQMonitorTestCase



from rqmonitor.cli import create_app_with_blueprint

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500

class TestBlueprintViews(RQMonitorTestCase):

    def test_dashboard_ok(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, HTTP_OK)

    def test_redis_index_before_request(self):
        response = self.client.get('/', query_string={ 'redis_instance_index' : 100})
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_job_cancel_without_id(self):
        response = self.client.post('/jobs/cancel')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_job_delete_without_id(self):
        response = self.client.post('/jobs/delete')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_job_requeue_without_id(self):
        response = self.client.post('/jobs/requeue')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_queue_empty_without_id(self):
        response = self.client.post('/queues/empty')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_queue_delete_without_id(self):
        response = self.client.post('/queues/delete')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)
