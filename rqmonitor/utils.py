from django.shortcuts import render
from rq.worker import Worker
from rq.queue import Queue
from rq.job import Job
from rq.registry import (StartedJobRegistry,
                         FinishedJobRegistry,
                         FailedJobRegistry,
                         DeferredJobRegistry,
                         ScheduledJobRegistry)
from rq.utils import utcformat
import redis
import json
import os
import signal
import logging

logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)


REDIS_RQ_HOST = 'localhost:6379'
redis_connection = redis.Redis(host='localhost', port=6379)


REGISTRIES = [StartedJobRegistry, FinishedJobRegistry,
              FailedJobRegistry, DeferredJobRegistry,
              ScheduledJobRegistry]

JobStatus = ['queued', 'finished', 'failed', 'started', 'deferred', 'scheduled']


def send_signal_worker(worker_id):
    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix+worker_id,
                                         connection=redis_connection)
    worker_instance.request_stop(signum=2, frame=5)


def delete_worker(worker_id, signal_to_pass=signal.SIGINT):
    """
    Expect worker ID without RQ REDIS WORKER NAMESPACE PREFIX of rq:worker:
    By default performs warm shutdown

    :param worker_id:
    :param signal_to_pass:
    :return:
    """
    # find worker instance by key, refreshes worker implicitly
    try:
        worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix + worker_id,
                                         connection=redis_connection)
        os.kill(worker_instance.pid, signal_to_pass)
    except ValueError:
        logger.warning(f'Unable to find worker with ID {worker_id}')
        return False

    return True


def list_all_queues():
    """
    :return: Iterable for all available queue instances
    """
    return Queue.all(connection=redis_connection)


def list_all_possible_job_status():
    """
    :return: list of all possible job status
    """
    return JobStatus


def list_all_queues_names():
    """
    :return: Iterable of all queue names
    """
    return [queue.name for queue in list_all_queues()]


def reformat_job_data(job: Job):
    """
    Create serialized version of Job which can be consumer  by DataTable
    (RQ provides to_dict) including origin(queue), created_at, data, description,
    enqueued_at, started_at, ended_at, result, exc_info, timeout, result_ttl,
     failure_ttl, status, dependency_id, meta, ttl

    :param job: Job Instance need to be serialized
    :return: serialized job
    """
    serialized_job = job.to_dict()
    # remove decompression
    serialized_job['exc_info'] = job.exc_info
    return {
        "job_info": {
            "job_id": job.id,
            "job_func": job.func_name,
            "job_description": serialized_job['description'],
            "job_exc_info": serialized_job['exc_info'],
            "job_status": serialized_job['status'],
            "job_queue": serialized_job['origin'],
            "job_ttl": "Infinite" if job.get_ttl() is None else job.get_ttl(),
            "job_timeout":"Infinite" if job.timeout is None else job.timeout,
            "job_result_ttl": '500s' if job.result_ttl is None else job.result_ttl,
            "job_fail_ttl": '1y' if job.failure_ttl is None else job.failure_ttl,
        },
    }


def get_queue(queue):
    """
    :param queue: Queue Name or Queue ID or Queue Redis Key or Queue Instance
    :return: Queue instance
    """
    if isinstance(queue, Queue):
        return queue

    if isinstance(queue, str):
        if queue.startswith(Queue.redis_queue_namespace_prefix):
            return Queue.from_queue_key(queue, connection=redis_connection)
        else:
            return Queue.from_queue_key(Queue.redis_queue_namespace_prefix+queue,
                                        connection=redis_connection)

    raise TypeError(f'{queue} is not of class {str} or {Queue}')


def list_jobs_on_queue(queue):
    """
    If no worker has started jobs are not available in registries
    Worker does movement of jobs across registries
    :param queue: Queue to fetch jobs from
    :return: all valid jobs untouched by workers
    """
    queue = get_queue(queue)
    return queue.jobs


def list_jobs_in_queue_all_registries(queue):
    """
    :param queue: List all jobs in all registries of given queue
    :return: list of jobs
    """
    jobs = []
    for registry in REGISTRIES:
        jobs.extend(list_jobs_in_queue_registry(queue, registry))
    return jobs


def list_jobs_in_queue_registry(queue, registry):
    """
    :param queue: Queue name from which jobs need to be listed
    :param registry: registry class from which jobs to be returned, default is all registries
    :return: list of all jobs matching above criteria
    """
    queue = get_queue(queue)
    if registry == StartedJobRegistry:
        job_ids = queue.started_job_registry.get_job_ids()
        return [Job.fetch(job_id, connection=redis_connection) for job_id in job_ids]
    elif registry == FinishedJobRegistry:
        job_ids = queue.finished_job_registry.get_job_ids()
        return [Job.fetch(job_id, connection=redis_connection) for job_id in job_ids]
    elif registry == FailedJobRegistry:
        job_ids = queue.failed_job_registry.get_job_ids()
        return [Job.fetch(job_id, connection=redis_connection) for job_id in job_ids]
    elif registry == DeferredJobRegistry:
        job_ids = queue.deferred_job_registry.get_job_ids()
        return [Job.fetch(job_id, connection=redis_connection) for job_id in job_ids]
    elif registry == ScheduledJobRegistry:
        job_ids = queue.scheduled_job_registry.get_job_ids()
        return [Job.fetch(job_id, connection=redis_connection) for job_id in job_ids]
    else:
        raise TypeError(f'{registry} : Invalid Registry class supplied')