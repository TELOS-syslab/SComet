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

available_benchmark_set = ['parsec-benchmark', 'stream', 'iperf', 'spec2017', 'ecp']

LC_instr = {
    "memcached": [f"bash {ROOT}/benchmarks/memcached/script/server.sh",
                  f"bash {ROOT}/benchmarks/memcached/script/client.sh"],
    "nginx": [f"bash {ROOT}/benchmarks/nginx/script/server.sh",
              f"bash {ROOT}/benchmarks/nginx/script/client.sh"]
}


LC_tasks = ["memcached", "nginx"]

test_time = 30
if '-T' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-T') + 1])

LC_threads = [8, 8]
if '-t' in sys.argv:
    LC_threads = sys.argv[sys.argv.index('-t') + 1].split(',')
    LC_threads = [int(t) for t in LC_threads]

BE_threads = len(CPU_cores['NUMA0']) - 2 * sum(LC_threads)

LC_rps = [59000, 16500]
if '-r0' in sys.argv:
    LC_rps[0] = int(sys.argv[sys.argv.index('-r0') + 1])
if '-r1' in sys.argv:
    LC_rps[1] = int(sys.argv[sys.argv.index('-r1') + 1])

LC_cache_ways = [7, 7]
if '-c' in sys.argv:
    LC_cache_ways = sys.argv[sys.argv.index('-c') + 1].split(',')
    LC_cache_ways = [int(c) for c in LC_cache_ways]

LC_memory_bandwidth_ratio = [50, 40]
if '-m' in sys.argv:
    LC_memory_bandwidth_ratio = sys.argv[sys.argv.index('-m') + 1].split(',')
    LC_memory_bandwidth_ratio = [int(m) for m in LC_memory_bandwidth_ratio]

core = []
core.append(','.join(CPU_cores['NUMA0'][:LC_threads[0]]))
core.append(','.join(CPU_cores['NUMA0'][LC_threads[0]: 2 * LC_threads[0]]))
core.append(','.join(CPU_cores['NUMA0'][2 * LC_threads[0]: 2 * LC_threads[0] + LC_threads[1]]))
core.append(','.join(CPU_cores['NUMA0'][2 * LC_threads[0] + LC_threads[1]: 2 * LC_threads[0] + 2 * LC_threads[1]]))
core.append(','.join(CPU_cores['NUMA0'][2 * LC_threads[0] + 2 * LC_threads[1]: 2 * LC_threads[0] + 2 * LC_threads[1] + BE_threads]))

