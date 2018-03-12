import json
import argparse
import requests
from semaphore import Semaphore
import logging
import time

parser = argparse.ArgumentParser()
def doit(endpoint_url, lock_path):
    while True:
        s = Semaphore(service_name=lock_path, concurrency_limit=1, host_url=endpoint_url)
        print('Attempting to get the lock')
        s.acquire(True)
        print('I has the lockz!!!')
        time.sleep(3)
        print('Releasing lock')
        time.sleep(1)
        s.release()

if __name__ == '__main__':
    parser.add_argument("--endpoint-url", default="localhost:8500", help="endpoint url, default: http://localhost:8500")
    parser.add_argument("--lock-path", default="semaphoretest", help="the KV path to lock with, default: semaphoretest")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    log_level = args.log_level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % log_level)
    logging.basicConfig(level=numeric_level)

    _log = logging.getLogger(__name__)

    endpoint_url = args.endpoint_url
    lock_path = args.lock_path
    print(f'endpoint url: {endpoint_url}')
    print(f'lock path: {lock_path}')
    doit(endpoint_url, lock_path)





