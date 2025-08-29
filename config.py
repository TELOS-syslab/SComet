import subprocess
import os
import re
import time
import signal
import shlex

ROOT = "/home/wjy/SComet"
curr_ip = "162.105.86.11"

CPU_cores = {
    'NUMA0': [str(i) for i in range(0, 56)],
    # 'NUMA1': [str(i) for i in range(56, 112)],
}

nodes = {
    '172.17.1.73': {'user': 'wjy', 'passwd': 'gis.xen'}, # mars
    '172.17.1.74': {'user': 'wjy', 'passwd': 'gis.xen'}, # mercury
    '172.17.1.75': {'user': 'wjy', 'passwd': 'gis.xen'}, # jupiter
    '172.17.1.78': {'user': 'wjy', 'passwd': 'gis.xen'}, # neptune
}

def run_on_node(ip, instr):
    command = (
        f"sshpass -p {shlex.quote(nodes[ip]['passwd'])} "
        f"ssh -o StrictHostKeyChecking=no {shlex.quote(nodes[ip]['user'])}@{ip} "
        f"{instr}"
    )
    # print(command)
    return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)


def copy_from_node(ip, src, dest):
    remote_src = f"{nodes[ip]['user']}@{ip}:{src}"
    command = (
        f"sshpass -p {shlex.quote(nodes[ip]['passwd'])} "
        f"scp -o StrictHostKeyChecking=no {remote_src} {shlex.quote(dest)}"
    )
    return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)

LC_instr = {
    "memcached": [f"bash {ROOT}/benchmarks/memcached/script/server.sh",
                  f"bash {ROOT}/benchmarks/memcached/script/client.sh"],
    "nginx": [f"bash {ROOT}/benchmarks/nginx/script/server.sh",
              f"bash {ROOT}/benchmarks/nginx/script/client.sh"],
    # "masstree": [f"bash {ROOT}/benchmarks/masstree/script/server.sh",
    #              f"bash {ROOT}/benchmarks/masstree/script/client.sh"]
    "masstree": [f"",
                  f"bash {ROOT}/benchmarks/masstree/script/masstree.sh"],
    "xapian": [f"",
                 f"bash {ROOT}/benchmarks/xapian/script/xapian.sh"]
}

tailbench_benchmarks = ['masstree', 'xapian']

QoS = {
    "memcached": 120,
    "nginx": 3000,
    "masstree": 2000,
    "xapian": 10000,
}

def get_cache_ways():
    try:
        result = subprocess.run('pqos -s', stdout=subprocess.PIPE, universal_newlines=True, shell=True)
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

total_ways = get_cache_ways()

