#!/usr/bin/env python3
import subprocess
import re
import psutil
import time
import os

# 你的测试脚本和参数
threads = "16"
qps = "4000"
duration = "60"
cmd = [
    "bash",
    "/home/wjy/SComet/benchmarks/test/script/masstree_real_time.sh",
    threads, qps, duration
]

print("Running program with perf stat to measure IPC, cache misses, memory usage and MBL...")

# 启动测试进程
proc = subprocess.Popen(
    ["perf", "stat", "-e", "cycles,instructions,cache-misses"] + cmd,
    stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
)

# 给 perf stat 足够时间运行
stdout, stderr = proc.communicate()
perf_output = stderr

# 提取 cycles, instructions, cache-misses
def parse_perf(pattern, text):
    match = re.search(pattern, text)
    return int(match.group(1).replace(',', '')) if match else None

cycles = parse_perf(r'([\d,]+)\s+cycles', perf_output)
instructions = parse_perf(r'([\d,]+)\s+instructions', perf_output)
cache_misses = parse_perf(r'([\d,]+)\s+cache-misses', perf_output)

ipc = round(instructions / cycles, 2) if cycles and instructions else 1.0

# 获取程序进程信息 (假设第一个 Masstree 进程就是目标)
vms = rss = mbl = 0
for p in psutil.process_iter(['pid', 'name']):
    if "mttest_integrated" in p.info['name']:
        try:
            mem = p.memory_info()
            vms = mem.vms
            rss = mem.rss
            # 读取 /proc/<pid>/io 获取 MBL
            io_file = f"/proc/{p.pid}/io"
            if os.path.exists(io_file):
                with open(io_file) as f:
                    for line in f:
                        if line.startswith("read_bytes:"):
                            mbl += int(line.split()[1])
                        if line.startswith("write_bytes:"):
                            mbl += int(line.split()[1])
        except (psutil.NoSuchProcess, FileNotFoundError):
            continue

print("\n=== Measured Values ===")
print(f"IPC: {ipc}")
print(f"Cache Misses: {cache_misses}")
print(f"MBL (bytes): {mbl}")
print(f"Virt_Memory (VMS): {vms}")
print(f"Res_Memory (RSS): {rss}")

# 生成 MAX_VAL 建议
MAX_VAL = {
    "CPU_Utilization": 3200,  # MHz
    "Frequency": 3400,        # MHz
    "IPC": ipc,
    "Misses": cache_misses if cache_misses else 1,
    "MBL": mbl,
    "Virt_Memory": vms,
    "Res_Memory": rss,
    "Allocated_Cache": 15,    # LLC ways
    "Allocated_Core": 32,
    "MBL_N": mbl,
    "Allocated_Cache_N": 15,
    "Allocated_Core_N": 32,
    "Target_Cache": 15,
    "Target_Core": 32,
    "QoS": 1
}

print("\nSuggested MAX_VAL for normalization:")
print(MAX_VAL)
