import sys
import os
from tests import RQMonitorTestCase
from tests import fixtures
from rq.job import Job
from rqmonitor.utils import fetch_job
from rq.exceptions import NoSuchJobError

sys.path.insert(0, os.path.join(os.getcwd(), "../"))

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500
HTTP_METHOD_NOT_ALLOWED = 405


class TestUtils(RQMonitorTestCase):
    def test_fetch_job(self):
        job = Job.create(func=fixtures.some_calculation, args=(3, 4), kwargs=dict(z=2))
        # will generate the job id lazily
        generated_jobid = job.get_id()
        job.save()
        fetched_job = fetch_job(generated_jobid)
        self.assertTrue(generated_jobid, fetched_job.get_id)
        with self.assertRaises(NoSuchJobError) as exc:
            none_job = fetch_job("somenonexistentid")