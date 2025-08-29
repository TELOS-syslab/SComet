#!/usr/bin/python3
import container
import time
import math
import sys
import json
import copy

sys.path.append('/home/wjy/SComet')
from config import *
from container import *
from allocator import *

lc_task_example = {
    "memcached": {
        "threads": 8,
        "max_load": 1000,
        "QoS": 1000,
        "commands": [],
    },
    "nginx": {
        "threads": 8,
        "max_load": 1000,
        "QoS": 1000,
        "commands": [],
    },
}

be_task_example = {
    "lbm": {
        "threads": 8,
        "commands": [],
    },
}


class Scheduler:
    def __init__(self, benchmark_set_, ip_list_, lc_tasks_=lc_task_example, be_tasks_=be_task_example):
        self.benchmark_set = benchmark_set_
        self.lc_tasks = lc_tasks_
        self.be_tasks = be_tasks_
        self.all_lc = copy.deepcopy(lc_tasks_)
        self.all_be = copy.deepcopy(be_tasks_)
        self.node_dict = {}
        for ip in ip_list_:
            print(f"Generating Allocator for {ip}")
            self.node_dict[ip] = Allocator(self.benchmark_set, lc_tasks_, be_tasks_, ip)

    def lc_algorithm(self):
        max_slack = 0
        max_ip = None
        for ip in self.node_dict:
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if not self.node_dict[ip].lc_containers and self.lc_tasks:
                return list(self.lc_tasks)[0], ip
            if QoS_status == 1:
                if max_slack < slack_list[0][1]["slack"]:
                    max_slack = slack_list[0][1]["slack"]
                    max_ip = ip
        if max_ip and self.lc_tasks:
            return list(self.lc_tasks)[0], max_ip
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
            return list(self.be_tasks)[0], max_ip
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
            time.sleep(5)
            print(f'\ntime {time.time() - start_time}:')
            self.prune()
            self.reallocate()

            for ip in self.node_dict:
                print(f"lc on {ip}: ", self.node_dict[ip].lc_containers)
                print(f"be on {ip}: ", self.node_dict[ip].be_containers)

            while self.lc_tasks:
                lc, lc_ip = self.lc_algorithm()
                if not lc:
                    continue
                self.node_dict[lc_ip].run_lc_task(lc, self.lc_tasks[lc]["commands"])
                self.lc_tasks.pop(lc)
                time.sleep(5)

            be, be_ip = self.be_algorithm()
            if be:
                self.node_dict[be_ip].run_be_task(be, self.be_tasks[be]["commands"])
                self.be_tasks.pop(be)
                print('be task remain %d :' % len(self.be_tasks), self.be_tasks)
                time.sleep(5)

            if not self.be_tasks:
                finished = True
                for ip in self.node_dict:
                    if self.node_dict[ip].be_containers:
                        finished = False
                if finished:
                    print('finished')
                    for ip in self.node_dict:
                        print(ip)
                        with open(f'{ip}_latency_result.txt', mode='w') as result_f:
                            result_f.write(json.dumps(self.node_dict[ip].latency_result))
                        with open(f'{ip}_violate_result.txt', mode='w') as result_f:
                            result_f.write(json.dumps(self.node_dict[ip].violate_result))
                        self.node_dict[ip].kill_all()
                    break