from django.shortcuts import render
from django.http import HttpResponse
from rq.worker import Worker
import redis
import json
import os
import signal
import logging
import multiprocessing
# Create your views here.

logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)


REDIS_RQ_HOST = 'localhost:6379'
redis_connection = redis.Redis(host='localhost', port=6379)

def index(request):
    return HttpResponse("You are at index!")


def list_workers_api(request):
    workers_list = Worker.all(connection=redis_connection)
    rq_workers = []
    for worker in workers_list:
        rq_workers.append(
            {
                'name': worker.name,
                'queues': ', '.join(queue.name for queue in worker.queues),
                'state': worker.get_state(),
                'current_job': worker.get_current_job(),
                'success_job_count': worker.successful_job_count,
                'failed_job_count': worker.failed_job_count,
            }
        )

    return render(request, 'monitor/workers.html', {
        'rq_workers': rq_workers,
        'rq_workers_count': len(rq_workers),
        'rq_host_url': REDIS_RQ_HOST,
    })


def refresh_workers_list_api(request):
    workers_list = Worker.all(connection=redis_connection)
    rq_workers = []
    for worker in workers_list:
        rq_workers.append(
            {
                'name': worker.name,
                'queues': ', '.join(queue.name for queue in worker.queues),
                'state': worker.get_state(),
                'current_job': worker.get_current_job(),
                'success_job_count': worker.successful_job_count,
                'failed_job_count': worker.failed_job_count,
            }
        )

    return render(request, 'monitor/table_workers.html', {
        'rq_workers': rq_workers,
        'rq_workers_count': len(rq_workers)
    })


def send_signal_worker(worker_id):
    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix+worker_id,
                                         connection=redis_connection)
    worker_instance.request_stop(signum=2, frame=5)


'''
Expect worker ID without RQ REDIS WORKER NAMESPACE PREFIX of rq:worker:
By default performs warm shutdown
'''
def delete_worker(worker_id, signal_to_pass=signal.SIGINT):
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


def worker_info_api(request):
    worker_id = None
    if request.method == 'GET':
        worker_id = request.GET.get('worker_id', None)

    # needs implementation to show properly on page
    if worker_id is None:
        return HttpResponse('Not Found')

    worker_instance = Worker.find_by_key(Worker.redis_worker_namespace_prefix + worker_id,
                                         connection=redis_connection)
    return render(request, 'monitor/worker_info.html', {
        'worker_ttl': worker_instance.default_worker_ttl,
        'worker_result_ttl': worker_instance.default_result_ttl,
        'worker_name': worker_instance.name,
        'worker_birth_date': worker_instance.birth_date,
        'worker_host_name': worker_instance.hostname,
        'worker_death_date': worker_instance.death_date,
        'worker_last_cleaned_at': worker_instance.last_cleaned_at,
        'worker_failed_job_count': worker_instance.failed_job_count,
        'worker_successful_job_count': worker_instance.successful_job_count,
        'worker_job_monitoring_interval': worker_instance.job_monitoring_interval,
        'worker_last_heartbeat': worker_instance.last_heartbeat,
        'worker_current_job_id': worker_instance.get_current_job_id()
    })


