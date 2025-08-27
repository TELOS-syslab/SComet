#!/usr/bin/python3
import allocater
import container
import time
import math
import sys
import json

sys.path.append('/home/wjy/SComet')
import exe

lc_task_example = {
    "memcached": {
        "threads": 8,
        "max_load": 1000,
        "QoS": 1000,
    },
    "nginx": {
        "threads": 8,
        "max_load": 1000,
        "QoS": 1000,
    },
}

be_task_example = {
    "lbm": {
        "threads": 8,
    },
}


class Scheduler:
    def __init__(self, benchmark_set_, lc_tasks_, be_tasks_, ip_list_):
        self.benchmark_set = benchmark_set_
        self.lc_tasks = lc_tasks_
        self.be_tasks = be_tasks_
        self.all_lc = lc_tasks_
        self.all_be = be_tasks_
        self.node_dict = {}
        for ip in ip_list_:
            self.node_dict[ip] = allocater.Allocater(self.benchmark_set, lc_tasks_, be_tasks_, ip)

    def lc_algorithm(self):
        max_slack = 0
        max_ip = None
        for ip in self.node_dict.keys():
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if not slack_list:
                return ip
            if QoS_status == 1:
                if max_slack < slack_list[0][1]["slack"]:
                    max_slack = slack_list[0][1]["slack"]
                    max_ip = ip
        if max_ip:
            return max_ip
        print("Warning! No available node for LC task")
        return None

    def be_algorithm(self):
        available = []
        for ip in self.node_dict.keys():
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if QoS_status == -1 and self.node_dict[ip].be_containers:
                self.be_tasks.append(self.node_dict[ip].be_containers[-1].task)
                self.node_dict[ip].be_containers[-1].remove()
                del self.node_dict[ip].be_containers[-1]
                time.sleep(60)
            elif QoS_status == 1:
                available.append(ip)
        if available and self.be_tasks:
            be_host = available[len(self.be_tasks) % len(available)]
            return self.be_tasks[0], be_host
        return None, None

    def prune(self):
        for ip in self.node_dict.keys():
            finished_lc, finished_be = self.node_dict[ip].prune()
            self.lc_tasks += finished_lc

    def run(self):
        start_time = time.time()
        while True:
            time.sleep(10)
            print(f'\ntime {(time.time() - start_time}:')
            self.prune()
            for ip in self.node_dict.keys():
                print(f"lc on {ip}: ", self.node_dict[ip].lc_containers)
                print(f"be on {ip}: ", self.node_dict[ip].be_containers)

            if self.lc_tasks:
                lc = self.lc_tasks.pop()
                lc_host = self.lc_target[lc]
                self.node_dict[lc_host].lc_containers.append(
                    container.Container('scomet', 'lc_container%d' % self.node_dict[lc_host].unused_lc_index(), lc_host,
                                        self.passwd[lc_host]))
                rps_delta = int(time.time() - start_time) % 10800
                rps_delta = 1 - (abs(rps_delta - 5400) / 5400)
                rps = int(self.max_load[lc_host][lc] * rps_delta * 3 / 4 + self.max_load[lc_host][lc] / 4)
                self.node_dict[lc_host].lc_containers[-1].run_task(self.benchmark_set, lc,
                                                                   '%d %d' % (rps, self.threads[lc_host][lc]))
                time.sleep(60)
                continue
            be, be_host = self.algorithm()
            if be:
                self.be_tasks.remove(be)
                self.node_dict[be_host].be_containers.append(
                    container.Container('scomet', 'be_container%d' % self.node_dict[be_host].unused_be_index(), be_host,
                                        self.passwd[be_host]))
                self.node_dict[be_host].be_containers[-1].run_task(self.benchmark_set, be)
                print('be task remain %d :' % len(self.be_tasks), self.be_tasks)
                time.sleep(60)
            if not self.be_tasks:
                finished = True
                for ip in self.node_dict.keys():
                    if self.node_dict[ip].be_containers:
                        finished = False
                if finished:
                    print('finished')
                    for ip in self.node_dict.keys():
                        print(ip)
                        with open('%s_latency_result.txt' % ip, mode='w') as result_f:
                            result_f.write(json.dumps(self.node_dict[ip].latency_result))
                        with open('%s_violate_result.txt' % ip, mode='w') as result_f:
                            result_f.write(json.dumps(self.node_dict[ip].violate_result))
                        for container_instance in self.node_dict[ip].lc_containers + self.node_dict[ip].be_containers:
                            container_instance.remove()
                    break