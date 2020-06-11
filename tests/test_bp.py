import unittest
import sys
import os
import json
import redis
from rq import  pop_connection, push_connection

sys.path.insert(0, os.path.join(os.getcwd(), "../"))

from tests import RQMonitorTestCase
from tests import fixtures
from rq.job import Job
from rq.queue import Queue
from rq.connections import _connection_stack
from rq.worker import Worker

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500
HTTP_METHOD_NOT_ALLOWED = 405

class TestBlueprintViews(RQMonitorTestCase):

    def test_dashboard_ok(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, HTTP_OK)

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

    def test_delete_worker_without_id(self):
        response = self.client.post('/workers/delete')
        self.assertEqual(response.status_code, HTTP_BAD_REQUEST)

    def test_queue_empty_api(self):
        some_queue = Queue(name='some_queue')
        job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
        some_queue.enqueue_job(job)

        response = self.client.post('/queues/empty', data={'queue_id': some_queue.name})
        self.assertEqual(response.status_code, HTTP_OK)
        self.assertEqual(some_queue.is_empty(), True)

    def test_queue_empty_api_via_get(self):
        some_queue = Queue(name='some_queue')
        job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
        some_queue.enqueue_job(job)

        response = self.client.get('/queues/empty', query_string={'queue_id': some_queue.name})
        self.assertEqual(response.status_code, HTTP_METHOD_NOT_ALLOWED)

    def test_queue_delete_api(self):
        some_queue = Queue(name='some_queue')
        job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
        some_queue.enqueue_job(job)

        response = self.client.post('/queues/delete', data={'queue_id': some_queue.name})
        self.assertEqual(response.status_code, HTTP_OK)

        queues_list_response = self.client.get('/queues', query_string={'queue_id': some_queue.name})
        json_resp = json.loads(queues_list_response.data.decode('utf-8'))
        self.assertEqual(json_resp["data"], [])

    def test_queues_delete_multiple(self):
        some_queues = ['q1', 'q2', 'q3', 'q4']
        some_queues_instances = []
        for queue in some_queues:
            some_queues_instances.append(Queue(name=queue))

        for queue in some_queues_instances:
            job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
            queue.enqueue_job(job)

        response = self.client.post('/queues/empty/all')

        self.assertEqual(response.status_code, HTTP_OK)
        for queue in some_queues_instances:
            self.assertEqual(queue.is_empty(), True)

    def test_redis_memory(self):
        response = self.client.get('/redis/memory')
        self.assertIn("redis_memory_used", json.loads(response.data.decode('utf-8')))

    def test_requeue_failed_jobs_without_queuelist(self):
        response = self.client.post('/jobs/requeue/all', data={})
        self.assertEqual(response.status_code, HTTP_OK)