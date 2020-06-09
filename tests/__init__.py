"""
Taken as reference from RQ's testing module
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from redis import Redis
from rq import pop_connection, push_connection
import unittest
from rqmonitor.cli import create_app_with_blueprint


def find_empty_redis_database():
    """Tries to connect to a random Redis database (starting from 4), and
        will use/connect it when no keys are in there.
    """
    for dbnum in range(4, 16):
        testconn = Redis(db=dbnum)
        empty = testconn.dbsize() == 0
        if empty:
            return testconn
    assert False, 'No empty Redis database found to run tests in.'



class RQMonitorTestCase(unittest.TestCase):
    """Base class to inherit test cases from for RQ Monitor.

    It sets up the Redis connection (available via self.testconn), turns off
    logging to the terminal and flushes the Redis database before and after
    running each test.

    Also offers assertQueueContains(queue, that_func) assertion method.
    """

    @classmethod
    def setUpClass(cls):
        # Set up connection to Redis
        testconn = find_empty_redis_database()

        # Store the connection (for sanity checking)
        cls.testconn = testconn

        # Shut up logging
        logging.disable(logging.ERROR)

        cls.app = create_app_with_blueprint()
        cls.app.testing = True
        cls.app.config['RQ_MONITOR_REDIS_URL'] = 'redis://127.0.0.1:6379'
        cls.client = cls.app.test_client()
        cls.app.redis_conn = testconn


    def setUp(self):
        # Flush beforewards (we like our hygiene)
        self.testconn.flushdb()

    def tearDown(self):
        # Flush afterwards
        self.testconn.flushdb()


    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

        # Pop the connection to Redis, it should be empty
        testconn = pop_connection()
        assert testconn == None, 'Corrupted Redis connection stack'
