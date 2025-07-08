import subprocess

CPU_cores = {
    'NUMA0': [str(i) for i in range(0, 56)],
    # 'NUMA1': [str(i) for i in range(56, 112)],
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

nodes = {'172.17.1.36': ('wjy', 'gis.xen'), '172.17.4.149': ('root', 'gis.xen')}

def run_on_node(ip, instr):
    return subprocess.Popen(f'sshpass -p "{nodes[ip][1]}" ssh {nodes[ip][0]}@{ip}', shell=True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, preexec_fn=os.setsid)