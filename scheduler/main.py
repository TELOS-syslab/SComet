#!/usr/bin/python3
import container
import time
import math
import sys
import json

sys.path.append('/home/wjy/SComet')
from config import *
from container import *
from allocator import *
import scheduler

LC_TASKS = 'masstree'
THREADS = 16
MAX_LOAD = [12000, 14000, 16000, 18000]
QOS = 3 # ms

benchmark_set = 'microbenchmark'
if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
    print(f'benchmark set: {benchmark_set}')
else:
    print('Microbench name needed')
    exit(0)

lc_tasks = {}
for max_load in MAX_LOAD:
    lc_tasks[f"{LC_TASKS}-{max_load}"] = {
        "threads": THREADS,
        "max_load": max_load,
        "QoS": QOS,
        "commands": [f'/home/wjy/SComet/benchmarks/{benchmark_set}/script/{LC_TASKS}_real_time.sh {THREADS} {max_load} 600'],
    }

benchmark_list = []
be_tasks = {}
for root, dirs, files in os.walk(f'/home/wjy/SComet/benchmarks/{benchmark_set}/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_name = '.'.join(file.split('.')[0:-1])
            benchmark_list.append(benchmark_name)
            if LC_TASKS in benchmark_name:
                continue
            be_tasks[benchmark_name] = {
                "threads": 1,
                "commands": [f'bash /home/wjy/SComet/benchmarks/{benchmark_set}/script/{file} 1'],
            }
print(be_tasks.keys())

ip_list = ['172.17.1.73', '172.17.1.74', '172.17.1.75', '172.17.1.78']

PARTIES_scheduler = scheduler.Scheduler(benchmark_set, ip_list, lc_tasks, be_tasks)
PARTIES_scheduler.run()