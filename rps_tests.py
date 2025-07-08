import json
import copy
import os
import sys
import time
import subprocess
import signal
import random
from config import *

# memcached result (after adjusting NUMA node to 1)
# {'8_100000': 609.875, '8_101000': 658.625, '8_102000': 439.5, '8_103000': 645.875, '8_104000': 1848.0, '8_105000': 2641.75, '8_106000': 2966.375, '8_107000': 3338.125, '8_108000': 4801.5, '8_109000': 5475.75, '8_110000': 6252.125, '8_111000': 9005.25, '8_112000': 8602.25, '8_113000': 10368.0, '8_114000': 15722.25, '8_115000': 17647.125, '8_116000': 25344.25, '8_117000': 23683.625, '8_118000': 199598.625, '8_119000': 372905.875}
# nginx result (after)
# {'8_100000': 1170.0, '8_100500': 1328.75, '8_101000': 1380.0, '8_101500': 1623.75, '8_102000': 1300.0, '8_102500': 1380.0, '8_103000': 1421.25, '8_103500': 1600.0, '8_104000': 1202.5, '8_104500': 1263.75, '8_105000': 1603.75, '8_105500': 1983.75, '8_106000': 1596.25, '8_106500': 1443.75, '8_107000': 1078.75, '8_107500': 1550.0, '8_108000': 1642.5, '8_108500': 370751.25, '8_109000': 356351.25, '8_109500': 1438.75, '8_110000': 284287.5, '8_110500': 1635.0, '8_111000': 232031.25, '8_111500': 349822.5, '8_112000': 1626.25, '8_112500': 284160.0, '8_113000': 1626.25, '8_113500': 394846.25, '8_114000': 405760.0, '8_114500': 918656.25, '8_115000': 1648.75, '8_115500': 904985.0, '8_116000': 516065.0, '8_116500': 659391.25, '8_117000': 309856.25, '8_117500': 323967.5, '8_118000': 339262.5, '8_118500': 331421.25, '8_119000': 928488.75, '8_119500': 415328.75, '8_120000': 367966.25
# nginx result (after, close turbo)
# {'16_40000': 2312.125, '16_41000': 2616.25, '16_42000': 2547.375, '16_43000': 2857.5, '16_44000': 3074.625, '16_45000': 6182.25, '16_46000': 16185.5, '16_47000': 18174.0, '16_48000': 105367.0, '16_49000': 72555.0}

# memcached result (2025.4.25)
# {'8_80000': 64.75, '8_81000': 66.125, '8_82000': 66.875, '8_83000': 69.0, '8_84000': 71.0, '8_85000': 72.875, '8_86000': 75.375, '8_87000': 79.375, '8_88000': 87.375, '8_89000': 85.75, '8_90000': 107.0, '8_91000': 120.375, '8_92000': 203.625, '8_93000': 221.75, '8_94000': 357.5, '8_95000': 346.375, '8_96000': 518.625, '8_97000': 725.375, '8_98000': 779.625, '8_99000': 1144.875}
# nginx result (2025.4.25)
# {'8_10000': 1936.125, '8_20000': 2324.75, '8_30000': 2145.0, '8_40000': 2501.0, '8_50000': 2832.25, '8_60000': 2829.75, '8_70000': 2961.0, '8_80000': 235631.0, '8_90000': 5434879.0, '8_100000': 12013567.0}
# memcached result(2025.4.28)
# {'16_100000': 61.8125, '16_110000': 71.8125, '16_120000': 85.0, '16_130000': 103.1875, '16_140000': 156.6875}
# masstree result(2025.4.30)
# {'16_9000': 1819.0, '16_9200': 1809.0, '16_9400': 1918.0, '16_9600': 2392.0, '16_9800': 4372.0, '16_10000': 6876.0}

subprocess.Popen("sudo rm -rf /var/lock/libpqos", shell=True).wait()

LC_task = "memcached"
if '--lc' in sys.argv:
    LC_task = sys.argv[sys.argv.index('--lc') + 1]
    if LC_task not in LC_instr.keys():
        print(f"Invalid LC task {LC_task}")
        exit(0)

test_time = 120
if '-T' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-T') + 1])

threads = [16, 16, 24]
if '-t' in sys.argv:
    threads = sys.argv[sys.argv.index('-t') + 1].split(',')
    threads = [int(t) for t in threads]
LC_threads = threads[:-1]
BE_threads = threads[-1]

core = []
for i in range(len(threads)):
    core_str = ','.join(CPU_cores['NUMA0'][sum(threads[0:i]): sum(threads[0:i + 1])])
    print(core_str)
    core.append(core_str)

cache_ways = [7, 7, 1]
if '-c' in sys.argv:
    cache_ways = sys.argv[sys.argv.index('-c') + 1].split(',')
    cache_ways = [int(c) for c in cache_ways]

memory_bandwidth_ratio = [30, 30, 10]
if '-m' in sys.argv:
    memory_bandwidth_ratio = sys.argv[sys.argv.index('-m') + 1].split(',')
    memory_bandwidth_ratio = [int(m) for m in memory_bandwidth_ratio]

resource_allocation(threads, core, cache_ways, memory_bandwidth_ratio)

latency_dict = {}
for LC_rps in list(range(9000, 11000, 200)):
    if LC_instr[LC_task][0]:
        LC_instr0 = f"sudo {LC_instr[LC_task][0]} {LC_threads[i * 2]} {LC_rps[i]} {test_time} {core[i * 2]}"
    else:
        LC_instr0 = ""
    print(LC_instr0)
    cmd_result.append(subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid))
    time.sleep(3)

    if LC_instr[LC_task][1]:
        LC_instr1 = f"sudo {LC_instr[LC_task][1]} {LC_threads[i * 2 + 1]} {LC_rps[i]} {test_time} {core[i * 2 + 1]}"
    else:
        LC_instr1 = ""
    print(LC_instr1)
    cmd_result.append(subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid))
    time.sleep(3)

    print(LC_instr0)
    print(LC_instr1)
    cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
    time.sleep(5)
    cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
    print('waiting for perf...')
    cmd_result1.wait()

    latency = []
    for n in range(LC_client_threads):
        latency.append(read_LC_latency_99(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log'))
    if latency:
        latency_dict[f'{LC_client_threads}_{LC_rps}'] = sum(latency) / len(latency)
        print(latency_dict)
    else:
        break




 


