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
from scheduler import *

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


class SComet_Scheduler(Scheduler):
    def __init__(self, name_, benchmark_set_, ip_list_, lc_tasks_, be_tasks_):
        super().__init__(name_, benchmark_set_, ip_list_, lc_tasks_, be_tasks_)
        
    def be_algorithm(self):
        print("Choosing BE to run...")
        max_slack = 0
        max_ip = None
        be = None
        be_list = list(self.be_tasks)
        if not be_list:
            return None, None
        sorted_be_list = sorted(
            be_list,
            key=lambda x: interference_dict.get(x, float("inf"))
        )
        # print(sorted_be_list)
        for ip in self.node_dict:
            QoS_status, slack_list = self.node_dict[ip].get_QoS_status()
            if QoS_status == 1:
                if not (self.node_dict[ip].available_resources['CPU'] and \
                        self.node_dict[ip].available_resources['LLC'] > 0 and \
                        self.node_dict[ip].available_resources['MBW'] >= 10):
                    continue
                if max_slack < slack_list[0][1]["slack"]:
                    max_slack = slack_list[0][1]["slack"]
                    max_prev_slack = slack_list[0][1]["prev_slack"]
                    max_ip = ip
                    if max_slack > 0.8 and max_prev_slack > 0.8:
                        be = sorted_be_list[-1]
                    else:
                        be = sorted_be_list[0]
        if max_ip and self.be_tasks:
            return be, max_ip
        return None, None

