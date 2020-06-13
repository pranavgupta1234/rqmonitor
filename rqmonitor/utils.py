import humanize
import redis
import os
import signal
import logging
import socket
from rq.registry import (StartedJobRegistry,
                         FinishedJobRegistry,
                         FailedJobRegistry,
                         DeferredJobRegistry,
                         ScheduledJobRegistry)
from rq.connections import resolve_connection
from rq.utils import utcparse
from rq.exceptions import InvalidJobOperationError
from rqmonitor.exceptions import ActionFailed
from datetime import datetime
from rq.worker import Worker
from rq.queue import Queue
from rq.job import Job


logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)



REGISTRIES = [StartedJobRegistry, FinishedJobRegistry,
              FailedJobRegistry, DeferredJobRegistry,
              ScheduledJobRegistry]

JobStatus = ['queued', 'finished', 'failed', 'started', 'deferred', 'scheduled']


def create_redis_connection(redis_url):
    return redis.Redis.from_url(redis_url)

def send_signal_worker(worker_id):
    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix+worker_id)
    worker_instance.request_stop(signum=2, frame=5)


def delete_queue(queue_id):
    """
    :param queue_id: Queue ID/name to delete
    :return: None

    As no specific exception is raised for below method
    we are using general Exception class for now
    """
    def attach_rq_queue_prefix(queue_id):
        return Queue.redis_queue_namespace_prefix + queue_id

    try:
        queue_instance = Queue.from_queue_key(attach_rq_queue_prefix(queue_id))
        queue_instance.delete()
    except Exception as e:
        raise ActionFailed


def empty_queue(queue_id):
    """
    :param queue_id: Queue ID/name to delete
    :return: None

    As no specific exception is raised for below method
    we are using general Exception class for now
    """
    def attach_rq_queue_prefix(queue_id):
        return Queue.redis_queue_namespace_prefix + queue_id

    try:
        queue_instance = Queue.from_queue_key(attach_rq_queue_prefix(queue_id))
        queue_instance.empty()
    except Exception as e:
        raise ActionFailed


def delete_workers(worker_ids, signal_to_pass=signal.SIGINT):
    """
    Expect worker ID without RQ REDIS WORKER NAMESPACE PREFIX of rq:worker:
    By default performs warm shutdown

    :param worker_id: list of worker id's to delete
    :param signal_to_pass:
    :return:
    """
    # find worker instance by key, refreshes worker implicitly
    def attach_rq_worker_prefix(worker_id):
        return Worker.redis_worker_namespace_prefix + worker_id

    try:
        for worker_instance in [Worker.find_by_key(attach_rq_worker_prefix(worker_id))
                                for worker_id in worker_ids]:
            # kill if on same instance
            if socket.gethostname() == worker_instance.hostname.decode('utf-8'):
                os.kill(worker_instance.pid, signal_to_pass)
    except ValueError:
        logger.warning('Problem in deleting workers {0}'.format(worker_ids))
        return False

    return True



def list_all_queues():
    """
    :return: Iterable for all available queue instances
    """
    return Queue.all()


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
    Create serialized version of Job which can be consumed by DataTable
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
            "job_exc_info": str(serialized_job['exc_info']),
            "job_status": serialized_job['status'],
            "job_queue": serialized_job['origin'],
            "job_enqueued_at": serialized_job['enqueued_at'],
            "job_created_at": serialized_job['created_at'],
            "job_created_time_humanize": humanize.naturaltime(utcparse(serialized_job['created_at']).timestamp()
                                                              - datetime.now().timestamp()),
            "job_enqueued_time_humanize": humanize.naturaltime(utcparse(serialized_job['enqueued_at']).timestamp()
                                                              - datetime.now().timestamp()),
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
            return Queue.from_queue_key(queue)
        else:
            return Queue.from_queue_key(Queue.redis_queue_namespace_prefix+queue)

    raise TypeError('{0} is not of class {1} or {2}'.format(queue, str, Queue))


def list_jobs_on_queue(queue):
    """
    If no worker has started jobs are not available in registries
    Worker does movement of jobs across registries
    :param queue: Queue to fetch jobs from
    :return: all valid jobs untouched by workers
    """
    queue = get_queue(queue)
    return queue.jobs