try:
    cos1_ways = LC_cache_ways[0]
    cos2_ways = LC_cache_ways[1]
    cos3_ways = total_ways - LC_cache_ways[0] - LC_cache_ways[1]
    cos1_llc = '0x' + format((1 << cos1_ways) - 1, 'x').zfill(total_ways // 4).rjust(total_ways // 4, '0')
    cos2_llc = '0x' + format(((1 << (cos1_ways + cos2_ways)) - 1) ^ int(cos1_llc, 16), 'x').zfill(total_ways // 4)[
                      -total_ways // 4:].rjust(total_ways // 4, '0')
    cos3_llc = '0x' + format(int(cos1_llc, 16) ^ int(cos2_llc, 16) ^ ((1 << total_ways) - 1), 'x').zfill(
        total_ways // 4)[-total_ways // 4:].rjust(total_ways // 4, '0')

    print(f"COS1 LLC Mask: {cos1_llc}")
    print(f"COS2 LLC Mask: {cos2_llc}")
    print(f"COS3 LLC Mask: {cos3_llc}")

    cos1_cmd = f'pqos -R -e "llc:1={cos1_llc};mba:1={LC_memory_bandwidth_ratio[0]}"'
    cos2_cmd = f'pqos -e "llc:2={cos2_llc};mba:2={LC_memory_bandwidth_ratio[1]}"'
    cos3_cmd = f'pqos -e "llc:3={cos3_llc};mba:3={100 - LC_memory_bandwidth_ratio[0] - LC_memory_bandwidth_ratio[1]}"'
    print(cos1_cmd)
    print(cos2_cmd)
    print(cos3_cmd)
    subprocess.run(cos1_cmd, shell=True, check=True)
    subprocess.run(cos2_cmd, shell=True, check=True)
    subprocess.run(cos3_cmd, shell=True, check=True)

    core1_cmd = f'pqos -a "llc:1={core[0]},{core[1]}"'
    core2_cmd = f'pqos -a "llc:2={core[2]},{core[3]}"'
    core3_cmd = f'pqos -a "llc:3={core[4]}"'
    print(core1_cmd)
    print(core2_cmd)
    print(core3_cmd)
    subprocess.run(core1_cmd, shell=True, check=True)
    subprocess.run(core2_cmd, shell=True, check=True)
    subprocess.run(core3_cmd, shell=True, check=True)

except subprocess.CalledProcessError as e:
    print(f"Error configuring pqos: {e}")

def read_99_latency(filename):
    with open(filename, mode='r') as output_f:
        outputs = output_f.readlines()
        if 'memcached' in filename:
            for i in range(len(outputs)):
                if 'service' in outputs[i]:
                    return float(outputs[i + 1].split()[3])
        elif 'nginx' in filename:
            for i in range(len(outputs)):
                if '0.990625' in outputs[i].split():
                    return float(outputs[i].split()[0])
        else:
            print('Unavailable LC task')
            exit()

def read_95_latency(filename):
    with open(filename, mode='r') as output_f:
        outputs = output_f.readlines()
        if 'memcached' in filename:
            print('Unavailable LC task')
            exit()
        elif 'nginx' in filename:
            for i in range(len(outputs)):
                if '0.950000' in outputs[i].split():
                    return float(outputs[i].split()[0])
        else:
            print('Unavailable LC task')
            exit()


latency_dict = {}

benchmark_set = "spec2017"
benchmark_list = ["519.lbm_r_100_100_130", "baseline"]

for benchmark in benchmark_list:
    latency_dict[benchmark] = []
    if benchmark == "baseline":
        BE_instr = f"taskset -c {core[-1]} sleep 1000"
    else:
        BE_instr = 'bash /home/wjy/SComet/benchmarks/%s/script/%s.sh %d %s' % (benchmark_set, benchmark, BE_threads, core[-1])
    print(BE_instr)

    cmd_result = []
    for i in range(len(LC_tasks)):
        LC_task = LC_tasks[i]
        LC_instr0 = f"sudo taskset -c {core[i * 2]} {LC_instr[LC_task][0]}"
        LC_instr1 = f"sudo {LC_instr[LC_task][1]} {LC_threads[i]} {LC_rps[i]} {test_time} {core[i * 2 + 1]}"
        print(LC_instr0)
        print(LC_instr1)
        cmd_result.append(subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid))
        cmd_result.append(subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid))
    cmd_result_be = subprocess.Popen(BE_instr, shell=True, preexec_fn=os.setsid)
    print('waiting for perf...')
    cmd_result[1].wait()
    cmd_result[3].wait()
    os.killpg(os.getpgid(cmd_result_be.pid), signal.SIGTERM)
    cmd_result_be.wait()

    latency_dict[benchmark] = []
    for i in range(len(LC_tasks)):
        LC_task = LC_tasks[i]
        latency_list = []
        for n in range(LC_threads[i]):
            latency_list.append(read_99_latency(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log'))
        latency_dict[benchmark].append(sum(latency_list) / len(latency_list))
    print(latency_dict)

with open(f'/home/wjy/SComet/results/proof/t{LC_threads}_r{LC_rps}_c{LC_cache_ways}_m{LC_memory_bandwidth_ratio}.json', mode='a') as output_f:
    json.dump(latency_dict, output_f)
    output_f.write('\n')




 


