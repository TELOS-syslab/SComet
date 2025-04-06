import json
import copy
import os
import sys
import time
import subprocess
import signal
import random
from config import *

ROOT = "/home/wjy/SComet/"

# memcached result of thread 8 (after adjusting NUMA node to 1)
# {'8_100000': 609.875, '8_101000': 658.625, '8_102000': 439.5, '8_103000': 645.875, '8_104000': 1848.0, '8_105000': 2641.75, '8_106000': 2966.375, '8_107000': 3338.125, '8_108000': 4801.5, '8_109000': 5475.75, '8_110000': 6252.125, '8_111000': 9005.25, '8_112000': 8602.25, '8_113000': 10368.0, '8_114000': 15722.25, '8_115000': 17647.125, '8_116000': 25344.25, '8_117000': 23683.625, '8_118000': 199598.625, '8_119000': 372905.875}
# nginx result of thread 8 (after)
# {'8_100000': 1170.0, '8_100500': 1328.75, '8_101000': 1380.0, '8_101500': 1623.75, '8_102000': 1300.0, '8_102500': 1380.0, '8_103000': 1421.25, '8_103500': 1600.0, '8_104000': 1202.5, '8_104500': 1263.75, '8_105000': 1603.75, '8_105500': 1983.75, '8_106000': 1596.25, '8_106500': 1443.75, '8_107000': 1078.75, '8_107500': 1550.0, '8_108000': 1642.5, '8_108500': 370751.25, '8_109000': 356351.25, '8_109500': 1438.75, '8_110000': 284287.5, '8_110500': 1635.0, '8_111000': 232031.25, '8_111500': 349822.5, '8_112000': 1626.25, '8_112500': 284160.0, '8_113000': 1626.25, '8_113500': 394846.25, '8_114000': 405760.0, '8_114500': 918656.25, '8_115000': 1648.75, '8_115500': 904985.0, '8_116000': 516065.0, '8_116500': 659391.25, '8_117000': 309856.25, '8_117500': 323967.5, '8_118000': 339262.5, '8_118500': 331421.25, '8_119000': 928488.75, '8_119500': 415328.75, '8_120000': 367966.25
LC_instr = {
    "memcached": [f"sudo bash {ROOT}/benchmarks/memcached/script/server.sh",
                  f"bash {ROOT}/benchmarks/memcached/script/client.sh"],
    "nginx": [f"bash {ROOT}/benchmarks/nginx/script/server.sh",
              f"bash {ROOT}/benchmarks/nginx/script/client.sh"]
}

subprocess.Popen("sudo rm -rf /var/lock/libpqos", shell=True).wait()

test_time = 30
if '-t' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-t') + 1])

LC_task = "memcached"
if '--lc' in sys.argv:
    LC_task = sys.argv[sys.argv.index('--lc') + 1]
    if LC_task not in LC_instr.keys():
        print(f"Invalid LC task {LC_task}")
        exit(0)

def read_LC_latency(filename):
    with open(filename, mode='r') as output_f:
        outputs = output_f.readlines()
        if 'memcached' in filename:
            for i in range(len(outputs)):
                if 'service' in outputs[i]:
                    return float(outputs[i + 1].split()[3])
        elif 'nginx' in filename:
            for i in range(len(outputs)):
                if '99.000%' in outputs[i]:
                    if 'us' in outputs[i]:
                        latency = float(outputs[i].split()[-1].split('us')[0])
                    elif 'ms' in outputs[i]:
                        latency = float(outputs[i].split()[-1].split('ms')[0]) * 1000
                    elif 's' in outputs[i]:
                        latency = float(outputs[i].split()[-1].split('s')[0]) * 1000000
                    return latency
        else:
            print('Unavailable LC task')
            exit()

for LC_server_threads in [8]:
    latency_99_dict = {}
    for LC_client_threads in [8]:
        for LC_rps in list(range(100000, 200000, 500)):
            LC_instr0 = f"sudo taskset -c {','.join(CPU_cores['NUMA0'][:LC_server_threads])} " + LC_instr[LC_task][0]
            LC_instr0 = LC_instr0 + ' ' + str(LC_server_threads)
            LC_instr1 = f"sudo taskset -c {','.join(CPU_cores['NUMA0'][LC_server_threads:LC_server_threads + LC_client_threads])} " + LC_instr[LC_task][1]
            LC_instr1 = LC_instr1 + ' ' + str(LC_client_threads)
            LC_instr1 = LC_instr1 + ' ' + str(LC_rps)
            LC_instr1 = LC_instr1 + ' ' + str(test_time)
            LC_instr1 = LC_instr1 + ' ' + ','.join(CPU_cores['NUMA0'][LC_server_threads:LC_server_threads + LC_client_threads])

            print(LC_instr0)
            print(LC_instr1)
            cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
            cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
            print('waiting for perf...')
            cmd_result1.wait()

            latency_99 = []
            for n in range(LC_client_threads):
                latency_99.append(read_LC_latency(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log'))
            if latency_99:
                latency_99_dict[f'{LC_client_threads}_{LC_rps}'] = sum(latency_99) / len(latency_99)
                print(latency_99_dict)
            else:
                break




 


