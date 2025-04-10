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
    "memcached": [f"sudo taskset -c {','.join(CPU_cores['NUMA0'][:8])} bash {ROOT}/benchmarks/memcached/script/server.sh 8",
                  f"bash {ROOT}/benchmarks/memcached/script/client.sh"]
}

BE_thread = [32]

if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
    if not any(benchmark_set in available for available in available_benchmark_set):
        print('multi thread not supported')
        BE_thread = [1]
else:
    print('Microbench name needed')
    exit(0)

benchmark_list = []
for root, dirs, files in os.walk('./benchmarks/' + benchmark_set + '/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_list.append('.'.join(file.split('.')[0:-1]))
benchmark_list.sort()
print('benchmark list:')


LC_cache_ways = total_ways - 1
if '-c' in sys.argv:
    LC_cache_ways = int(sys.argv[sys.argv.index('-c') + 1])
print(f"Cache ways for LC task: {LC_cache_ways}")


LC_memory_bandwidth_ratio = 90
if '-m' in sys.argv:
    LC_memory_bandwidth_ratio = int(sys.argv[sys.argv.index('-m') + 1])
print(f"Memory bandwidth ratio for LC task: {LC_memory_bandwidth_ratio}")


test_time = 30
if '-t' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-t') + 1])

LC_task = "memcached"
if '--lc' in sys.argv:
    LC_task = sys.argv[sys.argv.index('--lc') + 1]
    if LC_task not in LC_instr.keys():
        print(f"Invalid LC task {LC_task}")
        exit(0)

LC_threads = 8
if '--lc-threads' in sys.argv:
    LC_threads = int(sys.argv[sys.argv.index('--lc-threads') + 1])

LC_rps = 70000
if '--lc-rps' in sys.argv:
    LC_rps = int(sys.argv[sys.argv.index('--lc-rps') + 1])

LC_instr0 = LC_instr[LC_task][0]
LC_instr1 = f"sudo taskset -c {','.join(CPU_cores['NUMA0'][8:8 + LC_threads])} " + LC_instr[LC_task][1]
LC_instr1 = LC_instr1 + ' ' + str(LC_threads)
LC_instr1 = LC_instr1 + ' ' + str(LC_rps)
LC_instr1 = LC_instr1 + ' ' + str(test_time)

BE_num = 1
if '--be-num' in sys.argv:
    BE_num = int(sys.argv[sys.argv.index('--be-num') + 1])

# config pqos
# Configure pqos
try:
    cos1_llc = '0x' + format((1 << LC_cache_ways) - 1, 'x').zfill(total_ways // 4).rjust(total_ways // 4, '0')
    # Set COS2
    cos2_llc = '0x' + format(int(cos1_llc, 16) ^ ((1 << total_ways) - 1), 'x').zfill(total_ways // 4)[
                      -total_ways // 4:].rjust(total_ways // 4, '0')
    cos2_cmd = f'pqos -R -e "llc:2={cos2_llc};mba:2={100 - LC_memory_bandwidth_ratio}"'
    print(cos2_cmd)
    subprocess.run(cos2_cmd, shell=True, check=True)
    # Bind core2 to COS2
    core2_cmd = 'pqos -a "llc:2={}"'.format(CPU_cores["NUMA0"][-1])
    print(core2_cmd)
    subprocess.run(core2_cmd, shell=True, check=True)
except subprocess.CalledProcessError as e:
    print(f"Error configuring pqos: {e}")


latency_99_dict = {}

print(LC_instr0)
print(LC_instr1)
cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
print('waiting for perf...')
cmd_result1.wait()

latency_99 = []
for n in range(LC_threads - 1):
    with open(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log', mode='r') as output_f:
        outputs = output_f.readlines()
        for i in range(len(outputs)):
            if 'service' in outputs[i]:
                latency_99.append(int(outputs[i + 1].split()[3]))
latency_99_dict['baseline'] = sum(latency_99) / len(latency_99)
print(latency_99_dict)


for benchmark in benchmark_list:
    latency_99_dict[benchmark] = []
    for BEn in range(1, BE_num + 1):
        for threads in BE_thread:
            print(LC_instr0)
            print(LC_instr1)
            if len(BE_thread) > 1:
                instr1 = 'taskset -c %s bash /home/wjy/SComet/benchmarks/%s/script/%s.sh %d' % (CPU_cores["NUMA0"][-1], benchmark_set, benchmark, threads)
            else:
                instr1 = 'taskset -c %s bash /home/wjy/SComet/benchmarks/%s/script/%s.sh' % (CPU_cores["NUMA0"][-1], benchmark_set, benchmark)
            print(instr1)
            
            cmd_result0 = subprocess.Popen(LC_instr0, shell=True, preexec_fn=os.setsid)
            cmd_result1 = subprocess.Popen(LC_instr1, shell=True, preexec_fn=os.setsid)
            cmd_result = []
            for n in range(BEn):
                cmd_result.append(subprocess.Popen(instr1, shell=True, preexec_fn=os.setsid))
            print('waiting for perf...')
            cmd_result1.wait()
            for n in range(BEn):
                os.killpg(os.getpgid(cmd_result[n].pid), signal.SIGTERM)
                cmd_result[n].wait()

            latency_99 = []
            for n in range(LC_threads - 1):
                with open(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}_{n}.log', mode='r') as output_f:
                    outputs = output_f.readlines()
                    for i in range(len(outputs)):
                        if 'service' in outputs[i]:
                            latency_99.append(int(outputs[i + 1].split()[3]))
            latency_99_dict[benchmark].append(sum(latency_99) / len(latency_99))
            print(latency_99_dict)

with open(f'thread_test_{LC_threads}_{LC_rps}.json', mode='w') as output_f:
    json.dump(latency_99_dict, output_f)




 


