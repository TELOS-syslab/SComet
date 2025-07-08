import subprocess
import time
import signal
import os
import re
import sys
import json
import random
sys.path.append('/home/wjy/SComet')
from config import *

benchmark_set = sys.argv[1]
benchmark_list = []
for root, dirs, files in os.walk(f'{ROOT}/benchmarks/' + benchmark_set + '/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_list.append('.'.join(file.split('.')[0:-1]))
benchmark_list.sort()

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
    core_str = ','.join(CPU_cores['NUMA0'][sum(threads[0:i]): sum(threads[0:i+1])])
    core.append(core_str)

# LC_tasks = ['memcached']
LC_tasks = ['masstree']
if '--lc' in sys.argv:
    LC_tasks = [sys.argv[sys.argv.index('--lc') + 1]]

# LC_rps = [72000]
LC_rps = [17000]
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

def run_and_monitor_bw(benchmark_set, benchmark, test_time):
    subprocess.Popen("sudo pqos -R", shell=True, preexec_fn=os.setsid).wait()
    subprocess.Popen("sudo pkill -f pqos", shell=True, preexec_fn=os.setsid).wait()
    pqosout = open("pqos.all", "w")
    pqos_proc = subprocess.Popen("taskset -c 2 sudo pqos -i 1 -m all:1", shell=True, stdout=pqosout, preexec_fn=os.setsid)

    if benchmark != "baseline":
        BE_instr = 'bash /home/wjy/SComet/benchmarks/%s/script/%s.sh %d %s' % (
            benchmark_set, benchmark, 1, 1)
        print(BE_instr)
        cmd_result_be = subprocess.Popen(BE_instr, shell=True, preexec_fn=os.setsid)

    time.sleep(test_time)
    os.killpg(os.getpgid(cmd_result_be.pid), signal.SIGTERM)
    os.killpg(os.getpgid(pqos_proc.pid), signal.SIGTERM)

    total_mbl = 0
    count = 0
    with open("pqos.all", 'r') as f:
        file = f.readlines()
        for i in range(len(file)):
            if 'MBL[MB/s]' in  file[i]:
                parts = file[i+1].split()
                if len(parts) >= 6:
                    try:
                        mbl_value = float(parts[4])
                        total_mbl += mbl_value
                        count += 1
                    except ValueError:
                        pass
    if count == 0:
        print("No MBL data found.")
    else:
        avg_mbl = total_mbl / count
        print(f"Average MBL: {avg_mbl:.2f} MB/s")

    subprocess.Popen("rm -rf pqos.all", shell=True).wait()
    subprocess.Popen('sudo pqos -R', shell=True).wait()
    time.sleep(5)

    return avg_mbl

def run_and_monitor_interference(benchmark_set, benchmark, test_time):
    
    resource_allocation(threads, core, cache_ways, memory_bandwidth_ratio)
    subprocess.Popen("sudo pkill -f 'memcached|nginx|mutated|wrk|lbm|mttest|_r_base'", shell=True, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL).wait()
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

    return run_test(LC, BE, 0)

subprocess.Popen("sudo pqos -R", shell=True, preexec_fn=os.setsid).wait()
result = {}
''' benchmark_list = [
    '500.perlbench_r',
    '505.mcf_r',
    '507.cactuBSSN_r',
    '508.namd_r',
    '510.parest_r',
    '519.lbm_r',
    '520.omnetpp_r',
    '521.wrf_r',
    '523.xalancbmk_r',
    '526.blender_r',
    '527.cam4_r',
    '538.imagick_r',
    '541.leela_r',
    '548.exchange2_r',
] '''

benchmark_list = ['baseline'] + benchmark_list
# benchmark_list = ['baseline', '505.mcf_r']
random.shuffle(benchmark_list)
print('benchmark list:')
print(benchmark_list)

for benchmark in benchmark_list:
    # bw = run_and_monitor_bw(benchmark_set, benchmark, test_time)
    bw = 0
    inteference = run_and_monitor_interference(benchmark_set, benchmark, test_time)
    result[benchmark] = (bw, inteference)
    print(result)
with open(f'/home/wjy/SComet/results/profiling/{LC_tasks}_t{threads}_r{LC_rps}_c{cache_ways}_m{memory_bandwidth_ratio}_{benchmark_set}.json', mode='a') as output_f:
    json.dump(result, output_f)
    output_f.write('\n')
subprocess.Popen("sudo pqos -R", shell=True, preexec_fn=os.setsid).wait()

