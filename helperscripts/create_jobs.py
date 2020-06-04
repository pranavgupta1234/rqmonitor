from rq import Queue, Worker
from tqdm import tqdm
from rq.job import Job
import time
import random
import redis

TOTAL_JOBS=500000
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
JOB_TIMEOUT = 100 # keep greater than job processing time for testing

queues = ['queue1', 'queue2', 'queue3', 'queue4', 'queue5', 'high', 'default', 'low']

#redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# create job which takes random time to complete
def func():
    time.sleep(random.randint(10, 50))

def main():
    queue_instances = []
    # create queues
    for queue_name in queues:
        queue_instances.append(Queue(name=queue_name, connection=redis_client))

    for i in tqdm(range(TOTAL_JOBS)):
        #create and submit on any random queue einstance
        queue_instances[random.randint(0, len(queue_instances)-1)].\
            enqueue_job(Job.create(func=func, connection=redis_client, timeout=JOB_TIMEOUT))


if __name__ == '__main__':
    main()
