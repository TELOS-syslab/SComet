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

BE_threads = 24

test_time = 30
if '-T' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-T') + 1])

LC_task = "memcached"
if '--lc' in sys.argv:
    LC_task = sys.argv[sys.argv.index('--lc') + 1]
    if LC_task not in LC_instr.keys():
        print(f"Invalid LC task {LC_task}")
        exit(0)

LC_threads = 16
if '-t' in sys.argv:
    LC_threads = int(sys.argv[sys.argv.index('-t') + 1])

LC_rps = 30000
if '-r' in sys.argv:
    LC_rps = int(sys.argv[sys.argv.index('-r') + 1])

LC_cache_ways = total_ways // 2
if '-c' in sys.argv:
    LC_cache_ways = int(sys.argv[sys.argv.index('-c') + 1])
print(f"Cache ways for LC task: {LC_cache_ways}")

LC_memory_bandwidth_ratio = 50
if '-m' in sys.argv:
    LC_memory_bandwidth_ratio = int(sys.argv[sys.argv.index('-m') + 1])
print(f"Memory bandwidth ratio for LC task: {LC_memory_bandwidth_ratio}")

core0 = ','.join(CPU_cores['NUMA0'][:LC_threads])
core1 = ','.join(CPU_cores['NUMA0'][LC_threads: 2 * LC_threads])
core2 = ','.join(CPU_cores['NUMA0'][2 * LC_threads: 2 * LC_threads + BE_threads])
# core3 = ','.join(CPU_cores['NUMA1'][2 * LC_threads: 2 * LC_threads + BE_threads])

# Configure pqos
try:
    # Set COS1 LLC mask
    cos1_llc = '0x' + format((1 << LC_cache_ways) - 1, 'x').zfill(total_ways // 4).rjust(total_ways // 4, '0')
    # Set COS2 LLC mask (remaining ways)
    cos2_llc = '0x' + format(int(cos1_llc, 16) ^ ((1 << total_ways) - 1), 'x').zfill(total_ways // 4)[
                      -total_ways // 4:].rjust(total_ways // 4, '0')

    # Configure COS1 (for core0 and core1)
    cos1_cmd = f'pqos -R -e "llc:1={cos1_llc};mba:1={LC_memory_bandwidth_ratio}"'
    print(cos1_cmd)
    subprocess.run(cos1_cmd, shell=True, check=True)

    # Configure COS2 (for core2)
    cos2_cmd = f'pqos -e "llc:2={cos2_llc};mba:2={100 - LC_memory_bandwidth_ratio}"'
    print(cos2_cmd)
    subprocess.run(cos2_cmd, shell=True, check=True)

    # Bind core0 and core1 to COS1
    core1_cmd = f'pqos -a "llc:1={core0},{core1}"'
    print(core1_cmd)
    subprocess.run(core1_cmd, shell=True, check=True)

    # Bind core2 to COS2
    core2_cmd = f'pqos -a "llc:2={core2}"'
    print(core2_cmd)
    subprocess.run(core2_cmd, shell=True, check=True)

except subprocess.CalledProcessError as e:
    print(f"Error configuring pqos: {e}")

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


LC_instr0 = f"sudo taskset -c {core0} {LC_instr[LC_task][0]}"
LC_instr1 = f"sudo {LC_instr[LC_task][1]} {LC_threads} {LC_rps} {test_time} {core1}"

latency_99_dict = {}

print(LC_instr0)
print(LC_instr1)
cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
print('waiting for perf...')
cmd_result1.wait()

latency_99 = []
for n in range(LC_threads):
    latency_99.append(read_LC_latency(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log'))
latency_99_dict['baseline'] = sum(latency_99) / len(latency_99)
print(latency_99_dict)

benchmark_set = "spec2017"
# benchmark_list = ["519.lbm_r_5_5_52000", "519.lbm_r_10_10_13000", "519.lbm_r_50_50_520", "519.lbm_r_100_100_130", "519.lbm_r_200_200_30", "519.lbm_r_500_500_5"]
benchmark_list = ["519.lbm_r_100_100_130"]

for benchmark in benchmark_list:

    latency_99_dict[benchmark] = []
    print(LC_instr0)
    print(LC_instr1)
    BE_instr = 'bash /home/wjy/SComet/benchmarks/%s/script/%s.sh %d %s' % (benchmark_set, benchmark, BE_threads, core2)
    print(BE_instr)

    cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
    cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
    cmd_result = subprocess.Popen(BE_instr, shell=True, preexec_fn=os.setsid)
    print('waiting for perf...')
    cmd_result1.wait()
    os.killpg(os.getpgid(cmd_result.pid), signal.SIGTERM)
    cmd_result.wait()

    latency_99 = []
    for n in range(LC_threads):
        latency_99.append(read_LC_latency(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log'))
    latency_99_dict[benchmark] = sum(latency_99) / len(latency_99)
    print(latency_99_dict)

    '''print(LC_instr0)
    print(LC_instr1)
    BE_instr = 'bash /home/wjy/SComet/benchmarks/%s/script/%s.sh %d %s' % (benchmark_set, benchmark, BE_threads, core3)
    print(BE_instr)
    
    cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
    cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
    cmd_result = subprocess.Popen(BE_instr, shell=True, preexec_fn=os.setsid)
    print('waiting for perf...')
    cmd_result1.wait()
    os.killpg(os.getpgid(cmd_result.pid), signal.SIGTERM)
    cmd_result.wait()
    
    latency_99 = []
    for n in range(LC_threads):
        with open(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log', mode='r') as output_f:
            outputs = output_f.readlines()
            for i in range(len(outputs)):
                if 'service' in outputs[i]:
                    latency_99.append(int(outputs[i + 1].split()[3]))
    latency_99_dict[benchmark].append(sum(latency_99) / len(latency_99))
    print(latency_99_dict)'''

with open(f'/home/wjy/SComet/results/proof/t{LC_threads}_r{LC_rps}_c{LC_cache_ways}_m{LC_memory_bandwidth_ratio}.json', mode='a') as output_f:
    json.dump(latency_99_dict, output_f)
    output_f.write('\n')




 


