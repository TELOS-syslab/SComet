import json
import copy
import os
import sys
import time
import subprocess
import signal
import random

available_benchmark_set = ['parsec-benchmark', 'stream', 'iperf', 'spec2017', 'ecp']

LC_instr = {
    "microbench": "perf stat -I 1000 -o temp.log sh /home/wjy/SComet/benchmarks/microbenchmark/script/microbench.sh",
    "memcached": "perf stat -I 1000 -o temp.log sh /home/wjy/SComet/benchmarks/memcached/script/memcached.sh 4",
    "nginx": "perf stat -I 1000 -o temp.log sh /home/wjy/SComet/benchmarks/nginx/script/nginx.sh 4",
}

BE_thread = [1, 2, 4, 8]

def get_cache_ways():
    try:
        result = subprocess.run(['pqos', '-s'], stdout=subprocess.PIPE, universal_newlines=True)
        for line in result.stdout.split('\n'):
            if 'L3CA COS' in line:
                cache_info = line.split()
                hex_value = cache_info[-1]
                bin_value = bin(int(hex_value, 16))
                ways = bin_value.count('1')
                return ways
    except Exception as e:
        print(f"Error retrieving cache information: {e}")
        return None


def get_last_two_cores():
    try:
        result = subprocess.run(['lscpu'], stdout=subprocess.PIPE, universal_newlines=True)
        for line in result.stdout.split('\n'):
            if 'CPU(s):' in line and 'NUMA' not in line:
                total_cores = int(line.split()[-1])
                return total_cores - 2, total_cores - 1
    except Exception as e:
        print(f"Error retrieving core information: {e}")
        return None, None


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
print(benchmark_list)

core1, core2 = get_last_two_cores()
print(f"Last two cores: {core1}, {core2}")

# total_ways = get_cache_ways()
total_ways = 11
print(f"Cache ways: {total_ways}")
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

LC_threads = 0
if '--lc-threads' in sys.argv:
    LC_threads = int(sys.argv[sys.argv.index('--lc-threads') + 1])

LC_task = "microbench"
if '--lc' in sys.argv:
    LC_task = sys.argv[sys.argv.index('--lc') + 1]
    if LC_task not in LC_instr.keys():
        print(f"Invalid LC task {LC_task}")
        exit(0)
    if LC_threads > 0:
        LC_instr[LC_task] = LC_instr[LC_task][:-1] + str(LC_threads)

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
    core2_cmd = f'pqos -R -a "llc:2={core2}"'
    print(core2_cmd)
    subprocess.run(core2_cmd, shell=True, check=True)
except subprocess.CalledProcessError as e:
    print(f"Error configuring pqos: {e}")


ipcs = {}
instr0 = LC_instr[LC_task]
print(instr0)
print('waiting for perf...')
cmd_result0 = subprocess.Popen(instr0, shell=True, preexec_fn=os.setsid)
if test_time <= 0:
    cmd_result0.wait()
else:
    time.sleep(test_time)
    print('%d second passed...' % test_time)
os.killpg(os.getpgid(cmd_result0.pid), signal.SIGTERM)
cmd_result0.wait()

with open('temp.log', 'r') as log_f:
    logs = log_f.readlines()
single_ipc = []
for log in logs:
    if 'insn per cycle' in log:
        print(log)
        ipc = log.split()[log.split().index('#') + 1]
        single_ipc.append(float(ipc))
subprocess.Popen('rm -rf temp.log', shell=True).wait()
ipcs['baseline'] = [sum(single_ipc) / len(single_ipc)]
print(ipcs)


for benchmark in benchmark_list:
    ipcs[benchmark] = []
    for BEn in range(1, BE_num + 1):
        for threads in BE_thread:
            instr0 = LC_instr[LC_task]
            if len(BE_thread) > 1:
                instr1 = 'taskset -c %d sh /home/wjy/SComet/benchmarks/%s/script/%s.sh %d' % (core2, benchmark_set, benchmark, threads)
            else:
                instr1 = 'taskset -c %d sh /home/wjy/SComet/benchmarks/%s/script/%s.sh' % (core2, benchmark_set, benchmark)
            print(instr0)
            print(instr1)

            print('waiting for perf...')
            cmd_result0 = subprocess.Popen(instr0, shell=True, preexec_fn=os.setsid)
            cmd_result = []
            for n in range(BEn):
                cmd_result.append(subprocess.Popen(instr1, shell=True, preexec_fn=os.setsid))
            if test_time <= 0:
                cmd_result0.wait()
            else:
                time.sleep(test_time)
                print('%d second passed...' % test_time)

            os.killpg(os.getpgid(cmd_result0.pid), signal.SIGTERM)
            cmd_result0.wait()
            for n in range(BEn):
                os.killpg(os.getpgid(cmd_result[n].pid), signal.SIGTERM)
                cmd_result[n].wait()

            with open('temp.log', 'r') as log_f:
                logs = log_f.readlines()
            single_ipc = []
            for log in logs:
                if 'insn per cycle' in log:
                    print(log)
                    ipc = log.split()[log.split().index('#') + 1]
                    single_ipc.append(float(ipc))
            subprocess.Popen('rm -rf temp.log', shell=True).wait()
            ipcs[benchmark].append(sum(single_ipc) / len(single_ipc))
            print(ipcs)

            subprocess.Popen("docker ps -a | grep spirals/parsec-3.0 | awk '{print $1}' | xargs docker stop", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
            subprocess.Popen("docker ps -a | grep spirals/parsec-3.0 | awk '{print $1}' | xargs docker rm", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()




 


