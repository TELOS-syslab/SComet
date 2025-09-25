#!/usr/bin/python3
import container
import time
import math
import sys
import json
import copy
import json

sys.path.append('/home/wjy/SComet')
from config import *
from container import *
from allocator import *
from scheduler import *

profiling_data = {
    "masstree-2500": {
        "cpu": [
          13,
          21
        ],
        "l1d": [
          10,
          3
        ],
        "l1i": [
          10,
          21
        ],
        "l2": [
          2,
          7
        ],
        "l3": [
          13,
          21
        ],
        "memBw": [
          21,
          1
        ],
        "memCap": [
          5,
          21
        ]
      }
}

interference_dict = {
    "519.lbm_r": 2.462280015,
    "507.cactuBSSN_r": 0.797576537,
    "500.perlbench_r": 0.040854815,
    "502.gcc_r": 0.024762225,
    "503.bwaves_r": 0,
    "505.mcf_r": 0.673663423,
    "508.namd_r": 0.042205266,
    "510.parest_r": 0.201912056,
    "511.povray_r": 0,
    "520.omnetpp_r": 0.486317134,
    "521.wrf_r": 0,
    "523.xalancbmk_r": 0.104899582,
    "525.x264_r": 0.016690667,
    "526.blender_r": 0.128601614,
    "527.cam4_r": 0,
    "531.deepsjeng_r": 0.015343912,
    "538.imagick_r": 0,
    "541.leela_r": 0.004873213,
    "544.nab_r": 0.005871788,
    "548.exchange2_r": 0,
    "549.fotonik3d_r": 0,
    "554.roms_r": 0,
    "557.xz_r": 0.263610953,
}


class SComet_Paragon_Scheduler(Scheduler):
    def __init__(self, name_, benchmark_set_, ip_list_, lc_tasks_, be_tasks_):
        super().__init__(name_, benchmark_set_, ip_list_, lc_tasks_, be_tasks_)

    def get_curr_info(self, ip, resources):
        existing_tasks_info = {
            t.task: profiling_data[t.task]
            for t in self.node_dict[ip].lc_containers.values()
        }
        existing_tasks_info.update({
            t.task: profiling_data[t.task]
            for t in self.node_dict[ip].be_containers.values()
        })
        aggregated = {}
        for res in resources:
            max_sens = 0
            sum_cause = 0
            for t in existing_tasks_info.values():
                sens, cause = t[res]
                max_sens = max(max_sens, sens)
                sum_cause += cause
            aggregated[res] = (max_sens, sum_cause)
        return aggregated

        
    def be_algorithm(self):
        print("Choosing BE to run...")
        max_margin = -float("inf")
        max_ip = None
        chosen_be = None
        be_list = list(self.be_tasks)
        if not be_list:
            return None, None
        sorted_be_list = sorted(
            be_list,
            key=lambda x: interference_dict.get(x, float("inf"))
        )

        global profiling_data
        with open("paragon_profiling.json", "r") as f:
            profiling_data = json.load(f)
        profiling_data = {k.replace(".sh", ""): v for k, v in profiling_data.items()}

        for ip in self.node_dict:
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if QoS_status != 1:
                continue

            if not (self.node_dict[ip].available_resources['CPU'] and \
                self.node_dict[ip].available_resources['LLC'] > 0 and \
                self.node_dict[ip].available_resources['MBW'] >= 10):
                continue
                
            used_be_list = []
            if slack_list[0][1]["slack"] > 0.8 and slack_list[0][1]["prev_slack"] > 0.8:
                used_be_list = sorted_be_list[len(sorted_be_list) // 2:]
            else:
                used_be_list = sorted_be_list[:len(sorted_be_list) // 2]

            best_score = -float("inf")
            best_be = None
            for be in used_be_list:
                new_task_info = profiling_data.get(be)
                if not new_task_info:
                    print(f"{be} not found in profiling data, error")
                    exit()
                aggregated = self.get_curr_info(ip, list(new_task_info.keys()))
                margins = []
                for res, (new_sens, new_cause) in new_task_info.items():
                    exist_sens, exist_cause = aggregated[res]
                    margin = min(new_sens - exist_cause, exist_sens - new_cause)
                    margins.append(margin)
                score = min(margins)
                if score > best_score:
                    best_score = score
                    best_be = be
            if best_score > max_margin:
                max_ip = ip
                max_margin = best_score
                chosen_be = best_be

        if max_ip and chosen_be:
            return chosen_be, max_ip
        return None, None


