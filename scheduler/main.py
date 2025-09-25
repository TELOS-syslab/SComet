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
import SComet_scheduler
import Paragon_scheduler
import SComet_Paragon_scheduler

LC_TASKS = 'masstree'
THREADS = 16
MAX_LOAD = [2500, 3000, 3500, 4000]
QOS = 5 # ms

benchmark_set = 'microbenchmark'
if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
    print(f'benchmark set: {benchmark_set}')
else:
    print('Microbench name needed')
    exit(0)

algorithm = "SComet"
if len(sys.argv) > 2:
    algorithm = sys.argv[2]
    print(f"Algorithm: {algorithm}")

constant = True
if len(sys.argv) > 3:
    constant = bool(int(sys.argv[3]))
    print(f"constant: {constant}")


lc_tasks = {}
phase = 0
for i, max_load in enumerate(MAX_LOAD):
    phase += 0.3
    if i % 2 == 0 or constant:
        lc_tasks[f"{LC_TASKS}-{max_load}"] = {
            "threads": THREADS,
            "max_load": max_load,
            "QoS": QOS,
            "commands": [f'bash /home/wjy/SComet/benchmarks/{benchmark_set}/script/{LC_TASKS}_real_time.sh'],
            "phase": -1
        }
    else:
        lc_tasks[f"{LC_TASKS}-{max_load}"] = {
            "threads": THREADS,
            "max_load": max_load,
            "QoS": QOS,
            "commands": [f'bash /home/wjy/SComet/benchmarks/{benchmark_set}/script/{LC_TASKS}_real_time.sh'],
            "phase": phase
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
                "commands": [f'bash /home/wjy/SComet/benchmarks/{benchmark_set}/script/{file}'],
            }
print(be_tasks.keys())

ip_list = ['172.17.1.72', '172.17.1.74', '172.17.1.73', '172.17.1.75']

for ip in ip_list:
    run_on_node(ip, f"mkdir -p /home/wjy/SComet/benchmarks/{benchmark_set}/QoS").wait()
    proc = run_on_node(ip, "docker ps -a --format '{{.ID}} {{.Names}}'")
    out, err = proc.communicate()
    containers = out.decode().strip().splitlines()
    to_delete = []
    for line in containers:
        cid, name = line.split(maxsplit=1)
        if name.startswith("lc_container") or name.startswith("be_container"):
            to_delete.append(cid)

    if to_delete:
        ids = " ".join(to_delete)
        print(f"Deleting containers {ids} on {ip}")
        run_on_node(ip, f"docker rm -f {ids}")
    else:
        print("No matching containers found.")

if algorithm == "SComet":
    SComet_scheduler = SComet_scheduler.SComet_Scheduler("SComet", benchmark_set, ip_list, lc_tasks, be_tasks)
    SComet_scheduler.run(0)
if algorithm == "PARTIES":
    PARTIES_scheduler = scheduler.Scheduler("PARTIES", benchmark_set, ip_list, lc_tasks, be_tasks)
    PARTIES_scheduler.run()
if algorithm == "Paragon":
    Paragon_scheduler = Paragon_scheduler.Paragon_Scheduler("Paragon", benchmark_set, ip_list, lc_tasks, be_tasks)
    Paragon_scheduler.run()
if algorithm == "SComet_Paragon":
    SComet_Paragon_scheduler = SComet_Paragon_scheduler.SComet_Paragon_Scheduler("SComet_Paragon", benchmark_set, ip_list, lc_tasks, be_tasks)
    SComet_Paragon_scheduler.run()