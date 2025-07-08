import json
import copy
import os
import sys
import time
import subprocess
import signal
import random
from scipy.stats import pearsonr
import numpy as np

# Use linear regression to get relevant PMU events

if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
else:
    print('Microbench name needed')
    exit(0)

test_time = 5
if '-t' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-t') + 1])

benchmark_list = []
benchmark_path = '../benchmarks/' + benchmark_set
for root, dirs, files in os.walk(benchmark_path +'/log'):
    for file in files:
        if file.endswith('.log') and all(x not in file for x in ['analysis', 'baseline', 'dummy', 'metrics']):
            benchmark_list.append('.'.join(file.split('.')[0:-1]))
benchmark_list.sort()
print('benchmark list:')
print(benchmark_list)


all_interference = {
    "500.perlbench_r": (0.965310983, 1.252605752),
    "505.mcf_r": (50.06120042, 2.289745235),
    "507.cactuBSSN_r": (1.070500137, 0.911776277),
    "508.namd_r": (53.62824952, 3.540334562),
    "510.parest_r": (72.73674315, 2.481422496),
    "519.lbm_r": (58.49486352, 2.710285108),
    "520.omnetpp_r": (167.7740932, 5.049620414),
    "521.wrf_r": (1.09284602, 2.018916492),
    "523.xalancbmk_r": (0.963792709, 1.207781052),
    "526.blender_r": (1.070928369, 1.226285471),
    "527.cam4_r": (46.83089677, 3.477028936),
    "538.imagick_r": (7.808951635, 1.489737785),
    "541.leela_r": (0.969126134, 0.969653149),
    "548.exchange2_r": (0.977145736, 1.254815147),
    "microbench": (1.453899423, 3.125319156),
    "microbench_pollu_1": (3.834039571, 5.067735216),
    "microbench_pollu_2": (39.52184666, 4.001036515),
    "microbench_pollu_3": (45.89313273, 36.56838763),
    "microbench_pollu_4": (45.67099753, 36.64660149),
    "microbench_pollu_5": (9105.69066, 204.2043207),
    "microbench_pollu_6":   (4.07649629, 28.05179685),
    "microbench_pollu_7":   (3.849175598,32.93782588),
    "baseline": (1, 1)
}

interference = {key: all_interference[key][1] for key in benchmark_list if key in benchmark_list}

dict = {}
for benchmark_name in benchmark_list:
    dict[benchmark_name] = {}
    with open(f'{benchmark_path}/log/{benchmark_name}.log', 'r') as result_f:
        result_list = result_f.readlines()
        for result in result_list:
            result_tuple = result.split()
            dict[benchmark_name][result_tuple[0]] = float(result_tuple[1].strip().replace(',', ''))
    with open(f'{benchmark_path}/log/{benchmark_name}_metrics.log', 'r') as result_f:
        result_list = result_f.readlines()
        for result in result_list:
            if "error" in result or "Error" in result :
                continue
            result_tuple = result.split()
            dict[benchmark_name][result_tuple[0]] = float(result_tuple[1].strip().replace(',', ''))


with open(benchmark_path + '/log/analysis.log', 'w') as result_f:
    result_f.write(''.ljust(80, ' '))
    for benchmark_name in benchmark_list:
        result_f.write(benchmark_name.ljust(80, ' '))
    result_f.write('\n')

    result_f.write('interference'.ljust(80, ' '))
    for benchmark_name in benchmark_list:
        result_f.write(str(interference[benchmark_name]).ljust(80, ' '))
    result_f.write('\n')

    pearson_result = {}
    event_list = dict[benchmark_list[0]].keys()
    for event in event_list:
        print(event)
        y = []
        for benchmark_name in benchmark_list:
            if event not in dict[benchmark_name].keys():
                break
            num = float(dict[benchmark_name][event])
            y.append(num)
            
        x = np.array(list(interference.values()))
        y = np.array(y)
        if len(x) != len(y):
            continue
        pc = pearsonr(x, y)
        if pc[0] == pc[0]:
            pearson_result[event] = [' '.join(y.astype(str)), pc[0], pc[1]]

    sorted_result = sorted(pearson_result.items(), key=lambda x: abs(x[1][1]), reverse=True)
    for i in range(len(sorted_result)):
        result_f.write('%s %s %f %f\n' % (sorted_result[i][0], sorted_result[i][1][0], sorted_result[i][1][1], sorted_result[i][1][2]))

    with open('related_events.txt', mode='w') as related_f:
        related_f.write('victim_ipc ')
        for benchmark_name in benchmark_list:
            related_f.write(str(interference[benchmark_name]) + ' ')
        related_f.write('\n')
        for i in range(min(len(sorted_result), 10)):
            related_f.write('%s %s\n' % (sorted_result[i][0], sorted_result[i][1][0]))

        



 


