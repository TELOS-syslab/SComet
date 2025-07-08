#!/usr/bin/python3
import container
import time
import math
import sys
import os
import numpy
sys.path.append('/home/wjy/SComet')
from config import *

class Allocater:
    benchmark_set = ''
    lc_containers = []
    be_containers = []
    latency_result = {}
    violate_result = {}
    QoS = {}
    main_ip = ''

    def __init__(self, benchmark_set_, QoS_, main_ip_ = '172.17.1.119'):
        self.benchmark_set = benchmark_set_
        self.lc_containers = []
        self.be_containers = []
        self.latency_result = {}
        self.violate_result = {}
        self.QoS = QoS_
        self.main_ip = main_ip_

    def get_lc_latency(self, container_instance):
        benchmark = container_instance.task
        print('get latency %s' % benchmark)
        if benchmark not in self.QoS.keys():
            return None

        log_path = '/home/wjy/SComet/%s/QoS/%s.%s.log' % (self.benchmark_set, container_instance.ip, benchmark)
        if benchmark == 'memcached':
            result_path = "/home/wjy/SComet/%s/QoS/%s.log" % (self.benchmark_set, benchmark)
            container_instance.copy_file(result_path, log_path)
        elif benchmark == 'nginx':
            result_path = '/home/wjy/SComet/wrk2/result.txt'
            container_instance.copy_file(result_path, log_path)
        elif benchmark == 'masstree' or benchmark == 'silo' or benchmark == 'sphinx':
            result_path = '/home/wjy/SComet/tailbench/tailbench-v0.9/%s/lats.bin' % benchmark
            container_instance.copy_file(result_path, result_path)
            exe.cmd_and_wait('%s "python /home/wjy/SComet/tailbench/tailbench-v0.9/utilities/parselats.py %s"' % (container_instance.ssh_pre(), result_path))
            exe.cmd_and_wait('%s "mv lats.txt %s"' % (container_instance.ssh_pre(), log_path))
        elif benchmark == 'redis-master' or benchmark == 'redis-slave':
            result_path = "/home/wjy/SComet/%s/QoS/redis.log" % self.benchmark_set
            container_instance.copy_file(result_path, log_path)

        if self.main_ip != container_instance.ip:
            print('start sending latency result')
            exe.cmd_and_wait('sshpass -p \'%s\' scp root@%s:%s %s' % (container_instance.passwd, container_instance.ip, log_path, log_path))
            print('finish sending latency result')

        output = []
        violate = []
        if not os.path.exists(log_path):
            return output

        with open(log_path, mode='r') as log_f:
            logs = log_f.readlines()
            logs = [log for log in logs if ['percentile','latency'] == log.split()[1:3]]
            for index in range(1, len(logs)):
                log = logs[index]
                try:
                    percentile = float(log.split('th')[0])
                    latency = float(log.split()[-1])
                    prev_latency = float(logs[index - 1].split()[-1])
                except ValueError:
                    continue
                if percentile == 99:
                    output.append(latency)
                if prev_latency < self.QoS[benchmark] and latency >= self.QoS[benchmark]:
                    violate.append(round(100 - percentile, 2))
                if latency < self.QoS[benchmark] and percentile == 100:
                    violate.append(0)

        if benchmark not in self.violate_result.keys():
            self.violate_result[benchmark] = [violate]
        if len(self.violate_result[benchmark][-1]) > len(violate):
            self.violate_result[benchmark].append(violate)
        else:
            self.violate_result[benchmark][-1] = violate

        if benchmark not in self.latency_result.keys():
            self.latency_result[benchmark] = [output]
        if len(self.latency_result[benchmark][-1]) > len(output):
            self.latency_result[benchmark].append(output)
        else:
            self.latency_result[benchmark][-1] = output

        return output

    def get_QoS_status(self):
        slack_dict = {}
        for index in range(len(self.lc_containers)):
            container_instance = self.lc_containers[index]
            benchmark = container_instance.task
            latency = self.get_lc_latency(container_instance)
            if not latency:
                continue
            if len(latency) >= 2:
                curr_latency = latency[-1]
                prev_latency = latency[-2]
                print('benchmark %s latency: %f' % (benchmark, curr_latency))
                print('benchmark %s prev latency: %f' % (benchmark, prev_latency))
                slack = (self.QoS[benchmark] - curr_latency) / self.QoS[benchmark]
                prev_slack = (self.QoS[benchmark] - prev_latency) / self.QoS[benchmark]
                slack_dict[index] = (slack, prev_slack)
        slack_sorted_list = sorted(slack_dict.items(), key=lambda x: x[1][0])
        if not slack_sorted_list:
            return 0, slack_sorted_list
        max_slack = slack_sorted_list[-1][1][0]
        max_slack_prev = slack_sorted_list[-1][1][1]
        min_slack = slack_sorted_list[0][1][0]
        min_slack_prev = slack_sorted_list[0][1][1]
        if min_slack < 0 and min_slack_prev < 0:
            return -1, slack_sorted_list
        elif max_slack >= 0.15 and max_slack_prev >= 0.15:
            return 1, slack_sorted_list
        else:
            return 0, slack_sorted_list
        
    def prune(self):
        unfinished_lc = []
        unfinished_be = []
        index = 0
        while index < len(self.lc_containers):
            if self.lc_containers[index].running:
                if self.lc_containers[index].running.poll() != None:
                    print('lc task %s finished' % self.lc_containers[index].get_running_task())
                    unfinished_lc.append(self.lc_containers[index].get_running_task())
                    self.lc_containers[index].remove()
                    del self.lc_containers[index]
                    continue
            index += 1
        index = 0
        while index < len(self.be_containers):
            if self.be_containers[index].running:
                if self.be_containers[index].running.poll() != None:
                    print('be task %s finished' % self.be_containers[index].get_running_task())
                    self.be_containers[index].remove()
                    del self.be_containers[index]
                    continue
            index += 1
        return unfinished_lc, unfinished_be

    def unused_lc_index(self):
        index = 0
        for index in range(10):
            used = False
            for container_instance in self.lc_containers:
                if int(container_instance.name[-1]) == index:
                    used = True
                    break
            if not used:
                return index
        return None

    def unused_be_index(self):
        index = 0
        for index in range(10):
            used = False
            for container_instance in self.be_containers:
                if int(container_instance.name[-1]) == index:
                    used = True
                    break
            if not used:
                return index
        return None