def list_job_ids_on_queue(queue):
    """
    If no worker has started jobs are not available in registries
    Worker does movement of jobs across registries
    :param queue: Queue to fetch jobs from
    :return: all valid jobs untouched by workers
    """
    queue = get_queue(queue)
    return queue.job_ids


def list_jobs_in_queue_all_registries(queue):
    """
    :param queue: List all jobs in all registries of given queue
    :return: list of jobs
    """
    jobs = []
    for registry in REGISTRIES:
        jobs.extend(list_jobs_in_queue_registry(queue, registry))
    return jobs


def list_jobs_in_queue_registry(queue, registry, start, end):
    """
    :param queue: Queue name from which jobs need to be listed
    :param registry: registry class from which jobs to be returned, default is all registries
    :return: list of all jobs matching above criteria
    """
    queue = get_queue(queue)
    if registry == StartedJobRegistry or registry == 'started':
        job_ids = queue.started_job_registry.get_job_ids(start, end)
        return [Job.fetch(job_id) for job_id in job_ids]
    elif registry == FinishedJobRegistry or registry == 'finished':
        job_ids = queue.finished_job_registry.get_job_ids(start, end)
        return [Job.fetch(job_id) for job_id in job_ids]
    elif registry == FailedJobRegistry or registry == 'failed':
        job_ids = queue.failed_job_registry.get_job_ids(start, end)
        return [Job.fetch(job_id) for job_id in job_ids]
    elif registry == DeferredJobRegistry or registry == 'deferred':
        job_ids = queue.deferred_job_registry.get_job_ids(start, end)
        return [Job.fetch(job_id) for job_id in job_ids]
    elif registry == ScheduledJobRegistry or registry == 'scheduled':
        job_ids = queue.scheduled_job_registry.get_job_ids(start, end)
        return [Job.fetch(job_id) for job_id in job_ids]
    # although not implemented as registry this is for ease
    elif registry == 'queued':
        return queue.get_jobs(start, end-start)
    else:
        return []


def list_job_ids_in_queue_registry(queue, registry, start=0, end=-1):
    """
    :param queue: Queue name from which jobs need to be listed
    :param registry: registry class from which jobs to be returned, default is all registries
    :return: list of all jobs matching above criteria
    """
    queue = get_queue(queue)
    if registry == StartedJobRegistry or registry == 'started':
        return queue.started_job_registry.get_job_ids(start, end)
    elif registry == FinishedJobRegistry or registry == 'finished':
        return queue.finished_job_registry.get_job_ids(start, end)
    elif registry == FailedJobRegistry or registry == 'failed':
        return queue.failed_job_registry.get_job_ids(start, end)
    elif registry == DeferredJobRegistry or registry == 'deferred':
        return queue.deferred_job_registry.get_job_ids(start, end)
    elif registry == ScheduledJobRegistry or registry == 'scheduled':
        return queue.scheduled_job_registry.get_job_ids(start, end)
    # although not implemented as registry this is for ease and uniformity
    elif registry == 'queued':
        return queue.get_job_ids(start, end-start)
    else:
        return []


def empty_registry(registry_name, queue_name, connection=None):
    """Empties a specific registry for a specific queue, Not in RQ, implemented
            here for performance reasons
    """
    redis_connection = resolve_connection(connection)

    queue_instance = Queue.from_queue_key(Queue.redis_queue_namespace_prefix+queue_name)

    registry_instance = None
    if registry_name == 'failed':
        registry_instance = queue_instance.failed_job_registry
    elif registry_name == 'started':
        registry_instance = queue_instance.started_job_registry
    elif registry_name == 'scheduled':
        registry_instance = queue_instance.scheduled_job_registry
    elif registry_name == 'deferred':
        registry_instance = queue_instance.deferred_job_registry
    elif registry_name == 'finished':
        registry_instance = queue_instance.finished_job_registry

    script = """
        local prefix = "{0}"
        local q = KEYS[1]
        local count = 0
        while true do
            local job_id, score = unpack(redis.call("zpopmin", q))
            if job_id == nil or score == nil then
                break
            end

            -- Delete the relevant keys
            redis.call("del", prefix..job_id)
            redis.call("del", prefix..job_id..":dependents")
            count = count + 1
        end
        return count
    """.format(registry_instance.job_class.redis_job_namespace_prefix).encode("utf-8")
    script = redis_connection.register_script(script)
    return script(keys=[registry_instance.key])


