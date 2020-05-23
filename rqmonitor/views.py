from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import HttpResponse
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
from monitor.apps import MonitorConfig
from django.apps import apps

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


def delete_all_worker_api(request):
    worker_ids = []
    if request.method == 'POST':
        worker_ids = request.POST.get('worker_ids', None)
    success = 0
    failed = 0
    for worker_id in worker_ids:
        if delete_worker(worker_id):
            success+=1
        else:
            failed+=1

    ctx = {'successful': success, 'failed': failed}
    return HttpResponse(json.dumps(ctx), content_type='application/json')


def delete_single_worker_api(request):
    worker_id = None
    if request.method == 'POST':
        worker_id = request.POST.get('worker_id', None)

    # needs implementation to show properly on page
    if worker_id is None:
        return HttpResponse('Not Found')

    kill_result = delete_worker(worker_id)
    ctx = {'worker_id': worker_id, 'message': 'Successful' if kill_result else 'Failed'}
    return HttpResponse(json.dumps(ctx), content_type='application/json')

#24274a
def worker_info_api(request):
    worker_id = None
    if request.method == 'GET':
        worker_id = request.GET.get('worker_id', None)

    # needs implementation to show properly on page
    if worker_id is None:
        return HttpResponse('Not Found')

    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix + worker_id,
                                         connection=redis_connection)
    return HttpResponse(json.dumps({
        'worker_host_name': worker_instance.hostname.decode('utf-8'),
        'worker_ttl': worker_instance.default_worker_ttl,
        'worker_result_ttl': worker_instance.default_result_ttl,
        'worker_name': worker_instance.name,
        'worker_birth_date': worker_instance.birth_date.strftime('%d-%m-%Y %H:%M:%S')
                            if worker_instance.birth_date is not None else "Not Available",
        'worker_death_date': worker_instance.death_date.strftime('%d-%m-%Y %H:%M:%S')
                            if worker_instance.death_date is not None else "Is Alive",
        'worker_last_cleaned_at': worker_instance.last_cleaned_at.strftime('%d-%m-%Y %H:%M:%S')
                            if worker_instance.last_cleaned_at is not None else "Not Yet Cleaned",
        'worker_failed_job_count': worker_instance.failed_job_count,
        'worker_successful_job_count': worker_instance.successful_job_count,
        'worker_job_monitoring_interval': worker_instance.job_monitoring_interval,
        'worker_last_heartbeat': worker_instance.last_heartbeat.strftime('%d-%m-%Y %H:%M:%S')
                            if worker_instance.last_heartbeat is not None else "Not Available",
        'worker_current_job_id': worker_instance.get_current_job_id(),
    }), content_type='application/json')


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


def list_jobs_api(request):
    """
    :param request: Django GET request containing two parameters acting as filter for jobs
                    1) Jobs Status list (with these status)
                    2) queues list (to fetch queues)
    :return: rendered output
    """

    requested_queues = request.GET.getlist('queues[]', default=list_all_queues_names())
    requested_job_status = request.GET.getlist('jobstatus[]', default=list_all_possible_job_status())

    job_data_for_dashboard = []

    for queue in requested_queues:
        for job in list_jobs_on_queue(queue):
            if job.get_status() in requested_job_status:
                job_data_for_dashboard.append(reformat_job_data(job))
        # Include jobs from registries as well
        for job in list_jobs_in_queue_all_registries(queue):
            if job.get_status() in requested_job_status:
                job_data_for_dashboard.append(reformat_job_data(job))

    request_source = request.GET.get('from_datatable', None)

    return HttpResponse(json.dumps({
                                'rq_host_url': REDIS_RQ_HOST,
                                'data': job_data_for_dashboard,
                                }),
    content_type='application/json')


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