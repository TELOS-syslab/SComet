#!/usr/bin/python3
import container
import time
import math
import sys
import json
import copy
import random
from datetime import datetime

sys.path.append('/home/wjy/SComet')
from config import *
from container import *
from allocator import *


def sin_value(max_val, min_val, theta):
    A = (max_val - min_val) / 2   # 振幅
    C = (max_val + min_val) / 2   # 中心值
    return C + A * math.sin(math.pi * theta)

class Scheduler:
    def __init__(self, name_, benchmark_set_, ip_list_, lc_tasks_, be_tasks_):
        self.benchmark_set = benchmark_set_
        self.name = name_
        self.lc_tasks = lc_tasks_
        self.be_tasks = be_tasks_
        self.all_lc = copy.deepcopy(lc_tasks_)
        self.all_be = copy.deepcopy(be_tasks_)
        self.node_dict = {}
        for ip in ip_list_:
            print(f"Generating Allocator for {ip}")
            self.node_dict[ip] = Allocator(self.benchmark_set, lc_tasks_, be_tasks_, ip)
            run_on_node(ip, f'rm -rf /home/wjy/SComet/benchmarks/{benchmark_set_}/QoS/*')

    def lc_algorithm(self):
        print("Choosing LC to run...")
        for lc in self.lc_tasks:
            i = list(self.all_lc).index(lc)
            ip = list(self.node_dict)[i % len(list(self.node_dict))]
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if not self.node_dict[ip].lc_containers or QoS_status == 1:
                return lc, ip
        print("Warning! No available node for LC task")
        return None, None

    def be_algorithm(self):
        max_slack = 0
        max_ip = None
        for ip in self.node_dict:
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if QoS_status == 1:
                if max_slack < slack_list[0][1]["slack"]:
                    max_slack = slack_list[0][1]["slack"]
                    max_ip = ip
        if max_ip and self.be_tasks:
            return random.choice(list(self.be_tasks)), max_ip
        return None, None

    def prune(self):
        for ip in self.node_dict:
            finished_lc, finished_be = self.node_dict[ip].prune()
            for task in finished_lc:
                self.lc_tasks[task] = self.all_lc[task]

    def reallocate(self):
        for ip in self.node_dict:
            result = self.node_dict[ip].reallocate()
            if result == -1:
                print(f"Remove BE tasks from {ip}")
                self.node_dict[ip].remove_newest_be_task()

    def run(self):
        start_time = time.time()
        while True:
            time.sleep(1)
            print(f'\n\ntime {time.time() - start_time}:')
            self.prune()
            self.reallocate()

            print()
            for ip in self.node_dict:
                print(f'IP: {ip} status')
                for container in self.node_dict[ip].lc_containers.values():
                    print(container)
                for container in self.node_dict[ip].be_containers.values():
                    print(container)
            for ip in self.node_dict:
                self.node_dict[ip].get_QoS_status(True)

            while self.lc_tasks:
                print()
                lc, lc_ip = self.lc_algorithm()
                if not lc:
                    continue
                print(f"Try to run {lc}")
                threads = self.lc_tasks[lc]["threads"]
                if  self.lc_tasks[lc]["phase"] < 0:
                    rps = int(self.lc_tasks[lc]["max_load"])
                else:
                    rps = int(self.lc_tasks[lc]["max_load"] * sin_value(1, 0.5, (time.time() - start_time) / 1800 + self.lc_tasks[lc]["phase"]))
                run_time = 300
                command = f'{self.lc_tasks[lc]["commands"][0]} {threads} {rps} {run_time}'
                if self.node_dict[lc_ip].run_lc_task(lc, command):
                    self.lc_tasks.pop(lc)
                    time.sleep(1)

            print()
            be, be_ip = self.be_algorithm()
            if be:
                print(f"Try to run {be}")
                threads = self.be_tasks[be]["threads"]
                command = f'{self.be_tasks[be]["commands"][0]} {threads}'
                if self.node_dict[be_ip].run_be_task(be, command):
                    self.be_tasks.pop(be)
                    time.sleep(1)
                print('be task remain %d :' % len(self.be_tasks), self.be_tasks.keys())

            if not self.be_tasks:
                finished = True
                for ip in self.node_dict:
                    if self.node_dict[ip].be_containers:
                        finished = False
                if finished:
                    print('finished')
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_dir = os.path.join(os.getcwd(), f"{self.name}_{timestamp}")
                    os.makedirs(output_dir, exist_ok=True)
                    for ip in self.node_dict:
                        print(ip)
                        with open(os.path.join(output_dir, f'{ip}_latency_result.txt'), mode='w') as result_f:
                            result_f.write(json.dumps(self.node_dict[ip].latency_result))
                        with open(os.path.join(output_dir, f'{ip}_violate_result.txt'), mode='w') as result_f:
                            result_f.write(json.dumps(self.node_dict[ip].violate_result))
                        self.node_dict[ip].kill_all()
                    break