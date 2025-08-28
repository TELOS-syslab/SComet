#!/usr/bin/python3
import container
import time
import math
import sys
import json

sys.path.append('/home/wjy/SComet')
from config import *
from container import *
from allocater import *
import scheduler

LC_TASKS = ['masstree']

lc_tasks = {
    "masstree-500": {
        "threads": 8,
        "max_load": 500,
        "QoS": 3000,
        "commands": ['/home/wjy/SComet/benchmarks/test/script/masstree_real_time.sh 8 500 600'],
    },
    "masstree-1000": {
        "threads": 8,
        "max_load": 1000,
        "QoS": 3000,
        "commands": ['/home/wjy/SComet/benchmarks/test/script/masstree_real_time.sh 8 1000 600'],
    },
    "masstree-1500": {
        "threads": 8,
        "max_load": 1500,
        "QoS": 3000,
        "commands": ['/home/wjy/SComet/benchmarks/test/script/masstree_real_time.sh 8 1500 600'],
    },
    "masstree-2000": {
        "threads": 8,
        "max_load": 2000,
        "QoS": 3000,
        "commands": ['/home/wjy/SComet/benchmarks/test/script/masstree_real_time.sh 8 2000 600'],
    },
}

be_tasks = {
    "masstree-2000": {
        "threads": 8,
        "commands": ['/home/wjy/SComet/benchmarks/test/script/masstree_real_time.sh 8 2000 600'],
    },
}

benchmark_set = 'microbenchmark'
if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
    print(f'benchmark set: {benchmark_set}')
else:
    print('Microbench name needed')
    exit(0)

'''benchmark_list = []
lc_tasks = []
be_tasks = []
for root, dirs, files in os.walk(f'/home/wjy/SComet/{benchmark_set}/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_name = '.'.join(file.split('.')[0:-1])
            benchmark_list.append(benchmark_name)
            for LC in LC_TASKS:
                if LC in benchmark_name:
                    lc_tasks.append(benchmark_name)
                    break
            if benchmark_name not in LC_TASKS:
                be_tasks.append(benchmark_name)'''

ip_list = ['172.17.1.73', '172.17.1.74']

PARTIES_scheduler = scheduler.(benchmark_set, ip_list, lc_tasks, be_tasks)
PARTIES_scheduler.run()