def resource_allocation(threads, core, cache_ways, memory_bandwidth_ratio):
    subprocess.Popen('sudo rm -rf /var/lock/libpqos', shell=True).wait()
    subprocess.Popen("sudo pqos -R", shell=True, preexec_fn=os.setsid).wait()
    subprocess.Popen("sudo pkill -f pqos", shell=True, preexec_fn=os.setsid).wait()
    try:
        cos_llc_masks = []
        used_mask = 0
        start_bit = 0
        for ways in cache_ways:
            if ways:
                mask = ((1 << ways) - 1) << start_bit
                cos_llc_masks.append('0x' + format(mask, 'x').zfill(total_ways // 4).rjust(total_ways // 4, '0'))
                start_bit += ways
            else:
                cos_llc_masks.append('0x0')

        for i in range(len(cos_llc_masks)):
            if core[i]:
                print(f"COS{i} LLC Mask: {cos_llc_masks[i]}")
                cos_cmd = f'pqos -e "llc:{i}={cos_llc_masks[i]};mba:{i}={memory_bandwidth_ratio[i]}"'
                print(cos_cmd)
                subprocess.run(cos_cmd, shell=True, check=True, capture_output=True)
                core_cmd = f'pqos -a "llc:{i}={core[i]}"'
                print(core_cmd)
                subprocess.run(core_cmd, shell=True, check=True, capture_output=True)

    except subprocess.CalledProcessError as e:
        print(f"Error configuring pqos: {e}")

def read_LC_latency_95(filename):
    with open(filename, mode='r') as output_f:
        outputs = output_f.readlines()
        if 'memcached' in filename:
            for i in range(len(outputs)):
                if 'service' in outputs[i]:
                    return float(outputs[i + 1].split()[3])
        elif 'nginx' in filename:
            for i in range(len(outputs)):
                if '0.950000' in outputs[i]:
                    latency = float(outputs[i].split()[0]) * 1000
                    return latency
        elif any([lc in filename for lc in tailbench_benchmarks]):
            for i in range(len(outputs)):
                if 'end2end' in outputs[i]:
                    return float(outputs[i].split()[6]) * 1000
        else:
            print('Unavailable LC task')
            exit()

def read_LC_latency_99(filename):
    with open(filename, mode='r') as output_f:
        outputs = output_f.readlines()
        if 'memcached' in filename:
            for i in range(len(outputs)):
                if 'service' in outputs[i]:
                    return float(outputs[i + 1].split()[4])
        elif 'nginx' in filename:
            for i in range(len(outputs)):
                if '0.990625' in outputs[i]:
                    latency = float(outputs[i].split()[0]) * 1000
                    return latency
        elif any([lc in filename for lc in tailbench_benchmarks]):
            for i in range(len(outputs)):
                if 'end2end' in outputs[i]:
                    return float(outputs[i].split()[10]) * 1000
        else:
            print('Unavailable LC task')
            exit()

def read_LC_latency_violate_QoS(filename, threshold):
    with open(filename, 'r') as f:
        lines = f.readlines()
    start_idx = None
    for i, line in enumerate(lines):
        if 'memcached' in filename or any([lc in filename for lc in tailbench_benchmarks]):
            if "service latency percentiles" in line.lower():
                start_idx = i + 1
                break
        if 'nginx' in filename:
            if "value" in line.lower() and "percentile" in line.lower():
                start_idx = i + 2
                break
    if start_idx is None:
        raise ValueError("no service latency percentiles")

    percentiles = {}
    if 'memcached' in filename:
        pattern = re.compile(r'(\d+)[a-z]{2} percentile:\s+(\d+)')
    if 'nginx' in filename:
        pattern = re.compile(r'^\s*(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)\s+([\d\.]+|inf)$')
    if any([lc in filename for lc in tailbench_benchmarks]):
        pattern = re.compile(r'(\d+)(?:st|nd|rd|th) percentile:\s+([0-9.eE+-]+)')

    for line in lines[start_idx:]:
        match = pattern.search(line)
        if not match:
            break
        if 'memcached' in filename:
            percentile = float(match.group(1))
            value = float(match.group(2))
        if 'nginx' in filename:
            percentile = float(match.group(2)) * 100
            value = float(match.group(1)) * 1000
        if any([lc in filename for lc in tailbench_benchmarks]):
            percentile = float(match.group(1))
            value = float(match.group(2)) * 1000
        # print(percentile, value)
        percentiles[percentile] = value

    sorted_items = sorted(percentiles.items())
    # print(sorted_items)
    for i, (p, val) in enumerate(sorted_items):
        if threshold < val:
            return (100 - p + (threshold - sorted_items[i - 1][1]) /
                    (val - sorted_items[i - 1][1])) if i > 0 else 100.0
    return 0

def run_test(LC_tasks, BE_tasks, test_time):
    cmd_result_lc = []
    for i in range(len(LC_tasks)):
        if LC_tasks[i][0]:
            print(LC_tasks[i][0])
        else:
            LC_tasks[i][0] = ""
        cmd_result_lc.append(subprocess.Popen(LC_tasks[i][0], shell=True, preexec_fn=os.setsid))
        time.sleep(5)

        if LC_tasks[i][1]:
            print(LC_tasks[i][1])
        else:
            LC_tasks[i][1] = ""
        cmd_result_lc.append(subprocess.Popen(LC_tasks[i][1], shell=True, preexec_fn=os.setsid))
        time.sleep(5)

    cmd_result_be = []
    for i in range(len(BE_tasks)):
        if BE_tasks[i]:
            print(BE_tasks[i])
        else:
            BE_tasks[i] = ""
        cmd_result_be.append(subprocess.Popen(BE_tasks[i], shell=True, preexec_fn=os.setsid))

    start_time = time.time()
    print('waiting for perf...')
    if test_time > 0:
        while time.time() - start_time < test_time:
            print(int(time.time() - start_time))
            for i in range(len(LC_tasks)):
                if LC_tasks[i][1]:
                    if cmd_result_lc[2 * i + 1].poll() is not None:
                        cmd_result_lc[2 * i + 1] = subprocess.Popen(LC_tasks[i][1], shell=True, preexec_fn=os.setsid)
            for i in range(len(BE_tasks)):
                if BE_tasks[i]:
                    if cmd_result_be[i].poll() is not None:
                        cmd_result_be[i] = subprocess.Popen(BE_tasks[i], shell=True, preexec_fn=os.setsid)
            time.sleep(5)
    else:
        for i in range(len(LC_tasks)):
            if LC_tasks[i][1]:
                cmd_result_lc[2 * i + 1].wait()

    print(f'perf finished in {time.time() - start_time}s...')
    for i in range(len(cmd_result_lc)):
        try:
            os.killpg(os.getpgid(cmd_result_lc[i].pid), signal.SIGTERM)
            cmd_result_lc[i].wait()
        except Exception as e:
            print(f"Error when killing lc task {i}", e)
    for i in range(len(BE_tasks)):
        try:
            os.killpg(os.getpgid(cmd_result_be[i].pid), signal.SIGTERM)
            cmd_result_be[i].wait()
        except Exception as e:
            print(f"Error when killing be task {i}", e)

    print('reading latencies...')
    result = []
    for i in range(len(LC_tasks)):
        LC_task = ""
        for LC in LC_instr.keys():
            if LC in LC_tasks[i][1]:
                LC_task = LC
                break
        if LC_task == "":
            print(f"no LC task for {LC_tasks[i][1]}")
            exit()
        latency_list_95 = []
        latency_list_99 = []
        violate_list = []
        latency_95 = read_LC_latency_95(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}.log')
        latency_99 = read_LC_latency_99(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}.log')
        violate = read_LC_latency_violate_QoS(f'/home/wjy/SComet/benchmarks/{LC_task}/QoS/{LC_task}.log', QoS[LC_task])
        result.append([latency_95, latency_99, violate])
    return result
