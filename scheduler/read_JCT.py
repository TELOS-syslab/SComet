import re
import sys
import glob
import os

log_dir = sys.argv[1]

time_pattern = re.compile(r"time\s+([0-9.]+):")
be_pattern = re.compile(r"\[be_container\d+@([\d.]+)\]")
ip_pattern = re.compile(r"Generating Allocator for\s+([\d.]+)")

log_files = glob.glob(os.path.join(log_dir, "*.log"))

for logfile in log_files:
    print(f"Processing {logfile}...")

    current_time = None
    last_seen = {}    # ip -> last time
    total_time = {}   # ip -> accumulated runtime
    all_ips = set()   # 从开头读取的所有 ip
    final_time = 0.0

    with open(logfile, "r") as f:
        for line in f:
            # 收集所有 Allocator 的 IP
            m = ip_pattern.search(line)
            if m:
                all_ips.add(m.group(1))

            # 解析时间
            m = time_pattern.search(line)
            if m:
                current_time = float(m.group(1))
                final_time = current_time
                continue

            # 解析 BE 容器
            m = be_pattern.search(line)
            if m and current_time is not None:
                ip = m.group(1)
                if ip in last_seen:
                    total_time[ip] = total_time.get(ip, 0.0) + (current_time - last_seen[ip])
                last_seen[ip] = current_time

    # 如果需要，把最后一次看到的持续到文件末尾也算进去
    for ip, last_t in last_seen.items():
        total_time[ip] = total_time.get(ip, 0.0) + (final_time - last_t)

    # 确保所有 ip 都有输出（没有运行过的就是 0）
    for ip in sorted(all_ips):
        print(f"{ip} runtime {total_time.get(ip, 0.0):.3f} seconds")
    print()
