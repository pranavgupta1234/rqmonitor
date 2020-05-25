from flask import (
    Blueprint,
    current_app,
    make_response,
    render_template,
    request,
    send_from_directory,
    url_for,
    jsonify
)
from six import string_types
from flask import Blueprint
from rqmonitor.utils import list_all_queues_names, list_all_possible_job_status, list_all_queues, \
    list_jobs_in_queue_all_registries, list_jobs_on_queue, list_jobs_in_queue_registry,\
    reformat_job_data, delete_worker, create_redis_connection, delete_queue, empty_queue

from rq.connections import pop_connection, push_connection
from rqmonitor.decorators import cache_control_no_store
from rqmonitor.exceptions import RQMonitorException, ActionFailed

from redis import Redis

from rq.worker import Worker
import logging

logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)

REDIS_RQ_HOST = 'localhost:6379'

monitor_blueprint = Blueprint('rqmonitor', __name__, template_folder='templates', static_folder='static')

# Plan to separate between HTTP and non HTTP errors by using HTTPException class
@monitor_blueprint.errorhandler(RQMonitorException)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@monitor_blueprint.before_app_first_request
def setup_redis_connection():
    redis_url = current_app.config.get("RQ_MONITOR_REDIS_URL")
    print(redis_url)
    if isinstance(redis_url, string_types):
        # update as tuple
        current_app.config["RQ_MONITOR_REDIS_URL"] = (redis_url,)
        current_app.redis_connection = create_redis_connection((redis_url,)[0])
    elif isinstance(redis_url, (tuple, list)):
        current_app.redis_connection = create_redis_connection(redis_url[0])
    else:
        raise RuntimeError("No Redis configuration!")


@monitor_blueprint.before_request
def push_rq_connection():
    new_instance_number = request.view_args.get("instance_number")
    if new_instance_number is not None:
        redis_url = current_app.config.get("RQ_MONITOR_REDIS_URL")
        if new_instance_number < len(redis_url):
            new_instance = create_redis_connection(redis_url[new_instance_number])
        else:
            raise LookupError("Index exceeds RQ list. Not Permitted.")
    else:
        new_instance = current_app.redis_connection
    push_connection(new_instance)
    current_app.redis_connection = new_instance


@monitor_blueprint.teardown_request
def pop_rq_connection(exception=None):
    pop_connection()


@monitor_blueprint.route('/', defaults={"instance_number": 0})
@cache_control_no_store
def home(instance_number):
    rq_queues_list = list_all_queues_names()
    rq_possible_job_status = list_all_possible_job_status()

    return render_template('rqmonitor/index.html', rq_host_url= REDIS_RQ_HOST,
                                                rq_queues_list= rq_queues_list,
                           rq_possible_job_status= rq_possible_job_status,
                           redis_instance_list=current_app.config.get('RQ_MONITOR_REDIS_URL'))


@monitor_blueprint.route('/jobs_dashboard')
@cache_control_no_store
def get_jobs_dashboard():
    return render_template('rqmonitor/jobs.html', rq_host_url= REDIS_RQ_HOST)


@monitor_blueprint.route('/workers_dashboard')
@cache_control_no_store
def get_workers_dashboard():
    return render_template('rqmonitor/workers.html', rq_host_url= REDIS_RQ_HOST)


@monitor_blueprint.route('/queues_dashboard')
@cache_control_no_store
def get_queues_dashboard():
    return render_template('rqmonitor/queues.html', rq_host_url=REDIS_RQ_HOST)


@monitor_blueprint.route('/queues')
@cache_control_no_store
def list_queues_api():
    queue_list = list_all_queues()
    rq_queues = []
    for queue in queue_list:
        rq_queues.append(
            {
                'queue_name': queue.name,
                'job_count': queue.count,
            }
        )

    return {
        'rq_host_url': REDIS_RQ_HOST,
        'rq_workers_count': len(rq_queues),
        'data': rq_queues,
    }


@monitor_blueprint.route('/workers')
@cache_control_no_store
def list_workers_api():
    workers_list = Worker.all()
    rq_workers = []
    for worker in workers_list:
        rq_workers.append(
            {
                'worker_name': worker.name,
                'listening_on': ', '.join(queue.name for queue in worker.queues),
                'status': worker.get_state(),
                'current_job_id': worker.get_current_job_id(),
                'success_jobs': worker.successful_job_count,
                'failed_jobs': worker.failed_job_count,
            }
        )

    return {
        'rq_host_url': REDIS_RQ_HOST,
        'rq_workers_count': len(rq_workers),
        'data': rq_workers,
    }


@monitor_blueprint.route('/jobs')
@cache_control_no_store
def list_jobs_api():
    """
    :param request: Django GET request containing two parameters acting as filter for jobs
                    1) Jobs Status list (with these status)
                    2) queues list (to fetch queues)
    :return: rendered output
    """
    requested_queues = request.args.getlist('queues[]')
    if requested_queues is None:
        requested_queues = list_all_queues_names()
    requested_job_status = request.args.getlist('jobstatus[]')
    if requested_job_status is None:
        requested_job_status = list_all_possible_job_status()

    job_data_for_dashboard = []

    for queue in requested_queues:
        for job in list_jobs_on_queue(queue):
            if job.get_status() in requested_job_status:
                job_data_for_dashboard.append(reformat_job_data(job))
        # Include jobs from registries as well
        for job in list_jobs_in_queue_all_registries(queue):
            if job.get_status() in requested_job_status:
                job_data_for_dashboard.append(reformat_job_data(job))

    request_source = request.args.get('from_datatable', None)

    return {
        'rq_host_url': REDIS_RQ_HOST,
        'data': job_data_for_dashboard,
    }

@monitor_blueprint.route('/workers/delete')
@cache_control_no_store
def delete_single_worker_api():
    worker_id = request.args.get('worker_id')
    if worker_id is None:
        raise RQMonitorException('Worker ID not received', status_code=400)
    try:
        delete_worker(worker_id)
    except ActionFailed:
        raise RQMonitorException(f'Unable to delete {worker_id}', status_code=500)

    return {
        'worker_id': worker_id,
        'message': f'Successfully deleted worker {worker_id}'
    }


@monitor_blueprint.route('/queues/delete')
@cache_control_no_store
def delete_queue_api():
    queue_id = request.args.get('queue_id', None)
    if queue_id is None:
        raise RQMonitorException('Queue Name not received', status_code=400)
    try:
        delete_queue(queue_id)
    except ActionFailed as e:
        raise RQMonitorException(f'Unable to delete Queue {queue_id}', status_code=500)
    return {
        'queue_id': queue_id,
        'message': f'Successfully deleted {queue_id}'
    }


@monitor_blueprint.route('/queues/empty')
@cache_control_no_store
def empty_queue_api():
    queue_id = request.args.get('queue_id', None)
    if queue_id is None:
        raise RQMonitorException('Queue Name not received', status_code=400)
    try:
        empty_queue(queue_id)
    except ActionFailed as e:
        raise RQMonitorException(f'Unable to empty Queue {queue_id}', status_code=500)
    return {
        'queue_id': queue_id,
        'message': f'Successfully emptied {queue_id}'
    }


@monitor_blueprint.route('/workers/info')
@cache_control_no_store
def worker_info_api():
    worker_id = None
    if request.method == 'GET':
        worker_id = request.args.get('worker_id', None)

    # needs implementation to show properly on page
    if worker_id is None:
        return "Not found"

    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix + worker_id)
    return {
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
    }
