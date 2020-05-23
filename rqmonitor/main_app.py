from flask import Flask
from flask import request
from flask.templating import render_template
from utils import (list_all_queues_names,
                    list_all_possible_job_status,
                    list_all_queues,
                    list_jobs_in_queue_all_registries,
                    list_jobs_on_queue,
                    list_jobs_in_queue_registry,
                    reformat_job_data,
                    delete_worker)

from redis import Redis

from rq.worker import Worker
import logging

logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)

app = Flask(__name__, template_folder='templates', static_folder='static')

REDIS_RQ_HOST = 'localhost:6379'
redis_connection = Redis(host='localhost', port=6379)


@app.route('/')
def home():
    rq_queues_list = list_all_queues_names()
    rq_possible_job_status = list_all_possible_job_status()

    return render_template('rqmonitor/index.html', rq_host_url= REDIS_RQ_HOST,
                                                rq_queues_list= rq_queues_list,
                           rq_possible_job_status= rq_possible_job_status)


@app.route('/jobs_dashboard/')
def get_jobs_dashboard():
    return render_template('rqmonitor/jobs.html', rq_host_url= REDIS_RQ_HOST)


@app.route('/workers_dashboard/')
def get_workers_dashboard():
    return render_template('rqmonitor/workers.html', rq_host_url= REDIS_RQ_HOST)


@app.route('/queues_dashboard/')
def get_queues_dashboard():
    return render_template('rqmonitor/queues.html', rq_host_url=REDIS_RQ_HOST)


@app.route('/queues/')
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


@app.route('/workers/')
def list_workers_api():
    workers_list = Worker.all(connection=redis_connection)
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


@app.route('/jobs/')
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

@app.route('/workers/delete/')
def delete_single_worker_api():
    worker_id = request.args.get('worker_id')

    # needs implementation to show properly on page
    if worker_id is None:
        return {'message' : 'Not found'}

    kill_result = delete_worker(worker_id)
    ctx = {'worker_id': worker_id, 'message': 'Successful' if kill_result else 'Failed'}
    return ctx


@app.route('/worker/info/')
def worker_info_api():
    worker_id = None
    if request.method == 'GET':
        worker_id = request.args.get('worker_id', None)

    # needs implementation to show properly on page
    if worker_id is None:
        return "Not found"

    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix + worker_id,
                                         connection=redis_connection)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8899, debug=True)