def delete_all_jobs_in_queues_registries(queues, registries):
    for queue in queues:
        for registry in registries:
            if registry == 'queued':
                # removes all jobs from queue and from job namespace
                get_queue(queue).empty()
            else:
                empty_registry(registry, queue)


def requeue_all_jobs_in_failed_registry(queues):
    fail_count = 0
    for queue in queues:
        failed_job_registry = get_queue(queue).failed_job_registry
        job_ids = failed_job_registry.get_job_ids()

        for job_id in job_ids:
            try:
                failed_job_registry.requeue(job_id)
            except InvalidJobOperationError:
                fail_count += 1

    return fail_count


def cancel_all_queued_jobs(queues):
    for queue in queues:
        job_ids = get_queue(queue).get_job_ids()
        for job_id in job_ids:
            Job.fetch(job_id).cancel()


def job_count_in_queue_registry(queue, registry):
    """
    :param queue: Queue name from which jobs need to be listed
    :param registry: registry class from which jobs to be returned, default is all registries
    :return: list of all jobs matching above criteria
    """
    queue = get_queue(queue)
    if registry == StartedJobRegistry or registry == 'started':
        return len(queue.started_job_registry)
    elif registry == FinishedJobRegistry or registry == 'finished':
        return len(queue.finished_job_registry)
    elif registry == FailedJobRegistry or registry == 'failed':
        return len(queue.failed_job_registry)
    elif registry == DeferredJobRegistry or registry == 'deferred':
        return len(queue.deferred_job_registry)
    elif registry == ScheduledJobRegistry or registry == 'scheduled':
        return len(queue.scheduled_job_registry)
    # although not implemented as registry this is for ease
    elif registry == 'queued':
        return len(queue)
    else:
        return 0


def get_redis_memory_used(connection=None):
    """
    All memory used in redis rq: namespace
    :param connection:
    :return:
    """
    RQ_REDIS_NAMESPACE = 'rq:*'
    redis_connection = resolve_connection(connection)
    script = """
        local sum = 0;
        local keys = {};
        local done = false;
        local cursor = "0"
        repeat
            local result = redis.call("SCAN", cursor, "match", ARGV[1])
            cursor = result[1];
            keys = result[2];
            for i, key in ipairs(keys) do
                local mem = redis.call("MEMORY", "USAGE", key);
                sum = sum + mem;
            end
            if cursor == "0" then
                done = true;
            end
        until done
        return sum;
    """
    script = redis_connection.register_script(script)
    return humanize.naturalsize(script(args=[RQ_REDIS_NAMESPACE]))


def delete_job(job_id):
    """
    Deleted job from the queue
    Does a implicit cancel with Job hash deleted
    :param job_id: Job id to be deleted
    :return: None
    """
    job_instance = Job.fetch(job_id)
    job_instance.delete(remove_from_queue=True)


def requeue_job(job_id):
    """
    Requeue job from the queue
    Will work only if job was failed
    :param job_id: Job id to be requeue
    :return: None

    """
    job_instance = Job.fetch(job_id)
    job_instance.requeue()


def cancel_job(job_id):
    """
    Only removes job from the queue
    :param job_id: Job id to be cancelled
    :return: None
    """
    job_instance = Job.fetch(job_id)
    job_instance.cancel()


def resolve_jobs(job_counts, start, length):

    start_block = 0
    cursor = 0
    jobs = []

    cumulative_count = 0
    for i, job_count in enumerate(job_counts):
        cumulative_count += job_count[2]
        if cumulative_count > start:
            start_block = i
            cursor = start - (cumulative_count - job_count[2])
            break

    for i, block in enumerate(job_counts[start_block:]):
        current_block_length = block[2]
        while cursor < current_block_length:
            current_block_jobs = list_jobs_in_queue_registry(block[0], block[1], cursor,
                                                             cursor+length)
            cursor += length
            jobs.extend(current_block_jobs)
            if len(jobs) >= length:
                return jobs
        cursor = 0

    return jobs
