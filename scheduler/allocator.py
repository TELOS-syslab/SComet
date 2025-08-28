#!/usr/bin/python3
import time
import math
import sys
import os
import numpy

sys.path.append('/home/wjy/SComet')
from config import *
from container import *


class Allocator:
    def __init__(self, benchmark_set_, lc_tasks_, be_tasks_, ip_):
        self.benchmark_set = benchmark_set_
        self.lc_containers = {}
        self.be_containers = {}
        self.latency_result = {}
        self.violate_result = {}
        self.lc_tasks = lc_tasks_
        self.be_tasks = be_tasks_
        self.ip = ip_
        self.max_container = 8

        self.available_resources = {
            'CPU': list(range(56)),
            'LLC': 0x7fff,
            'MBW': 100
        }

        self.resource_allocation = {}
        self.resource_wheel = ['CPU', 'LLC', 'MBW']

    def get_lc_latency(self, container_instance):
        benchmark = container_instance.task
        print(f'get latency {benchmark}')
        if benchmark not in self.lc_tasks.keys():
            return None, None

        # copy from remote node
        log_path = f'/home/wjy/SComet/{self.benchmark_set}/QoS/{container_instance.ip}.{benchmark}.log'
        if benchmark in ['masstree', 'silo', 'sphinx']:
            result_path = f'/home/wjy/SComet/benchmarks/{benchmark}/QoS/{benchmark}_0.log'
            container_instance.copy_from_container(result_path, log_path)
        else:
            print(f"Benchmark {self.benchmark_set}-{benchmark} not supported")
            return None, None
        if curr_ip != container_instance.ip:
            print('start sending latency result')
            copy_from_node(container_instance.ip, log_path, log_path)
            print('finish sending latency result')

        output = None
        violate = None
        prev_latency = 0.0
        qos_threshold = self.lc_tasks[benchmark]["QoS"]
        if not os.path.exists(log_path):
            return None, None
        with open(log_path, 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if 'percentile' in line and ':' in line:
                try:
                    percentile_str, latency_str = line.split('percentile:')
                    percentile = int(
                        percentile_str.strip().replace('th', '').replace('st', '').replace('nd', '').replace('rd', ''))
                    latency = float(latency_str.strip())
                except ValueError:
                    continue

                if percentile == 99:
                    output = latency
                if prev_latency < qos_threshold and latency >= qos_threshold:
                    violate = round(100 - percentile, 2)
                if latency < qos_threshold and percentile == 100:
                    violate = 0
                prev_latency = latency

        if benchmark not in self.latency_result:
            self.latency_result[benchmark] = []
        if benchmark not in self.violate_result:
            self.violate_result[benchmark] = []
        self.latency_result[benchmark].append(output)
        self.violate_result[benchmark].append(violate)

        return output, violate

    def get_QoS_status(self):
        slack_dict = {}
        for index in self.lc_containers:
            container_instance = self.lc_containers[index]
            self.get_lc_latency(container_instance)

            benchmark = container_instance.task
            latencies = self.latency_result[benchmark]
            curr_latency = latencies[-1]
            prev_latency = latencies[-2] if len(latencies) > 1 else latencies[-1]

            print(f'benchmark {benchmark} latency: {curr_latency}')
            print(f'benchmark {benchmark} prev latency: {prev_latency}')
            slack = (self.lc_tasks[benchmark]["QoS"] - curr_latency) / self.lc_tasks[benchmark]["QoS"]
            prev_slack = (self.lc_tasks[benchmark]["QoS"] - prev_latency) / self.lc_tasks[benchmark]["QoS"]
            slack_dict[index] = {'slack': slack, 'prev_slack': prev_slack}

        # sort with current slack
        slack_sorted_list = sorted(slack_dict.items(), key=lambda x: x[1]['slack'])
        if not slack_sorted_list:
            return 0, slack_sorted_list
        max_slack = slack_sorted_list[-1][1]['slack']
        max_slack_prev = slack_sorted_list[-1][1]['prev_slack']
        min_slack = slack_sorted_list[0][1]['slack']
        min_slack_prev = slack_sorted_list[0][1]['prev_slack']

        # LC tasks violating QoS, need to remove BE tasks
        if min_slack < 0 and min_slack_prev < 0:
            return -1, slack_sorted_list

        # LC tasks idle, can add BE tasks
        elif max_slack >= 0.15 and max_slack_prev >= 0.15:
            return 1, slack_sorted_list

        # LC tasks not idle or busy, keep BE tasks unchanged
        else:
            return 0, slack_sorted_list

    def prune(self):
        finished_lc = []
        finished_be = []
        remaining_lc = {}
        remaining_be = {}

        for index, container in self.lc_containers.items():
            if (container.running and container.running.poll() is not None) or container.task == "killed":
                print(f'lc task {container.get_running_task()} finished')
                finished_lc.append(container.get_running_task())
                if index in self.resource_allocation:
                    alloc = self.resource_allocation.pop(index)
                    self.available_resources['CPU'].extend(alloc['CPU'])
                    self.available_resources['LLC'] |= alloc['LLC']
                    self.available_resources['MBW'] += alloc['MBW']
                container.remove()
            else:
                remaining_lc[index] = container
        self.lc_containers = remaining_lc

        for index, container in self.be_containers.items():
            if (container.running and container.running.poll() is not None) or container.task == "killed":
                print(f'be task {container.get_running_task()} finished')
                finished_be.append(container.get_running_task())
                if index in self.resource_allocation:
                    alloc = self.resource_allocation.pop(index)
                    self.available_resources['CPU'].extend(alloc['CPU'])
                    self.available_resources['LLC'] |= alloc['LLC']
                    self.available_resources['MBW'] += alloc['MBW']
                container.remove()
            else:
                remaining_be[index] = container
        self.be_containers = remaining_be

        self.available_resources['CPU'].sort()
        return finished_lc, finished_be

    def unused_index(self):
        for i in range(self.max_container):
            if i not in list(self.lc_containers) + list(self.be_containers):
                return i
        return None

    def get_lowest_llc_line(self, mask=None):
        if mask is None:
            mask = self.available_resources['LLC']
        return mask & -mask

    def run_lc_task(self, task, commands):
        if not self.available_resources['CPU'] or self.available_resources['LLC'] == 0 or self.available_resources[
            'MBW'] < 1:
            print(f"No enough resource for task {task} on {self.ip}:")
            print(self.available_resources)
            return None

        index = self.unused_index()
        if index is None:
            print(f"Cannot add more than {self.max_container} tasks to {self.ip}")
            return None

        container = Container('lc_container:v1', f'lc_container{index}', index, self.ip, index)

        allocated_cpu = self.available_resources['CPU'][:]
        allocated_llc = self.available_resources['LLC']
        allocated_mbw = self.available_resources['MBW']
        container.assign_cpu_cores(allocated_cpu)
        container.assign_llc_mbw(allocated_llc, allocated_mbw)
        self.resource_allocation[index] = {
            'CPU': allocated_cpu,
            'LLC': allocated_llc,
            'MBW': allocated_mbw
        }
        self.available_resources['CPU'] = []
        self.available_resources['LLC'] = 0
        self.available_resources['MBW'] = 0

        container.run_task(self.benchmark_set, task, commands)
        self.lc_containers[index] = container
        return f'lc_container{index}'

    def run_be_task(self, task, commands):
        if not self.available_resources['CPU'] or self.available_resources['LLC'] == 0 or self.available_resources[
            'MBW'] < 10:
            print(f"No enough resource for task {task}:")
            print(self.available_resources)
            return

        index = self.unused_index()
        if index is None:
            print(f"Cannot add more than {self.max_container} tasks to {self.ip}")
            return None

        container = Container('be_container:v1', f'be_container{index}', index, self.ip, index)

        allocated_cpu = [self.available_resources['CPU'][0]]
        allocated_llc = self.get_lowest_llc_line()
        allocated_mbw = 10
        container.assign_cpu_cores(allocated_cpu)
        container.assign_llc_mbw(allocated_llc, allocated_mbw)
        self.resource_allocation[index] = {
            'CPU': allocated_cpu,
            'LLC': allocated_llc,
            'MBW': allocated_mbw
        }
        self.available_resources['CPU'].pop(0)
        self.available_resources['LLC'] &= ~allocated_llc
        self.available_resources['MBW'] -= 10

        container.run_task(self.benchmark_set, task, commands)
        self.be_containers[index] = container
        return f'be_container{index}'

    def assign_all(self):
        for index, container in list(self.lc_containers.items()) + list(self.be_containers.items()):
            if index not in self.resource_allocation:
                continue
            alloc = self.resource_allocation[index]
            cpu = alloc["CPU"]
            llc = alloc["LLC"]
            mbw = alloc["MBW"]
            if cpu is not None:
                container.assign_cpu_cores(cpu)
            if llc is not None and mbw is not None:
                container.assign_llc_mbw(llc, mbw)

    def push_wheel(self):
        if not self.resource_wheel:
            return None
        self.resource_wheel.append(self.resource_wheel.pop(0))
        return self.resource_wheel[0]

    def reallocate(self):
        QoS_status, slack_list = self.get_QoS_status()
        if QoS_status == 0:
            return 0
        if QoS_status == 1:
            if self.release_lc_resource(slack_list):
                if self.be_containers:
                    be_index = list(self.be_containers)[0]
                    if be_index not in self.resource_allocation:
                        self.resource_allocation[be_index] = {'CPU': [], 'LLC': 0, 'MBW': 0}
                    self.resource_allocation[be_index]['CPU'].extend(self.available_resources['CPU'])
                    self.resource_allocation[be_index]['LLC'] |= self.available_resources['LLC']
                    self.resource_allocation[be_index]['MBW'] += self.available_resources['MBW']
                    self.available_resources['CPU'] = []
                    self.available_resources['LLC'] = 0
                    self.available_resources['MBW'] = 0
                    self.assign_all()
            else:
                return 0
        if QoS_status == -1:
            success = False
            for try_num in range(3):
                success = self.add_lc_resource(slack_list)
                if success:
                    return 1
                if self.release_lc_resource(slack_list):
                    continue
                for be_index, be_container in self.be_containers.items():
                    if self.release_container_resource(be_index):
                        break
            print("Warning! QoS violation but no more resource!")
            print(slack_list)
            return -1

    def release_lc_resource(self, slack_list):
        for index, slack_info in reversed(slack_list):
            if self.release_container_resource(index):
                return True
        return False

    def add_lc_resource(self, slack_list):
        index, slack_info = slack_list[0]
        if self.add_container_resource(index):
            return True
        return False

    def release_container_resource(self, index):
        success = False
        for n in range(3):
            if self.resource_wheel[0] == "CPU":
                if len(self.resource_allocation[index]['CPU']) > 1:
                    self.available_resources['CPU'].append(self.resource_allocation[index]['CPU'].pop(0))
                    self.available_resources['CPU'].sort()
                    success = True
                    break
            if self.resource_wheel[0] == "LLC":
                if self.get_lowest_llc_line(self.resource_allocation[index]['LLC']) != self.resource_allocation[index][
                    'LLC']:
                    allocated_llc = self.get_lowest_llc_line(self.resource_allocation[index]['LLC'])
                    self.resource_allocation[index]['LLC'] &= ~allocated_llc
                    self.available_resources['LLC'] |= allocated_llc
                    success = True
                    break
            if self.resource_wheel[0] == "MBW":
                if self.resource_allocation[index]['MBW'] > 10:
                    self.resource_allocation[index]['MBW'] -= 10
                    self.available_resources['MBW'] += 10
                    success = True
                    break
            self.push_wheel()
        if success:
            self.assign_all()
            return True
        return False

    def add_container_resource(self, index):
        success = False
        for n in range(3):
            if self.resource_wheel[0] == "CPU":
                if len(self.available_resources['CPU']) > 1:
                    self.resource_allocation[index]['CPU'].append(self.available_resources['CPU'].pop(0))
                    self.available_resources['CPU'].sort()
                    success = True
                    break
            if self.resource_wheel[0] == "LLC":
                if self.get_lowest_llc_line(self.available_resources['LLC']) != self.available_resources['LLC']:
                    allocated_llc = self.get_lowest_llc_line(self.available_resources['LLC'])
                    self.available_resources['LLC'] &= ~allocated_llc
                    self.resource_allocation[index]['LLC'] |= allocated_llc
                    success = True
                    break
            if self.resource_wheel[0] == "MBW":
                if self.available_resources['MBW'] > 10:
                    self.available_resources['MBW'] -= 10
                    self.resource_allocation[index]['MBW'] += 10
                    success = True
                    break
            self.push_wheel()
        if success:
            self.assign_all()
            return True
        return False

    def kill_task(self, index):
        if index in self.lc_containers:
            self.lc_containers[index].task = "killed"
        if index in self.be_containers:
            self.be_containers[index].task = "killed"
        return self.prune()

    def kill_all(self):
        for index in list(self.lc_containers) + list(self.be_containers):
            self.kill_task(index)

    def remove_newest_be_task(self):
        if not self.be_containers:
            return None
        return self.kill_task(list(self.be_containers)[-1])

