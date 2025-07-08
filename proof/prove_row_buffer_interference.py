import json
import copy
import os
import sys
import time
import subprocess
import signal
import random
import re

sys.path.append('/home/wjy/SComet')
from config import *

available_benchmark_set = ['parsec-benchmark', 'stream', 'iperf', 'spec2017', 'ecp']

LC_tasks = ["memcached", "nginx", "masstree"]

if '--lc' in sys.argv:
    LC_tasks = [sys.argv[sys.argv.index('--lc') + 1]]

# benchmark_set = "microbenchmark"
benchmark_set = "spec2017"
# benchmark_list = ["503.bwaves_r", "505.mcf_r", "538.imagick_r", "541.leela_r", "baseline"]
benchmark_list = ["baseline", "557.xz_r", "505.mcf_r", "548.exchange2_r"]

test_time = 60
if '-T' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-T') + 1])

threads = [8, 8, 24]
if '-t' in sys.argv:
    threads = sys.argv[sys.argv.index('-t') + 1].split(',')
    threads = [int(t) for t in threads]
LC_threads = threads[:-1]
BE_threads = threads[-1]
    
core = []
for i in range(len(threads)):
    core_str = ','.join(CPU_cores['NUMA0'][sum(threads[0:i]): sum(threads[0:i+1])])
    print(core_str)
    core.append(core_str)

LC_rps = [59000]
if '-r' in sys.argv:
    LC_rps = sys.argv[sys.argv.index('-r') + 1].split(',')
    LC_rps = [int(r) for r in LC_rps]

cache_ways = [7, 7, 1]
if '-c' in sys.argv:
    cache_ways = sys.argv[sys.argv.index('-c') + 1].split(',')
    cache_ways = [int(c) for c in cache_ways]

memory_bandwidth_ratio = [50, 40, 10]
if '-m' in sys.argv:
    memory_bandwidth_ratio = sys.argv[sys.argv.index('-m') + 1].split(',')
    memory_bandwidth_ratio = [int(m) for m in memory_bandwidth_ratio]

resource_allocation(threads, core, cache_ways, memory_bandwidth_ratio)

latency_dict = {}

for benchmark in benchmark_list:
    subprocess.Popen("sudo pkill -f 'memcached|nginx|mutated|wrk|lbm|mttest|_r_base'", shell=True, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL).wait()
    if benchmark != benchmark_list[0]:
        time.sleep(10)

    LC = []
    BE = []
    for i in range(len(LC_tasks)):
        LC_task = LC_tasks[i]
        if LC_instr[LC_task][0]:
            LC_instr0 = f"sudo {LC_instr[LC_task][0]} {LC_threads[i * 2]} {LC_rps[i]} {2 * test_time} {core[i * 2]}"
        else:
            LC_instr0 = ""
        if LC_instr[LC_task][1]:
            LC_instr1 = f"sudo {LC_instr[LC_task][1]} {LC_threads[i * 2 + 1]} {LC_rps[i]} {2 * test_time} {core[i * 2 + 1]}"
        else:
            LC_instr1 = ""
        LC.append([LC_instr0, LC_instr1])

    if benchmark != "baseline" and BE_threads != 0:
        BE_instr = f"bash /home/wjy/SComet/benchmarks/{benchmark_set}/script/{benchmark}.sh {BE_threads} {core[-1]}"
    else:
        BE_instr = ""
    BE = [BE_instr]

    latency_dict[benchmark] = run_test(LC, BE, 0)
    print(latency_dict)

with open(f'/home/wjy/SComet/results/proof/{LC_tasks}_t{threads}_r{LC_rps}_c{cache_ways}_m{memory_bandwidth_ratio}.json',
          mode='a') as output_f:
    json.dump(latency_dict, output_f)
    output_f.write('\n')






