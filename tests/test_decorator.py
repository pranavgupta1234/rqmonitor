import unittest
import sys
import os
import redis
from rq import pop_connection, push_connection
from rqmonitor.cli import create_app_with_blueprint

sys.path.insert(0, os.path.join(os.getcwd(), "../"))

HTTP_OK = 200


class TestDecorators(unittest.TestCase):
    redis_client = None

    def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = redis.Redis()
        return self.redis_client

    def setUp(self):
        self.app = create_app_with_blueprint()
        self.app.testing = True
        self.app.config["RQ_MONITOR_REDIS_URL"] = "redis://127.0.0.1"
        self.app.redis_conn = self.get_redis_client()
        push_connection(self.get_redis_client())
        self.client = self.app.test_client()

    def tearDown(self):
        pop_connection()

    def test_cache_control_no_store(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
