import subprocess
import time
import signal
import os
import re
import sys

LC_instr = {
    "microbench": "perf stat -I 1000 -o temp.log sh /home/wjy/SComet/benchmarks/microbenchmark/script/microbench.sh",
    "memcached": "perf stat -I 1000 -o temp.log sh /home/wjy/SComet/benchmarks/memcached/script/memcached.sh 4",
    "nginx": "perf stat -I 1000 -o temp.log sh /home/wjy/SComet/benchmarks/nginx/script/nginx.sh 4",
}

def run_and_monitor_bw(program, run_time):
    try:
        # subprocess.Popen('pqos -R -e "mba:1=80"', shell=True).wait()
        # subprocess.Popen('pqos -R -e "mba:2=20"', shell=True).wait()
        # subprocess.Popen('pqos -a "llc:1=0"', shell=True).wait()
        # subprocess.Popen('pqos -a "llc:2=1"', shell=True).wait()
        pqos_proc = subprocess.Popen("pqos -r", shell=True, preexec_fn=os.setsid)
        os.killpg(os.getpgid(pqos_proc.pid), signal.SIGTERM)
        pqos_proc.wait()
        program_proc = subprocess.Popen("taskset -c 1 " + program, shell=True, preexec_fn=os.setsid)
        pqosout = open("pqos.all", "w")
        pqos_proc = subprocess.Popen("taskset -c 2 pqos -i 1 -m all:1", shell=True, stdout=pqosout, preexec_fn=os.setsid)

        time.sleep(run_time)
        os.killpg(os.getpgid(program_proc.pid), signal.SIGTERM)
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
        subprocess.Popen('pqos -R', shell=True).wait()

        return avg_mbl

    except KeyboardInterrupt:
        print("Monitoring interrupted.")
        os.kill(program_proc.pid, signal.SIGTERM)


def run_and_monitor_interference(program, run_time):
    try:
        # subprocess.Popen('pqos -R -e "mba:1=80"', shell=True).wait()
        subprocess.Popen('pqos -R -e "mba:2=20"', shell=True).wait()
        # subprocess.Popen('pqos -a "llc:1=0"', shell=True).wait()
        subprocess.Popen('pqos -a "llc:2=1"', shell=True).wait()

        pqos_proc = subprocess.Popen("pqos -r", shell=True, preexec_fn=os.setsid)
        os.killpg(os.getpgid(pqos_proc.pid), signal.SIGTERM)
        pqos_proc.wait()
        LC_proc = subprocess.Popen("taskset -c 0 sh /home/wjy/SComet/benchmarks/microbenchmark/script/microbench.sh",
                                   shell=True, preexec_fn=os.setsid)
        pqosout = open("pqos.all", "w")
        pqos_proc = subprocess.Popen("taskset -c 2 pqos -i 1 -m all:0", shell=True, stdout=pqosout,
                                     preexec_fn=os.setsid)

        time.sleep(run_time)
        os.killpg(os.getpgid(LC_proc.pid), signal.SIGTERM)
        os.killpg(os.getpgid(pqos_proc.pid), signal.SIGTERM)

        total_IPC = 0
        count = 0

        with open("pqos.all", 'r') as f:
            file = f.readlines()
            for i in range(len(file)):
                if 'IPC' in file[i]:
                    parts = file[i + 1].split()
                    if len(parts) >= 6:
                        try:
                            IPC_value = float(parts[1])
                            total_IPC += IPC_value
                            count += 1
                        except ValueError:
                            pass

        if count == 0:
            print("No IPC data found.")
        else:
            solo_IPC = total_IPC / count
            print(f"Solo IPC: {solo_IPC:.2f}")

        pqos_proc = subprocess.Popen("pqos -r", shell=True, preexec_fn=os.setsid)
        os.killpg(os.getpgid(pqos_proc.pid), signal.SIGTERM)
        pqos_proc.wait()
        LC_proc = subprocess.Popen("taskset -c 0 sh /home/wjy/SComet/benchmarks/microbenchmark/script/microbench.sh", shell=True, preexec_fn=os.setsid)
        program_proc = subprocess.Popen("taskset -c 1 " + program, shell=True, preexec_fn=os.setsid)
        pqosout = open("pqos.all", "w")
        pqos_proc = subprocess.Popen("taskset -c 2 pqos -i 1 -m all:0", shell=True, stdout=pqosout, preexec_fn=os.setsid)

        time.sleep(run_time)
        os.killpg(os.getpgid(LC_proc.pid), signal.SIGTERM)
        os.killpg(os.getpgid(program_proc.pid), signal.SIGTERM)
        os.killpg(os.getpgid(pqos_proc.pid), signal.SIGTERM)

        total_IPC = 0
        count = 0

        with open("pqos.all", 'r') as f:
            file = f.readlines()
            for i in range(len(file)):
                if 'IPC' in  file[i]:
                    parts = file[i+1].split()
                    if len(parts) >= 6:
                        try:
                            IPC_value = float(parts[1])
                            total_IPC += IPC_value
                            count += 1
                        except ValueError:
                            pass

        if count == 0:
            print("No IPC data found.")
        else:
            corun_IPC = total_IPC / count
            print(f"Corun IPC: {corun_IPC:.2f}")

        print(corun_IPC / solo_IPC)

        subprocess.Popen("rm -rf pqos.all", shell=True).wait()
        subprocess.Popen('pqos -R', shell=True).wait()

        return corun_IPC / solo_IPC

    except KeyboardInterrupt:
        print("Monitoring interrupted.")
        os.kill(program_proc.pid, signal.SIGTERM)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python pqos_bandwidth_monitor.py '<program>' <run_time>")
        sys.exit(1)

    benchmark_set = sys.argv[1]
    run_duration = int(sys.argv[2])

    benchmark_list = []
    for root, dirs, files in os.walk('./benchmarks/' + benchmark_set + '/script'):
        for file in files:
            if file.split('.')[-1] == 'sh':
                benchmark_list.append('.'.join(file.split('.')[0:-1]))
    benchmark_list.sort()
    print('benchmark list:')
    print(benchmark_list)

    result = {}
    for benchmark in benchmark_list:
        instr = f"bash ./benchmarks/{benchmark_set}/script/{benchmark}.sh"
        bw = run_and_monitor_bw(instr, run_duration)
        ipc = run_and_monitor_interference(instr, run_duration)
        result[benchmark] = (bw, ipc)
        print(result)
