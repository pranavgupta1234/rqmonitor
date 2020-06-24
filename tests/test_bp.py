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
from pprint import pprint

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

    def test_jobs_pagination_non_overlap(self):
        q1 = Queue('q1')
        q2 = Queue('q2')

        for i in range(12):
            job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
            q1.enqueue_job(job)
        for i in range(13):
            job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
            q2.enqueue_job(job)

        self.assertEqual(q1.count+q2.count, 25)

        query_string1 = {
            'start': 0,
            'length': 10,
            'draw': 1,
            'queues[]': ['q1', 'q2'],
            'jobstatus[]': ['queued', 'failed']
        }
        query_string2 = {
            'start': 10,
            'length': 10,
            'draw': 2,
            'queues[]': ['q1', 'q2'],
            'jobstatus[]': ['queued', 'failed']
        }
        query_string3 = {
            'start': 20,
            'length': 10,
            'draw': 3,
            'queues[]': ['q1', 'q2'],
            'jobstatus[]': ['queued', 'failed']
        }
        response1 = self.client.get('/jobs', query_string=query_string1)
        response1_json = json.loads(response1.data.decode('utf-8'))
        self.assertEqual(response1_json['draw'], 1)
        self.assertEqual(response1_json['recordsTotal'], 25)
        self.assertEqual(response1_json['recordsFiltered'], 25)
        self.assertEqual(len(response1_json['data']), 10)
        data1 = response1_json['data']
        data1_ids = [job['job_info']['job_id'] for job in data1]
        response2 = self.client.get('/jobs', query_string=query_string2)
        response2_json = json.loads(response2.data.decode('utf-8'))
        self.assertEqual(response2_json['draw'], 2)
        self.assertEqual(response2_json['recordsTotal'], 25)
        self.assertEqual(response2_json['recordsFiltered'], 25)
        self.assertEqual(len(response2_json['data']), 10)
        data2 = response2_json['data']
        data2_ids = [job['job_info']['job_id'] for job in data2]
        for job_id in data1_ids:
            self.assertNotIn(job_id, data2_ids)
        for job_id in data2_ids:
            self.assertNotIn(job_id, data1_ids)
        response3 = self.client.get('/jobs', query_string=query_string3)
        response3_json = json.loads(response3.data.decode('utf-8'))
        self.assertEqual(response3_json['draw'], 3)
        self.assertEqual(response3_json['recordsTotal'], 25)
        self.assertEqual(response3_json['recordsFiltered'], 25)
        self.assertEqual(len(response3_json['data']), 5)
        data3 = response3_json['data']
        for job_data in data2:
            self.assertNotIn(job_data, data3)
        for job_id in data1:
            self.assertNotIn(job_id, data2)